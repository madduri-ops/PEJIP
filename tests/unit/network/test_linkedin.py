from __future__ import annotations

import zipfile
from datetime import date

import pytest

from pejip.network import linkedin
from pejip.network.linkedin import ExportError, compare_imports, parse_export
from tests.conftest import NOW
from tests.linkedin import HEADER, export, row, zipped


def test_parses_an_export_with_linkedins_notes_preamble() -> None:
    data = export(
        row(),
        row("Blake", "Sample", "Company X, Inc.", "Principal, Technology Strategy", connected=""),
    )
    preview = parse_export(data, NOW)
    assert preview.records_parsed == 2
    assert preview.records_accepted == 2
    assert preview.rejected == ()
    assert preview.duplicates == 0
    assert preview.undated == 1
    assert preview.source_type == "LINKEDIN_CONNECTIONS_EXPORT"
    assert len(preview.source_file_hash) == 64
    first, second = preview.connections
    assert first.name == "Avery Example"
    assert first.profile_url == "https://www.linkedin.com/in/avery-example"
    assert first.company_raw == "Alpha"
    assert first.connected_on == date(2019, 3, 14)
    assert first.imported_at == NOW
    assert first.relationship_strength == "UNKNOWN"
    assert second.company_raw == "Company X, Inc."
    assert second.position_raw == "Principal, Technology Strategy"
    assert second.connected_on is None


def test_email_addresses_are_never_kept() -> None:
    preview = parse_export(export(row(email="avery@example.invalid")), NOW)
    assert "example.invalid" not in repr(preview)


def test_an_export_without_notes_and_other_date_formats() -> None:
    preview = parse_export(
        export(row(connected="2024-02-01"), row("Blake", connected="02/03/2024"), notes=False),
        NOW,
    )
    assert [c.connected_on for c in preview.connections] == [date(2024, 2, 1), date(2024, 2, 3)]
    assert preview.undated == 0


def test_bad_rows_are_rejected_with_reasons_and_blank_lines_skipped() -> None:
    data = export(
        row(),
        "",
        row("", ""),
        "Only,Three,Cells",
        row("Bl�ke"),
    )
    preview = parse_export(data, NOW)
    assert preview.records_parsed == 4
    assert [(r.line, r.reason) for r in preview.rejected] == [
        (7, "no first or last name"),
        (8, "wrong number of columns"),
        (9, "unreadable characters"),
    ]


def test_duplicates_merge_by_profile_url_or_by_name_and_company() -> None:
    data = export(
        row(url="https://www.linkedin.com/in/avery"),
        row(url="http://www.linkedin.com/in/avery/"),
        row("Blake", "Sample", url=""),
        row("blake", "sample", url=""),
        row("Blake", "Sample", company="Beta", url=""),
    )
    preview = parse_export(data, NOW)
    assert preview.duplicates == 2
    assert preview.records_accepted == 3
    assert preview.connections[1].profile_url is None


def test_reads_connections_csv_from_a_zip() -> None:
    preview = parse_export(zipped(export(row())), NOW)
    assert preview.records_accepted == 1


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\xff\xfe\x00junk", "not UTF-8"),
        (b"PK\x03\x04 not really a zip", "damaged"),
        (zipped(export(row()), name="Profile.csv"), "no Connections.csv"),
        (b"Name,Company\nAvery,Alpha\n", "header row"),
        (b"First Name,Last Name,URL\nAvery,Example,x\n", "missing: Company, Position"),
        (export(), "no connection rows"),
    ],
)
def test_unusable_uploads_are_refused(data: bytes, message: str) -> None:
    with pytest.raises(ExportError, match=message):
        parse_export(data, NOW)


def test_oversized_uploads_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(linkedin, "MAX_EXPORT_BYTES", 1000)
    with pytest.raises(ExportError, match="larger"):
        parse_export(b"x" * 1001, NOW)
    # A small zip that expands past the limit (a zip bomb) is refused before reading.
    bomb = zipped(export(*[row() for _ in range(50)]), compression=zipfile.ZIP_DEFLATED)
    assert len(bomb) <= 1000
    with pytest.raises(ExportError, match="larger"):
        parse_export(bomb, NOW)


def test_a_corrupted_zip_member_is_refused() -> None:
    data = bytearray(zipped(export(row())))
    data[data.index(b"Avery")] ^= 0xFF
    with pytest.raises(ExportError, match="damaged"):
        parse_export(bytes(data), NOW)


def test_header_constant_matches_linkedins_columns() -> None:
    assert ",".join(linkedin.HEADER) == HEADER


def test_compare_imports_finds_new_moved_retitled_and_gone() -> None:
    before = parse_export(
        export(row("Avery"), row("Blake"), row("Casey"), row("Devon")), NOW
    ).connections
    after = parse_export(
        export(
            row("Avery"),
            row("Blake", company="Beta"),
            row("Casey", position="Chief Operating Officer"),
            row("Emery"),
        ),
        NOW,
    ).connections
    changes = compare_imports(before, after)
    assert [c.first_name for c in changes.new] == ["Emery"]
    assert [(a.company_raw, b.company_raw) for a, b in changes.changed_employer] == [
        ("Alpha", "Beta")
    ]
    assert [b.position_raw for _, b in changes.changed_title] == ["Chief Operating Officer"]
    assert [c.first_name for c in changes.gone] == ["Devon"]


def test_an_unreadable_connection_date_is_kept_as_unknown() -> None:
    preview = parse_export(export(row(connected="sometime in spring")), NOW)
    assert preview.connections[0].connected_on is None
    assert preview.undated == 1


def test_quoted_fields_may_span_lines_and_hold_unicode_separators() -> None:
    data = export(
        row("Avery", position='"VP\nPlatform"'.strip('"')),
        row("Blake", position="VP\u2028Platform"),
        row("", ""),
    )
    preview = parse_export(data, NOW)
    assert [c.position_raw for c in preview.connections] == ["VP\nPlatform", "VP\u2028Platform"]
    # The row after a two-line record keeps its true line number.
    assert [(r.line, r.reason) for r in preview.rejected] == [(8, "no first or last name")]
