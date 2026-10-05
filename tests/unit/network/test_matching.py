from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from pejip.config import SearchConfig
from pejip.network.companies import CompanyDirectory
from pejip.network.linkedin import Connection, parse_export
from pejip.network.loader import (
    directory_for,
    load_decisions,
    load_index,
    tracked_companies,
)
from pejip.network.matching import (
    MATURED,
    NOT_MATURED,
    YOUR_CALL,
    NetworkIndex,
    TitleDecision,
)
from pejip.scoring import NetworkFacts
from tests.conftest import NOW, ROOT
from tests.linkedin import export, row


def connections(*rows: str) -> tuple[Connection, ...]:
    return parse_export(export(*rows), NOW).connections


DIRECTORY = CompanyDirectory.build(
    ["Company A", "Company B", "Company X"], {"Company A": ["Company A Labs"]}
)
PEOPLE = connections(
    row("Avery", company="Company A", position="SVP Technology"),
    row("Blake", company="Company A Labs", position="Chief Operating Officer"),
    row("Casey", company="Company A", position="Principal, Technology Strategy"),
    row("Devon", company="Company A", position="Senior Director, Engineering"),
    row("Emery", company="Company B", position="VP Program Management"),
    row("Finley", company="Company X Cloud", position="VP Engineering"),
    row("Gray", company="Elsewhere Inc", position="CEO"),
    row("Harper", company="", position="Advisor"),
)


def test_connections_group_by_resolved_company_and_ambiguous_ones_wait() -> None:
    index = NetworkIndex.build(PEOPLE, DIRECTORY)
    assert {c: len(p) for c, p in index.by_company.items()} == {"Company A": 4, "Company B": 1}
    assert list(index.unresolved) == ["Company X Cloud"]
    assert index.held_back["Company X Cloud"] == 1
    assert index.imported_at == NOW


def test_signal_sorts_matured_then_your_call_then_the_rest() -> None:
    signal = NetworkIndex.build(PEOPLE, DIRECTORY).signal("Company A, Inc.", "VP")
    assert signal.company == "Company A"
    assert signal.role_level == "VP"
    assert signal.imported_at == NOW
    assert [(m.connection.first_name, m.status) for m in signal.matches] == [
        ("Avery", MATURED),
        ("Blake", MATURED),
        ("Casey", YOUR_CALL),
        ("Devon", NOT_MATURED),
    ]
    assert signal.facts() == NetworkFacts(first_degree=4, matured=2, your_call=1)


def test_a_more_senior_role_needs_a_more_senior_connection() -> None:
    signal = NetworkIndex.build(PEOPLE, DIRECTORY).signal("Company A", "C_LEVEL")
    assert [m.connection.first_name for m in signal.by_status(MATURED)] == ["Blake"]


def test_your_call_decisions_apply_by_company_title_and_level() -> None:
    decisions = [
        TitleDecision("Company A", "principal,  technology strategy", "VP", matured=True),
        TitleDecision("Company A", "Principal, Technology Strategy", "SVP", matured=False),
    ]
    index = NetworkIndex.build(PEOPLE, DIRECTORY, decisions)
    vp = index.signal("Company A", "VP")
    casey = next(m for m in vp.matches if m.connection.first_name == "Casey")
    assert (casey.status, casey.decided, casey.level) == (MATURED, True, "UNCLEAR")
    svp = index.signal("Company A", "SVP")
    casey = next(m for m in svp.matches if m.connection.first_name == "Casey")
    assert (casey.status, casey.decided) == (NOT_MATURED, True)
    # A level nobody has answered for is still the candidate's call.
    c_level = index.signal("Company A", "C_LEVEL")
    assert [m.connection.first_name for m in c_level.by_status(YOUR_CALL)] == ["Casey"]


def test_an_unknown_role_level_falls_back_to_the_title_then_to_the_candidate() -> None:
    index = NetworkIndex.build(PEOPLE, DIRECTORY)
    by_title = index.signal("Company A", "UNKNOWN", "Chief Technology Officer")
    assert by_title.role_level == "C_LEVEL"
    assert [m.connection.first_name for m in by_title.by_status(MATURED)] == ["Blake"]
    unclear = index.signal("Company A", "UNKNOWN", "Partner, Strategy")
    assert unclear.role_level == "UNCLEAR"
    assert {m.status for m in unclear.matches} == {YOUR_CALL}
    assert unclear.facts() == NetworkFacts(first_degree=4, matured=0, your_call=4)


def test_a_company_with_no_connections_or_no_match_gives_an_empty_signal() -> None:
    index = NetworkIndex.build(PEOPLE, DIRECTORY)
    assert index.signal("Company X", "VP").matches == ()
    unknown = index.signal("Unknown Corp", "VP")
    assert unknown.company is None
    assert unknown.facts() == NetworkFacts(0, 0, 0)


def test_the_latest_import_time_is_kept() -> None:
    older = Connection("id-old", "Old", "Person", None, "Company B", "VP", None, NOW - timedelta(1))
    index = NetworkIndex.build([older, *PEOPLE[:1]], DIRECTORY)
    assert index.imported_at == NOW
    assert NetworkIndex.build([], DIRECTORY).imported_at is None


def test_loader_reads_config_aliases_and_decisions(config: SearchConfig, tmp_path: Path) -> None:
    assert "Anthropic" in tracked_companies(config)
    assert "Meta" in tracked_companies(config)
    decisions_file = tmp_path / "decisions.yaml"
    decisions_file.write_text(
        "companies: {Company X Cloud: null}\n"
        "titles:\n"
        "  - {company: Anthropic, position: Partner, role_level: VP, matured: true}\n"
    )
    decisions = load_decisions(decisions_file)
    assert decisions.companies == {"Company X Cloud": None}
    assert decisions.titles[0].matured is True
    directory = directory_for(config, decisions)
    assert directory.resolve("Facebook").company == "Meta"
    assert directory.resolve("Company X Cloud").method == "DECISION"
    no_network = config.model_copy(update={"network": None, "inbox": None})
    assert directory_for(no_network, decisions).resolve("Facebook").company is None


def test_missing_or_empty_decisions_files_mean_no_decisions(tmp_path: Path) -> None:
    assert load_decisions(None).titles == []
    assert load_decisions(tmp_path / "absent.yaml").companies == {}
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    assert load_decisions(empty).titles == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("titles: [{company: A, position: B, role_level: KING, matured: true}]\n")
    with pytest.raises(ValidationError):
        load_decisions(bad)


def test_load_index_uses_the_file_time_as_the_import_date(config: SearchConfig) -> None:
    sample = ROOT / "examples" / "Connections.example.csv"
    decisions = ROOT / "examples" / "network-decisions.example.yaml"
    preview, index = load_index(config, sample, decisions)
    assert preview.records_accepted == 8
    assert index.imported_at is not None
    assert index.imported_at.timestamp() == pytest.approx(sample.stat().st_mtime)
    assert set(index.by_company) == {"Anthropic", "Meta", "Scale AI", "Stripe"}
    signal = index.signal("Anthropic", "VP")
    assert signal.facts() == NetworkFacts(first_degree=4, matured=3, your_call=0)
