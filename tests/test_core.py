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


def test_error_body_forwards_real_code():
    assert _core.error_body(403, '{"error":"x","code":"algorithm_not_on_plan"}') == {
        "error": "x",
        "code": "algorithm_not_on_plan",
    }


def test_error_body_does_not_forward_null_code():
    assert _core.error_body(429, '{"error":"monthly_hard_cap","code":null}') == {
        "error": "monthly_hard_cap"
    }


def test_error_body_codeless_body_stays_error_only():
    assert _core.error_body(400, '{"error":"invalid_request"}') == {"error": "invalid_request"}


def test_should_degrade():
    assert _core.should_degrade(DetentTransportError("x")) is True
    assert _core.should_degrade(DetentAPIError(503, {"error": "x"})) is True
    assert _core.should_degrade(DetentAPIError(401, {"error": "x"})) is False


def test_parse_stats_maps_hard_cap_when_present():
    data = {
        "namespace": "api",
        "total": 100,
        "blocked": 4,
        "days": [],
        "month": {"month": "2026-07", "total": 100, "quota": 1000, "over_quota": False, "hard_cap": 5000},
    }
    assert _core.parse_stats(data).month.hard_cap == 5000


def test_parse_stats_defaults_hard_cap_to_none_when_absent():
    data = {
        "namespace": "api",
        "total": 100,
        "blocked": 4,
        "days": [],
        "month": {"month": "2026-07", "total": 100, "quota": 1000, "over_quota": False},
    }
    assert _core.parse_stats(data).month.hard_cap is None


def test_api_error_types_the_monthly_hard_cap():
    from detent.errors import DetentQuotaExceeded

    e = _core.api_error(429, {"error": "monthly_hard_cap"})
    assert isinstance(e, DetentQuotaExceeded)
    assert isinstance(e, DetentAPIError)
    assert e.status == 429
    # A hard cap must never fail open — it is a deliberate block.
    assert _core.should_degrade(e) is False
    # A 429 with any other body stays a generic DetentAPIError.
    other = _core.api_error(429, {"error": "slow down"})
    assert type(other) is DetentAPIError


def test_api_error_dispatches_public_surface_codes():
    from detent.errors import (
        DetentPaymentRequired,
        DetentAlgorithmNotOnPlan,
        DetentInvalidRequest,
        DetentUnknownAlgorithm,
        DetentInvalidDuration,
        DetentQuotaExceeded,
    )

    cases = {
        "payment_required": (402, DetentPaymentRequired),
        "monthly_hard_cap": (429, DetentQuotaExceeded),
        "algorithm_not_on_plan": (403, DetentAlgorithmNotOnPlan),
        "invalid_request": (400, DetentInvalidRequest),
        "unknown_algorithm": (400, DetentUnknownAlgorithm),
        "invalid_duration": (400, DetentInvalidDuration),
    }
    for code, (status, cls) in cases.items():
        e = _core.api_error(status, {"error": "human message", "code": code})
        assert type(e) is cls
        assert e.status == status
        assert e.code == code


def test_api_error_falls_back_to_error_string_for_codeless_gate():
    from detent.errors import DetentQuotaExceeded, DetentPaymentRequired

    assert isinstance(_core.api_error(429, {"error": "monthly_hard_cap"}), DetentQuotaExceeded)
    assert isinstance(_core.api_error(402, {"error": "payment_required"}), DetentPaymentRequired)


def test_api_error_defaults_for_unknown_code():
    from detent.errors import DetentAPIError

    e = _core.api_error(404, {"error": "not found", "code": "rule_not_found"})
    assert type(e) is DetentAPIError
    assert e.status == 404
    assert e.code == "rule_not_found"
