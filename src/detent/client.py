from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any

import httpx

from . import _core
from ._config import DEFAULT_BASE_URL, DEFAULT_TIMEOUT, FailMode
from .errors import DetentError, DetentLeaseDenied, DetentTransportError
from .models import AcquireResult, Algorithm, LimitResult, ReleaseResult, StatsResult


class Detent:
    """Synchronous Detent client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        fail_mode: FailMode = "open",
        on_error: Callable[[DetentError], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.fail_mode: FailMode = fail_mode
        self.on_error = on_error
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            resp = self._client.request(method, path, json=body)
        except httpx.TransportError as exc:
            raise DetentTransportError("Detent request failed") from exc
        if resp.is_success:
            data: dict[str, Any] = resp.json()
            return data
        raise _core.api_error(resp.status_code, _core.error_body(resp.status_code, resp.text))

    def limit(
        self,
        *,
        namespace: str,
        key: str,
        algorithm: Algorithm | None = None,
        limit: int | None = None,
        window_ms: int | None = None,
    ) -> LimitResult:
        body = _core.limit_body(namespace, key, algorithm, limit, window_ms)
        try:
            data = self._request("POST", _core.LIMIT_PATH, body)
        except DetentError as err:
            if _core.should_degrade(err):
                if self.on_error is not None:
                    self.on_error(err)
                return _core.degraded_limit(self.fail_mode, limit)
            raise
        return _core.parse_limit(data)

    def acquire(
        self,
        *,
        namespace: str,
        key: str,
        limit: int | None = None,
        window_ms: int | None = None,
    ) -> AcquireResult:
        data = self._request(
            "POST", _core.LEASES_PATH, _core.acquire_body(namespace, key, limit, window_ms)
        )
        return _core.parse_acquire(data)

    def release(self, lease_id: str) -> ReleaseResult:
        return _core.parse_release(self._request("DELETE", _core.release_path(lease_id)))

    @contextmanager
    def lease(
        self,
        *,
        namespace: str,
        key: str,
        limit: int | None = None,
        window_ms: int | None = None,
    ) -> Iterator[AcquireResult]:
        acq = self.acquire(namespace=namespace, key=key, limit=limit, window_ms=window_ms)
        if not acq.allowed:
            raise DetentLeaseDenied(acq)
        try:
            yield acq
        except BaseException:
            if acq.lease_id is not None:
                try:
                    self.release(acq.lease_id)
                except Exception:
                    pass  # never mask the in-body exception
            raise
        else:
            if acq.lease_id is not None:
                self.release(acq.lease_id)

    def get_stats(self, *, namespace: str) -> StatsResult:
        return _core.parse_stats(self._request("GET", _core.stats_path(namespace)))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Detent:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
