"""Shared rate limiter and polite HTTP client for every job source (policy section 11).

Every source request goes through :class:`PoliteClient`, which

* waits for the per-host budget in :class:`RateLimiter`,
* honours ``robots.txt`` for the host,
* sends a clear user agent, and
* backs off and retries on 429 and 5xx responses.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from pejip.config import FetchConfig


class FetchError(Exception):
    """A source could not be fetched; the run records it and carries on."""


class RobotsDisallowed(FetchError):
    """``robots.txt`` does not allow this fetch."""


class RateLimiter:
    """Enforces a minimum interval between requests to the same host."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = self._clock()
            last = self._last.get(host)
            if last is not None:
                remaining = self._min_interval - (now - last)
                if remaining > 0:
                    self._sleep(remaining)
                    now = self._clock()
            self._last[host] = now


class PoliteClient:
    """The only HTTP path source adapters may use."""

    RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        config: FetchConfig,
        limiter: RateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._limiter = limiter or RateLimiter(config.min_interval_seconds)
        self._sleep = sleep
        self._robots: dict[str, RobotFileParser] = {}
        self._http = httpx.Client(
            headers={"User-Agent": config.user_agent},
            timeout=config.timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._http.close()

    def get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        """GET ``url`` politely and decode its JSON body."""
        if not self._allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        response = self._get(url, params)
        if response.status_code != 200:
            raise FetchError(f"{url} returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise FetchError(f"{url} returned invalid JSON") from exc

    def _get(self, url: str, params: dict[str, str] | None) -> httpx.Response:
        host = urlsplit(url).netloc
        attempt = 0
        while True:
            self._limiter.wait(host)
            try:
                response = self._http.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    raise FetchError(f"{url} failed: {type(exc).__name__}") from exc
            else:
                if response.status_code not in self.RETRY_STATUSES:
                    return response
                if attempt >= self._config.max_retries:
                    return response
            self._sleep(self._config.backoff_base_seconds * (2**attempt))
            attempt += 1

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = self._load_robots(origin)
            self._robots[origin] = parser
        return parser.can_fetch(self._config.user_agent, url)

    def _load_robots(self, origin: str) -> RobotFileParser:
        # Same status rules as urllib.robotparser.RobotFileParser.read().
        parser = RobotFileParser()
        response = self._get(f"{origin}/robots.txt", None)
        if response.status_code in (401, 403):
            parser.parse(["User-agent: *", "Disallow: /"])
        elif 400 <= response.status_code < 500:
            parser.parse([])
        elif response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            raise FetchError(f"{origin}/robots.txt returned HTTP {response.status_code}")
        return parser
