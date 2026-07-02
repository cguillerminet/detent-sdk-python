from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Algorithm = Literal["sliding_window", "token_bucket", "fixed_window"]


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    remaining: int
    reset_ms: int
    limit: int
    degraded: bool


@dataclass(frozen=True)
class AcquireResult:
    allowed: bool
    lease_id: str | None
    active: int
    limit: int
    reset_ms: int


@dataclass(frozen=True)
class ReleaseResult:
    released: bool
    active: int


@dataclass(frozen=True)
class DayStat:
    day: str
    total: int
    blocked: int


@dataclass(frozen=True)
class MonthSummary:
    month: str
    total: int
    quota: int | None
    over_quota: bool


@dataclass(frozen=True)
class StatsResult:
    namespace: str
    total: int
    blocked: int
    days: list[DayStat]
    month: MonthSummary
