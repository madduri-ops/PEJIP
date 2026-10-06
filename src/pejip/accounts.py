"""Accounts: whose data a run, a request or a command works on (design doc 0016).

Every piece of personal data lives under its account: on AWS the database at
``/data/accounts/<id>/pejip.db``, the profile and companies at
``/pejip/accounts/<id>/...`` in SSM, and the LinkedIn export under
``network/<id>/``. Settings name those places with an ``{account}`` placeholder,
which ``Settings.from_env`` fills in, so a run for one account never opens
another's files.

Before accounts, Babu's database and digests sat directly under ``/data``. The
first time Babu's account opens its store, ``adopt_legacy_data`` copies that
database into the account's folder (the original stays, so a rollback still has
it) and moves the old digests across, so the 90-day purge keeps covering them.
Only the default account adopts it: no other account can ever receive Babu's
data.
"""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from contextlib import closing, suppress
from pathlib import Path
from typing import TYPE_CHECKING

from pejip.store import Store

if TYPE_CHECKING:
    from pejip.config import Settings

# Account ids name folders and parameter paths, so they are kept plain.
ACCOUNT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")

# Babu's account: the one ``PEJIP_AUTH_ALLOWED_EMAIL`` signs in as, the account a
# command works on unless ``PEJIP_ACCOUNT`` names another, and the only account
# that adopts the pre-account data.
DEFAULT_ACCOUNT_ID = "babu"

PLACEHOLDER = "{account}"

_SQLITE_PREFIX = "sqlite:///"


def check_account_id(account: str) -> str:
    """Return ``account`` if it is a valid id, else raise ValueError."""
    if not ACCOUNT_ID_PATTERN.fullmatch(account):
        msg = "account ids are lowercase letters, digits and dashes, starting with a letter"
        raise ValueError(msg)
    return account


def fill(template: str, account: str) -> str:
    """Put the account id in a setting that names a per-account place."""
    return template.replace(PLACEHOLDER, account)


def sqlite_path(database_url: str) -> Path | None:
    """The file behind a ``sqlite:///`` URL, or None for any other database."""
    if not database_url.startswith(_SQLITE_PREFIX):
        return None
    path = database_url.removeprefix(_SQLITE_PREFIX)
    if not path or path == ":memory:":
        return None
    return Path(path)


def open_store(settings: Settings) -> Store:
    """The account's database, with its folders made and legacy data adopted."""
    prepare(settings)
    return Store(settings.database_url)


def prepare(settings: Settings) -> None:
    """Make the account's folders, adopting the pre-account data where it applies."""
    database = sqlite_path(settings.database_url)
    if database is not None:
        database.parent.mkdir(parents=True, exist_ok=True)
    if settings.legacy_database_url and database is not None:
        legacy = sqlite_path(settings.legacy_database_url)
        if legacy is not None and legacy != database and legacy.is_file():
            _adopt_database(legacy, database)
    if settings.legacy_output_dir and settings.legacy_output_dir != settings.output_dir:
        _adopt_output(settings.legacy_output_dir, settings.output_dir)


def _adopt_database(legacy: Path, target: Path) -> None:
    """Copy the legacy database to ``target`` once, without ever overwriting it.

    The copy goes to a private temporary file first (SQLite's backup API, so it is
    consistent even if something still writes the original), then is linked into
    place: linking fails if ``target`` exists, so a second process that raced this
    one cannot replace rows the first has already written.
    """
    if target.exists():
        return
    scratch = target.with_name(f".{target.name}.{uuid.uuid4().hex}.adopting")
    try:
        with (
            closing(sqlite3.connect(legacy)) as source,
            closing(sqlite3.connect(scratch)) as copy,
        ):
            source.backup(copy)
        with suppress(FileExistsError):
            os.link(scratch, target)
    finally:
        scratch.unlink(missing_ok=True)


def _adopt_output(legacy: Path, target: Path) -> None:
    """Move the legacy digests and exports into the account's output folder.

    Only regular files at the top level are moved (that is all the run writes);
    symbolic links are left alone, and a file already in the target is kept.
    Modified times survive the move, so the purge still deletes each on time.
    """
    if not legacy.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for path in legacy.iterdir():
        destination = target / path.name
        if path.is_file() and not path.is_symlink() and not destination.exists():
            path.replace(destination)
