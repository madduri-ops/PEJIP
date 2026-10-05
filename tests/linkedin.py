"""Synthetic LinkedIn Connections exports. Every person and company here is invented."""

from __future__ import annotations

import io
import zipfile

NOTES = (
    "Notes:\n"
    '"When exporting your connection data, you may notice that some of the email '
    'addresses are missing."\n'
    "\n"
)
HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"


def row(  # noqa: PLR0913 - one argument per export column
    first: str = "Avery",
    last: str = "Example",
    company: str = "Alpha",
    position: str = "SVP Technology",
    *,
    url: str | None = None,
    connected: str = "14 Mar 2019",
    email: str = "",
) -> str:
    link = url if url is not None else f"https://www.linkedin.com/in/{first}-{last}".lower()
    cells = [first, last, link, email, company, position, connected]
    return ",".join(f'"{c}"' if "," in c else c for c in cells)


def export(*rows: str, notes: bool = True) -> bytes:
    text = (NOTES if notes else "") + HEADER + "\n" + "\n".join(rows) + "\n"
    return text.encode("utf-8")


def zipped(
    data: bytes,
    name: str = "Basic_LinkedInDataExport/Connections.csv",
    compression: int = zipfile.ZIP_STORED,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr(name, data)
    return buffer.getvalue()
