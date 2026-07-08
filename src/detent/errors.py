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

    @property
    def code(self) -> str | None:
        """Stable machine error code, when the API tagged this error (#56/#57)."""
        return self.body.get("code")


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


class DetentPaymentRequired(DetentAPIError):
    """402 — account out of billing good standing (§7). Never failed open."""

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(402, body)


class DetentAlgorithmNotOnPlan(DetentAPIError):
    """403 — the rule's algorithm is not available on the account's plan."""

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(403, body)


class DetentInvalidRequest(DetentAPIError):
    """400 — malformed request body."""

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(400, body)


class DetentUnknownAlgorithm(DetentAPIError):
    """400 — unknown algorithm name."""

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(400, body)


class DetentInvalidDuration(DetentAPIError):
    """400 — invalid duration."""

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(400, body)


class DetentKeyTypeConflict(DetentAPIError):
    """409 — the namespace+key already holds state for a different algorithm.

    The API returned ``409 {"error": "...", "code": "key_type_conflict"}``
    from ``/v1/limit`` or ``/v1/leases``: a hard deny, not a rate-limit
    verdict. Subclasses :class:`DetentAPIError`, so it carries ``status``
    (always 409) and ``body``. It is **never** failed open — reusing a key
    across algorithms is a caller bug, not a degraded backend.
    """

    def __init__(self, body: dict[str, str]) -> None:
        super().__init__(409, body)


class DetentTransportError(DetentError):
    """A network/DNS/timeout failure reaching the Detent API."""


class DetentLeaseDenied(DetentError):
    """Raised by lease() when a concurrent slot could not be acquired."""

    def __init__(self, result: AcquireResult) -> None:
        super().__init__("Lease denied: no concurrent slot available")
        self.result = result
