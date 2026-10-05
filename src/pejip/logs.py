"""Structured JSON logging with a run id and personal-data redaction (policy 14).

All application logging goes through :class:`JsonFormatter`. Fields whose names
are in :data:`REDACTED_FIELDS` are replaced, and e-mail addresses and phone numbers
are scrubbed from free text, so personal data never reaches a log line.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_id", default=None)

REDACTED = "[REDACTED]"
REDACTED_FIELDS = frozenset(
    {
        "name",
        "email",
        "phone",
        "headline",
        "career_direction",
        "evidence",
        "profile",
        "compensation",
        "salary",
        "notes",
    }
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_STANDARD = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None)))


def scrub(text: str) -> str:
    return _PHONE.sub(REDACTED, _EMAIL.sub(REDACTED, text))


def redact(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in REDACTED_FIELDS:
        return REDACTED
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return scrub(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": scrub(record.getMessage()),
            "run_id": run_id_var.get(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and key not in entry:
                entry[key] = redact(value, key)
        if record.exc_info and record.exc_info[0] is not None:
            entry["error_type"] = record.exc_info[0].__name__
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
