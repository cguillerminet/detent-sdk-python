"""Typed Python client for the Detent rate-limiting API."""

from .async_client import AsyncDetent
from .client import Detent
from .errors import (
    DetentAPIError,
    DetentError,
    DetentLeaseDenied,
    DetentQuotaExceeded,
    DetentTransportError,
)
from .models import (
    AcquireResult,
    Algorithm,
    DayStat,
    LimitResult,
    MonthSummary,
    ReleaseResult,
    StatsResult,
)

__all__ = [
    "Detent",
    "AsyncDetent",
    "DetentError",
    "DetentAPIError",
    "DetentTransportError",
    "DetentLeaseDenied",
    "DetentQuotaExceeded",
    "LimitResult",
    "AcquireResult",
    "ReleaseResult",
    "StatsResult",
    "DayStat",
    "MonthSummary",
    "Algorithm",
]
