"""The career profile read from an encrypted SSM parameter (synthetic data only)."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from pejip.profile import load_profile_parameter, make_ssm_client
from tests.conftest import ROOT

PROFILE_TEXT = (ROOT / "examples" / "profile.example.yaml").read_text(encoding="utf-8")


class FakeSsm:
    def __init__(self, value: str | None = PROFILE_TEXT, error: str | None = None) -> None:
        self.value = value
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get_parameter(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise ClientError({"Error": {"Code": self.error, "Message": "x"}}, "GetParameter")
        return {"Parameter": {"Name": kwargs["Name"], "Value": self.value}}


def test_profile_is_read_decrypted_from_the_parameter() -> None:
    ssm = FakeSsm()
    profile = load_profile_parameter(ssm, "/pejip/profile")
    assert profile is not None
    assert profile.evidence
    assert ssm.calls == [{"Name": "/pejip/profile", "WithDecryption": True}]


def test_a_missing_parameter_means_no_profile_yet() -> None:
    assert load_profile_parameter(FakeSsm(error="ParameterNotFound"), "/pejip/profile") is None


def test_other_failures_are_raised() -> None:
    with pytest.raises(ClientError, match="AccessDenied"):
        load_profile_parameter(FakeSsm(error="AccessDeniedException"), "/pejip/profile")


def test_make_ssm_client_builds_a_regional_boto3_client() -> None:
    client: Any = make_ssm_client("us-west-2")
    assert client.meta.region_name == "us-west-2"
    assert callable(client.get_parameter)
