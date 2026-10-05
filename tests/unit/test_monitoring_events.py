"""The log metric filters in infra/monitoring.tf must match events the app logs.

CloudWatch only counts log lines whose JSON fields match a filter, and nothing
checks that at plan time. If an event were renamed in the code, its alarm would
go quiet for good, so this test ties each filter to the code that logs it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MONITORING = ROOT / "infra" / "monitoring.tf"
SOURCE = ROOT / "src" / "pejip"

EVENT = re.compile(r'\$\.event = \\"(\w+)\\"')
STATUS = re.compile(r'\$\.status = \\"(\w+)\\"')


def _logged_events() -> set[str]:
    events: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        events.update(re.findall(r'log\.\w+\(\s*"(\w+)"', path.read_text()))
    return events


def test_every_filtered_event_is_logged_by_the_app() -> None:
    filtered = set(EVENT.findall(MONITORING.read_text()))

    assert filtered == {"run_finished", "source_failed"}
    assert filtered <= _logged_events()


def test_crashed_runs_are_left_to_the_task_failed_alert() -> None:
    # A crash exits non-zero, which the task-failed rule already emails, so
    # AppErrors must not count the same crash a second time.
    text = MONITORING.read_text()

    assert "run_crashed" in _logged_events()
    assert '$.level = \\"ERROR\\"' in text
    assert '$.event != \\"run_crashed\\"' in text


def test_filtered_run_statuses_are_the_pipeline_statuses() -> None:
    pipeline = (SOURCE / "pipeline.py").read_text()
    statuses = set(STATUS.findall(MONITORING.read_text()))

    assert statuses == {"SUCCESS", "PARTIAL", "FAILED"}
    for status in statuses:
        assert f'status = "{status}"' in pipeline
