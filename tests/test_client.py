import json

import httpx
import pytest

from detent import (
    AcquireResult,
    Detent,
    DetentAPIError,
    DetentLeaseDenied,
    LimitResult,
)


def make(handler, **kw):
    return Detent(
        api_key="dt_test_x",
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
        **kw,
    )


def test_limit_sends_bearer_and_body_and_parses():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == "Bearer dt_test_x"
        assert req.url.path == "/v1/limit"
        assert json.loads(req.content) == {"namespace": "api", "key": "u1", "window_ms": 60000}
        return httpx.Response(
            200, json={"allowed": True, "remaining": 9, "reset_ms": 5, "limit": 10}
        )

    r = make(handler).limit(namespace="api", key="u1", window_ms=60000)
    assert r == LimitResult(allowed=True, remaining=9, reset_ms=5, limit=10, degraded=False)


def test_limit_200_denial_is_not_an_error():
    def handler(req):
        return httpx.Response(
            200, json={"allowed": False, "remaining": 0, "reset_ms": 1, "limit": 10}
        )

    r = make(handler).limit(namespace="api", key="u1")
    assert r.allowed is False and r.degraded is False


def test_limit_fails_open_on_transport_error():
    def handler(req):
        raise httpx.ConnectError("refused")

    seen = []
    r = make(handler, fail_mode="open", on_error=seen.append).limit(
        namespace="api", key="u1", limit=10
    )
    assert r == LimitResult(True, 0, 0, 10, True)
    assert len(seen) == 1


def test_limit_fails_closed_on_5xx():
    def handler(req):
        return httpx.Response(503, json={"error": "down"})

    r = make(handler, fail_mode="closed").limit(namespace="api", key="u1")
    assert r.allowed is False and r.degraded is True


def test_limit_raises_on_4xx():
    def handler(req):
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(DetentAPIError) as ei:
        make(handler).limit(namespace="api", key="u1")
    assert ei.value.status == 401 and ei.value.body == {"error": "bad key"}


def test_acquire_and_release_paths():
    seen = []

    def handler(req):
        seen.append(f"{req.method} {req.url.path}")
        if req.method == "POST":
            return httpx.Response(
                200,
                json={"allowed": True, "lease_id": "LID", "active": 1, "limit": 5, "reset_ms": 0},
            )
        return httpx.Response(200, json={"released": True, "active": 0})

    rg = make(handler)
    acq = rg.acquire(namespace="n", key="k")
    assert acq == AcquireResult(True, "LID", 1, 5, 0)
    rel = rg.release("LID")
    assert (rel.released, rel.active) == (True, 0)
    assert seen == ["POST /v1/leases", "DELETE /v1/leases/LID"]


def test_lease_releases_even_when_body_raises():
    seen = []

    def handler(req):
        seen.append(req.method)
        if req.method == "POST":
            return httpx.Response(
                200,
                json={"allowed": True, "lease_id": "LID", "active": 1, "limit": 5, "reset_ms": 0},
            )
        return httpx.Response(200, json={"released": True, "active": 0})

    rg = make(handler)
    with pytest.raises(RuntimeError, match="boom"):
        with rg.lease(namespace="n", key="k"):
            raise RuntimeError("boom")
    assert seen == ["POST", "DELETE"]


def test_lease_denied_raises_and_skips_release():
    seen = []

    def handler(req):
        seen.append(req.method)
        return httpx.Response(
            200, json={"allowed": False, "active": 5, "limit": 5, "reset_ms": 300}
        )

    rg = make(handler)
    with pytest.raises(DetentLeaseDenied):
        with rg.lease(namespace="n", key="k"):
            pass
    assert seen == ["POST"]


def test_get_stats_maps_response():
    def handler(req):
        assert req.url.path == "/v1/namespaces/api/stats"
        return httpx.Response(
            200,
            json={
                "namespace": "api",
                "total": 100,
                "blocked": 4,
                "days": [{"day": "2026-07-01", "total": 60, "blocked": 2}],
                "month": {"month": "2026-07", "total": 100, "quota": 1000, "over_quota": False},
            },
        )

    s = make(handler).get_stats(namespace="api")
    assert s.total == 100 and s.month.over_quota is False and s.days[0].day == "2026-07-01"
