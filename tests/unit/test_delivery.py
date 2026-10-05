"""Emailing the digest through SNS."""

from __future__ import annotations

from typing import Any

from pejip.delivery import (
    MAX_MESSAGE_BYTES,
    MAX_SUBJECT_CHARS,
    fit_message,
    make_sns_client,
    send_digest,
    subject,
)
from pejip.digest import Digest, DigestItem
from tests.conftest import NOW


def item(priority: str | None) -> DigestItem:
    job = {"title": "VP, Technology Operations", "company": "Acme"}
    rec = None if priority is None else {"priority": priority, "fit": 80.0}
    return DigestItem(job, "NEW_POSTING", rec)


class FakeSns:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def publish(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"MessageId": "m-1"}


def test_subject_counts_roles_that_need_attention() -> None:
    digest = Digest("r", NOW, "PARTIAL", [], [item("IMMEDIATE"), item("HIGH"), item("LOW")])
    assert subject(digest) == "PEJIP digest 2026-10-05: 2 need attention, 3 roles (PARTIAL)"
    one = Digest("r", NOW, "SUCCESS", [], [item(None)])
    assert subject(one) == "PEJIP digest 2026-10-05: 0 need attention, 1 role (SUCCESS)"


def test_subject_is_short_ascii() -> None:
    digest = Digest("r", NOW, "SUCCESS\u00e9" + "x" * 200, [])
    text = subject(digest)
    assert len(text) == MAX_SUBJECT_CHARS
    assert text.isascii()
    assert "\n" not in text


def test_short_digests_are_sent_whole() -> None:
    assert fit_message("# digest\n", "/data/output/d.md") == "# digest\n"


def test_long_digests_are_cut_at_a_line_with_a_note() -> None:
    line = "- Why it fits: café ✓ " * 4 + "\n"
    text = line * (MAX_MESSAGE_BYTES // len(line.encode()) + 50)
    cut = fit_message(text, "/data/output/d.md")
    assert len(cut.encode("utf-8")) < MAX_MESSAGE_BYTES + 200
    body, note = cut.rsplit("\n[", 1)
    assert body.endswith("\n")
    assert all(row + "\n" == line for row in body.rstrip("\n").split("\n"))
    assert "/data/output/d.md" in note


def test_send_digest_publishes_to_the_topic() -> None:
    sns = FakeSns()
    digest = Digest("r", NOW, "SUCCESS", [], [item("HIGH")])
    send_digest(sns, "arn:aws:sns:us-west-2:111111111111:pejip-digest", digest, "# d\n", "p")
    assert sns.calls == [
        {
            "TopicArn": "arn:aws:sns:us-west-2:111111111111:pejip-digest",
            "Subject": "PEJIP digest 2026-10-05: 1 need attention, 1 role (SUCCESS)",
            "Message": "# d\n",
        }
    ]


def test_make_sns_client_builds_a_regional_boto3_client() -> None:
    client: Any = make_sns_client("us-west-2")
    assert client.meta.region_name == "us-west-2"
    assert callable(client.publish)
