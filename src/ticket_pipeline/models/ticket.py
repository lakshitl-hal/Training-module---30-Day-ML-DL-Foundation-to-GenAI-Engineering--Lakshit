"""
Ticket domain model — the support-ticket data contract used by the pipeline.

A ``Ticket`` is immutable and validated on construction, so code that
receives one never needs to re-check it. Violations raise
``InvalidTicketField`` (a ``ValueError`` subclass) naming the field;
turning that into a row-level report is the parser's job.

``customer`` and ``description`` are treated as sensitive free text: they are
excluded from ``repr()`` and never included in error messages.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Status(StrEnum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Category(StrEnum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"
    UNKNOWN = "unknown"  # explicit representation of an unrecognised category


class InvalidTicketField(ValueError):
    """A ticket field breaks an invariant. ``field_name`` names the field."""

    def __init__(self, field_name: str, reason: str) -> None:
        self.field_name = field_name
        self.reason = reason
        super().__init__(f"{field_name}: {reason}")


@dataclass(frozen=True)
class Ticket:
    """One support ticket. Optional numeric fields use ``None`` for 'not recorded'."""

    ticket_id: str
    customer: str = field(repr=False)
    priority: Priority
    category: Category
    status: Status
    description: str = field(repr=False)
    created_at: datetime
    resolution_time_hours: float | None = None
    customer_rating: int | None = None

    MAX_DESCRIPTION_LENGTH: ClassVar[int] = 500
    MIN_RATING: ClassVar[int] = 1
    MAX_RATING: ClassVar[int] = 5
    OPEN_STATUSES: ClassVar[frozenset[Status]] = frozenset({Status.OPEN, Status.PENDING})
    HIGH_PRIORITIES: ClassVar[frozenset[Priority]] = frozenset({Priority.HIGH, Priority.URGENT})

    def __post_init__(self) -> None:
        for name in ("ticket_id", "customer", "description"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidTicketField(name, "must be non-empty text")
        if len(self.description) > self.MAX_DESCRIPTION_LENGTH:
            raise InvalidTicketField(
                "description", f"must be at most {self.MAX_DESCRIPTION_LENGTH} characters"
            )
        for name, enum_type in (
            ("priority", Priority), ("category", Category), ("status", Status)
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise InvalidTicketField(name, f"must be a {enum_type.__name__} member")
        if not isinstance(self.created_at, datetime):
            raise InvalidTicketField("created_at", "must be a datetime")
        self._check_resolution_time()
        self._check_rating()

    def _check_resolution_time(self) -> None:
        hours = self.resolution_time_hours
        if hours is None:
            return
        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise InvalidTicketField("resolution_time_hours", "must be a number")
        if not math.isfinite(hours):  # inf, -inf and nan pass every range check
            raise InvalidTicketField("resolution_time_hours", "must be finite")
        if hours < 0:
            raise InvalidTicketField("resolution_time_hours", "must not be negative")

    def _check_rating(self) -> None:
        rating = self.customer_rating
        if rating is None:
            return
        if isinstance(rating, bool) or not isinstance(rating, int):
            raise InvalidTicketField("customer_rating", "must be a whole number")
        if not self.MIN_RATING <= rating <= self.MAX_RATING:
            raise InvalidTicketField(
                "customer_rating", f"must be between {self.MIN_RATING} and {self.MAX_RATING}"
            )

    @property
    def is_open(self) -> bool:
        """True while the ticket needs attention (OPEN or PENDING)."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_high_priority(self) -> bool:
        return self.priority in self.HIGH_PRIORITIES

    def __str__(self) -> str:
        # Intentionally omits customer and description (sensitive free text).
        return f"{self.ticket_id} [{self.priority.value}/{self.status.value}] {self.category.value}"
