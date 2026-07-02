import httpx
import pytest

from detent import AcquireResult, AsyncDetent, DetentAPIError, DetentLeaseDenied, LimitResult


def make(handler, **kw):
    return AsyncDetent(
        api_key="rg_test_x",
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
        **kw,
    )


async def test_limit_parses():
    def handler(req):
        return httpx.Response(200, json={"allowed": True, "remaining": 9, "reset_ms": 5, "limit": 10})

    r = await make(handler).limit(namespace="api", key="u1")
    assert r == LimitResult(True, 9, 5, 10, False)


async def test_limit_fails_open_on_5xx():
    def handler(req):
        return httpx.Response(502, json={"error": "bad gw"})

    seen = []
    r = await make(handler, on_error=seen.append).limit(namespace="api", key="u1", limit=7)
    assert r == LimitResult(True, 0, 0, 7, True)
    assert len(seen) == 1


async def test_limit_raises_on_4xx():
    def handler(req):
        return httpx.Response(403, json={"error": "plan"})

    with pytest.raises(DetentAPIError) as ei:
        await make(handler).limit(namespace="api", key="u1")
    assert ei.value.status == 403


async def test_lease_releases_when_body_raises():
    seen = []

    def handler(req):
        seen.append(req.method)
        if req.method == "POST":
            return httpx.Response(
                200, json={"allowed": True, "lease_id": "LID", "active": 1, "limit": 5, "reset_ms": 0}
            )
        return httpx.Response(200, json={"released": True, "active": 0})

    rg = make(handler)
    with pytest.raises(RuntimeError, match="boom"):
        async with rg.lease(namespace="n", key="k"):
            raise RuntimeError("boom")
    assert seen == ["POST", "DELETE"]


async def test_lease_denied_raises():
    def handler(req):
        return httpx.Response(200, json={"allowed": False, "active": 5, "limit": 5, "reset_ms": 300})

    with pytest.raises(DetentLeaseDenied):
        async with make(handler).lease(namespace="n", key="k"):
            pass


async def test_acquire_returns_result():
    def handler(req):
        return httpx.Response(
            200, json={"allowed": True, "lease_id": "LID", "active": 1, "limit": 5, "reset_ms": 0}
        )

    acq = await make(handler).acquire(namespace="n", key="k")
    assert acq == AcquireResult(True, "LID", 1, 5, 0)
