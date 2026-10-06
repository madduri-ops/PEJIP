"""The retention window and the file purge (build policy section 10)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pejip.retention import RETENTION_DAYS, cutoff, delete_files, purge_files

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def _write(path: Path, age: timedelta) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic digest", encoding="utf-8")
    stamp = (NOW - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_policy_window_is_90_days() -> None:
    assert RETENTION_DAYS == 90
    assert cutoff(NOW) == NOW - timedelta(days=90)


def test_window_can_be_shortened() -> None:
    assert cutoff(NOW, 1) == NOW - timedelta(days=1)


@pytest.mark.parametrize("days", [0, -1, 91, 365])
def test_window_outside_policy_is_rejected(days: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 90 days"):
        cutoff(NOW, days)


def test_naive_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        cutoff(NOW.replace(tzinfo=None))


def test_purge_deletes_only_expired_files(tmp_path: Path) -> None:
    old = _write(tmp_path / "digest-2026-06-01.md", timedelta(days=91))
    nested_old = _write(tmp_path / "runs" / "export.json", timedelta(days=200))
    edge = _write(tmp_path / "digest-edge.md", timedelta(days=90))
    fresh = _write(tmp_path / "digest-2026-10-04.md", timedelta(days=1))

    assert purge_files(tmp_path, NOW) == 2

    assert not old.exists()
    assert not nested_old.exists()
    assert edge.exists()
    assert fresh.exists()
    assert (tmp_path / "runs").is_dir()


def test_purge_honours_a_shorter_window(tmp_path: Path) -> None:
    week_old = _write(tmp_path / "digest.md", timedelta(days=8))

    assert purge_files(tmp_path, NOW, days=7) == 1
    assert not week_old.exists()


def test_purge_never_follows_or_deletes_symlinks(tmp_path: Path) -> None:
    outside = _write(tmp_path / "outside" / "keep.md", timedelta(days=400))
    purged = tmp_path / "output"
    purged.mkdir()
    (purged / "link.md").symlink_to(outside)
    (purged / "linked-dir").symlink_to(outside.parent, target_is_directory=True)

    assert purge_files(purged, NOW) == 0

    assert outside.exists()
    assert (purged / "link.md").is_symlink()
    assert (purged / "linked-dir").is_symlink()


def test_purge_of_missing_directory_deletes_nothing(tmp_path: Path) -> None:
    assert purge_files(tmp_path / "never-written", NOW) == 0


def test_purge_rejects_a_window_longer_than_policy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between 1 and 90 days"):
        purge_files(tmp_path, NOW, days=120)


def test_delete_files_deletes_every_file_but_no_link(tmp_path: Path) -> None:
    outside = _write(tmp_path / "outside" / "keep.md", timedelta(days=400))
    out = tmp_path / "out"
    fresh = _write(out / "digest.md", timedelta(0))
    nested = _write(out / "runs" / "export.json", timedelta(days=3))
    (out / "link.md").symlink_to(outside)

    assert delete_files(out) == 2

    assert not fresh.exists()
    assert not nested.exists()
    assert (out / "link.md").is_symlink()
    assert outside.exists()
    assert delete_files(tmp_path / "missing") == 0
