"""Unit tests for the release tooling."""

import datetime
from pathlib import Path

import pytest

from ci import release
from ci.release import Release, ReleaseError

PYPROJECT = '[project]\nname = "pejip"\nversion = "0.2.0"\n\n[tool.x]\nversion = "9.9.9"\n'
CHANGELOG = """# Changelog

Intro text.

## Unreleased

### Added

- Something new.

## 0.2.0 - 2026-10-04

### Fixed

- A bug.

## 0.1.0 - 2026-10-01

### Added

- First release.
"""
TODAY = datetime.date(2026, 12, 1)


def _sections(text: str) -> list[release.Section]:
    return release.parse_changelog(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0.0.0", (0, 0, 0)), ("1.2.3", (1, 2, 3)), ("10.20.30", (10, 20, 30))],
)
def test_parse_version(text: str, expected: tuple[int, int, int]) -> None:
    assert release.parse_version(text) == expected


@pytest.mark.parametrize("text", ["1.2", "v1.2.3", "01.2.3", "1.2.3-rc1", "1.2.3 ", ""])
def test_parse_version_rejects_non_semver(text: str) -> None:
    with pytest.raises(ReleaseError, match=r"not a MAJOR\.MINOR\.PATCH"):
        release.parse_version(text)


def test_parse_changelog_splits_sections() -> None:
    sections = _sections(CHANGELOG)
    assert [s.version for s in sections] == [None, "0.2.0", "0.1.0"]
    assert sections[0].body == "### Added\n\n- Something new."
    assert sections[1].date == datetime.date(2026, 10, 4)
    assert sections[2].body == "### Added\n\n- First release."


def test_parse_changelog_without_sections() -> None:
    assert _sections("# Changelog\n\nNothing yet.\n") == []


@pytest.mark.parametrize(
    ("heading", "error"),
    [
        ("## 0.1.0 (2026-10-05)", "is not"),
        ("## 0.1.0", "is not"),
        ("## Unreleased - 2026-10-05", "is not"),
        ("## 0.1 - 2026-10-05", "not a MAJOR.MINOR.PATCH"),
        ("## 0.1.0 - 2026-13-05", "invalid date"),
    ],
)
def test_parse_changelog_rejects_bad_headings(heading: str, error: str) -> None:
    with pytest.raises(ReleaseError, match=error):
        _sections(f"## Unreleased\n\n{heading}\n\n- x\n")


def test_check_changelog_accepts_valid() -> None:
    release.check_changelog(_sections(CHANGELOG), "0.2.0")


def test_check_changelog_accepts_single_release() -> None:
    release.check_changelog(_sections("## Unreleased\n\n## 0.1.0 - 2026-10-05\n- x\n"), "0.1.0")


@pytest.mark.parametrize(
    ("text", "version", "error"),
    [
        ("# Changelog\n", "0.1.0", "must start with"),
        ("## 0.1.0 - 2026-10-05\n- x\n## Unreleased\n", "0.1.0", "must start with"),
        (
            "## Unreleased\n## 0.1.0 - 2026-10-05\n- x\n## Unreleased\n",
            "0.1.0",
            "more than one",
        ),
        ("## Unreleased\n## 0.1.0 - 2026-10-05\n", "0.1.0", "lists no changes"),
        (
            "## Unreleased\n## 0.1.0 - 2026-10-05\n- x\n## 0.2.0 - 2026-10-01\n- y\n",
            "0.1.0",
            "is not newer",
        ),
        (
            "## Unreleased\n## 0.1.0 - 2026-10-05\n- x\n## 0.1.0 - 2026-10-05\n- y\n",
            "0.1.0",
            "is not newer",
        ),
        (
            "## Unreleased\n## 0.2.0 - 2026-10-01\n- x\n## 0.1.0 - 2026-10-05\n- y\n",
            "0.2.0",
            "dated before",
        ),
        ("## Unreleased\n## 0.1.0 - 2026-10-05\n- x\n", "0.2.0", "newest CHANGELOG.md"),
        ("## Unreleased\n- x\n", "0.1.0", "newest CHANGELOG.md release is None"),
        ("## Unreleased\n## 0.1.0 - 2026-10-05\n- x\n", "0.1", "not a MAJOR"),
    ],
)
def test_check_changelog_rejects(text: str, version: str, error: str) -> None:
    with pytest.raises(ReleaseError, match=error):
        release.check_changelog(_sections(text), version)


def test_project_version_reads_first_version_line() -> None:
    assert release.project_version(PYPROJECT) == "0.2.0"


def test_project_version_missing() -> None:
    with pytest.raises(ReleaseError, match="no `version"):
        release.project_version('[project]\nname = "pejip"\n')


def test_prepare_cuts_release() -> None:
    changelog, pyproject = release.prepare(CHANGELOG, PYPROJECT, "0.3.0", TODAY)
    sections = _sections(changelog)
    assert [s.version for s in sections] == [None, "0.3.0", "0.2.0", "0.1.0"]
    assert sections[0].body == ""
    assert sections[1].body == "### Added\n\n- Something new."
    assert sections[1].date == TODAY
    assert release.project_version(pyproject) == "0.3.0"
    assert 'version = "9.9.9"' in pyproject
    assert changelog.startswith("# Changelog\n\nIntro text.\n")


@pytest.mark.parametrize("version", ["0.2.0", "0.1.9", "1.0"])
def test_prepare_rejects_versions_not_newer(version: str) -> None:
    with pytest.raises(ReleaseError):
        release.prepare(CHANGELOG, PYPROJECT, version, TODAY)


def test_prepare_rejects_empty_unreleased() -> None:
    empty = CHANGELOG.replace("### Added\n\n- Something new.\n\n", "", 1)
    with pytest.raises(ReleaseError, match="is empty"):
        release.prepare(empty, PYPROJECT, "0.3.0", TODAY)


def test_prepare_rejects_a_date_before_the_last_release() -> None:
    with pytest.raises(ReleaseError, match="dated before"):
        release.prepare(CHANGELOG, PYPROJECT, "0.3.0", datetime.date(2026, 10, 3))


def test_check_tag() -> None:
    release.check_tag("v1.2.3", "1.2.3")
    with pytest.raises(ReleaseError, match=r"expected v1\.2\.3"):
        release.check_tag("v1.2.4", "1.2.3")


def test_notes() -> None:
    assert release.notes(_sections(CHANGELOG), "0.2.0") == "### Fixed\n\n- A bug."
    with pytest.raises(ReleaseError, match=r"no section for 0\.9\.0"):
        release.notes(_sections(CHANGELOG), "0.9.0")


REFS = """v0.1.0 aaa
v0.10.0 tagobj ccc
v0.2.0 bbb
latest ddd
v1.0 eee
vnext fff
"""


def test_releases_from_refs_newest_first_and_peels_annotated_tags() -> None:
    assert release.releases_from_refs(REFS) == [
        Release("0.10.0", "ccc"),
        Release("0.2.0", "bbb"),
        Release("0.1.0", "aaa"),
    ]


RELEASES = [Release("0.3.0", "ccc"), Release("0.2.0", "bbb"), Release("0.1.0", "aaa")]


def test_rollback_target_named_version() -> None:
    assert release.rollback_target(RELEASES, "0.1.0", "ccc") == Release("0.1.0", "aaa")


def test_rollback_target_unknown_version() -> None:
    with pytest.raises(ReleaseError, match=r"no release tag v0\.9\.0"):
        release.rollback_target(RELEASES, "0.9.0", None)


def test_rollback_target_skips_the_live_commit() -> None:
    assert release.rollback_target(RELEASES, None, "ccc") == Release("0.2.0", "bbb")


def test_rollback_target_from_unreleased_head_is_newest_release() -> None:
    assert release.rollback_target(RELEASES, None, "fff") == Release("0.3.0", "ccc")


def test_rollback_target_needs_an_earlier_release() -> None:
    with pytest.raises(ReleaseError, match="no earlier release"):
        release.rollback_target([Release("0.1.0", "aaa")], None, "aaa")


def _repo(tmp_path: Path, changelog: str = CHANGELOG, pyproject: str = PYPROJECT) -> Path:
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return tmp_path


def test_main_check(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main(["--root", str(_repo(tmp_path)), "check"]) == 0
    assert "agree on 0.2.0" in capsys.readouterr().out


def test_main_check_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, pyproject=PYPROJECT.replace("0.2.0", "0.3.0", 1))
    assert release.main(["--root", str(root), "check"]) == 1
    assert capsys.readouterr().out.startswith("::error::pyproject.toml is at 0.3.0")


def test_main_prepare(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert release.main(["--root", str(root), "prepare", "0.3.0"]) == 0
    assert release.main(["--root", str(root), "check"]) == 0
    assert release.project_version((root / "pyproject.toml").read_text()) == "0.3.0"


def test_main_check_tag(tmp_path: Path) -> None:
    root = str(_repo(tmp_path))
    assert release.main(["--root", root, "check-tag", "v0.2.0"]) == 0
    assert release.main(["--root", root, "check-tag", "v0.1.0"]) == 1


def test_main_notes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert release.main(["--root", str(_repo(tmp_path)), "notes", "0.1.0"]) == 0
    assert capsys.readouterr().out == "### Added\n\n- First release.\n"


def test_main_rollback_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(release, "_git_release_refs", lambda _root: "v0.1.0 aaa\nv0.2.0 bbb\n")
    assert release.main(["--root", str(tmp_path), "rollback-target", "--head", "bbb"]) == 0
    assert capsys.readouterr().out == "version=0.1.0\nsha=aaa\n"
    assert release.main(["--root", str(tmp_path), "rollback-target", "--version", ""]) == 0
    assert capsys.readouterr().out == "version=0.2.0\nsha=bbb\n"
    assert release.main(["--root", str(tmp_path), "rollback-target", "--version", "0.5.0"]) == 1
