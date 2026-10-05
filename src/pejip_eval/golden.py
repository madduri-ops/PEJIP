"""Load and validate the golden evaluation set (spec 9.42, 17.31-17.34)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib

DEFAULT_GOLDEN_DIR = Path(__file__).resolve().parents[2] / "eval" / "golden"


class GoldenSetError(ValueError):
    """The golden set on disk is malformed. Carries every problem found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("invalid golden set:\n  " + "\n  ".join(problems))


@dataclass(frozen=True)
class Job:
    title: str
    company: str
    location: str
    work_model: str
    posted_hours_ago: float
    description: str
    base_min_usd: int | None = None
    base_max_usd: int | None = None
    travel_percent: int | None = None


@dataclass(frozen=True)
class Context:
    """Signals that may change Priority but never Fit (spec 9.8)."""

    connections: int
    strong_relationships: int


@dataclass(frozen=True)
class Expected:
    role_family: str
    inferred_level: str
    fit_min: float
    fit_max: float
    confidence: tuple[str, ...]
    priority: tuple[str, ...]
    positive_reasons: tuple[str, ...]
    concerns: tuple[str, ...]


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    categories: tuple[str, ...]
    notes: str
    invariance_probe: bool
    job: Job
    context: Context
    expected: Expected


@dataclass(frozen=True)
class Manifest:
    golden_set_version: str
    labelled_by: str
    labelled_on: str
    confidence_levels: tuple[str, ...]
    priority_levels: tuple[str, ...]
    inferred_levels: tuple[str, ...]
    work_models: tuple[str, ...]
    categories: tuple[str, ...]
    positive_reasons: tuple[str, ...]
    concerns: tuple[str, ...]


@dataclass(frozen=True)
class GoldenSet:
    manifest: Manifest
    profile: dict[str, Any]
    cases: tuple[Case, ...]

    @property
    def version(self) -> str:
        return self.manifest.golden_set_version


def _read_toml(path: Path, problems: list[str]) -> dict[str, Any] | None:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        problems.append(f"{path.name}: file not found")
    except tomllib.TOMLDecodeError as exc:
        problems.append(f"{path.name}: not valid TOML ({exc})")
    return None


def _strs(
    raw: dict[str, Any], key: str, where: str, problems: list[str]
) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        problems.append(f"{where}: '{key}' must be a list of strings")
        return ()
    return tuple(value)


def _str(raw: dict[str, Any], key: str, where: str, problems: list[str]) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{where}: '{key}' must be a non-empty string")
        return ""
    return value


def _int(
    raw: dict[str, Any],
    key: str,
    where: str,
    problems: list[str],
    *,
    optional: bool = False,
) -> int | None:
    value = raw.get(key)
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        problems.append(f"{where}: '{key}' must be a non-negative integer")
        return None
    return value


def _subset(
    values: tuple[str, ...],
    allowed: tuple[str, ...],
    label: str,
    where: str,
    problems: list[str],
) -> None:
    for value in values:
        if value not in allowed:
            problems.append(f"{where}: unknown {label} '{value}'")


def _load_manifest(raw: dict[str, Any], problems: list[str]) -> Manifest:
    where = "manifest.toml"
    return Manifest(
        golden_set_version=_str(raw, "golden_set_version", where, problems),
        labelled_by=_str(raw, "labelled_by", where, problems),
        labelled_on=_str(raw, "labelled_on", where, problems),
        confidence_levels=_strs(raw, "confidence_levels", where, problems),
        priority_levels=_strs(raw, "priority_levels", where, problems),
        inferred_levels=_strs(raw, "inferred_levels", where, problems),
        work_models=_strs(raw, "work_models", where, problems),
        categories=_strs(raw, "categories", where, problems),
        positive_reasons=_strs(raw, "positive_reasons", where, problems),
        concerns=_strs(raw, "concerns", where, problems),
    )


def _load_case(
    raw: dict[str, Any], where: str, manifest: Manifest, problems: list[str]
) -> Case:
    job_raw = raw.get("job") if isinstance(raw.get("job"), dict) else {}
    ctx_raw = raw.get("context") if isinstance(raw.get("context"), dict) else {}
    exp_raw = raw.get("expected") if isinstance(raw.get("expected"), dict) else {}
    for section, value in (
        ("job", job_raw),
        ("context", ctx_raw),
        ("expected", exp_raw),
    ):
        if not value:
            problems.append(f"{where}: missing [{section}] table")

    job = Job(
        title=_str(job_raw, "title", where, problems),
        company=_str(job_raw, "company", where, problems),
        location=_str(job_raw, "location", where, problems),
        work_model=_str(job_raw, "work_model", where, problems),
        posted_hours_ago=_int(job_raw, "posted_hours_ago", where, problems) or 0,
        description=_str(job_raw, "description", where, problems).strip(),
        base_min_usd=_int(job_raw, "base_min_usd", where, problems, optional=True),
        base_max_usd=_int(job_raw, "base_max_usd", where, problems, optional=True),
        travel_percent=_int(job_raw, "travel_percent", where, problems, optional=True),
    )
    _subset((job.work_model,), manifest.work_models, "work model", where, problems)
    if (
        job.base_min_usd is not None
        and job.base_max_usd is not None
        and job.base_min_usd > job.base_max_usd
    ):
        problems.append(f"{where}: base_min_usd is above base_max_usd")

    context = Context(
        connections=_int(ctx_raw, "connections", where, problems) or 0,
        strong_relationships=_int(ctx_raw, "strong_relationships", where, problems)
        or 0,
    )
    if context.strong_relationships > context.connections:
        problems.append(f"{where}: strong_relationships exceeds connections")

    fit = exp_raw.get("fit")
    fit_min, fit_max = 0.0, 0.0
    if (
        isinstance(fit, list)
        and len(fit) == 2
        and all(isinstance(v, int | float) and not isinstance(v, bool) for v in fit)
        and 0 <= fit[0] <= fit[1] <= 100
    ):
        fit_min, fit_max = float(fit[0]), float(fit[1])
    else:
        problems.append(
            f"{where}: 'fit' must be [min, max] with 0 <= min <= max <= 100"
        )

    expected = Expected(
        role_family=_str(exp_raw, "role_family", where, problems),
        inferred_level=_str(exp_raw, "inferred_level", where, problems),
        fit_min=fit_min,
        fit_max=fit_max,
        confidence=_strs(exp_raw, "confidence", where, problems),
        priority=_strs(exp_raw, "priority", where, problems),
        positive_reasons=_strs(exp_raw, "positive_reasons", where, problems),
        concerns=_strs(exp_raw, "concerns", where, problems),
    )
    _subset(
        (expected.inferred_level,),
        manifest.inferred_levels,
        "inferred level",
        where,
        problems,
    )
    _subset(
        expected.confidence, manifest.confidence_levels, "confidence", where, problems
    )
    _subset(expected.priority, manifest.priority_levels, "priority", where, problems)
    _subset(
        expected.positive_reasons,
        manifest.positive_reasons,
        "positive reason",
        where,
        problems,
    )
    _subset(expected.concerns, manifest.concerns, "concern", where, problems)
    if not expected.confidence:
        problems.append(f"{where}: 'confidence' needs at least one level")
    if not expected.priority:
        problems.append(f"{where}: 'priority' needs at least one level")

    categories = _strs(raw, "categories", where, problems)
    _subset(categories, manifest.categories, "category", where, problems)
    probe = raw.get("invariance_probe", False)
    if not isinstance(probe, bool):
        problems.append(f"{where}: 'invariance_probe' must be true or false")
        probe = False

    return Case(
        id=_str(raw, "id", where, problems),
        name=_str(raw, "name", where, problems),
        categories=categories,
        notes=_str(raw, "notes", where, problems),
        invariance_probe=probe,
        job=job,
        context=context,
        expected=expected,
    )


def load_golden_set(root: Path = DEFAULT_GOLDEN_DIR) -> GoldenSet:
    """Load the golden set under ``root``, raising GoldenSetError with all problems."""
    problems: list[str] = []
    manifest_raw = _read_toml(root / "manifest.toml", problems)
    if manifest_raw is None:
        raise GoldenSetError(problems)
    manifest = _load_manifest(manifest_raw, problems)

    profile = (
        _read_toml(root / str(manifest_raw.get("profile", "profile.toml")), problems)
        or {}
    )
    cases_dir = root / str(manifest_raw.get("cases_dir", "cases"))
    case_paths = sorted(cases_dir.glob("*.toml"))
    if not case_paths:
        problems.append(f"{cases_dir.name}/: no case files found")

    cases: list[Case] = []
    for path in case_paths:
        raw = _read_toml(path, problems)
        if raw is not None:
            cases.append(
                _load_case(raw, f"{cases_dir.name}/{path.name}", manifest, problems)
            )

    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            problems.append(f"duplicate case id '{case.id}'")
        seen.add(case.id)

    covered = {c for case in cases for c in case.categories}
    for category in manifest.categories:
        if category not in covered:
            problems.append(f"category '{category}' has no case")

    if problems:
        raise GoldenSetError(problems)
    return GoldenSet(manifest=manifest, profile=profile, cases=tuple(cases))
