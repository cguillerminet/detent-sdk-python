from detent import _core
from detent.errors import DetentAPIError, DetentTransportError
from detent.models import LimitResult


def test_limit_body_omits_none_optionals():
    assert _core.limit_body("api", "u1", None, None, 60000) == {
        "namespace": "api",
        "key": "u1",
        "window_ms": 60000,
    }


def test_limit_body_includes_given_optionals():
    assert _core.limit_body("api", "u1", "sliding_window", 10, 60000) == {
        "namespace": "api",
        "key": "u1",
        "algorithm": "sliding_window",
        "limit": 10,
        "window_ms": 60000,
    }


def test_paths_are_url_encoded():
    assert _core.stats_path("a/b") == "/v1/namespaces/a%2Fb/stats"
    assert _core.release_path("L/D") == "/v1/leases/L%2FD"


def test_parse_limit():
    r = _core.parse_limit({"allowed": True, "remaining": 9, "reset_ms": 5, "limit": 10})
    assert r == LimitResult(allowed=True, remaining=9, reset_ms=5, limit=10, degraded=False)


def test_degraded_limit_open_vs_closed():
    assert _core.degraded_limit("open", 10) == LimitResult(True, 0, 0, 10, True)
    assert _core.degraded_limit("closed", None) == LimitResult(False, 0, 0, 0, True)


def test_error_body_falls_back_on_non_json():
    assert _core.error_body(502, "<html>bad gateway</html>") == {"error": "HTTP 502"}
    assert _core.error_body(401, '{"error":"bad key"}') == {"error": "bad key"}


def test_should_degrade():
    assert _core.should_degrade(DetentTransportError("x")) is True
    assert _core.should_degrade(DetentAPIError(503, {"error": "x"})) is True
    assert _core.should_degrade(DetentAPIError(401, {"error": "x"})) is False
