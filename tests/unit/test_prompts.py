from __future__ import annotations

import pytest

from pejip.ai import prompts
from pejip.ai.prompts import PromptError, load_prompt, parse_prompt


def test_parse_prompt() -> None:
    prompt = parse_prompt("---\nid: X_Y\nversion: 2\n---\n\n Body text \n")
    assert (prompt.id, prompt.version, prompt.text) == ("X_Y", 2, "Body text")


def test_parse_prompt_needs_header() -> None:
    with pytest.raises(PromptError):
        parse_prompt("no header")


@pytest.mark.parametrize("prompt_id", ["JOB_ANALYSIS", "EVIDENCE_MATCHING"])
def test_shipped_prompts_load(prompt_id: str) -> None:
    prompt = load_prompt(prompt_id)
    assert prompt.version >= 1
    assert "UNKNOWN" in prompt.text


def test_load_prompt_picks_the_highest_version(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.v1.md").write_text("---\nid: A\nversion: 1\n---\none")
    (tmp_path / "a.v2.md").write_text("---\nid: A\nversion: 2\n---\ntwo")
    (tmp_path / "b.v1.md").write_text("---\nid: B\nversion: 1\n---\nb")
    (tmp_path / "notes.txt").write_text("ignored")
    monkeypatch.setattr(prompts.resources, "files", lambda _pkg: tmp_path)
    assert load_prompt("A").text == "two"
    with pytest.raises(PromptError, match="no prompt"):
        load_prompt("C")
