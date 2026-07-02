"""Typed Python client for the Detent rate-limiting API."""

from .client import Detent
from .errors import (
    DetentAPIError,
    DetentError,
    DetentLeaseDenied,
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
    "DetentError",
    "DetentAPIError",
    "DetentTransportError",
    "DetentLeaseDenied",
    "LimitResult",
    "AcquireResult",
    "ReleaseResult",
    "StatsResult",
    "DayStat",
    "MonthSummary",
    "Algorithm",
]
