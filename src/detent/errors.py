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


class DetentTransportError(DetentError):
    """A network/DNS/timeout failure reaching the Detent API."""


class DetentLeaseDenied(DetentError):
    """Raised by lease() when a concurrent slot could not be acquired."""

    def __init__(self, result: AcquireResult) -> None:
        super().__init__("Lease denied: no concurrent slot available")
        self.result = result
