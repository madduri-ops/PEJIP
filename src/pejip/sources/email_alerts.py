"""Job-alert emails from the career sites, read from PEJIP's own inbox (design doc 0010).

SES stores each email received at ``alerts@inbox.job-search.zephyr-mcg.com`` whole
(MIME) in an encrypted bucket. A run lists the new messages, turns every link to a
configured company's careers pages into a posting, and deletes the message.

Nothing here fetches the career sites: a posting carries only what the alert said
(title, the text beside the link, the link itself). Messages are never logged
(policy section 10); only counts are.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any, Protocol, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from botocore.exceptions import BotoCoreError, ClientError

from pejip.config import AlertCompany
from pejip.models import Posting
from pejip.sources.http import FetchError

SOURCE = "email_alert"
INBOX_PREFIX = "inbound/"
MAX_TITLE_CHARS = 200
MAX_CONTEXT_LINES = 6
MAX_CONTEXT_LINE_CHARS = 160
# Link text that names an action, not a role ("View job", "Apply now").
_GENERIC_TEXT = re.compile(
    r"^(view|see|apply|learn|read|open|show|click|explore|find|manage|search|more)\b"
    r"|^(here|details|job details|jobs?)$",
    re.IGNORECASE,
)
_CONFIRM_TEXT = re.compile(r"\b(confirm|verify|activate|validate)", re.IGNORECASE)
_NOT_A_ROLE = re.compile(f"{_GENERIC_TEXT.pattern}|{_CONFIRM_TEXT.pattern}", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s<>\"')\]]+")
# Query parameters that only track the click; dropping them keeps one id per role.
_TRACKING = re.compile(r"^(utm_.*|src|source|ref|refid|trk|tracking.*|mc_.*|_hs.*|cid|eid)$", re.I)


class InboxError(FetchError):
    """The inbox bucket could not be read; the run records it and carries on."""

    def __init__(self, action: str, cause: Exception) -> None:
        super().__init__(f"job-alert inbox {action} failed: {type(cause).__name__}")


class S3Client(Protocol):
    """The three S3 calls the inbox makes (a boto3 S3 client satisfies it)."""

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def delete_object(self, **kwargs: Any) -> dict[str, Any]: ...


def make_s3_client(region: str | None) -> S3Client:
    """A boto3 S3 client using the task role's credentials (no keys in config)."""
    import boto3  # noqa: PLC0415  (only runs where an inbox is configured)

    return cast(S3Client, boto3.client("s3", region_name=region))


class S3Inbox:
    """Lists, reads and deletes the raw messages SES delivered."""

    def __init__(self, client: S3Client, bucket: str, prefix: str = INBOX_PREFIX) -> None:
        self._client = client
        self._bucket = bucket
        self._prefix = prefix

    def message_keys(self) -> list[str]:
        keys: list[str] = []
        request: dict[str, Any] = {"Bucket": self._bucket, "Prefix": self._prefix}
        while True:
            page = self._call("list", self._client.list_objects_v2, **request)
            keys += [str(item["Key"]) for item in page.get("Contents", [])]
            if not page.get("IsTruncated"):
                return keys
            request["ContinuationToken"] = page["NextContinuationToken"]

    def read(self, key: str) -> bytes:
        response = self._call("read", self._client.get_object, Bucket=self._bucket, Key=key)
        try:
            return cast(bytes, response["Body"].read())
        finally:
            response["Body"].close()

    def delete(self, key: str) -> None:
        self._call("delete", self._client.delete_object, Bucket=self._bucket, Key=key)

    @staticmethod
    def _call(action: str, method: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return cast(dict[str, Any], method(**kwargs))
        except (BotoCoreError, ClientError) as exc:
            raise InboxError(action, exc) from exc


@dataclass(frozen=True)
class AlertMessage:
    """What one email yielded."""

    sender: str
    subject: str
    postings: list[Posting] = field(default_factory=list)
    confirm_links: list[str] = field(default_factory=list)


@dataclass
class _Link:
    url: str
    text: str
    after: list[str] = field(default_factory=list)


class _LinkExtractor(HTMLParser):
    """Collects each link with its text and the text that follows it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[_Link] = []
        self._open: _Link | None = None
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("style", "script", "head"):
            self._skip += 1
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            self._open = _Link(href.strip(), "")
            self.links.append(self._open)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "head"):
            self._skip = max(0, self._skip - 1)
        elif tag == "a":
            self._open = None

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if self._skip or not text:
            return
        if self._open is not None:
            self._open.text = f"{self._open.text} {text}".strip()
        elif self.links:
            self.links[-1].after.append(text)


def _html_links(markup: str) -> list[_Link]:
    parser = _LinkExtractor()
    parser.feed(markup)
    parser.close()
    return parser.links


def _text_links(body: str) -> list[_Link]:
    """Links in a plain-text email: the line before a URL is its text."""
    links: list[_Link] = []
    previous = ""
    for raw in body.splitlines():
        line = " ".join(raw.split())
        urls = _URL.findall(line)
        if urls:
            label = _URL.sub("", line).strip(" :-|")
            links += [_Link(url, label or previous) for url in urls]
            previous = ""
        elif line:
            if links and len(links[-1].after) < MAX_CONTEXT_LINES:
                links[-1].after.append(line)
            previous = line
    return links


def _unwrap(url: str) -> str:
    """Follow a click-tracking wrapper to the URL it carries in its query."""
    for _ in range(3):
        inner = next(
            (
                v
                for _k, v in parse_qsl(urlsplit(url).query)
                if v.startswith(("http://", "https://"))
            ),
            None,
        )
        if inner is None:
            break
        url = inner
    return url


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k))
    return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def _company_for(url: str, companies: list[AlertCompany]) -> str | None:
    parts = urlsplit(url)
    host, path = parts.netloc.lower(), parts.path.lower()
    for company in companies:
        for pattern in company.link_patterns:
            p_host, _, p_path = pattern.lower().partition("/")
            if (host == p_host or host.endswith(f".{p_host}")) and path.startswith(f"/{p_path}"):
                return company.company
    return None


def _clean_lines(lines: list[str]) -> list[str]:
    kept = [line[:MAX_CONTEXT_LINE_CHARS] for line in lines if not _URL.fullmatch(line)]
    return kept[:MAX_CONTEXT_LINES]


def _postings(links: list[_Link], companies: list[AlertCompany]) -> Iterator[Posting]:
    roles: dict[str, tuple[str, str, list[str]]] = {}
    for link in links:
        url = _unwrap(link.url)
        company = _company_for(url, companies)
        title = link.text.strip()[:MAX_TITLE_CHARS]
        if company is None or not title or _NOT_A_ROLE.search(title):
            continue
        key = _canonical(url)
        if key not in roles:
            roles[key] = (company, title, _clean_lines(link.after))
    for key, (company, title, context) in roles.items():
        location = context[0] if context else ""
        lines = [f"{title} at {company}, from a job-alert email.", *context]
        yield Posting(
            source=SOURCE,
            source_job_id=key[-255:],
            company=company,
            title=title,
            location=location,
            description="\n".join(lines),
            url=key,
            extra={"origin": "job_alert_email"},
        )


def _body(message: EmailMessage) -> tuple[str, bool]:
    part = message.get_body(preferencelist=("html", "plain"))
    if part is None:
        return "", False
    content = cast(EmailMessage, part).get_content()
    return str(content), part.get_content_subtype() == "html"


def parse_alert(raw: bytes, companies: list[AlertCompany]) -> AlertMessage:
    """Turn one raw email into the roles it lists."""
    message = message_from_bytes(raw, policy=policy.default)
    body, is_html = _body(message)
    links = _html_links(body) if is_html else _text_links(body)
    confirm = [_unwrap(link.url) for link in links if _CONFIRM_TEXT.search(link.text)]
    return AlertMessage(
        sender=parseaddr(str(message.get("From", "")))[1],
        subject=" ".join(str(message.get("Subject", "")).split()),
        postings=list(_postings(links, companies)),
        confirm_links=list(dict.fromkeys(confirm)),
    )
