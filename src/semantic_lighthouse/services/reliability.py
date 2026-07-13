from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
import time
from typing import Any

import httpx


RETRYABLE_STATUS_CODES = {408, 429}


def post_with_retry(
    url: str,
    *,
    json: Any,
    headers: dict[str, str],
    timeout: float,
    max_attempts: int,
    backoff_seconds: float,
) -> httpx.Response:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must not be negative")

    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.post(
                url,
                json=json,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = (
                status_code in RETRYABLE_STATUS_CODES or status_code >= 500
            )
            if not retryable or attempt == max_attempts:
                raise
        except httpx.TransportError:
            if attempt == max_attempts:
                raise

        if backoff_seconds:
            time.sleep(backoff_seconds * attempt)

    raise RuntimeError("provider retry loop exhausted without a terminal result")


class AdmissionRejected(RuntimeError):
    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        retry_after_seconds: int = 1,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds


@dataclass
class AdmissionLease:
    _semaphore: asyncio.Semaphore
    _released: bool = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._semaphore.release()


class RagAdmissionController:
    def __init__(
        self,
        *,
        max_concurrency: int,
        max_queue: int,
        queue_timeout_seconds: float,
        rate_limit_requests: int,
        rate_limit_window_seconds: float,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if max_queue < 0:
            raise ValueError("max_queue must not be negative")
        if queue_timeout_seconds <= 0:
            raise ValueError("queue_timeout_seconds must be positive")
        if rate_limit_requests < 1:
            raise ValueError("rate_limit_requests must be at least 1")
        if rate_limit_window_seconds <= 0:
            raise ValueError("rate_limit_window_seconds must be positive")

        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_queue = max_queue
        self._queue_timeout_seconds = queue_timeout_seconds
        self._rate_limit_requests = rate_limit_requests
        self._rate_limit_window_seconds = rate_limit_window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._waiting = 0
        self._lock = asyncio.Lock()

    async def acquire(self, rate_limit_key: str) -> AdmissionLease:
        queued = False
        async with self._lock:
            self._enforce_rate_limit(rate_limit_key)
            if not self._semaphore.locked():
                await self._semaphore.acquire()
                self._record_admission(rate_limit_key)
                return AdmissionLease(self._semaphore)
            if self._waiting >= self._max_queue:
                raise AdmissionRejected(503, "RAG request queue is full")
            self._waiting += 1
            queued = True

        acquired = False
        recorded = False
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._queue_timeout_seconds,
            )
            acquired = True
            async with self._lock:
                self._enforce_rate_limit(rate_limit_key)
                self._record_admission(rate_limit_key)
                recorded = True
            return AdmissionLease(self._semaphore)
        except TimeoutError as exc:
            raise AdmissionRejected(503, "RAG request queue wait timed out") from exc
        finally:
            if queued:
                async with self._lock:
                    self._waiting -= 1
            if acquired and not recorded:
                self._semaphore.release()

    def _enforce_rate_limit(self, key: str) -> None:
        now = time.monotonic()
        events = self._events[key]
        cutoff = now - self._rate_limit_window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self._rate_limit_requests:
            raise AdmissionRejected(429, "RAG request rate limit exceeded")

    def _record_admission(self, key: str) -> None:
        self._events[key].append(time.monotonic())
