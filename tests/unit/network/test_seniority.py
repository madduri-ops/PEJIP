from __future__ import annotations

import pytest

from pejip.network.seniority import UNCLEAR, is_comparable_or_senior, normalize_title, title_level


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("SVP Technology", "SVP"),
        ("Executive Vice President, Operations", "SVP"),
        ("Sr. Vice President", "SVP"),
        ("EVP", "SVP"),
        ("VP Program Management", "VP"),
        ("Vice President", "VP"),
        ("Group Vice President, Cloud", "VP"),
        ("Chief Operating Officer", "C_LEVEL"),
        ("CTO", "C_LEVEL"),
        ("Co-Founder & CEO", "C_LEVEL"),
        ("President, Cloud Division", "C_LEVEL"),
        ("Head of Platform", "HEAD_OF"),
        ("Sr. Director, Engineering", "SENIOR_DIRECTOR"),
        ("Senior Director of Product", "SENIOR_DIRECTOR"),
        ("Director of Product", "DIRECTOR"),
        ("Senior Software Engineer", "BELOW_DIRECTOR"),
        ("Engineering Manager", "BELOW_DIRECTOR"),
        ("Lead Recruiter", "BELOW_DIRECTOR"),
    ],
)
def test_clear_titles_have_a_level(title: str, level: str) -> None:
    assert title_level(title) == level


@pytest.mark.parametrize(
    "title",
    [
        "Principal, Technology Strategy",
        "Partner",
        "Managing Director",
        "General Manager",
        "Distinguished Engineer",
        "Chief of Staff to the CEO",
        "Former VP Engineering",
        "Ex-CTO, now advising startups",
        "AVP, Operations",
        "Board Member",
        "Investor",
        "Something odd",
        "",
        "  --  ",
    ],
)
def test_titles_without_a_clear_level_are_unclear(title: str) -> None:
    assert title_level(title) == UNCLEAR


def test_normalize_title() -> None:
    assert normalize_title("  Sr. Director,  Product & Design ") == "sr director product design"


def test_comparison_uses_the_scoring_ladder() -> None:
    assert is_comparable_or_senior("SVP", "VP")
    assert is_comparable_or_senior("VP", "VP")
    assert is_comparable_or_senior("HEAD_OF", "VP")
    assert not is_comparable_or_senior("SENIOR_DIRECTOR", "VP")
    assert not is_comparable_or_senior("VP", "C_LEVEL")
