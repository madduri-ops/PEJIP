"""Read a LinkedIn Connections export (spec 8.16 to 8.19).

LinkedIn's "Get a copy of your data" sends ``Connections.csv``, alone or inside a zip.
The file starts with a few lines of notes, then the header row
``First Name,Last Name,URL,Email Address,Company,Position,Connected On``.

Parsing never needs a LinkedIn login and keeps only what matching uses: email
addresses are dropped as they are read. Nothing here writes anything; the preview is
handed to the caller, which stores it only when the candidate chooses Import.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

SOURCE_TYPE = "LINKEDIN_CONNECTIONS_EXPORT"
# Larger than any real export (tens of thousands of rows is a few MB), small enough
# that a hostile upload cannot exhaust memory.
MAX_EXPORT_BYTES = 20 * 1024 * 1024
HEADER = ("First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On")
REQUIRED_COLUMNS = ("First Name", "Last Name", "Company", "Position")
DATE_FORMATS = ("%d %b %Y", "%Y-%m-%d", "%m/%d/%Y")


_PROBLEMS = {
    "too_large": "the file is larger than a LinkedIn Connections export can be",
    "not_utf8": "the file is not UTF-8 text",
    "bad_zip": "the zip file is damaged",
    "no_csv": "the zip file has no Connections.csv",
    "no_header": "no 'First Name,Last Name,...' header row was found",
    "no_rows": "the export has no connection rows",
    "missing_columns": "the header is missing: ",
}


class ExportError(ValueError):
    """The upload is not a readable LinkedIn Connections export."""

    def __init__(self, problem: str, detail: str = "") -> None:
        super().__init__(_PROBLEMS.get(problem, problem) + detail)


@dataclass(frozen=True)
class Connection:
    """One first-degree connection as of an import (spec 8.18).

    The company and position are kept exactly as imported; resolution to a tracked
    company happens separately and never overwrites them. Relationship strength is
    never inferred from LinkedIn data, so it starts ``UNKNOWN`` (spec 8.23).
    """

    connection_id: str
    first_name: str
    last_name: str
    profile_url: str | None
    company_raw: str
    position_raw: str
    connected_on: date | None
    imported_at: datetime
    relationship_strength: str = "UNKNOWN"

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class RejectedRow:
    line: int
    reason: str


@dataclass(frozen=True)
class ImportPreview:
    """What an upload contains, shown before anything is saved (spec 8.17)."""

    source_type: str
    source_file_hash: str
    imported_at: datetime
    records_parsed: int
    connections: tuple[Connection, ...]
    rejected: tuple[RejectedRow, ...]
    duplicates: int
    undated: int = 0

    @property
    def records_accepted(self) -> int:
        return len(self.connections)


def _connection_id(profile_url: str | None, first: str, last: str, company: str) -> str:
    """Stable across imports: the profile URL when there is one, otherwise the name."""
    basis = profile_url or f"{first}|{last}|{company}".lower()
    return hashlib.sha256(basis.encode()).hexdigest()[:24]


def _profile_url(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    return url.rstrip("/").replace("http://", "https://", 1)


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()  # noqa: DTZ007 - a date, no time
        except ValueError:
            continue
    return None


def _csv_text(data: bytes) -> str:
    if len(data) > MAX_EXPORT_BYTES:
        raise ExportError("too_large")
    if data[:4] == b"PK\x03\x04":
        data = _from_zip(data)
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExportError("not_utf8") from exc


def _from_zip(data: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [
                i for i in archive.infolist() if i.filename.rsplit("/", 1)[-1] == "Connections.csv"
            ]
            if not members:
                raise ExportError("no_csv")
            # zipfile stops reading at the declared size, so checking it bounds memory.
            if members[0].file_size > MAX_EXPORT_BYTES:
                raise ExportError("too_large")
            return archive.read(members[0])
    except zipfile.BadZipFile as exc:
        raise ExportError("bad_zip") from exc


def parse_export(data: bytes, imported_at: datetime) -> ImportPreview:
    """Parse and validate an upload into a preview; raise :class:`ExportError` if unusable."""
    text = _csv_text(data)
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("First Name,")), None)
    if start is None:
        raise ExportError("no_header")
    reader = csv.reader(lines[start:])
    header = [h.strip() for h in next(reader)]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise ExportError("missing_columns", ", ".join(missing))
    col = {name: header.index(name) for name in HEADER if name in header}

    connections: dict[str, Connection] = {}
    rejected: list[RejectedRow] = []
    parsed = duplicates = undated = 0
    for offset, row in enumerate(reader, start=start + 2):
        if not any(cell.strip() for cell in row):
            continue
        parsed += 1
        if len(row) != len(header):
            rejected.append(RejectedRow(offset, "wrong number of columns"))
            continue
        if any("�" in cell for cell in row):
            rejected.append(RejectedRow(offset, "unreadable characters"))
            continue

        def cell(name: str, row: list[str] = row) -> str:
            return row[col[name]].strip() if name in col else ""

        first, last = cell("First Name"), cell("Last Name")
        if not first and not last:
            rejected.append(RejectedRow(offset, "no first or last name"))
            continue
        url = _profile_url(cell("URL"))
        connected_raw = cell("Connected On")
        connected_on = _parse_date(connected_raw) if connected_raw else None
        if connected_on is None:
            undated += 1
        cid = _connection_id(url, first, last, cell("Company"))
        if cid in connections:
            duplicates += 1
            continue
        connections[cid] = Connection(
            connection_id=cid,
            first_name=first,
            last_name=last,
            profile_url=url,
            company_raw=cell("Company"),
            position_raw=cell("Position"),
            connected_on=connected_on,
            imported_at=imported_at,
        )
    if parsed == 0:
        raise ExportError("no_rows")
    return ImportPreview(
        source_type=SOURCE_TYPE,
        source_file_hash=hashlib.sha256(data).hexdigest(),
        imported_at=imported_at,
        records_parsed=parsed,
        connections=tuple(connections.values()),
        rejected=tuple(rejected),
        duplicates=duplicates,
        undated=undated,
    )


@dataclass(frozen=True)
class ImportChanges:
    """How a new import differs from the previous one (the "New" and "Updated" counts)."""

    new: tuple[Connection, ...]
    changed_employer: tuple[tuple[Connection, Connection], ...]
    changed_title: tuple[tuple[Connection, Connection], ...]
    gone: tuple[Connection, ...]


def compare_imports(previous: Iterable[Connection], current: Iterable[Connection]) -> ImportChanges:
    """Compare two snapshots by connection id; pairs are ``(before, after)``."""
    before = {c.connection_id: c for c in previous}
    after = {c.connection_id: c for c in current}
    employer = tuple(
        (before[cid], c)
        for cid, c in after.items()
        if cid in before and before[cid].company_raw != c.company_raw
    )
    title = tuple(
        (before[cid], c)
        for cid, c in after.items()
        if cid in before
        and before[cid].company_raw == c.company_raw
        and before[cid].position_raw != c.position_raw
    )
    return ImportChanges(
        new=tuple(c for cid, c in after.items() if cid not in before),
        changed_employer=employer,
        changed_title=title,
        gone=tuple(c for cid, c in before.items() if cid not in after),
    )
