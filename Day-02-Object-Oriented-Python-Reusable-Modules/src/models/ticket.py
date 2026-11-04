"""
Domain model for a support ticket.

Demonstrates:
- frozen dataclass for an immutable value object
- Enum for constrained string values
- __post_init__ for validation (invalid state can never exist)
- ClassVar constants (shared rules) vs instance fields (per-ticket state)
- Properties for derived state
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Status(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SupportTicket:
    """
    Immutable (frozen) value object representing a single support ticket.

    All fields are validated at construction time.
    Invalid values raise ValueError so the object never exists
    in an inconsistent state.

    Optional fields use ``None`` to explicitly mean "not provided":
        resolution_time_hours – finite, non-negative number
        customer_rating       – integer between MIN_RATING and MAX_RATING
    """

    ticket_id: str
    customer: str
    priority: Priority
    category: Category
    status: Status
    description: str
    created_at: datetime
    resolution_time_hours: Optional[float] = None
    customer_rating: Optional[int] = None

    # --- class-level constants (shared rules, not per-instance state) --------
    MAX_DESCRIPTION_LENGTH: ClassVar[int] = 500
    MIN_RATING: ClassVar[int] = 1
    MAX_RATING: ClassVar[int] = 5

    def __post_init__(self) -> None:
        """Validate all fields immediately after construction."""
        self._require_text("ticket_id", "ticket_id must not be empty")
        self._require_text("customer", "customer name must not be empty")
        self._require_text("description", "description must not be empty")
        # Enum fields must be real enum members. Priority is a str subclass,
        # so a plain "high" or "zzz" would otherwise slip through unnoticed.
        for name, enum_type in (
            ("priority", Priority), ("category", Category), ("status", Status)
        ):
            if not isinstance(getattr(self, name), enum_type):
                raise ValueError(f"{name} must be a {enum_type.__name__} member")
        if len(self.description) > self.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description exceeds {self.MAX_DESCRIPTION_LENGTH} characters"
            )
        if not isinstance(self.created_at, datetime):
            raise ValueError("created_at must be a datetime")
        self._validate_resolution_time()
        self._validate_rating()

    def _require_text(self, name: str, message: str) -> None:
        value = getattr(self, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(message)

    def _validate_resolution_time(self) -> None:
        value = self.resolution_time_hours
        if value is None:
            return
        # bool is a subclass of int; reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("resolution_time_hours must be a number")
        if not math.isfinite(value):
            raise ValueError("resolution_time_hours must be finite (no inf/nan)")
        if value < 0:
            raise ValueError("resolution_time_hours must not be negative")

    def _validate_rating(self) -> None:
        value = self.customer_rating
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("customer_rating must be an integer")
        if not self.MIN_RATING <= value <= self.MAX_RATING:
            raise ValueError(
                f"customer_rating must be between "
                f"{self.MIN_RATING} and {self.MAX_RATING}"
            )

    # --- properties ----------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Return True when the ticket still needs attention."""
        return self.status in (Status.OPEN, Status.PENDING)

    @property
    def is_high_priority(self) -> bool:
        """Return True for HIGH or URGENT tickets."""
        return self.priority in (Priority.HIGH, Priority.URGENT)

    # --- human-readable representation ---------------------------------------

    def __str__(self) -> str:
        return (
            f"[{self.ticket_id}] {self.customer} | "
            f"{self.priority.value.upper()} | {self.status.value} | "
            f"{self.description[:40]}..."
        )
