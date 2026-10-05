from __future__ import annotations

import pytest

from pejip.network.companies import (
    AMBIGUOUS,
    RESOLVED,
    UNMATCHED,
    CompanyDirectory,
    normalize_company,
)


@pytest.fixture
def directory() -> CompanyDirectory:
    return CompanyDirectory.build(
        ["Company X", "Company E", "Company F", "Meta", "Scale AI"],
        {"Meta": ["Facebook"], "Company E": ["Northstar"], "Company F": ["Northstar"]},
    )


def test_normalize_company() -> None:
    assert normalize_company("Company X, Inc.") == "company x"
    assert normalize_company("AT&T Corp") == "at and t"
    assert normalize_company("Acme Holdings Co. LLC") == "acme holdings"
    assert normalize_company("Inc.") == "inc"
    assert normalize_company("  ,  ") == ""


@pytest.mark.parametrize(
    ("raw", "company", "method"),
    [
        ("Company X", "Company X", "EXACT"),
        ("Company X Inc.", "Company X", "EXACT"),
        ("company x, llc", "Company X", "EXACT"),
        ("Facebook", "Meta", "ALIAS"),
        ("ScaleAI", "Scale AI", "EXACT"),
    ],
)
def test_deterministic_matches_resolve(
    directory: CompanyDirectory, raw: str, company: str, method: str
) -> None:
    res = directory.resolve(raw)
    assert (res.status, res.company, res.method, res.score) == (RESOLVED, company, method, 1.0)
    assert res.raw == raw


def test_a_name_shared_by_two_companies_is_ambiguous(directory: CompanyDirectory) -> None:
    res = directory.resolve("Northstar")
    assert res.status == AMBIGUOUS
    assert res.company is None
    assert res.candidates == ("Company E", "Company F")


def test_a_longer_form_of_a_tracked_name_is_reviewed_not_guessed(
    directory: CompanyDirectory,
) -> None:
    res = directory.resolve("Company X Cloud")
    assert res.status == AMBIGUOUS
    assert "Company X" in res.candidates
    assert res.company is None


def test_a_near_certain_fuzzy_match_resolves() -> None:
    directory = CompanyDirectory.build(["Databricks Platform Services"])
    res = directory.resolve("Databricks Platform Service")
    assert (res.status, res.method) == (RESOLVED, "FUZZY")
    assert res.company == "Databricks Platform Services"
    assert 0.95 <= res.score < 1.0


def test_a_close_but_uncertain_name_is_ambiguous() -> None:
    res = CompanyDirectory.build(["Meta"]).resolve("Metal")
    assert res.status == AMBIGUOUS
    assert res.candidates == ("Meta",)


def test_unrelated_and_empty_names_are_unmatched(directory: CompanyDirectory) -> None:
    acme = directory.resolve("Acme Rockets")
    assert acme.status == UNMATCHED
    assert acme.candidates == ()
    assert directory.resolve("").status == UNMATCHED
    assert CompanyDirectory.build([]).resolve("Acme").score == 0.0


def test_candidate_decisions_win(directory: CompanyDirectory) -> None:
    decided = CompanyDirectory.build(
        directory.aliases, decisions={"Northstar": "Company E", "Company X Cloud": None}
    )
    northstar = decided.resolve("northstar")
    assert (northstar.status, northstar.company, northstar.method) == (
        RESOLVED,
        "Company E",
        "DECISION",
    )
    cloud = decided.resolve("Company X Cloud")
    assert (cloud.status, cloud.company, cloud.method) == (UNMATCHED, None, "DECISION")


def test_alias_companies_need_not_be_listed_twice() -> None:
    directory = CompanyDirectory.build(["Meta"], {"Meta": ["Facebook"], "Micron": ["Micron Tech"]})
    assert set(directory.aliases) == {"Meta", "Micron"}
    assert directory.resolve("Micron Tech").company == "Micron"
