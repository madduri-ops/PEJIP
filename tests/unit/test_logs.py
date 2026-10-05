from __future__ import annotations

import json
import logging
import sys

from pejip.logs import REDACTED, JsonFormatter, configure_logging, redact, run_id_var


def record(msg: str, **extra: object) -> logging.LogRecord:
    rec = logging.LogRecord("pejip.test", logging.INFO, __file__, 1, msg, None, None)
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def test_personal_fields_are_redacted_from_log_lines() -> None:
    token = run_id_var.set("run-1")
    try:
        line = JsonFormatter().format(
            record(
                "contact alex@example.com or +1 (415) 555-0100",
                email="alex@example.com",
                phone="+1 415 555 0100",
                profile={"headline": "Exec", "evidence": ["E1 text"], "count": 3},
                compensation=350000,
                job_id=7,
                notes=["private"],
                path="output/digest.md",
            )
        )
    finally:
        run_id_var.reset(token)
    entry = json.loads(line)
    assert entry["run_id"] == "run-1"
    assert entry["event"] == f"contact {REDACTED} or {REDACTED}"
    assert entry["email"] == entry["phone"] == REDACTED
    assert entry["profile"] == REDACTED
    assert entry["compensation"] == REDACTED
    assert entry["notes"] == REDACTED
    assert entry["job_id"] == 7
    assert "Alex" not in line
    assert "alex@" not in line
    assert "350000" not in line


def test_redact_walks_nested_values() -> None:
    value = {"jobs": [{"email": "a@b.co", "title": "VP"}], "t": ("x@y.io",)}
    assert redact(value) == {"jobs": [{"email": REDACTED, "title": "VP"}], "t": [REDACTED]}


def test_exception_type_is_logged_without_message() -> None:
    detail = "secret detail"

    def fail() -> None:
        raise ValueError(detail)

    try:
        fail()
    except ValueError:
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    entry = json.loads(JsonFormatter().format(rec))
    assert entry["error_type"] == "ValueError"
    assert "secret detail" not in json.dumps(entry)


def test_configure_logging_installs_json_handler() -> None:
    configure_logging(logging.DEBUG)
    root = logging.getLogger()
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.DEBUG
