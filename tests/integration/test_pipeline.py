"""The whole run with stubbed sources and a stubbed model."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import httpx
import pytest

from pejip.ai.client import AIClient
from pejip.config import AlertCompany, InboxConfig, SearchConfig, SourceConfig
from pejip.cost import CostGuard, SqliteLedger
from pejip.digest import render
from pejip.pipeline import Pipeline
from pejip.profile import CareerProfile
from pejip.sources.email_alerts import INBOX_PREFIX, S3Inbox
from pejip.sources.http import HTTPStatusError, PoliteClient
from pejip.store import Store
from tests import factories as f
from tests.conftest import NOW, FakeMessages, response
from tests.mail import FakeS3, email

BODY = "<p>Lead technology operations for the company.</p><p>Own portfolio governance.</p>"


def gh_job(
    job_id: int, title: str, location: str = "San Francisco, CA", body: str = BODY
) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": title,
        "location": {"name": location},
        "absolute_url": f"https://boards.test/{job_id}",
        "first_published": (NOW - timedelta(days=1)).isoformat(),
        "content": body,
    }


class Boards:
    """A stub Greenhouse host whose jobs and failures the test controls."""

    def __init__(self, sources: tuple[str, ...] = ("alpha",)) -> None:
        self.sources = sources
        self.jobs: dict[str, list[dict[str, Any]]] = {
            "alpha": [
                gh_job(1, "VP, Technology Operations"),
                gh_job(2, "Head of Engineering Operations", "Remote - US"),
                gh_job(3, "Software Engineer"),
                gh_job(4, "VP, Technology Operations", "London, UK"),
            ]
        }
        self.down: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        board = request.url.path.split("/")[3]
        if board in self.down:
            return httpx.Response(404)
        return httpx.Response(200, json={"jobs": self.jobs.get(board, [])})


def model_responder(fail_titles: tuple[str, ...] = ()) -> Any:
    def respond(request: dict[str, Any]) -> Any:
        content = request["messages"][0]["content"]
        if "<posting>" in content:
            if any(t in content for t in fail_titles):
                return response("not json")
            reqs = [
                f.requirement("R1", quote="Lead technology operations"),
                f.requirement("R2", category="CAPABILITY", quote="Own portfolio governance"),
            ]
            return response(f.analysis(reqs))
        return response(f.matching([f.match("R1"), f.match("R2", evidence=["E4"])]))

    return respond


def build(
    config: SearchConfig,
    profile: CareerProfile,
    store: Store,
    boards: Boards,
    fake: FakeMessages,
    **options: Any,
) -> Pipeline:
    """Wire a pipeline to the stub boards and model.

    ``clock_days`` moves the clock forward and ``guard`` replaces the default cost
    guard; any other option overrides AI config.
    """
    clock_days = options.pop("clock_days", 0)
    inbox = options.pop("inbox", None)
    guard = options.pop("guard", None) or CostGuard(SqliteLedger(":memory:"), clock=lambda: NOW)
    cfg = config.model_copy(
        update={
            "sources": [
                SourceConfig(
                    adapter="greenhouse",
                    company=name.title(),
                    board=name,
                    api_base="https://gh.test",
                )
                for name in boards.sources
            ],
            "ai": config.ai.model_copy(update=options),
        }
    )
    when = NOW + timedelta(days=clock_days)
    http = PoliteClient(
        cfg.fetch.model_copy(update={"min_interval_seconds": 0}),
        transport=httpx.MockTransport(boards.handler),
        sleep=lambda _s: None,
    )
    client = AIClient(cfg.ai, guard, messages=fake, clock=lambda: when)
    return Pipeline(cfg, profile, store, client, http, clock=lambda: when, inbox=inbox)


def test_run_finds_scores_and_explains(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    fake = FakeMessages()
    fake.responder = model_responder()
    digest = build(config, profile, store, Boards(), fake).run()

    assert digest.status == "SUCCESS"
    assert [(s.fetched, s.candidates) for s in digest.sources] == [(4, 2)]
    assert len(fake.calls) == 4  # two prompts for each of the two candidates
    titles = {i.job["title"]: i for i in digest.items}
    assert set(titles) == {"VP, Technology Operations", "Head of Engineering Operations"}
    top = titles["VP, Technology Operations"]
    assert top.discovery == "NEW_POSTING"
    assert top.recommendation is not None
    assert top.recommendation["fit"] == 100.0
    stored = store.latest_recommendation(top.job["id"])
    assert stored is not None
    assert stored["priority"] == top.recommendation["priority"]
    analysis = store.latest_analysis(top.job["id"])
    assert analysis is not None
    assert analysis["provenance"]["analysis"]["prompt_id"] == "JOB_ANALYSIS"
    text = render(digest, config.scoring.strong_match_fit)
    assert "Requires your attention" in text
    assert '"Lead technology operations"' in text


def test_second_run_reuses_analysis_until_the_posting_changes(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    boards = Boards()
    fake = FakeMessages()
    fake.responder = model_responder()
    build(config, profile, store, boards, fake).run()
    assert len(fake.calls) == 4

    again = build(config, profile, store, boards, fake, clock_days=1).run()
    assert len(fake.calls) == 4
    assert {i.discovery for i in again.items} == {"PREVIOUSLY_SEEN"}
    assert all(i.recommendation for i in again.items)

    boards.jobs["alpha"][0] = gh_job(
        1, "VP, Technology Operations", body=BODY + "<p>Now hybrid.</p>"
    )
    changed = build(config, profile, store, boards, fake, clock_days=2).run()
    assert len(fake.calls) == 6
    assert sorted(i.discovery for i in changed.items) == ["MATERIALLY_CHANGED", "PREVIOUSLY_SEEN"]


def test_failures_are_isolated_and_visible(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    boards = Boards(sources=("alpha", "beta"))
    boards.down.add("beta")
    fake = FakeMessages()
    fake.responder = model_responder(fail_titles=("Head of Engineering Operations",))
    digest = build(config, profile, store, boards, fake).run()

    assert digest.status == "PARTIAL"
    assert [s.status for s in digest.sources] == ["OK", "FAILED"]
    assert digest.sources[1].error is not None
    assert "HTTP 404" in digest.sources[1].error
    failed = next(i for i in digest.items if i.job["title"] == "Head of Engineering Operations")
    assert failed.recommendation is None
    assert failed.failure == "analysis failed"
    stored = store.latest_analysis(failed.job["id"])
    assert stored is not None
    assert stored["status"] == "FAILED"


def test_all_sources_failing_fails_the_run(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    boards = Boards()
    boards.down.add("alpha")
    digest = build(config, profile, store, boards, FakeMessages()).run()
    assert digest.status == "FAILED"
    assert digest.items == []


def test_no_sources_is_an_empty_success(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    pipeline = build(config, profile, store, Boards(), FakeMessages())
    pipeline.config = pipeline.config.model_copy(update={"sources": []})
    digest = pipeline.run()
    assert (digest.status, digest.items) == ("SUCCESS", [])


def test_spend_cap_leaves_remaining_roles_unranked(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    guard = CostGuard(SqliteLedger(":memory:"), cap_usd="0.10", clock=lambda: NOW)
    fake = FakeMessages()
    digest = build(config, profile, store, Boards(), fake, guard=guard).run()
    assert fake.calls == []
    assert digest.status == "PARTIAL"
    assert all(i.recommendation is None and i.failure and "cap" in i.failure for i in digest.items)
    assert digest.notes
    assert "cap" in digest.notes[0]


def test_per_run_limit_defers_analysis(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    fake = FakeMessages()
    fake.responder = model_responder()
    digest = build(config, profile, store, Boards(), fake, max_jobs_per_run=1).run()
    deferred = [i for i in digest.items if i.recommendation is None]
    assert [i.failure for i in deferred] == ["deferred to the next run"]


def test_run_record_reflects_failed_sources(
    config: SearchConfig, profile: CareerProfile, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_client: PoliteClient, _source: SourceConfig) -> list[Any]:
        raise HTTPStatusError("stub", 503)

    monkeypatch.setitem(__import__("pejip.pipeline").pipeline.FETCHERS, "greenhouse", boom)
    digest = build(config, profile, store, Boards(), FakeMessages()).run()
    assert digest.sources[0].error == "stub returned HTTP 503"
    runs = json.loads(store.export_all())["runs"]
    assert runs[0]["status"] == "FAILED"


ALERT = """
<a href="https://careers.example.com/jobs/1">VP, Technology Operations</a>
<div>San Francisco, CA</div>
<p>Lead technology operations for the company.</p>
<a href="https://careers.example.com/jobs/2">Software Engineer</a><div>Remote</div>
"""
CONFIRM = '<a href="https://careers.example.com/confirm?t=1">Confirm your alert</a>'


def with_inbox(config: SearchConfig) -> SearchConfig:
    companies = [AlertCompany(company="Example", link_patterns=["careers.example.com/"])]
    return config.model_copy(update={"inbox": InboxConfig(companies=companies)})


def test_inbox_alerts_are_ranked_and_deleted(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    s3 = FakeS3(
        {
            f"{INBOX_PREFIX}a": email(ALERT),
            f"{INBOX_PREFIX}b": email(CONFIRM, subject="Confirm your alert"),
        }
    )
    fake = FakeMessages()
    fake.responder = model_responder()
    pipeline = build(
        with_inbox(config), profile, store, Boards(()), fake, inbox=S3Inbox(s3, "bucket")
    )
    digest = pipeline.run()

    assert digest.status == "SUCCESS"
    inbox_row = digest.sources[-1]
    assert (inbox_row.name, inbox_row.fetched, inbox_row.candidates) == (
        "Job-alert inbox (email)",
        2,
        1,
    )
    [item] = digest.items
    assert item.job["title"] == "VP, Technology Operations"
    assert item.job["source"] == "email_alert"
    assert item.recommendation is not None
    assert digest.notes == [
        "Job-alert inbox: an email from alerts@careers.example.com "
        '("Confirm your alert") listed no roles. '
        "To confirm the alert, open: https://careers.example.com/confirm?t=1"
    ]
    assert s3.objects == {}


def test_inbox_email_with_no_roles_or_links_is_noted(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    s3 = FakeS3({f"{INBOX_PREFIX}a": email("<p>Welcome</p>", subject="")})
    pipeline = build(
        with_inbox(config), profile, store, Boards(()), FakeMessages(), inbox=S3Inbox(s3, "b")
    )
    digest = pipeline.run()

    assert digest.notes == [
        'Job-alert inbox: an email from alerts@careers.example.com ("no subject") listed no roles.'
    ]


def test_a_failing_inbox_does_not_stop_the_boards(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    s3 = FakeS3({f"{INBOX_PREFIX}a": email(ALERT)}, fail="get_object")
    fake = FakeMessages()
    fake.responder = model_responder()
    pipeline = build(with_inbox(config), profile, store, Boards(), fake, inbox=S3Inbox(s3, "b"))
    digest = pipeline.run()

    assert digest.status == "PARTIAL"
    assert digest.sources[-1].status == "FAILED"
    assert digest.sources[-1].error == "job-alert inbox read failed: ClientError"
    assert digest.sources[0].candidates == 2
    assert f"{INBOX_PREFIX}a" in s3.objects


def test_an_inbox_without_configured_companies_is_not_read(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    s3 = FakeS3({f"{INBOX_PREFIX}a": email(ALERT)})
    cfg = config.model_copy(update={"inbox": None})
    digest = build(cfg, profile, store, Boards(()), FakeMessages(), inbox=S3Inbox(s3, "b")).run()

    assert digest.sources == []
    assert s3.calls == []


@pytest.mark.parametrize("missing", ["profile", "ai"])
def test_without_a_profile_or_claude_roles_are_stored_but_unranked(
    config: SearchConfig, profile: CareerProfile, store: Store, missing: str
) -> None:
    fake = FakeMessages()
    pipeline = build(config, profile, store, Boards(), fake)
    setattr(pipeline, missing, None)
    pipeline.unranked_reason = "Claude access is not set up for this workload yet"
    digest = pipeline.run()

    assert fake.calls == []
    assert digest.status == "PARTIAL"
    assert len(digest.items) == 2
    assert all(i.recommendation is None for i in digest.items)
    assert {i.failure for i in digest.items} == {pipeline.unranked_reason}
    assert store.latest_analysis(digest.items[0].job["id"]) is None
    lead = "Roles" if missing == "profile" else "New and changed roles"
    assert digest.notes == [
        f"{lead} are unranked because Claude access is not set up for this workload yet."
    ]
    text = render(digest, config.scoring.strong_match_fit)
    assert "Unranked: Claude access is not set up" in text


def test_without_claude_roles_analysed_before_are_still_scored(
    config: SearchConfig, profile: CareerProfile, store: Store
) -> None:
    boards = Boards()
    fake = FakeMessages()
    fake.responder = model_responder()
    build(config, profile, store, boards, fake).run()
    calls = len(fake.calls)

    boards.jobs["alpha"].append(gh_job(5, "VP, Engineering Operations"))
    pipeline = build(config, profile, store, boards, fake, clock_days=1)
    pipeline.ai = None
    pipeline.unranked_reason = "Claude access is not set up for this workload yet"
    digest = pipeline.run()

    assert len(fake.calls) == calls
    ranked = {i.job["title"]: i.recommendation is not None for i in digest.items}
    assert ranked == {
        "VP, Technology Operations": True,
        "Head of Engineering Operations": True,
        "VP, Engineering Operations": False,
    }
