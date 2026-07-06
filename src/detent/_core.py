from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from ._config import FailMode
from .errors import (
    DetentAPIError,
    DetentAlgorithmNotOnPlan,
    DetentError,
    DetentInvalidDuration,
    DetentInvalidRequest,
    DetentPaymentRequired,
    DetentQuotaExceeded,
    DetentTransportError,
    DetentUnknownAlgorithm,
)
from .models import (
    AcquireResult,
    DayStat,
    LimitResult,
    MonthSummary,
    ReleaseResult,
    StatsResult,
)

LIMIT_PATH = "/v1/limit"
LEASES_PATH = "/v1/leases"


def limit_body(
    namespace: str,
    key: str,
    algorithm: str | None,
    limit: int | None,
    window_ms: int | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"namespace": namespace, "key": key}
    if algorithm is not None:
        body["algorithm"] = algorithm
    if limit is not None:
        body["limit"] = limit
    if window_ms is not None:
        body["window_ms"] = window_ms
    return body


def acquire_body(
    namespace: str, key: str, limit: int | None, window_ms: int | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"namespace": namespace, "key": key}
    if limit is not None:
        body["limit"] = limit
    if window_ms is not None:
        body["window_ms"] = window_ms
    return body


def stats_path(namespace: str) -> str:
    return f"/v1/namespaces/{quote(namespace, safe='')}/stats"


def release_path(lease_id: str) -> str:
    return f"/v1/leases/{quote(lease_id, safe='')}"


def parse_limit(data: dict[str, Any]) -> LimitResult:
    return LimitResult(
        allowed=data["allowed"],
        remaining=data["remaining"],
        reset_ms=data["reset_ms"],
        limit=data["limit"],
        degraded=False,
    )


def degraded_limit(fail_mode: FailMode, limit: int | None) -> LimitResult:
    return LimitResult(
        allowed=(fail_mode == "open"),
        remaining=0,
        reset_ms=0,
        limit=limit or 0,
        degraded=True,
    )


def parse_acquire(data: dict[str, Any]) -> AcquireResult:
    return AcquireResult(
        allowed=data["allowed"],
        lease_id=data.get("lease_id"),
        active=data["active"],
        limit=data["limit"],
        reset_ms=data["reset_ms"],
    )


def parse_release(data: dict[str, Any]) -> ReleaseResult:
    return ReleaseResult(released=data["released"], active=data["active"])


def parse_stats(data: dict[str, Any]) -> StatsResult:
    month = data["month"]
    return StatsResult(
        namespace=data["namespace"],
        total=data["total"],
        blocked=data["blocked"],
        days=[DayStat(day=d["day"], total=d["total"], blocked=d["blocked"]) for d in data["days"]],
        month=MonthSummary(
            month=month["month"],
            total=month["total"],
            quota=month["quota"],
            over_quota=month["over_quota"],
            hard_cap=month.get("hard_cap"),
        ),
    )


def error_body(status: int, text: str) -> dict[str, str]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "error" in parsed:
            out = {"error": str(parsed["error"])}
            if parsed.get("code") is not None:
                out["code"] = str(parsed["code"])
            return out
    except ValueError:
        pass
    return {"error": f"HTTP {status}"}


_ERROR_BY_CODE: dict[str, Callable[[dict[str, str]], DetentAPIError]] = {
    "payment_required": DetentPaymentRequired,
    "monthly_hard_cap": DetentQuotaExceeded,
    "algorithm_not_on_plan": DetentAlgorithmNotOnPlan,
    "invalid_request": DetentInvalidRequest,
    "unknown_algorithm": DetentUnknownAlgorithm,
    "invalid_duration": DetentInvalidDuration,
}


def api_error(status: int, body: dict[str, str]) -> DetentAPIError:
    # Key off the machine ``code`` (#56/#57); fall back to the legacy ``error``
    # string so an SDK pointed at an API predating the gate ``code`` still
    # yields the typed quota/payment errors. Unknown codes -> DetentAPIError.
    cls = _ERROR_BY_CODE.get(body.get("code") or body.get("error", ""))
    if cls is not None:
        return cls(body)
    return DetentAPIError(status, body)


def should_degrade(err: DetentError) -> bool:
    if isinstance(err, DetentTransportError):
        return True
    if isinstance(err, DetentAPIError):
        return err.status >= 500
    return False
