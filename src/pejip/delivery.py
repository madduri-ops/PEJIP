"""Emails the digest to Babu through the encrypted ``pejip-digest`` SNS topic.

SNS sends the digest as a plain-text email to the address subscribed in
``infra/digest.tf``. The Markdown reads fine as text. SNS caps a message at
256 KB, so a longer digest is cut at a line boundary with a note saying where the
full digest is kept.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from pejip.digest import Digest, needs_attention

# SNS's limit is 262,144 bytes for the whole message; keep room for the note.
MAX_MESSAGE_BYTES = 250_000
# SNS email subjects must be under 100 characters, ASCII, with no line breaks.
MAX_SUBJECT_CHARS = 99


class SnsClient(Protocol):
    """The one SNS call delivery makes (a boto3 SNS client satisfies it)."""

    def publish(self, **kwargs: Any) -> dict[str, Any]: ...


def make_sns_client(region: str | None) -> SnsClient:
    """A boto3 SNS client using the task role's credentials (no keys in config)."""
    import boto3  # noqa: PLC0415  (only runs where a digest topic is configured)

    return cast(SnsClient, boto3.client("sns", region_name=region))


def subject(digest: Digest) -> str:
    """For example ``PEJIP digest 2026-10-06: 2 need attention, 14 roles (SUCCESS)``."""
    attention = needs_attention(digest)
    roles = len(digest.items)
    text = (
        f"PEJIP digest {digest.generated_at:%Y-%m-%d}: {attention} need attention, "
        f"{roles} role{'' if roles == 1 else 's'} ({digest.status})"
    )
    return text.encode("ascii", "replace").decode("ascii")[:MAX_SUBJECT_CHARS]


def fit_message(text: str, kept_at: str) -> str:
    """``text``, cut at a line boundary if SNS would refuse it as too long."""
    if len(text.encode("utf-8")) <= MAX_MESSAGE_BYTES:
        return text
    cut = text.encode("utf-8")[:MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
    if "\n" in cut:
        cut = cut[: cut.rfind("\n") + 1]
    return f"{cut}\n[Digest cut short for email. The full digest is kept at {kept_at}.]\n"


def send_digest(client: SnsClient, topic_arn: str, digest: Digest, text: str, kept_at: str) -> None:
    client.publish(
        TopicArn=topic_arn,
        Subject=subject(digest),
        Message=fit_message(text, kept_at),
    )
