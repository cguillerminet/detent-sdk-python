from detent.errors import (
    DetentAPIError,
    DetentError,
    DetentLeaseDenied,
    DetentTransportError,
)
from detent.models import AcquireResult, LimitResult


def test_limit_result_fields():
    r = LimitResult(allowed=True, remaining=9, reset_ms=100, limit=10, degraded=False)
    assert (r.allowed, r.remaining, r.reset_ms, r.limit, r.degraded) == (True, 9, 100, 10, False)


def test_api_error_carries_status_and_body():
    e = DetentAPIError(401, {"error": "bad key"})
    assert isinstance(e, DetentError)
    assert e.status == 401 and e.body == {"error": "bad key"}


def test_transport_error_is_detent_error():
    assert isinstance(DetentTransportError("boom"), DetentError)


def test_lease_denied_carries_result():
    acq = AcquireResult(allowed=False, lease_id=None, active=5, limit=5, reset_ms=300)
    e = DetentLeaseDenied(acq)
    assert isinstance(e, DetentError) and e.result.active == 5
