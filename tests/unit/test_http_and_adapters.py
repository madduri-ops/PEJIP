from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from pejip.config import FetchConfig, SourceConfig
from pejip.sources.greenhouse import fetch_greenhouse
from pejip.sources.http import FetchError, PoliteClient, RateLimiter, RobotsDisallowedError
from pejip.sources.lever import fetch_lever

FETCH = FetchConfig(
    user_agent="PEJIP-test",
    min_interval_seconds=0,
    max_retries=2,
    backoff_base_seconds=1,
    timeout_seconds=5,
)
Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler, sleeps: list[float] | None = None) -> PoliteClient:
    record = sleeps if sleeps is not None else []
    return PoliteClient(FETCH, transport=httpx.MockTransport(handler), sleep=record.append)


def routes(table: dict[str, httpx.Response | Exception]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        item = table[request.url.path]
        if isinstance(item, Exception):
            raise item
        return item

    return handler


class TestRateLimiter:
    def test_waits_only_for_the_remaining_interval_per_host(self) -> None:
        times = iter([0.0, 0.4, 1.0, 5.0, 5.1])
        sleeps: list[float] = []
        limiter = RateLimiter(1.0, clock=lambda: next(times), sleep=sleeps.append)
        limiter.wait("a")  # first request: no wait
        limiter.wait("a")  # 0.4s later: waits 0.6s
        limiter.wait("a")  # well past the interval: no wait
        limiter.wait("b")  # other host: no wait
        assert sleeps == [pytest.approx(0.6)]


class TestPoliteClient:
    def test_sends_user_agent_and_decodes_json(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers["user-agent"])
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")
            return httpx.Response(200, json={"ok": True})

        polite = client(handler)
        assert polite.get_json("https://h.test/a") == {"ok": True}
        assert polite.get_json("https://h.test/b") == {"ok": True}
        polite.close()
        assert seen == ["PEJIP-test"] * 3  # robots.txt fetched once per origin

    def test_robots_disallow_blocks_the_fetch(self) -> None:
        polite = client(
            routes({"/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /private\n")})
        )
        with pytest.raises(RobotsDisallowedError):
            polite.get_json("https://h.test/private/jobs")

    @pytest.mark.parametrize(("status", "allowed"), [(404, True), (403, False), (401, False)])
    def test_robots_status_rules(self, status: int, allowed: bool) -> None:
        polite = client(
            routes({"/robots.txt": httpx.Response(status), "/jobs": httpx.Response(200, json=[])})
        )
        if allowed:
            assert polite.get_json("https://h.test/jobs") == []
        else:
            with pytest.raises(RobotsDisallowedError):
                polite.get_json("https://h.test/jobs")

    def test_robots_server_error_fails_the_source(self) -> None:
        sleeps: list[float] = []
        polite = client(routes({"/robots.txt": httpx.Response(500)}), sleeps)
        with pytest.raises(FetchError, match=r"robots.txt returned HTTP 500"):
            polite.get_json("https://h.test/jobs")
        assert sleeps == [1, 2]  # retried with exponential backoff

    def test_retries_429_then_succeeds(self) -> None:
        answers = iter([httpx.Response(429), httpx.Response(200, json={"n": 1})])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return next(answers)

        sleeps: list[float] = []
        assert client(handler, sleeps).get_json("https://h.test/jobs") == {"n": 1}
        assert sleeps == [1]

    def test_non_200_is_a_fetch_error(self) -> None:
        polite = client(routes({"/robots.txt": httpx.Response(404), "/jobs": httpx.Response(410)}))
        with pytest.raises(FetchError, match="HTTP 410"):
            polite.get_json("https://h.test/jobs")

    def test_network_errors_are_retried_then_reported(self) -> None:
        sleeps: list[float] = []
        polite = client(
            routes({"/robots.txt": httpx.Response(404), "/jobs": httpx.ConnectError("down")}),
            sleeps,
        )
        with pytest.raises(FetchError, match="ConnectError"):
            polite.get_json("https://h.test/jobs")
        assert sleeps == [1, 2]

    def test_invalid_json_is_a_fetch_error(self) -> None:
        polite = client(
            routes(
                {"/robots.txt": httpx.Response(404), "/jobs": httpx.Response(200, text="<html>")}
            )
        )
        with pytest.raises(FetchError, match="unexpected payload from"):
            polite.get_json("https://h.test/jobs")

    def test_default_limiter_is_built_from_config(self) -> None:
        polite = PoliteClient(FETCH)
        polite.close()


GREENHOUSE_JOBS = {
    "jobs": [
        {
            "id": 101,
            "title": " VP, Technology Operations ",
            "location": {"name": "San Francisco, CA"},
            "absolute_url": "https://boards.example/101",
            "first_published": "2026-10-01T09:00:00-07:00",
            "content": (
                "&lt;p&gt;Lead operations.&lt;/p&gt;&lt;p&gt;Pay $300,000 - $350,000.&lt;/p&gt;"
            ),
        },
        {
            "id": 102,
            "title": "Recruiter",
            "location": None,
            "updated_at": "not a date",
            "content": None,
        },
        {"id": 103, "title": "Analyst", "updated_at": 12345},
    ]
}


def test_greenhouse_adapter_maps_postings() -> None:
    gh = SourceConfig(
        adapter="greenhouse", company="Northwind", board="northwind", api_base="https://gh.test"
    )
    polite = client(
        routes(
            {
                "/robots.txt": httpx.Response(404),
                "/v1/boards/northwind/jobs": httpx.Response(200, json=GREENHOUSE_JOBS),
            }
        )
    )
    first, second, third = fetch_greenhouse(polite, gh)
    assert first.source_job_id == "northwind:101"
    assert first.title == "VP, Technology Operations"
    assert first.location == "San Francisco, CA"
    assert first.description == "Lead operations.\n\nPay $300,000 - $350,000."
    assert first.posted_at == datetime.fromisoformat("2026-10-01T09:00:00-07:00")
    assert first.compensation is not None
    assert first.compensation.maximum == 350000
    assert (second.location, second.posted_at, second.compensation) == ("", None, None)
    assert third.posted_at is None


def test_greenhouse_adapter_rejects_unexpected_payload() -> None:
    gh = SourceConfig(adapter="greenhouse", company="N", board="n", api_base="https://gh.test")
    polite = client(
        routes(
            {
                "/robots.txt": httpx.Response(404),
                "/v1/boards/n/jobs": httpx.Response(200, json={"oops": 1}),
            }
        )
    )
    with pytest.raises(FetchError, match="unexpected payload from Greenhouse board"):
        fetch_greenhouse(polite, gh)


LEVER_POSTINGS = [
    {
        "id": "abc",
        "text": "Head of Engineering Operations",
        "categories": {"location": "Remote - US"},
        "descriptionPlain": "Lead engineering operations.",
        "lists": [{"text": "What you will do", "content": "<li>Run planning</li>"}],
        "additionalPlain": "Equal opportunity employer.",
        "hostedUrl": "https://jobs.lever.test/abc",
        "createdAt": 1759600000000,
        "workplaceType": "remote",
        "salaryRange": {
            "min": 300000,
            "max": 360000,
            "currency": "USD",
            "interval": "per-year-salary",
        },
    },
    {
        "id": "def",
        "text": "VP Ops",
        "salaryRange": {"min": 50, "max": 80, "interval": "per-hour-wage"},
        "workplaceType": "unspecified",
    },
    {"id": "ghi", "text": "VP Ops", "salaryRange": {"currency": "USD"}, "workplaceType": "On-site"},
    {"id": "jkl", "text": "VP Ops", "salaryRange": {"max": 400000}},
    {"id": "mno", "text": "VP Ops", "salaryRange": "n/a"},
]


def test_lever_adapter_maps_postings() -> None:
    lv = SourceConfig(
        adapter="lever", company="Plaidish", board="plaidish", api_base="https://lv.test"
    )
    polite = client(
        routes(
            {
                "/robots.txt": httpx.Response(404),
                "/v0/postings/plaidish": httpx.Response(200, json=LEVER_POSTINGS),
            }
        )
    )
    first, hourly, no_numbers, max_only, junk = fetch_lever(polite, lv)
    assert first.source_job_id == "plaidish:abc"
    assert first.location == "Remote - US"
    assert first.description == (
        "Lead engineering operations.\n\nWhat you will do\n\n- Run planning\n\n"
        "Equal opportunity employer."
    )
    assert first.posted_at == datetime.fromtimestamp(1759600000, tz=UTC)
    assert first.work_model_hint == "REMOTE"
    assert first.compensation is not None
    assert (
        first.compensation.minimum,
        first.compensation.currency,
    ) == (300000, "USD")
    assert hourly.compensation is None
    assert hourly.work_model_hint is None
    assert hourly.posted_at is None
    assert no_numbers.compensation is None
    assert no_numbers.work_model_hint == "ONSITE"
    assert max_only.compensation is not None
    assert (
        max_only.compensation.minimum,
        max_only.compensation.maximum,
        max_only.compensation.currency,
    ) == (None, 400000, None)
    assert junk.compensation is None


def test_lever_adapter_rejects_unexpected_payload() -> None:
    lv = SourceConfig(adapter="lever", company="P", board="p", api_base="https://lv.test")
    polite = client(
        routes(
            {
                "/robots.txt": httpx.Response(404),
                "/v0/postings/p": httpx.Response(200, content=json.dumps({"x": 1})),
            }
        )
    )
    with pytest.raises(FetchError, match="unexpected payload from Lever board"):
        fetch_lever(polite, lv)


def test_adapters_default_to_public_hosts() -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, json={"jobs": []} if "boards" in request.url.host else [])

    polite = client(handler)
    fetch_greenhouse(polite, SourceConfig(adapter="greenhouse", company="A", board="a"))
    fetch_lever(polite, SourceConfig(adapter="lever", company="B", board="b"))
    assert set(hosts) == {"boards-api.greenhouse.io", "api.lever.co"}
