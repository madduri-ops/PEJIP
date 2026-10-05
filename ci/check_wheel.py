"""Build-artifact check (docs/BUILD_POLICY.md section 2).

Fails when a built wheel ships anything other than the `pejip` package and its
metadata, or any dev, demo or test code.
"""

import argparse
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

ALLOWED_TOP_LEVEL = re.compile(r"^(pejip/|pejip-[^/]+\.dist-info/)")
DEV_ONLY = re.compile(r"(^|/)(tests?|demo|dev|fixtures|conftest\.py|test_[^/]*\.py)($|/)")


def violations(names: Sequence[str]) -> list[str]:
    return [name for name in names if not ALLOWED_TOP_LEVEL.match(name) or DEV_ONLY.search(name)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)

    with zipfile.ZipFile(args.wheel) as wheel:
        bad = violations(wheel.namelist())
    for name in bad:
        print(f"::error::{args.wheel.name} ships dev, demo or test code: {name}")
    if bad:
        return 1
    print(f"{args.wheel.name}: production code only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
