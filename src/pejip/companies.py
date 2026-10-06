"""The search setup an account's runs use: shipped, plus its companies and saved settings.

Babu's private target companies (ADR-0009) come from ``PEJIP_COMPANIES`` locally
or the encrypted SSM parameter ``PEJIP_COMPANIES_PARAMETER`` on AWS. The search
settings an account saved on the portal (design doc 0017) come from its database.
The run, the digest and the portal's Settings page all read the setup here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from pydantic import ValidationError

from pejip.config import (
    SearchConfig,
    Settings,
    load_config,
    parse_private_companies,
    with_private_companies,
)
from pejip.profile import SsmClient, read_parameter
from pejip.search_settings import SavedSettings, with_saved
from pejip.store import Store

log = logging.getLogger(__name__)

SAVED_UNREADABLE = (
    "Your saved Settings could not be read, so the shipped search settings were used. "
    "Save them again on the Settings page."
)


def load_search_config(
    settings: Settings,
    ssm: Callable[[str | None], SsmClient],
    store: Store | None = None,
) -> tuple[SearchConfig, str | None]:
    """The account's search configuration, and a note for the digest if part is missing.

    A malformed company list raises: searching without it would look like a quiet
    day rather than a broken setup. ``ssm`` builds the SSM client for a region.
    Settings saved in ``store`` replace the shipped ones they cover.
    """
    config, note = _with_companies(settings, ssm)
    config, problem = apply_saved(config, store)
    return config, " ".join(n for n in (note, problem) if n) or None


def apply_saved(config: SearchConfig, store: Store | None) -> tuple[SearchConfig, str | None]:
    """``config`` with the settings saved in ``store``, and a note if they are unreadable."""
    saved = store.saved_search_settings() if store is not None else None
    if saved is None:
        return config, None
    try:
        mine = SavedSettings.model_validate(saved[0])
    except ValidationError:
        # Only the event: the values are the account's own.
        log.warning("saved_settings_unreadable")
        return config, SAVED_UNREADABLE
    return with_saved(config, mine), None


def _with_companies(
    settings: Settings, ssm: Callable[[str | None], SsmClient]
) -> tuple[SearchConfig, str | None]:
    config = load_config(settings.config_path)
    if settings.companies_parameter:
        text = read_parameter(ssm(settings.aws_region), settings.companies_parameter)
        if text is None:
            return config, (
                "Your company list is not stored yet (SSM parameter"
                f" {settings.companies_parameter}), so only the test boards were searched."
            )
    elif settings.companies_path:
        text = settings.companies_path.read_text(encoding="utf-8")
    else:
        return config, None
    return with_private_companies(config, parse_private_companies(text)), None
