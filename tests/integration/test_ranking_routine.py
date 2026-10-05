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
from sqlalchemy import delete

from pejip import api, routine, workbench
from pejip.config import SearchConfig
from pejip.pipeline import Pipeline
from pejip.profile import CareerProfile
from pejip.ranking_api import RankingService
from pejip.store import Store, jobs
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
