"""The search settings each account edits on the portal's Settings page (design doc 0017).

An account can change which titles count (seniority words, role words, titles
always left out) and where roles may be (each location's places and preference,
and whether roles outside them are hidden). The latest saved values are kept in
the account's own database and replace those fields of the shipped
``config/search.yaml`` for every later search, ranking and digest. Ranking
weights stay in the shipped file: they change only through a reviewed change
that passes the ranking test set (policy section 12).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import get_args

from pydantic import BaseModel, ConfigDict

from pejip.config import GeographyConfig, GeoScope, Preference, SearchConfig, TaxonomyConfig

# Bounds on what the form accepts: far above any real list, small enough that a
# post can't fill the database or slow every title match.
MAX_TERMS = 100
MAX_TERM_CHARS = 80
# Letters, digits, spaces and the punctuation real titles and places use.
_TERM = re.compile(r"^[a-z0-9][a-z0-9 &/.'()+-]*$")

PREFERENCES: tuple[str, ...] = get_args(Preference)

# The form's text areas, in the order the page shows them.
TERM_FIELDS = {
    "role_terms": "Role words a title needs",
    "seniority_patterns": "Words that make a title senior",
    "excluded_title_patterns": "Words that never count as senior",
}
# Every considered role's title has a role word, so an empty list finds nothing.
REQUIRED_FIELDS = ("role_terms",)


class SavedSettings(BaseModel):
    """The fields of the search configuration an account has saved from the portal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    taxonomy: TaxonomyConfig
    geography: GeographyConfig


class SettingsError(ValueError):
    """A value on the Settings form that can't be saved; the message says which."""


def current(config: SearchConfig) -> SavedSettings:
    """The editable fields as they stand in ``config``."""
    return SavedSettings(taxonomy=config.taxonomy, geography=config.geography)


def with_saved(config: SearchConfig, saved: SavedSettings) -> SearchConfig:
    """``config`` with the account's saved fields in place of the shipped ones."""
    return config.model_copy(update={"taxonomy": saved.taxonomy, "geography": saved.geography})


@dataclass(frozen=True)
class SettingsForm:
    """The Settings form's values as text, so a refused post is shown back as typed."""

    terms: Mapping[str, str]
    places: Mapping[str, str]
    preferences: Mapping[str, str]
    hard_filter: bool

    @classmethod
    def of(cls, saved: SavedSettings) -> SettingsForm:
        scopes = saved.geography.scopes
        return cls(
            terms={name: "\n".join(getattr(saved.taxonomy, name)) for name in TERM_FIELDS},
            places={key: "\n".join(scope.places) for key, scope in scopes.items()},
            preferences={key: scope.preference for key, scope in scopes.items()},
            hard_filter=saved.geography.hard_filter,
        )

    @classmethod
    def posted(cls, fields: Mapping[str, list[str]], scopes: list[str]) -> SettingsForm:
        """The posted form; only the locations the page offers (``scopes``) are read."""

        def one(name: str) -> str:
            return fields.get(name, [""])[0]

        return cls(
            terms={name: one(name) for name in TERM_FIELDS},
            places={key: one(f"places.{key}") for key in scopes},
            preferences={key: one(f"preference.{key}") for key in scopes},
            hard_filter=one("hard_filter") == "on",
        )

    def parse(self, labels: Mapping[str, str] | None = None) -> SavedSettings:
        """The settings to save; raises :class:`SettingsError` naming the first bad value.

        ``labels`` names each location the way the page does, for the messages.
        """
        taxonomy = {
            name: _terms(self.terms[name], label, required=name in REQUIRED_FIELDS)
            for name, label in TERM_FIELDS.items()
        }
        scopes = {}
        for key, text in self.places.items():
            place = (labels or {}).get(key) or key.replace("_", " ").title()
            preference = self.preferences.get(key, "")
            if preference not in PREFERENCES:
                msg = f"Choose a preference for {place}."
                raise SettingsError(msg)
            places = _terms(text, f"Places for {place}", required=False)
            scopes[key] = GeoScope.model_validate({"preference": preference, "places": places})
        return SavedSettings(
            taxonomy=TaxonomyConfig(**taxonomy),
            geography=GeographyConfig(hard_filter=self.hard_filter, scopes=scopes),
        )


def _terms(text: str, label: str, *, required: bool) -> list[str]:
    """One term per line (or comma), lower-cased, blanks and repeats dropped."""
    found = [
        " ".join(part.split()).lower() for line in text.splitlines() for part in line.split(",")
    ]
    terms = list(dict.fromkeys(t for t in found if t))
    if required and not terms:
        msg = f"{label}: enter at least one, or no title will match."
        raise SettingsError(msg)
    if len(terms) > MAX_TERMS:
        msg = f"{label}: at most {MAX_TERMS} entries."
        raise SettingsError(msg)
    for term in terms:
        if len(term) > MAX_TERM_CHARS or not _TERM.match(term):
            msg = (
                f"{label}: “{term[:MAX_TERM_CHARS]}” can't be used. Use letters, digits, "
                f"spaces and & / . ' ( ) + -, up to {MAX_TERM_CHARS} characters."
            )
            raise SettingsError(msg)
    return terms
