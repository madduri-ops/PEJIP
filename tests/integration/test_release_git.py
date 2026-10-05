"""Integration tests: rollback target selection against real git tags."""

import shutil
import subprocess
from pathlib import Path

import pytest

from ci import release

GIT = shutil.which("git") or "git"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603
        [GIT, *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "commit", "--allow-empty", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "ci@example.invalid")
    _git(tmp_path, "config", "user.name", "CI")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _git(tmp_path, "config", "tag.gpgsign", "false")
    return tmp_path


def test_rollback_target_reads_lightweight_and_annotated_tags(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _commit(repo, "first")
    _git(repo, "tag", "v0.1.0")
    second = _commit(repo, "second")
    _git(repo, "tag", "-a", "v0.2.0", "-m", "Release 0.2.0")
    _git(repo, "tag", "not-a-release")
    head = _commit(repo, "unreleased work on main")

    assert release.releases_from_refs(release._git_release_refs(repo)) == [
        release.Release("0.2.0", second),
        release.Release("0.1.0", first),
    ]
    # Main is ahead of the newest release: roll back to that release.
    assert release.main(["--root", str(repo), "rollback-target", "--head", head]) == 0
    assert capsys.readouterr().out == f"version=0.2.0\nsha={second}\n"
    # Main is the newest release: roll back to the one before it.
    assert release.main(["--root", str(repo), "rollback-target", "--head", second]) == 0
    assert capsys.readouterr().out == f"version=0.1.0\nsha={first}\n"


def test_rollback_target_with_no_tags(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    head = _commit(repo, "first")
    assert release.main(["--root", str(repo), "rollback-target", "--head", head]) == 1
    assert "no earlier release" in capsys.readouterr().out


def test_fallback_parent_until_the_first_release(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    _git(repo, "add", "pyproject.toml")
    first = _commit(repo, "first")
    parent = _commit(repo, "second")
    head = _commit(repo, "change under test")
    args = ["--root", str(repo), "rollback-target", "--head", head, "--fallback-parent"]
    assert release.main(args) == 0
    captured = capsys.readouterr()
    assert captured.out == f"version=0.1.0\nsha={parent}\n"
    assert "parent commit" in captured.err
    # Once a release exists it is the target, not the parent.
    _git(repo, "tag", "v0.0.1", first)
    assert release.main(args) == 0
    assert capsys.readouterr().out == f"version=0.0.1\nsha={first}\n"
    # A named version never falls back.
    assert release.main([*args, "--version", "0.0.9"]) == 1


def _change(repo: Path, path: str, message: str) -> str:
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(f"{message}\n", encoding="utf-8")
    _git(repo, "add", path)
    return _commit(repo, message)


def test_image_commit_skips_commits_that_build_no_image(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = _change(repo, "src/pejip/app.py", "code change")
    _change(repo, "docs/notes.md", "docs only")
    assert release.main(["--root", str(repo), "image-commit", "HEAD"]) == 0
    assert capsys.readouterr().out == f"{code}\n"


def test_image_commit_with_no_image_commit(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _change(repo, "docs/notes.md", "docs only")
    assert release.main(["--root", str(repo), "image-commit", "HEAD"]) == 1
    assert "builds a container image" in capsys.readouterr().out


def test_rollback_target_by_image(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    first = _change(repo, "src/pejip/app.py", "0.1.0 code")
    _change(repo, "docs/notes.md", "0.1.0 docs")
    _git(repo, "tag", "v0.1.0")
    second = _change(repo, "Dockerfile", "0.2.0 image")
    _git(repo, "tag", "v0.2.0")
    # main moved on with docs only: the live image is still 0.2.0's.
    head = _change(repo, "README.md", "docs after 0.2.0")
    args = ["--root", str(repo), "rollback-target", "--head", head]
    assert release.main([*args, "--by-image"]) == 0
    assert capsys.readouterr().out == f"version=0.1.0\nsha={first}\n"
    # Without --by-image the docs commit looks like a new build.
    assert release.main(args) == 0
    assert capsys.readouterr().out == f"version=0.2.0\nsha={second}\n"
    # A named release reports its image commit.
    assert release.main([*args, "--by-image", "--version", "0.1.0"]) == 0
    assert capsys.readouterr().out == f"version=0.1.0\nsha={first}\n"


def test_rollback_target_by_image_defaults_head_to_checkout(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = _change(repo, "src/pejip/app.py", "0.1.0 code")
    _git(repo, "tag", "v0.1.0")
    _change(repo, "pyproject.toml", "unreleased build")
    assert release.main(["--root", str(repo), "rollback-target", "--by-image"]) == 0
    assert capsys.readouterr().out == f"version=0.1.0\nsha={first}\n"
