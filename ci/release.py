"""Release tooling (docs/BUILD_POLICY.md section 15, docs/design/0006-releases-and-rollback.md).

Keeps the version in `pyproject.toml`, the sections of `CHANGELOG.md` and the
`vMAJOR.MINOR.PATCH` git tags in step, and picks the release a rollback returns to.

    python -m ci.release check                 # changelog and version agree (pre-commit, CI)
    python -m ci.release prepare 0.2.0         # cut a release from the Unreleased section
    python -m ci.release version               # the version to release, once checked
    python -m ci.release check-tag v0.2.0      # a tag matches the version
    python -m ci.release notes 0.2.0           # release notes for the GitHub Release
    python -m ci.release rollback-target [--version 0.1.0] [--head SHA]
        [--fallback-parent | --by-image]
    python -m ci.release image-commit SHA      # the commit whose container image SHA runs
"""

import argparse
import datetime
import itertools
import re
import subprocess  # nosec B404
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG = re.compile(r"^v(.+)$")
UNRELEASED_HEADING = "## Unreleased"
RELEASE_HEADING = re.compile(r"^## (?P<version>\S+) - (?P<date>\d{4}-\d{2}-\d{2})$")
# What the Deploy workflow builds an image for on main (its push paths). A commit
# that touches none of these runs the image of the last commit that did.
IMAGE_PATHS = (
    "src",
    "pyproject.toml",
    "Dockerfile",
    ".dockerignore",
    ".github/workflows/deploy.yml",
)
PROJECT_VERSION = re.compile(r'^version = "(?P<version>[^"]*)"$', re.MULTILINE)


class ReleaseError(Exception):
    """A release rule is broken; the message says which."""


class NoEarlierReleaseError(ReleaseError):
    """No release tag exists to roll back to."""


def parse_version(text: str) -> tuple[int, int, int]:
    """`MAJOR.MINOR.PATCH` as a comparable tuple. Pre-release suffixes are not used."""
    match = SEMVER.match(text)
    if not match:
        msg = f"{text!r} is not a MAJOR.MINOR.PATCH version"
        raise ReleaseError(msg)
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


@dataclass(frozen=True)
class Section:
    heading: str
    version: str | None  # None for Unreleased
    date: datetime.date | None
    body: str


def parse_changelog(text: str) -> list[Section]:
    """Split a Keep a Changelog file into its `## ` sections, checking each heading."""
    sections: list[Section] = []
    heading: str | None = None
    body: list[str] = []

    def close() -> None:
        if heading is not None:
            sections.append(_section(heading, "\n".join(body).strip()))

    for line in text.splitlines():
        if line.startswith("## "):
            close()
            heading, body = line.rstrip(), []
        elif heading is not None:
            body.append(line)
    close()
    return sections


def _section(heading: str, body: str) -> Section:
    if heading == UNRELEASED_HEADING:
        return Section(heading, None, None, body)
    match = RELEASE_HEADING.match(heading)
    if not match:
        msg = f"changelog heading {heading!r} is not '## X.Y.Z - YYYY-MM-DD'"
        raise ReleaseError(msg)
    parse_version(match["version"])
    try:
        date = datetime.date.fromisoformat(match["date"])
    except ValueError:
        msg = f"changelog heading {heading!r} has an invalid date"
        raise ReleaseError(msg) from None
    return Section(heading, match["version"], date, body)


def check_changelog(sections: Sequence[Section], project_version: str) -> None:
    """Unreleased first, releases newest first with no repeats, and the newest
    release is the version in pyproject.toml."""
    parse_version(project_version)
    if not sections or sections[0].version is not None:
        msg = f"CHANGELOG.md must start with a '{UNRELEASED_HEADING}' section"
        raise ReleaseError(msg)
    releases = list(sections[1:])
    for section in releases:
        if section.version is None:
            msg = f"CHANGELOG.md has more than one '{UNRELEASED_HEADING}' section"
            raise ReleaseError(msg)
        if not section.body:
            msg = f"release {section.version} lists no changes"
            raise ReleaseError(msg)
    dated = [(s.version, s.date) for s in releases if s.version and s.date]
    for (newer, newer_date), (older, older_date) in itertools.pairwise(dated):
        if parse_version(newer) <= parse_version(older):
            msg = f"release {newer} is listed above {older} but is not newer"
            raise ReleaseError(msg)
        if newer_date < older_date:
            msg = f"release {newer} is dated before {older}"
            raise ReleaseError(msg)
    newest = releases[0].version if releases else None
    if newest != project_version:
        msg = (
            f"pyproject.toml is at {project_version} but the newest CHANGELOG.md release is "
            f"{newest}; bump both together with `python -m ci.release prepare`"
        )
        raise ReleaseError(msg)


def project_version(pyproject: str) -> str:
    match = PROJECT_VERSION.search(pyproject)
    if not match:
        msg = 'pyproject.toml has no `version = "..."` line'
        raise ReleaseError(msg)
    return match["version"]


def prepare(changelog: str, pyproject: str, version: str, today: datetime.date) -> tuple[str, str]:
    """Move the Unreleased notes into a new release section and bump the project version."""
    current = project_version(pyproject)
    check_changelog(parse_changelog(changelog), current)
    if parse_version(version) <= parse_version(current):
        msg = f"{version} must be newer than the current version {current}"
        raise ReleaseError(msg)
    unreleased = parse_changelog(changelog)[0]
    if not unreleased.body:
        msg = f"'{UNRELEASED_HEADING}' is empty; list the changes before releasing"
        raise ReleaseError(msg)
    heading = f"## {version} - {today.isoformat()}"
    new_changelog = changelog.replace(UNRELEASED_HEADING, f"{UNRELEASED_HEADING}\n\n{heading}", 1)
    new_pyproject = PROJECT_VERSION.sub(f'version = "{version}"', pyproject, count=1)
    check_changelog(parse_changelog(new_changelog), version)
    return new_changelog, new_pyproject


def check_tag(tag: str, version: str) -> None:
    if tag != f"v{version}":
        msg = f"tag {tag} does not match pyproject.toml version {version} (expected v{version})"
        raise ReleaseError(msg)


def notes(sections: Sequence[Section], version: str) -> str:
    for section in sections:
        if section.version == version:
            return section.body
    msg = f"CHANGELOG.md has no section for {version}"
    raise ReleaseError(msg)


@dataclass(frozen=True)
class Release:
    version: str
    sha: str


def releases_from_refs(refs: str) -> list[Release]:
    """Parse `git for-each-ref` output (`tag object peeled`) into releases, newest first.

    Tags that are not `vMAJOR.MINOR.PATCH` are ignored.
    """
    found = []
    for line in refs.splitlines():
        tag, obj, *peeled = line.split()
        match = TAG.match(tag)
        if match and SEMVER.match(match[1]):
            found.append(Release(match[1], peeled[0] if peeled else obj))
    return sorted(found, key=lambda release: parse_version(release.version), reverse=True)


def rollback_target(releases: Sequence[Release], version: str | None, head: str | None) -> Release:
    """The release to roll back to: the one asked for, or else the newest release that
    is not the commit deployed now (main's head, which continuous deploy keeps live)."""
    if version is not None:
        for release in releases:
            if release.version == version:
                return release
        msg = f"no release tag v{version}"
        raise ReleaseError(msg)
    for release in releases:
        if release.sha != head:
            return release
    msg = "there is no earlier release to roll back to"
    raise NoEarlierReleaseError(msg)


def _git(repo: Path, *args: str) -> str:
    # Fixed git arguments, no shell; git comes from PATH like every other CI tool.
    return subprocess.run(  # noqa: S603  # nosec B603 B607
        ["git", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _git_release_refs(repo: Path) -> str:
    return _git(
        repo,
        "for-each-ref",
        "--format=%(refname:short) %(objectname) %(*objectname)",
        "refs/tags/v*",
    )


def image_commit(repo: Path, sha: str) -> str:
    """The commit whose image (tagged with its full SHA in ECR) runs `sha`'s code."""
    found = _git(repo, "log", "-1", "--format=%H", sha, "--", *IMAGE_PATHS).strip()
    if not found:
        msg = f"no commit at or before {sha} builds a container image"
        raise ReleaseError(msg)
    return found


def parent_release(repo: Path, head: str | None) -> Release:
    """The commit before `head` and the version it declares: the drill's stand-in
    rollback target until the first release is tagged."""
    sha = _git(repo, "rev-parse", "--verify", f"{head or 'HEAD'}^1").strip()
    return Release(project_version(_git(repo, "show", f"{sha}:pyproject.toml")), sha)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(), help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("version")
    commands.add_parser("prepare").add_argument("version")
    commands.add_parser("check-tag").add_argument("tag")
    commands.add_parser("notes").add_argument("version")
    commands.add_parser("image-commit").add_argument("sha")
    rollback = commands.add_parser("rollback-target")
    rollback.add_argument("--version", help="release to return to; default: the previous one")
    rollback.add_argument("--head", help="commit deployed now; default: none")
    mode = rollback.add_mutually_exclusive_group()
    mode.add_argument(
        "--fallback-parent",
        action="store_true",
        help="with no earlier release, use the parent of --head (the CI drill only)",
    )
    mode.add_argument(
        "--by-image",
        action="store_true",
        help="compare and report image commits, so a docs-only head is not a new release",
    )
    return parser


def _rollback_target(args: argparse.Namespace) -> Release:
    releases = releases_from_refs(_git_release_refs(args.root))
    head = args.head
    if args.by_image:
        releases = [Release(r.version, image_commit(args.root, r.sha)) for r in releases]
        head = image_commit(args.root, head or "HEAD")
    try:
        return rollback_target(releases, args.version or None, head)
    except NoEarlierReleaseError:
        if not args.fallback_parent:
            raise
        print("No earlier release yet; using the parent commit.", file=sys.stderr)
        return parent_release(args.root, args.head)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    changelog_path = args.root / "CHANGELOG.md"
    pyproject_path = args.root / "pyproject.toml"
    try:
        if args.command == "image-commit":
            print(image_commit(args.root, args.sha))
            return 0
        if args.command == "rollback-target":
            target = _rollback_target(args)
            print(f"version={target.version}\nsha={target.sha}")
            return 0
        changelog = changelog_path.read_text(encoding="utf-8")
        pyproject = pyproject_path.read_text(encoding="utf-8")
        version = project_version(pyproject)
        if args.command == "check":
            check_changelog(parse_changelog(changelog), version)
            print(f"CHANGELOG.md and pyproject.toml agree on {version}.")
        elif args.command == "version":
            check_changelog(parse_changelog(changelog), version)
            print(version)
        elif args.command == "prepare":
            today = datetime.datetime.now(datetime.UTC).date()
            new_changelog, new_pyproject = prepare(changelog, pyproject, args.version, today)
            changelog_path.write_text(new_changelog, encoding="utf-8")
            pyproject_path.write_text(new_pyproject, encoding="utf-8")
            print(f"Prepared {args.version}; open a PR, then run the Release workflow once merged.")
        elif args.command == "check-tag":
            check_changelog(parse_changelog(changelog), version)
            check_tag(args.tag, version)
            print(f"{args.tag} matches pyproject.toml and CHANGELOG.md.")
        else:
            print(notes(parse_changelog(changelog), args.version))
    except ReleaseError as error:
        print(f"::error::{error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
