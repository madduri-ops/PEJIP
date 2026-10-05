"""Seniority levels read from a connection's job title (design doc 0014).

A title maps to the same ladder the scorer uses for roles. When a title has no clear
level ("Partner", "Principal", "Managing Director", "Former VP") the answer is
``UNCLEAR`` so the candidate decides, rather than PEJIP guessing either way.
"""

from __future__ import annotations

import re

from pejip.scoring import SENIORITY_RANK

UNCLEAR = "UNCLEAR"

# Checked in order; the first pattern that matches decides the level.
_RULES: tuple[tuple[str, str], ...] = (
    # A past or advisory title says nothing certain about the current position.
    (r"\b(ex|former|formerly|retired|previously)\b", UNCLEAR),
    (r"\bchief of staff\b", UNCLEAR),
    # Assistant and associate VPs and directors sit below the title they name.
    (r"\b(assistant|asst|associate|assoc) (vice president|vp|director)\b|\bavp\b", UNCLEAR),
    (r"\b(senior|sr|executive|exec) (vice president|vp)\b|\b(svp|evp|esvp)\b", "SVP"),
    (r"\b(group )?vice president\b|\b(vp|gvp)\b", "VP"),
    (
        r"\bchief\b|\b(ceo|cto|cio|coo|cfo|cpo|cmo|ciso|cdo|cro|cso|cao|cco|cxo)\b"
        r"|\bpresident\b",
        "C_LEVEL",
    ),
    (
        r"\b(partner|principal|fellow|distinguished|managing director|executive director"
        r"|general manager|gm|founder|cofounder|co founder|owner|advisor|adviser|board"
        r"|chair|chairman|chairwoman|chairperson|investor)\b",
        UNCLEAR,
    ),
    (r"\bhead of\b|\bhead\b", "HEAD_OF"),
    (r"\b(senior|sr)\.? director\b", "SENIOR_DIRECTOR"),
    (r"\bdirector\b", "DIRECTOR"),
    (
        r"\b(manager|engineer|analyst|specialist|associate|coordinator|recruiter|sourcer"
        r"|consultant|scientist|researcher|designer|developer|intern|assistant"
        r"|administrator|architect|lead|representative|accountant|student|technician"
        r"|programmer|writer|editor|officer|staff)\b",
        "BELOW_DIRECTOR",
    ),
)
_COMPILED = tuple((re.compile(pattern), level) for pattern, level in _RULES)
# "Director, Office of the CEO" or "Assistant to the President": the executive named
# after these words is someone else, so that part of the title is ignored.
_SOMEONE_ELSE = re.compile(r"\b(office of|to) the\b.*$")


def normalize_title(title: str) -> str:
    """Lowercase, with punctuation turned into spaces and runs of spaces collapsed."""
    text = re.sub(r"[^a-z0-9.]+", " ", title.lower()).replace(".", " ")
    return " ".join(text.split())


def title_level(title: str) -> str:
    """The seniority level a title states, or ``UNCLEAR``."""
    text = _SOMEONE_ELSE.sub("", normalize_title(title)).strip()
    if not text:
        return UNCLEAR
    for pattern, level in _COMPILED:
        if pattern.search(text):
            return level
    return UNCLEAR


def is_comparable_or_senior(connection_level: str, role_level: str) -> bool:
    """Whether a known connection level is at the role's level or above it."""
    return SENIORITY_RANK[connection_level] >= SENIORITY_RANK[role_level]
