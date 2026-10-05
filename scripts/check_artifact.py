"""Build-artifact check (docs/BUILD_POLICY.md section 2).

Asserts the built wheel ships only the application: the prompts it needs, and no
tests, evaluation data, examples, scripts or local data files.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

FORBIDDEN_PREFIXES = ("tests/", "evals/", "examples/", "scripts/", "config/", "infra/", "docs/")
FORBIDDEN_SUFFIXES = (".db", ".sqlite", "profile.yaml", ".env")
REQUIRED = ("pejip/prompts/job_analysis.v1.md", "pejip/prompts/evidence_matching.v1.md")


def problems(names: list[str]) -> list[str]:
    found = [f"forbidden file in wheel: {n}" for n in names if n.startswith(FORBIDDEN_PREFIXES)]
    found += [f"data file in wheel: {n}" for n in names if n.endswith(FORBIDDEN_SUFFIXES)]
    found += [f"missing from wheel: {r}" for r in REQUIRED if r not in names]
    return found


def main(dist: str = "dist") -> int:
    wheels = sorted(Path(dist).glob("pejip-*.whl"))
    if len(wheels) != 1:
        print(f"::error::expected one wheel in {dist}, found {len(wheels)}")
        return 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        errors = problems(wheel.namelist())
    for error in errors:
        print(f"::error::{error}")
    print(f"{wheels[0].name}: {'OK' if not errors else 'FAILED'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
