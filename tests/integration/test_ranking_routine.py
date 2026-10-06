"""The ranking routine end to end (design doc 0015): run, fetch, answer, submit, digest.

Stub job boards, the real API in process, the routine's command line talking to it
through a forwarding transport, and synthetic answers. No model is called.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from pejip import api, ranking_api, routine, workbench
from pejip.config import SearchConfig
from pejip.pipeline import Pipeline
from pejip.profile import CareerProfile
from pejip.ranking_api import RankingService, RankingServices
from pejip.store import Store, jobs, recommendations, runs
from tests import factories as f
from tests.conftest import NOW, FakeMessages
from tests.integration.test_pipeline import Boards, build

KEY = "routine-key-" + "x" * 30
KEY_HASH = hashlib.sha256(KEY.encode()).hexdigest()
AUTH = {"Authorization": f"Bearer {KEY}"}


def routine_run(config: SearchConfig, profile: CareerProfile, store: Store) -> Pipeline:
    pipeline = build(config, profile, store, Boards(), FakeMessages())
    pipeline.ai = None
    pipeline.routine = True
    pipeline.unranked_reason = "the ranking routine has not analysed it yet"
    return pipeline


def service(
    store: Store | None, profile: CareerProfile | None, config: SearchConfig, **kw: Any
) -> RankingService:
    return RankingService(
        key_hash=kw.get("key_hash", lambda: KEY_HASH),
        store=lambda: store,
        profile=lambda: profile,
        config=lambda: config,
    )


@pytest.fixture
def ran(config: SearchConfig, profile: CareerProfile, store: Store) -> Pipeline:
    pipeline = routine_run(config, profile, store)
    digest = pipeline.run()
    assert digest.status == "PARTIAL"
    assert all(item.recommendation is None for item in digest.items)
    assert digest.notes == []  # waiting for the routine is expected, not news
    return pipeline


@pytest.fixture
def client(ran: Pipeline, profile: CareerProfile, config: SearchConfig) -> TestClient:
    return TestClient(api.create_app(env={}, ranking=service(ran.store, profile, config)))


@pytest.fixture
def connected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Point the routine's command line at the in-process app."""

    def forward(request: httpx.Request) -> httpx.Response:
        reply = client.request(
            request.method, request.url.path, headers=request.headers, content=request.content
        )
        return httpx.Response(reply.status_code, content=reply.content, headers=reply.headers)

    monkeypatch.setattr(routine, "TRANSPORT", httpx.MockTransport(forward))
    monkeypatch.setenv("PEJIP_RANKING_URL", "https://pejip.test/")
    monkeypatch.setenv("PEJIP_RANKING_KEY", KEY)
    return client


def answer_all(work: Path) -> None:
    analysis = f.analysis(
        [
            f.requirement("R1", quote="Lead technology operations"),
            f.requirement("R2", category="CAPABILITY", quote="Own portfolio governance"),
        ]
    )
    matching = f.matching([f.match("R1"), f.match("R2", evidence=["E4"])])
    for role in workbench.load_roles(work):
        folder = work / workbench.ROLES_DIR / role.id
        (folder / workbench.ANALYSIS_FILE).write_text(json.dumps(analysis))
        (folder / workbench.MATCHING_FILE).write_text(json.dumps(matching))


def test_the_routine_ranks_the_runs_new_roles(
    ran: Pipeline, connected: TestClient, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = tmp_path / "work"
    assert routine.main(["--work", str(work), "fetch"]) == 0
    assert "Fetched 2 roles" in capsys.readouterr().out
    profile = workbench.load_profile(work)
    assert profile.name == "Career profile"  # the real name and email stay on AWS
    assert profile.email is None
    assert profile.compensation.minimum is None

    answer_all(work)
    assert routine.main(["--work", str(work), "submit", "--model", "test-model"]) == 0
    assert "PEJIP accepted 2 of 2 answers." in capsys.readouterr().out
    assert ran.store.analyses_since(NOW, "routine") == 2

    digest = ran.digest_from(ran.store.latest_run() or {})
    assert digest.status == "SUCCESS"
    assert all(item.recommendation is not None for item in digest.items)
    queue = connected.get("/api/ranking/queue", headers=AUTH).json()
    assert queue["roles"] == []


def test_queue_is_oldest_first_and_capped(
    ran: Pipeline, profile: CareerProfile, config: SearchConfig
) -> None:
    capped = config.model_copy(update={"ai": config.ai.model_copy(update={"max_jobs_per_run": 1})})
    app = api.create_app(env={}, ranking=service(ran.store, profile, capped))
    roles = TestClient(app).get("/api/ranking/queue", headers=AUTH).json()["roles"]
    assert len(roles) == 1
    first = min(ran.store.latest_run()["summary"]["seen"])  # type: ignore[index]
    assert roles[0]["job_id"] == first[0]


def test_queue_skips_roles_purged_since_the_run(client: TestClient, ran: Pipeline) -> None:
    with ran.store.engine.begin() as conn:
        conn.execute(delete(jobs))
    assert client.get("/api/ranking/queue", headers=AUTH).json()["roles"] == []
    assert ran.digest_from(ran.store.latest_run() or {}).items == []


def test_queue_is_empty_before_the_first_run(
    store: Store, profile: CareerProfile, config: SearchConfig
) -> None:
    app = api.create_app(env={}, ranking=service(store, profile, config))
    assert TestClient(app).get("/api/ranking/queue", headers=AUTH).json()["roles"] == []


def test_each_key_sees_only_its_own_accounts_roles(
    ran: Pipeline, tmp_path: Path, profile: CareerProfile, config: SearchConfig
) -> None:
    # Babu's key queues Babu's roles; the friend's key, on the same site, sees only
    # the friend's empty database and can't post answers for Babu's roles.
    friend_key = "friend-key-" + "z" * 30
    friend_store = Store(f"sqlite:///{tmp_path / 'friend.db'}")
    friend = service(
        friend_store,
        profile,
        config,
        key_hash=lambda: hashlib.sha256(friend_key.encode()).hexdigest(),
    )
    ranking = RankingServices({"babu": service(ran.store, profile, config), "friend": friend})
    client = TestClient(api.create_app(env={}, ranking=ranking))
    friend_auth = {"Authorization": f"Bearer {friend_key}"}

    assert client.get("/api/ranking/queue", headers=AUTH).json()["roles"]
    assert client.get("/api/ranking/queue", headers=friend_auth).json()["roles"] == []
    babu_job = min(ran.store.latest_run()["summary"]["seen"])[0]  # type: ignore[index]
    answer = {"job_id": babu_job, "content_hash": "x", "analysis": {}, "matching": {}}
    body = {"model": "m", "prompts": ranking_api.prompt_versions(), "results": [answer]}
    result = client.post("/api/ranking/analyses", headers=friend_auth, json=body).json()
    assert result == {"accepted": 0, "rejected": [{"job_id": babu_job, "reason": "no such role"}]}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer short"},
        {"Authorization": "Bearer " + "y" * 40},
        {"Authorization": KEY},
    ],
)
def test_the_key_is_required(client: TestClient, headers: dict[str, str]) -> None:
    for response in (
        client.get("/api/ranking/queue", headers=headers),
        client.post("/api/ranking/analyses", headers=headers, json={}),
    ):
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"


def test_unconfigured_pieces_answer_503(
    store: Store, profile: CareerProfile, config: SearchConfig
) -> None:
    for ranking in (
        service(store, profile, config, key_hash=lambda: None),
        service(None, profile, config),
        service(store, None, config),
    ):
        app = api.create_app(env={}, ranking=ranking)
        assert TestClient(app).get("/api/ranking/queue", headers=AUTH).status_code == 503


def test_other_routes_still_need_google_sign_in(client: TestClient) -> None:
    assert client.get("/", headers=AUTH).status_code == 503  # sign-in not configured here


def _submit(client: TestClient, results: list[dict[str, Any]], **body: Any) -> Any:
    prompts = client.get("/api/ranking/queue", headers=AUTH).json()["prompts"]
    payload = {"model": "m", "prompts": prompts, "results": results, **body}
    return client.post("/api/ranking/analyses", headers=AUTH, json=payload)


def test_bad_answers_are_refused_one_by_one(client: TestClient, ran: Pipeline) -> None:
    roles = client.get("/api/ranking/queue", headers=AUTH).json()["roles"]
    good = {"analysis": f.analysis(), "matching": f.matching()}
    ungrounded = f.analysis([f.requirement(quote="Not in the posting")])
    results = [
        {"job_id": 999, "content_hash": "h", **good},
        {"job_id": roles[0]["job_id"], "content_hash": "stale", **good},
        {
            "job_id": roles[0]["job_id"],
            "content_hash": roles[0]["content_hash"],
            "analysis": {"x": 1},
            "matching": f.matching(),
        },
        {
            "job_id": roles[1]["job_id"],
            "content_hash": roles[1]["content_hash"],
            "analysis": ungrounded,
            "matching": f.matching(),
        },
    ]
    reply = _submit(client, results)
    assert reply.status_code == 200
    body = reply.json()
    assert body["accepted"] == 0
    assert [r["reason"] for r in body["rejected"]] == [
        "no such role",
        "the posting has changed since it was queued",
        "the answer does not match the schema",
        "most requirements were not grounded in the posting",
    ]
    assert ran.store.analyses_since(NOW, "routine") == 0


def test_answers_from_old_prompts_are_refused(client: TestClient) -> None:
    reply = _submit(client, [], prompts={"JOB_ANALYSIS": 0, "EVIDENCE_MATCHING": 0})
    assert reply.status_code == 409


def test_too_many_answers_are_refused(client: TestClient) -> None:
    answer = {"job_id": 1, "content_hash": "h", "analysis": {}, "matching": {}}
    assert _submit(client, [answer] * 101).status_code == 422


@pytest.mark.usefixtures("connected")
def test_routine_reports_unanswered_and_refused_roles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = tmp_path / "work"
    routine.main(["--work", str(work), "fetch"])
    answer_all(work)
    first, second = workbench.load_roles(work)
    (work / workbench.ROLES_DIR / second.id / workbench.MATCHING_FILE).unlink()
    role_file = work / workbench.ROLES_DIR / first.id / workbench.ROLE_FILE
    data = json.loads(role_file.read_text())
    role_file.write_text(json.dumps({**data, "content_hash": "stale"}))
    capsys.readouterr()
    assert routine.main(["--work", str(work), "submit", "--model", "m"]) == 0
    out = capsys.readouterr().out
    assert "PEJIP accepted 0 of 1 answers." in out
    assert f"Refused role {first.id}: the posting has changed" in out
    assert f"Not answered (offered again next time): {second.id}" in out


@pytest.mark.usefixtures("connected")
def test_routine_needs_its_settings_and_a_willing_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    work = str(tmp_path / "work")
    monkeypatch.setenv("PEJIP_RANKING_KEY", "y" * 40)
    assert routine.main(["--work", work, "fetch"]) == 2
    assert "PEJIP did not accept the request" in capsys.readouterr().err
    monkeypatch.delenv("PEJIP_RANKING_KEY")
    assert routine.main(["--work", work, "fetch"]) == 2
    assert "PEJIP_RANKING_KEY is not set" in capsys.readouterr().err


def _set_summary(store: Store, **changes: Any) -> None:
    run = store.latest_run()
    assert run is not None
    with store.engine.begin() as conn:
        conn.execute(
            update(runs).where(runs.c.id == run["id"]).values(summary={**run["summary"], **changes})
        )


def test_a_role_reported_twice_is_queued_and_listed_once(client: TestClient, ran: Pipeline) -> None:
    seen = ran.store.latest_run()["summary"]["seen"]  # type: ignore[index]
    _set_summary(ran.store, seen=seen + seen)
    roles = client.get("/api/ranking/queue", headers=AUTH).json()["roles"]
    assert len(roles) == len(seen)
    assert len(ran.digest_from(ran.store.latest_run() or {}).items) == len(seen)


def test_runs_from_before_the_routine_still_make_a_digest(ran: Pipeline) -> None:
    run = ran.store.latest_run() or {}
    old = {**run, "summary": {"candidates": 0}}
    digest = ran.digest_from(old)
    assert digest.items == []
    assert digest.notes == []


def _recommendation_rows(store: Store) -> int:
    with store.engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(recommendations)).scalar_one())


@pytest.mark.usefixtures("connected")
def test_the_digest_adds_no_repeat_recommendations(ran: Pipeline, tmp_path: Path) -> None:
    work = tmp_path / "work"
    routine.main(["--work", str(work), "fetch"])
    answer_all(work)
    routine.main(["--work", str(work), "submit", "--model", "m"])
    run = ran.store.latest_run() or {}
    ran.digest_from(run)
    rows = _recommendation_rows(ran.store)
    assert rows == 2
    ran.digest_from(run)
    assert _recommendation_rows(ran.store) == rows


def test_large_or_unmeasured_bodies_are_refused_before_reading(client: TestClient) -> None:
    url = "/api/ranking/analyses"
    too_big = {**AUTH, "content-length": str(ranking_api.MAX_BODY_BYTES + 1)}
    assert client.post(url, headers=too_big, content=b"{}").status_code == 413

    def chunks() -> Any:
        yield b"{}"

    assert client.post(url, headers=AUTH, content=chunks()).status_code == 413
    # Without the key the body is never looked at.
    assert client.post(url, headers={"content-length": "999999999"}, content=b"").status_code == 401


def test_the_profile_and_config_are_read_once_per_interval(
    store: Store, profile: CareerProfile, config: SearchConfig
) -> None:
    calls = {"profile": 0, "config": 0}

    def count_profile() -> CareerProfile:
        calls["profile"] += 1
        return profile

    def count_config() -> SearchConfig:
        calls["config"] += 1
        return config

    ranking = RankingService(lambda: KEY_HASH, lambda: store, count_profile, count_config)
    app = TestClient(api.create_app(env={}, ranking=ranking))
    for _ in range(3):
        assert app.get("/api/ranking/queue", headers=AUTH).status_code == 200
    assert calls == {"profile": 1, "config": 1}
