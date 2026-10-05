"""Unit tests for the build-artifact check."""

import zipfile
from pathlib import Path

import pytest

from ci import check_wheel

CLEAN = ["pejip/__init__.py", "pejip/api.py", "pejip/devices.py", "pejip-0.1.0.dist-info/RECORD"]


def test_clean_wheel_has_no_violations() -> None:
    assert check_wheel.violations(CLEAN) == []


@pytest.mark.parametrize(
    "name",
    [
        "tests/test_api.py",
        "pejip/tests/test_x.py",
        "pejip/test_x.py",
        "pejip/conftest.py",
        "pejip/demo/seed.py",
        "pejip/dev/fake_source.py",
        "pejip/fixtures/profile.json",
        "ci/coverage_gate.py",
    ],
)
def test_dev_demo_and_test_code_is_flagged(name: str) -> None:
    assert check_wheel.violations([*CLEAN, name]) == [name]


def _wheel(path: Path, names: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as wheel:
        for name in names:
            wheel.writestr(name, "")
    return path


def test_main_passes_clean_wheel(tmp_path: Path) -> None:
    assert check_wheel.main([str(_wheel(tmp_path / "pejip.whl", CLEAN))]) == 0


def test_main_fails_dirty_wheel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wheel = _wheel(tmp_path / "pejip.whl", [*CLEAN, "pejip/demo/seed.py"])

    assert check_wheel.main([str(wheel)]) == 1
    assert "pejip/demo/seed.py" in capsys.readouterr().out
