"""HTTP-клиент для krisha.kz с rate-limit и ретраями."""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

DEFAULT_USER_AGENT = (
    "KRISHA_DWH/1.0 (data engineering, contact: dauren.aidarkhanov@gmail.com)"
)
BASE_URL = "https://krisha.kz"
LISTING_URL_TEMPLATE = f"{BASE_URL}/a/show/{{listing_id}}"


@dataclass
class FetchResult:
    listing_id: int
    url: str
    status: int
    html: str | None
    error: str | None = None


class Fetcher:
    """httpx.AsyncClient + семафор для ограничения RPS + tenacity для ретраев."""

    def __init__(
        self,
        user_agent: str | None = None,
        rate_limit_rps: float | None = None,
        timeout: float = 30.0,
        concurrency: int = 4,
    ) -> None:
        self.user_agent = user_agent or os.getenv("KRISHA_USER_AGENT", DEFAULT_USER_AGENT)
        rps = float(rate_limit_rps if rate_limit_rps is not None
                    else os.getenv("KRISHA_RATE_LIMIT_RPS", "2"))
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._timeout = timeout
        self._sem = asyncio.Semaphore(concurrency)
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            http2=True,
            timeout=self._timeout,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ru,en;q=0.7",
            },
            follow_redirects=True,
        )

    async def _throttle(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._last_call + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        await self._throttle()
        async with self._sem:
            return await client.get(url)

    async def fetch_listing(
        self, client: httpx.AsyncClient, listing_id: int
    ) -> FetchResult:
        url = LISTING_URL_TEMPLATE.format(listing_id=listing_id)
        last_err: str | None = None
        last_status: int = 0
        for attempt_n in range(1, 5):
            try:
                resp = await self._get(client, url)
                last_status = resp.status_code
                if resp.status_code == 200:
                    return FetchResult(listing_id, url, 200, resp.text)
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = f"http {resp.status_code}"
                    await asyncio.sleep(min(2 ** attempt_n, 30))
                    continue
                return FetchResult(
                    listing_id, url, resp.status_code, None,
                    error=f"http {resp.status_code}",
                )
            except (httpx.TransportError, httpx.HTTPError) as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                await asyncio.sleep(min(2 ** attempt_n, 30))
        return FetchResult(listing_id, url, last_status, None, error=last_err or "exhausted")

    async def fetch_many(self, listing_ids: Iterable[int]) -> list[FetchResult]:
        async with self._client() as client:
            tasks = [self.fetch_listing(client, lid) for lid in listing_ids]
            return await asyncio.gather(*tasks)


def fetch_text_sync(url: str, user_agent: str | None = None, timeout: float = 30.0) -> str:
    """Синхронный helper для одиночного запроса (sitemap-индекс)."""
    headers = {"User-Agent": user_agent or os.getenv("KRISHA_USER_AGENT", DEFAULT_USER_AGENT)}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
