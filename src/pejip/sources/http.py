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
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from pejip.config import FetchConfig


class FetchError(Exception):
    """A source could not be fetched; the run records it and carries on."""


class RobotsDisallowedError(FetchError):
    """``robots.txt`` does not allow this fetch."""

    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt disallows {url}")


class HTTPStatusError(FetchError):
    """The source answered with a status the client cannot use."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"{url} returned HTTP {status}")


class InvalidPayloadError(FetchError):
    """The source answered, but not with the data the adapter expects."""

    def __init__(self, origin: str, board: str | None = None) -> None:
        where = origin if board is None else f"{origin} board {board}"
        super().__init__(f"unexpected payload from {where}")


class TransportError(FetchError):
    """The request failed on every attempt before any response arrived."""

    def __init__(self, url: str, cause: Exception) -> None:
        super().__init__(f"{url} failed: {type(cause).__name__}")


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
            raise RobotsDisallowedError(url)
        response = self._get(url, params)
        if response.status_code != HTTPStatus.OK:
            raise HTTPStatusError(url, response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidPayloadError(url) from exc

    def _get(self, url: str, params: dict[str, str] | None) -> httpx.Response:
        host = urlsplit(url).netloc
        attempt = 0
        while True:
            self._limiter.wait(host)
            try:
                response = self._http.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt >= self._config.max_retries:
                    raise TransportError(url, exc) from exc
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
        status = response.status_code
        if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            parser.parse(["User-agent: *", "Disallow: /"])
        elif HTTPStatus.BAD_REQUEST <= status < HTTPStatus.INTERNAL_SERVER_ERROR:
            parser.parse([])
        elif status == HTTPStatus.OK:
            parser.parse(response.text.splitlines())
        else:
            raise HTTPStatusError(f"{origin}/robots.txt", status)
        return parser
