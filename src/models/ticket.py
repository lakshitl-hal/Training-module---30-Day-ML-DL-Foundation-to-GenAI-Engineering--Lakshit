"""
Domain model for a support ticket.

Demonstrates:
- dataclass for concise attribute definition
- Enum for constrained string values
- __post_init__ for validation
- __repr__ and __str__ via dataclass
- Properties for derived state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


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


@dataclass
class SupportTicket:
    """
    Immutable value object representing a single support ticket.

    All fields are validated at construction time.
    Invalid values raise ValueError so the object never exists
    in an inconsistent state.
    """

    ticket_id: str
    customer: str
    priority: Priority
    category: Category
    status: Status
    description: str
    created_at: datetime

    # --- class-level constant ------------------------------------------------
    MAX_DESCRIPTION_LENGTH: int = field(default=500, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Validate all fields immediately after construction."""
        if not self.ticket_id or not self.ticket_id.strip():
            raise ValueError("ticket_id must not be empty")
        if not self.customer or not self.customer.strip():
            raise ValueError("customer name must not be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description must not be empty")
        if len(self.description) > self.MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description exceeds {self.MAX_DESCRIPTION_LENGTH} characters"
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
