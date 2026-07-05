from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AcquireResult


class DetentError(Exception):
    """Base class for all Detent SDK errors."""


class DetentAPIError(DetentError):
    """A 4xx/5xx response from the Detent API."""

    def __init__(self, status: int, body: dict[str, str]) -> None:
        super().__init__(f"Detent API error {status}: {body.get('error', '')}")
        self.status = status
        self.body = body


class DetentQuotaExceeded(DetentAPIError):
    """The account exceeded its monthly hard ceiling (anti-abuse cap, §4.2).

    The API returned ``429 {"error": "monthly_hard_cap"}`` from ``/v1/limit`` or
    ``/v1/leases``. Subclasses :class:`DetentAPIError`, so it carries ``status``
    (always 429) and ``body``, and existing ``DetentAPIError`` handling still
    applies. It is **never** failed open — the cap is a deliberate block. Catch
    it specifically to alert or prompt an upgrade rather than treating it as a
    routine denial.
    """

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(429, body)


class DetentTransportError(DetentError):
    """A network/DNS/timeout failure reaching the Detent API."""


class DetentLeaseDenied(DetentError):
    """Raised by lease() when a concurrent slot could not be acquired."""

    def __init__(self, result: AcquireResult) -> None:
        super().__init__("Lease denied: no concurrent slot available")
        self.result = result
