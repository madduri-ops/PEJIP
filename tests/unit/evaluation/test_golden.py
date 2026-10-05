from __future__ import annotations

import re
from pathlib import Path

import pytest

from pejip.evaluation.golden import GoldenSet, GoldenSetError, load_golden_set


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _problems(root: Path) -> list[str]:
    with pytest.raises(GoldenSetError) as info:
        load_golden_set(root)
    problems: list[str] = info.value.problems
    return problems


def test_committed_set_loads(golden: GoldenSet) -> None:
    assert golden.version == "1.0.0"
    assert len(golden.cases) >= 20
    assert golden.profile["profile_version"] == "synthetic-1"


def test_every_spec_category_is_covered(golden: GoldenSet) -> None:
    covered = {c for case in golden.cases for c in case.categories}
    assert covered == set(golden.manifest.categories)


def test_spec_examples_keep_their_invariants(golden: GoldenSet) -> None:
    by_id = {case.id: case for case in golden.cases}
    # Spec 9.28 A vs B: same fit band, network only moves priority.
    assert (by_id["G01"].expected.fit_min, by_id["G01"].expected.fit_max) == (
        by_id["G02"].expected.fit_min,
        by_id["G02"].expected.fit_max,
    )
    assert by_id["G02"].context.connections == 0
    # Spec 9.28 C: a big network never lifts a weak match.
    assert by_id["G10"].context.connections >= 10
    assert by_id["G10"].expected.priority == ("LOW",)
    # Spec 9.14: hard filters exclude without lowering fit.
    assert by_id["G18"].expected.priority == ("EXCLUDED",)
    assert by_id["G18"].expected.fit_min >= 75
    assert sum(case.invariance_probe for case in golden.cases) >= 3


def test_fixtures_are_synthetic(golden: GoldenSet) -> None:
    # Policy section 10: no real personal data. No emails, phone numbers or URLs.
    pattern = re.compile(r"@|https?://|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
    for case in golden.cases:
        assert not pattern.search(case.job.description), case.id
    assert (
        "Synthetic"
        in Path(__file__).resolve().parents[3].joinpath("eval/golden/profile.toml").read_text()
    )


def test_missing_manifest(tmp_path: Path) -> None:
    assert _problems(tmp_path) == ["manifest.toml: file not found"]


def test_bad_toml_and_empty_cases(golden_copy: Path) -> None:
    for path in (golden_copy / "cases").glob("*.toml"):
        path.unlink()
    (golden_copy / "profile.toml").write_text("not = [valid", encoding="utf-8")
    problems = _problems(golden_copy)
    assert any(p.startswith("profile.toml: not valid TOML") for p in problems)
    assert "cases/: no case files found" in problems
    assert "category 'excellent_match' has no case" in problems


def test_manifest_field_types(golden_copy: Path) -> None:
    _edit(
        golden_copy / "manifest.toml",
        'golden_set_version = "1.0.0"',
        "golden_set_version = 1",
    )
    _edit(
        golden_copy / "manifest.toml",
        'confidence_levels = ["HIGH", "MEDIUM", "LOW"]',
        "confidence_levels = 3",
    )
    problems = _problems(golden_copy)
    assert "manifest.toml: 'golden_set_version' must be a non-empty string" in problems
    assert "manifest.toml: 'confidence_levels' must be a list of strings" in problems


def test_case_vocabulary_and_ranges(golden_copy: Path) -> None:
    case = golden_copy / "cases" / "g01-vp-enterprise-transformation.toml"
    _edit(case, 'priority = ["IMMEDIATE"]', 'priority = ["URGENT"]')
    _edit(case, "fit = [85, 100]", "fit = [90, 80]")
    _edit(case, 'work_model = "HYBRID"', 'work_model = "SOMETIMES"')
    _edit(case, "base_min_usd = 320_000", "base_min_usd = 420_000")
    _edit(case, "strong_relationships = 1", "strong_relationships = 9")
    _edit(
        case,
        'categories = ["excellent_match", "transformation"]',
        'categories = ["excellent", "transformation"]',
    )
    _edit(case, "invariance_probe = true", 'invariance_probe = "yes"')
    _edit(case, 'confidence = ["HIGH"]', "confidence = []")
    _edit(case, 'inferred_level = "VP_EQUIVALENT"', 'inferred_level = "BOSS"')
    _edit(case, "concerns = []", 'concerns = ["GRUMPY"]')
    _edit(case, '"STRONG_TRANSFORMATION_MATCH", "EXECUTIVE', '"NICE", "EXECUTIVE')
    _edit(case, "posted_hours_ago = 5", "posted_hours_ago = -5")
    where = "cases/g01-vp-enterprise-transformation.toml"
    problems = _problems(golden_copy)
    for expected in (
        f"{where}: unknown priority 'URGENT'",
        f"{where}: 'fit' must be [min, max] with 0 <= min <= max <= 100",
        f"{where}: unknown work model 'SOMETIMES'",
        f"{where}: base_min_usd is above base_max_usd",
        f"{where}: strong_relationships exceeds connections",
        f"{where}: unknown category 'excellent'",
        f"{where}: 'invariance_probe' must be true or false",
        f"{where}: 'confidence' needs at least one level",
        f"{where}: unknown inferred level 'BOSS'",
        f"{where}: unknown concern 'GRUMPY'",
        f"{where}: unknown positive reason 'NICE'",
        f"{where}: 'posted_hours_ago' must be a non-negative integer",
    ):
        assert expected in problems


def test_missing_tables_and_duplicate_ids(golden_copy: Path) -> None:
    (golden_copy / "cases" / "zz-empty.toml").write_text(
        'id = "G01"\npriority = []\n', encoding="utf-8"
    )
    problems = _problems(golden_copy)
    where = "cases/zz-empty.toml"
    assert f"{where}: missing [job] table" in problems
    assert f"{where}: missing [context] table" in problems
    assert f"{where}: missing [expected] table" in problems
    assert f"{where}: 'priority' needs at least one level" in problems
    assert "duplicate case id 'G01'" in problems


def test_unreadable_case_file(golden_copy: Path) -> None:
    (golden_copy / "cases" / "zz-broken.toml").write_text("id = ", encoding="utf-8")
    assert any(p.startswith("zz-broken.toml: not valid TOML") for p in _problems(golden_copy))


def test_custom_profile_and_cases_dir(golden_copy: Path) -> None:
    (golden_copy / "cases").rename(golden_copy / "roles")
    (golden_copy / "profile.toml").rename(golden_copy / "person.toml")
    _edit(
        golden_copy / "manifest.toml",
        'profile = "profile.toml"',
        'profile = "person.toml"',
    )
    _edit(golden_copy / "manifest.toml", 'cases_dir = "cases"', 'cases_dir = "roles"')
    assert len(load_golden_set(golden_copy).cases) >= 20
