"""Job-alert email parsing and the S3 inbox. Every email here is synthetic."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import pytest

from pejip.config import AlertCompany, SearchConfig
from pejip.sources.email_alerts import (
    INBOX_PREFIX,
    MAX_CONTEXT_LINES,
    SOURCE,
    InboxError,
    S3Inbox,
    make_s3_client,
    parse_alert,
)
from tests.mail import FakeS3, email

COMPANIES = [
    AlertCompany(company="Example", link_patterns=["careers.example.com/"]),
    AlertCompany(company="Sample", link_patterns=["sample.test/about/careers"]),
]


def tracked(url: str) -> str:
    return f"https://click.mailer.test/c?u={quote(url, safe='')}&id=9"


HTML_ALERT = f"""
<html><head><style>a {{ color: blue }}</style><title>Alert</title></head>
<body>
  <p>Hello, here are new roles matching your search.</p>
  <a href="{tracked("https://careers.example.com/jobs/101?utm_source=alert&team=ops")}">
    Vice President, Technology Operations</a>
  <div>San Francisco, CA</div><div>Operations</div>
  <a href="https://careers.example.com/jobs/101?team=ops&utm_medium=email">View job</a>
  <a href="https://careers.example.com/jobs/101/?team=ops">VP Technology Operations (dup)</a>
  <a href="https://sample.test/about/careers/applications/jobs/202">Head of Platform Strategy</a>
  <span>Remote, United States</span>
  <a href="https://sample.test/blog/post">Senior Director, Our Blog</a>
  <a href="https://careers.example.com/search">See all jobs</a>
  <a href="https://careers.example.com/jobs/303"></a>
  <a>Head of nothing</a>
  <a href="https://other.test/unsubscribe">Unsubscribe</a>
  <script>var x = "Chief of Scripts";</script>
</body></html>
"""


def test_html_alert_becomes_one_posting_per_role() -> None:
    alert = parse_alert(email(HTML_ALERT), COMPANIES)

    assert alert.sender == "alerts@careers.example.com"
    assert alert.subject == "New jobs for you"
    assert alert.confirm_links == []
    by_title = {p.title: p for p in alert.postings}
    assert set(by_title) == {"Vice President, Technology Operations", "Head of Platform Strategy"}

    vp = by_title["Vice President, Technology Operations"]
    assert vp.source == SOURCE
    assert vp.company == "Example"
    assert vp.location == "San Francisco, CA"
    # The tracking wrapper and utm_* parameters are gone; the role's own query stays.
    assert vp.url == "https://careers.example.com/jobs/101?team=ops"
    assert vp.source_job_id == vp.url
    assert vp.description.splitlines() == [
        "Vice President, Technology Operations at Example, from a job-alert email.",
        "San Francisco, CA",
        "Operations",
    ]
    assert vp.extra == {"origin": "job_alert_email"}

    head = by_title["Head of Platform Strategy"]
    assert (head.company, head.location) == ("Sample", "Remote, United States")


def test_plain_text_alert_uses_the_line_before_each_link() -> None:
    body = "\n".join(
        [
            "Jobs matching your alert",
            "",
            "Senior Director, Program Management",
            "https://careers.example.com/jobs/7",
            "Mountain View, CA",
            *[f"detail {i}" for i in range(MAX_CONTEXT_LINES + 3)],
            "Chief Technology Officer: https://careers.example.com/jobs/8",
            "https://careers.example.com/jobs/8/apply",
            "Manage alerts: https://careers.example.com/settings",
        ]
    )
    alert = parse_alert(email(body, subtype="plain"), COMPANIES)

    postings = {p.title: p for p in alert.postings}
    assert set(postings) == {"Senior Director, Program Management", "Chief Technology Officer"}
    first = postings["Senior Director, Program Management"]
    assert first.location == "Mountain View, CA"
    assert len(first.description.splitlines()) == 1 + MAX_CONTEXT_LINES
    # A bare link right after another has no text of its own and is skipped.
    assert postings["Chief Technology Officer"].url == "https://careers.example.com/jobs/8"


def test_a_sign_up_check_yields_its_confirmation_link() -> None:
    body = (
        '<p>Please confirm your job alert.</p><a href="'
        + tracked("https://careers.example.com/alerts/confirm?token=abc")
        + '">Confirm my alert</a>'
        '<a href="https://careers.example.com/alerts/confirm?token=abc">Verify email</a>'
    )
    alert = parse_alert(email(body, subject="Confirm   your  alert"), COMPANIES)

    assert alert.postings == []
    assert alert.subject == "Confirm your alert"
    assert alert.confirm_links == ["https://careers.example.com/alerts/confirm?token=abc"]


def test_an_email_without_a_readable_body_yields_nothing() -> None:
    message = EmailMessage()
    message.add_attachment(b"\x00\x01", maintype="application", subtype="octet-stream")
    alert = parse_alert(message.as_bytes(), COMPANIES)

    assert (alert.sender, alert.subject, alert.postings) == ("", "", [])


def test_deeply_nested_tracking_links_stop_unwrapping() -> None:
    url = "https://careers.example.com/jobs/9"
    for _ in range(4):
        url = tracked(url)
    alert = parse_alert(email(f'<a href="{url}">VP, Engineering</a>'), COMPANIES)

    # Three wrappers are followed; a fourth is left alone, so no company matches.
    assert alert.postings == []


def test_a_subdomain_of_a_careers_host_matches() -> None:
    body = '<a href="https://jobs.careers.example.com/role/5">Head of AI Operations</a>'
    alert = parse_alert(email(body), COMPANIES)

    assert [p.company for p in alert.postings] == ["Example"]


def test_the_shipped_configuration_names_the_target_companies(config: SearchConfig) -> None:
    assert config.inbox is not None
    names = {c.company for c in config.inbox.companies}
    assert names == {"Google", "NVIDIA", "Meta", "Micron", "OpenAI", "Microsoft", "LinkedIn"}


def test_inbox_lists_every_page_reads_and_deletes() -> None:
    objects = {f"{INBOX_PREFIX}m{i}": f"message {i}".encode() for i in range(5)}
    s3 = FakeS3({**objects, "elsewhere/x": b"not mail"})
    inbox = S3Inbox(s3, "bucket")

    keys = inbox.message_keys()
    assert keys == sorted(objects)
    assert inbox.read(keys[0]) == b"message 0"
    assert s3.bodies[0].closed
    inbox.delete(keys[0])
    assert f"{INBOX_PREFIX}m0" not in s3.objects
    assert all(call[1]["Bucket"] == "bucket" for call in s3.calls)


def test_an_empty_inbox_has_no_keys() -> None:
    assert S3Inbox(FakeS3({}), "bucket").message_keys() == []


KEY = f"{INBOX_PREFIX}m"
CALLS = {
    "list": lambda inbox: inbox.message_keys(),
    "read": lambda inbox: inbox.read(KEY),
    "delete": lambda inbox: inbox.delete(KEY),
}


@pytest.mark.parametrize(
    ("fail", "action"),
    [
        ("list_objects_v2", "list"),
        ("get_object", "read"),
        ("delete_object-transport", "delete"),
    ],
)
def test_inbox_errors_name_the_action_but_no_content(fail: str, action: str) -> None:
    inbox = S3Inbox(FakeS3({KEY: b"secret body"}, fail=fail), "bucket")
    with pytest.raises(InboxError, match=f"inbox {action} failed") as error:
        CALLS[action](inbox)
    assert "secret" not in str(error.value)


def test_make_s3_client_builds_a_regional_boto3_client() -> None:
    client: Any = make_s3_client("us-west-2")
    assert client.meta.region_name == "us-west-2"
    assert callable(client.list_objects_v2)


BOARD = AlertCompany(
    company="Board",
    job_board=True,
    link_patterns=["jobs.board.test/view"],
    job_id_pattern=r"view/\d+",
)

BOARD_SENDER = "Board Alerts <alerts@board.test>"

BOARD_ALERT = f"""
<p>Your job alert for vice president</p>
<a href="https://jobs.board.test/view/111/?trackingId=abc&refId=x">VP, Platform Engineering</a>
<p>Acme Corp · San Jose, CA (Hybrid)</p><p>Actively recruiting</p>
<a href="{tracked("https://jobs.board.test/view/111/?trk=other")}">VP, Platform Engineering</a>
<a href="https://jobs.board.test/view/222">Head of Technology Operations</a>
<p>Globex</p><p>Remote, United States</p>
<a href="https://jobs.board.test/view/333">Chief Operating Officer</a>
<a href="https://jobs.board.test/viewer/444">Senior Director, Programs</a><p>Initech</p>
<a href="https://jobs.board.test/view/abc">Senior Director, Strategy</a><p>Hooli | Oakland, CA</p>
"""


def test_a_job_board_alert_names_each_employer() -> None:
    alert = parse_alert(email(BOARD_ALERT, sender=BOARD_SENDER), [BOARD])

    by_title = {p.title: p for p in alert.postings}
    assert set(by_title) == {
        "VP, Platform Engineering",
        "Head of Technology Operations",
        "Senior Director, Strategy",
    }
    vp = by_title["VP, Platform Engineering"]
    assert (vp.company, vp.location) == ("Acme Corp", "San Jose, CA (Hybrid)")
    # The role id is cut from the link, so tracking variants are one role.
    assert vp.url == vp.source_job_id == "https://jobs.board.test/view/111"
    assert vp.extra == {"origin": "job_alert_email", "job_board": "Board"}
    assert vp.description.splitlines() == [
        "VP, Platform Engineering at Acme Corp, from a Board job-alert email.",
        "San Jose, CA (Hybrid)",
        "Actively recruiting",
    ]
    head = by_title["Head of Technology Operations"]
    assert (head.company, head.location) == ("Globex", "Remote, United States")
    # A link the id pattern does not match keeps its full canonical URL.
    strategy = by_title["Senior Director, Strategy"]
    assert (strategy.company, strategy.location) == ("Hooli", "Oakland, CA")
    assert strategy.url == "https://jobs.board.test/view/abc"


def test_a_job_board_role_with_no_employer_text_is_skipped() -> None:
    body = '<a href="https://jobs.board.test/view/9">VP, Operations</a><p> · Remote</p>'
    assert parse_alert(email(body, sender=BOARD_SENDER), [BOARD]).postings == []


def test_an_alert_forwarded_as_an_attachment_is_read() -> None:
    inner = EmailMessage()
    inner["From"] = "Board Alerts <alerts@board.test>"
    inner["Subject"] = "Your job alert"
    inner.set_content(BOARD_ALERT, subtype="html")
    outer = EmailMessage()
    outer["From"] = "Babu <someone@mail.test>"
    outer["Subject"] = "Fwd: Your job alert"
    outer.set_content("Forwarding this alert.")
    outer.add_attachment(inner)

    alert = parse_alert(outer.as_bytes(), [BOARD])

    assert alert.sender == "someone@mail.test"
    assert len(alert.postings) == 3


def test_an_invalid_job_id_pattern_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a valid regular expression"):
        AlertCompany(company="Bad", link_patterns=["x.test/"], job_id_pattern="(")


def test_a_confirm_link_to_an_unconfigured_site_is_not_surfaced() -> None:
    body = '<a href="https://bank.test/confirm?t=9">Confirm payment</a>'
    assert parse_alert(email(body), COMPANIES).confirm_links == []


def test_a_job_board_link_in_someone_elses_email_is_not_a_role() -> None:
    body = '<p>Saw this for you</p><a href="https://jobs.board.test/view/5">VP, Eng</a><p>A · B</p>'
    for sender in ("Friend <friend@mail.test>", ""):
        assert parse_alert(email(body, sender=sender), [BOARD]).postings == []


def test_a_role_is_kept_when_only_a_later_link_names_the_employer() -> None:
    body = (
        '<a href="https://jobs.board.test/view/1">VP, Operations</a>'
        '<a href="https://jobs.board.test/view/1?trk=x">VP, Operations</a><p>Acme · Austin, TX</p>'
    )
    [role] = parse_alert(email(body, sender=BOARD_SENDER), [BOARD]).postings
    assert (role.company, role.location) == ("Acme", "Austin, TX")


def test_a_role_has_one_id_with_or_without_www() -> None:
    board = BOARD.model_copy(update={"link_patterns": ["board.test/view"]})
    body = (
        '<a href="https://www.board.test/view/1">VP, Operations</a><p>Acme · Austin, TX</p>'
        '<a href="https://board.test/view/1">VP, Operations</a><p>Acme · Austin, TX</p>'
    )
    [role] = parse_alert(email(body, sender=BOARD_SENDER), [board]).postings
    assert role.url == "https://board.test/view/1"


def test_an_email_in_an_unknown_charset_yields_nothing() -> None:
    raw = (
        b"From: someone@mail.test\r\nSubject: Hi\r\n"
        b"Content-Type: text/plain; charset=unknown-8bit\r\n\r\n\xff\xfe hello\r\n"
    )
    alert = parse_alert(raw, COMPANIES)
    assert (alert.postings, alert.confirm_links) == ([], [])
