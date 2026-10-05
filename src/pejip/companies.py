"""Babu's private target companies, added to the shipped search setup (ADR-0009).

The run and the portal's Settings page both read them, from ``PEJIP_COMPANIES``
locally or the encrypted SSM parameter ``PEJIP_COMPANIES_PARAMETER`` on AWS.
"""

from __future__ import annotations

from collections.abc import Callable

from pejip.config import (
    SearchConfig,
    Settings,
    load_config,
    parse_private_companies,
    with_private_companies,
)
from pejip.profile import SsmClient, read_parameter


def load_search_config(
    settings: Settings, ssm: Callable[[str | None], SsmClient]
) -> tuple[SearchConfig, str | None]:
    """The search configuration with Babu's private companies, and a note if they are missing.

    A malformed company list raises: searching without it would look like a quiet
    day rather than a broken setup. ``ssm`` builds the SSM client for a region.
    """
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
