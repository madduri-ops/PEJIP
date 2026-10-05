"""Versioned prompt files (policy section 12, spec 14.41).

Each prompt is ``src/pejip/prompts/<name>.v<N>.md`` with a front-matter header
naming its id and version. The newest version of each prompt id is used, and its
id and version are recorded with every result it produces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources

_HEADER = re.compile(
    r"\A---\nid: (?P<id>[A-Z_]+)\nversion: (?P<version>\d+)\n---\n(?P<body>.*)\Z", re.S
)


class PromptError(Exception):
    pass


class MissingHeaderError(PromptError):
    """A prompt file lacks its id/version front-matter header."""

    def __init__(self) -> None:
        super().__init__("prompt file needs an id/version front-matter header")


class UnknownPromptError(PromptError):
    """No shipped prompt has the requested id."""

    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"no prompt with id {prompt_id}")


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    text: str


def parse_prompt(raw: str) -> Prompt:
    match = _HEADER.match(raw)
    if match is None:
        raise MissingHeaderError
    return Prompt(match["id"], int(match["version"]), match["body"].strip())


def load_prompt(prompt_id: str) -> Prompt:
    """Load the highest version of ``prompt_id`` shipped with the package."""
    found: list[Prompt] = []
    for entry in resources.files("pejip.prompts").iterdir():
        if entry.name.endswith(".md"):
            prompt = parse_prompt(entry.read_text(encoding="utf-8"))
            if prompt.id == prompt_id:
                found.append(prompt)
    if not found:
        raise UnknownPromptError(prompt_id)
    return max(found, key=lambda p: p.version)
