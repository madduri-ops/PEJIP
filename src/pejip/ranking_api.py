"""The two endpoints the ranking routine uses (design doc 0015, ADR-0008).

The routine is a Claude Code session on Babu's plan, outside AWS. It reads the
roles waiting for analysis, does the model step, and posts the answers back:

- ``GET /api/ranking/queue``: the latest run's roles with no analysis of their
  current text, oldest first, at most ``ai.max_jobs_per_run``, plus the parts of
  the career profile the matching step reads (no name, email or pay).
- ``POST /api/ranking/analyses``: answers for those roles. Each one is checked
  exactly as the API path checks its own (schema, then grounding against the
  posting and the profile) before it is stored.

These routes skip Google sign-in at the load balancer and in the app. Instead
they need ``Authorization: Bearer <key>``, whose SHA-256 is kept in an encrypted
SSM parameter (``PEJIP_RANKING_KEY_PARAMETER``). The key itself never reaches AWS.
Without a configured hash, a database or a profile they answer 503.

Each account has its own key, and the key alone decides whose roles and profile
a request sees (design doc 0016): each account's routine runs on that person's
own Claude plan, with their own key.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pejip.accounts import DEFAULT_ACCOUNT_ID, open_store
from pejip.ai.client import AIError
from pejip.ai.prompts import load_prompt
from pejip.analysis import (
    EvidenceMatching,
    JobAnalysis,
    PostingText,
    analysis_input,
    ground_analysis,
    ground_matching,
)
from pejip.config import SearchConfig, Settings, account_ids, load_config
from pejip.profile import (
    CareerProfile,
    Evidence,
    Seniority,
    load_profile,
    load_profile_parameter,
    make_ssm_client,
    read_parameter,
)
from pejip.store import AnalysisRecord, Store

RANKING_PREFIX = "/api/ranking/"
PROMPT_IDS = ("JOB_ANALYSIS", "EVIDENCE_MATCHING")
MAX_RESULTS = 100
# The key hash, profile and config are read again after this long, so a rotated
# key or a new profile works without a deploy.
KEY_HASH_TTL_SECONDS = 300
# Largest answers body accepted, checked before it is read (design doc 0015).
# 40 answers of a few KB each fit many times over.
MAX_BODY_BYTES = 2_000_000
_BEARER = "bearer "
_MIN_KEY_CHARS = 32
_MAX_KEY_CHARS = 256
_NO_KEY, _NO_DATABASE, _NO_PROFILE = "no key", "no database", "no career profile"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MatchingProfile(_Strict):
    """The profile fields the matching step reads; everything else stays on AWS."""

    headline: str
    target_seniority: list[Seniority]
    career_direction: str
    evidence: list[Evidence]

    def career_profile(self) -> CareerProfile:
        return CareerProfile(name="Career profile", **self.model_dump())


class QueueRole(_Strict):
    job_id: int
    content_hash: str
    title: str
    company: str
    location: str
    description: str


class Queue(_Strict):
    profile: MatchingProfile
    prompts: dict[str, int]
    roles: list[QueueRole]


class Answer(_Strict):
    job_id: int
    content_hash: str = Field(max_length=64)
    analysis: dict[str, Any]
    matching: dict[str, Any]


class Submission(_Strict):
    model: str = Field(min_length=1, max_length=100)
    prompts: dict[str, int]
    results: list[Answer] = Field(max_length=MAX_RESULTS)


class Rejection(_Strict):
    job_id: int
    reason: str


class SubmissionResult(_Strict):
    accepted: int
    rejected: list[Rejection]


def prompt_versions() -> dict[str, int]:
    return {prompt_id: load_prompt(prompt_id).version for prompt_id in PROMPT_IDS}


def key_hash_from_ssm(region: str | None, *names: str) -> Callable[[], str | None]:
    """Reads the key's SHA-256 (hex) from SSM, or None when it is not stored yet.

    With several names, the first one stored wins (Babu's account falls back to
    the parameter from before accounts).
    """

    def read() -> str | None:
        client = make_ssm_client(region)
        for name in names:
            value = read_parameter(client, name)
            if value is not None:
                return value.strip().lower()
        return None

    return read


@dataclass
class RankingService:
    """What the endpoints need, built lazily so the app starts without any of it."""

    key_hash: Callable[[], str | None]
    store: Callable[[], Store | None]
    profile: Callable[[], CareerProfile | None]
    config: Callable[[], SearchConfig]
    clock: Callable[[], float] = time.monotonic
    _cache: dict[str, tuple[float, Any]] = field(default_factory=dict, repr=False)

    @classmethod
    def from_env(cls, env: Mapping[str, str], account: str | None = None) -> RankingService:
        """The service for ``account`` (``PEJIP_ACCOUNT``, else Babu's).

        ``PEJIP_RANKING_KEY_SHA256`` (a fixed hash, for tests and CI) and
        ``PEJIP_LEGACY_RANKING_KEY_PARAMETER`` (the parameter from before
        accounts) are Babu's alone.
        """
        settings = Settings.from_env(dict(env), account=account)
        owner = settings.account == DEFAULT_ACCOUNT_ID
        fixed = env.get("PEJIP_RANKING_KEY_SHA256", "").strip().lower() if owner else ""
        names = [settings.ranking_key_parameter or ""]
        if owner:
            names.append(env.get("PEJIP_LEGACY_RANKING_KEY_PARAMETER", ""))
        names = [name for name in names if name]
        if fixed:
            key_hash: Callable[[], str | None] = lambda: fixed  # noqa: E731
        elif names:
            key_hash = key_hash_from_ssm(settings.aws_region, *names)
        else:
            key_hash = lambda: None  # noqa: E731
        stores: list[Store] = []

        def store() -> Store | None:
            if "PEJIP_DATABASE_URL" not in env:
                return None
            if not stores:
                stores.append(open_store(settings))
            return stores[0]

        def profile() -> CareerProfile | None:
            if settings.profile_parameter:
                client = make_ssm_client(settings.aws_region)
                return load_profile_parameter(client, settings.profile_parameter)
            if settings.profile_path.exists():
                return load_profile(settings.profile_path)
            return None

        return cls(key_hash, store, profile, lambda: load_config(settings.config_path))

    def _cached(self, name: str, read: Callable[[], Any]) -> Any:
        now = self.clock()
        hit = self._cache.get(name)
        if hit is None or now - hit[0] > KEY_HASH_TTL_SECONDS:
            hit = self._cache[name] = (now, read())
        return hit[1]

    def expected_hash(self) -> str | None:
        value: str | None = self._cached("key_hash", self.key_hash)
        return value

    def current_profile(self) -> CareerProfile | None:
        value: CareerProfile | None = self._cached("profile", self.profile)
        return value

    def current_config(self) -> SearchConfig:
        value: SearchConfig = self._cached("config", self.config)
        return value


class NotConfiguredError(HTTPException):
    """A piece the endpoints need is missing (503)."""

    def __init__(self, what: str) -> None:
        super().__init__(status_code=503, detail=f"ranking is not configured: {what}")


class KeyRequiredError(HTTPException):
    """No key, or the wrong one (401). The two look the same from outside."""

    def __init__(self) -> None:
        super().__init__(status_code=401, detail="a ranking key is required")


class BodyTooLargeError(HTTPException):
    """An answers body without a length, or longer than ``MAX_BODY_BYTES`` (413)."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail=f"bodies are limited to {MAX_BODY_BYTES} bytes")


@dataclass
class RankingServices:
    """Every account's ranking service; a request's key picks the account (design doc 0016)."""

    by_account: Mapping[str, RankingService]

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> RankingServices:
        return cls({account: RankingService.from_env(env, account) for account in account_ids(env)})

    def for_key(self, authorization: str) -> RankingService:
        """The service whose key ``authorization`` carries, else raise.

        Every account's hash is compared, in constant time, so the answer takes
        as long whichever account (if any) the key belongs to.
        """
        expected = [(s, h) for s in self.by_account.values() if (h := s.expected_hash())]
        if not expected:
            raise NotConfiguredError(_NO_KEY)
        header = authorization
        key = header[len(_BEARER) :] if header.lower().startswith(_BEARER) else ""
        if not _MIN_KEY_CHARS <= len(key) <= _MAX_KEY_CHARS:
            raise KeyRequiredError
        given = hashlib.sha256(key.encode()).hexdigest()
        matches = [service for service, hashed in expected if hmac.compare_digest(given, hashed)]
        if not matches:
            raise KeyRequiredError
        return matches[0]


def screen(services: RankingServices, request: Request) -> HTTPException | None:
    """Checks made before a body is read, so a caller without the key can't make
    the app read a large one (the WAF lets these bodies past its 8 KB limit)."""
    try:
        services.for_key(request.headers.get("authorization", ""))
        if request.method == "POST":
            length = request.headers.get("content-length", "")
            if not length.isdigit() or int(length) > MAX_BODY_BYTES:
                raise BodyTooLargeError
    except HTTPException as exc:
        return exc
    return None


class StalePromptsError(HTTPException):
    """The answers were made with other prompt versions than the ones in use (409)."""

    def __init__(self, current: dict[str, int]) -> None:
        super().__init__(status_code=409, detail=f"answers must use the current prompts {current}")


def router(services: RankingServices) -> APIRouter:
    def account_service(request: Request) -> RankingService:
        return services.for_key(request.headers.get("authorization", ""))

    def ready(service: RankingService) -> tuple[Store, CareerProfile]:
        store = service.store()
        if store is None:
            raise NotConfiguredError(_NO_DATABASE)
        profile = service.current_profile()
        if profile is None:
            raise NotConfiguredError(_NO_PROFILE)
        return store, profile

    # Every route needs a key (checked first, as a dependency); the key's account
    # is the only one a route can touch.
    routes = APIRouter(prefix=RANKING_PREFIX.rstrip("/"), dependencies=[Depends(account_service)])

    @routes.get("/queue")
    def queue(request: Request) -> Queue:
        """Roles from the latest run that still need an analysis, oldest first."""
        service = account_service(request)
        store, profile = ready(service)
        run = store.latest_run()
        waiting: list[dict[str, Any]] = []
        # A role reported by two sources in one run is queued once.
        seen = run["summary"].get("seen", []) if run else []
        for job_id in dict.fromkeys(job_id for job_id, _ in seen):
            job = store.find_job(job_id)
            if job is not None and store.needs_analysis(job):
                waiting.append(job)
        waiting.sort(key=lambda job: job["first_seen_at"])
        limit = service.current_config().ai.max_jobs_per_run
        return Queue(
            profile=MatchingProfile(
                headline=profile.headline,
                target_seniority=profile.target_seniority,
                career_direction=profile.career_direction,
                evidence=profile.evidence,
            ),
            prompts=prompt_versions(),
            roles=[
                QueueRole(
                    job_id=job["id"],
                    content_hash=job["content_hash"],
                    title=job["title"],
                    company=job["company"],
                    location=job["location"],
                    description=job["description"],
                )
                for job in waiting[:limit]
            ],
        )

    @routes.post("/analyses")
    def analyses(submission: Submission, request: Request) -> SubmissionResult:
        """Check each answer the way the API path does, and store the ones that pass."""
        service = account_service(request)
        store, profile = ready(service)
        current = prompt_versions()
        if submission.prompts != current:
            raise StalePromptsError(current)
        accepted, rejected = 0, []
        for answer in submission.results:
            reason = _store_answer(store, profile, submission, answer)
            if reason is None:
                accepted += 1
            else:
                rejected.append(Rejection(job_id=answer.job_id, reason=reason))
        return SubmissionResult(accepted=accepted, rejected=rejected)

    return routes


def _store_answer(
    store: Store, profile: CareerProfile, submission: Submission, answer: Answer
) -> str | None:
    """Store one answer, or say why it was refused."""
    job = store.find_job(answer.job_id)
    if job is None:
        return "no such role"
    if job["content_hash"] != answer.content_hash:
        return "the posting has changed since it was queued"
    try:
        analysis = JobAnalysis.model_validate(answer.analysis)
        matching = EvidenceMatching.model_validate(answer.matching)
        analysis, dropped = ground_analysis(analysis, analysis_input(PostingText.from_job(job)))
    except ValidationError:
        return "the answer does not match the schema"
    except AIError as exc:
        return str(exc)
    matching = ground_matching(matching, analysis, profile)
    payload = {
        "analysis": analysis.model_dump(),
        "matching": matching.model_dump(),
        "dropped_requirements": dropped,
    }
    provenance = {"ranker": "routine", "model": submission.model, "prompts": submission.prompts}
    store.add_analysis(
        AnalysisRecord(
            job["id"], job["content_hash"], "OK", payload, None, provenance, datetime.now(UTC)
        )
    )
    return None
