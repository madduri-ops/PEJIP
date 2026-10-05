"""The 90-day retention window for personal data, job postings and rankings.

Build policy section 10 keeps each of these for 90 days. Every store that holds
them deletes what is older than :func:`cutoff`, and files written to disk
(digests, exports) are deleted with :func:`purge_files`. The window can be
shortened for a test or a cautious run, never lengthened.
"""

from __future__ import annotations

import stat
from datetime import datetime, timedelta
from pathlib import Path

RETENTION_DAYS = 90


def cutoff(now: datetime, days: int = RETENTION_DAYS) -> datetime:
    """The oldest moment still inside the window; anything earlier is expired."""
    if now.tzinfo is None:
        msg = "now must be timezone-aware"
        raise ValueError(msg)
    if not 1 <= days <= RETENTION_DAYS:
        msg = f"retention must be between 1 and {RETENTION_DAYS} days, got {days}"
        raise ValueError(msg)
    return now - timedelta(days=days)


def purge_files(directory: Path, now: datetime, days: int = RETENTION_DAYS) -> int:
    """Delete regular files under ``directory`` last modified before the cutoff.

    Symbolic links are neither followed nor deleted, so a purge never reaches
    outside ``directory``. Directories are left in place. Returns the number of
    files deleted; a missing directory deletes nothing.
    """
    limit = cutoff(now, days).timestamp()
    if not directory.is_dir():
        return 0
    deleted = 0
    for root, _dirs, files in directory.walk():
        for name in files:
            path = root / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_mtime < limit:
                path.unlink(missing_ok=True)
                deleted += 1
    return deleted
