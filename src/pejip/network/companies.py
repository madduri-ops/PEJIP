"""Resolve employer names from an import to tracked companies (spec 8.21, 13.3, 13.4).

Resolution order: the candidate's own decisions, then deterministic alias and
normalized exact matches, then high-confidence fuzzy matches. Anything in between is
``AMBIGUOUS`` and waits for review, so a connection is never silently linked to the
wrong company. Names that resemble no tracked company are ``UNMATCHED``; most of a
network works elsewhere, so that is the normal case.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Legal and filler suffixes that do not change which company a name means.
_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "plc",
        "gmbh",
        "ag",
        "sa",
        "lp",
        "llp",
        "pbc",
    }
)
# At or above this similarity a single best candidate is taken without review.
AUTO_MATCH = 0.95
# At or above this similarity a candidate is close enough to ask about.
REVIEW_MATCH = 0.75

RESOLVED = "RESOLVED"
AMBIGUOUS = "AMBIGUOUS"
UNMATCHED = "UNMATCHED"


def normalize_company(name: str) -> str:
    """Lowercase, ``&`` as ``and``, no punctuation and no legal suffixes."""
    text = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("&", " and "))
    words = text.split()
    while len(words) > 1 and words[-1] in _SUFFIXES:
        words.pop()
    return " ".join(words)


@dataclass(frozen=True)
class Resolution:
    """How one employer name resolved.

    ``method`` is ``DECISION``, ``EXACT``, ``ALIAS``, ``FUZZY`` or ``NONE``;
    ``candidates`` lists the companies to choose from when the name is ambiguous, and
    ``score`` is the best similarity found (1.0 for exact and alias matches).
    """

    raw: str
    status: str
    company: str | None = None
    method: str = "NONE"
    score: float = 0.0
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanyDirectory:
    """Tracked companies with their aliases, plus the candidate's own mapping decisions.

    ``decisions`` maps an employer name (as normalized) to the company it means, or to
    ``None`` when the candidate said it is a separate company or should stay unmatched.
    """

    aliases: Mapping[str, tuple[str, ...]]
    decisions: Mapping[str, str | None] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        companies: Iterable[str],
        aliases: Mapping[str, Iterable[str]] | None = None,
        decisions: Mapping[str, str | None] | None = None,
    ) -> CompanyDirectory:
        extra = aliases or {}
        names = dict.fromkeys([*companies, *extra])
        merged = {name: tuple(extra.get(name, ())) for name in names}
        return cls(merged, {normalize_company(raw): co for raw, co in (decisions or {}).items()})

    def _names(self) -> dict[str, set[str]]:
        """Normalized name or alias to the companies it can mean."""
        names: dict[str, set[str]] = {}
        for company, aliases in self.aliases.items():
            for name in (company, *aliases):
                names.setdefault(normalize_company(name), set()).add(company)
        return names

    def resolve(self, raw: str) -> Resolution:
        key = normalize_company(raw)
        if not key:
            return Resolution(raw, UNMATCHED)
        if key in self.decisions:
            decided = self.decisions[key]
            status = UNMATCHED if decided is None else RESOLVED
            return Resolution(raw, status, decided, "DECISION", 1.0)
        names = self._names()
        exact = names.get(key)
        if not exact:
            # "ScaleAI" for "Scale AI": the same name written without spaces.
            squashed = key.replace(" ", "")
            exact = {c for n, cs in names.items() if n.replace(" ", "") == squashed for c in cs}
        if exact:
            if len(exact) > 1:
                return Resolution(raw, AMBIGUOUS, score=1.0, candidates=tuple(sorted(exact)))
            company = next(iter(exact))
            same = normalize_company(company).replace(" ", "") == key.replace(" ", "")
            method = "EXACT" if same else "ALIAS"
            return Resolution(raw, RESOLVED, company, method, 1.0)
        return _fuzzy(raw, key, names)


def _fuzzy(raw: str, key: str, names: dict[str, set[str]]) -> Resolution:
    """Similar names: taken only when one company is near certain, else reviewed."""
    scores: dict[str, float] = {}
    for name, companies in names.items():
        score = SequenceMatcher(None, key, name).ratio()
        # "company x cloud" for "company x": a longer form of a tracked name.
        if key.startswith(name + " ") or name.startswith(key + " "):
            score = max(score, REVIEW_MATCH)
        for company in companies:
            scores[company] = max(scores.get(company, 0.0), score)
    close = sorted((c for c, s in scores.items() if s >= REVIEW_MATCH), key=scores.__getitem__)
    if not close:
        return Resolution(raw, UNMATCHED, score=round(max(scores.values(), default=0.0), 2))
    best = close[-1]
    score = round(scores[best], 2)
    if len(close) == 1 and scores[best] >= AUTO_MATCH:
        return Resolution(raw, RESOLVED, best, "FUZZY", score)
    return Resolution(raw, AMBIGUOUS, score=score, candidates=tuple(sorted(close)))
