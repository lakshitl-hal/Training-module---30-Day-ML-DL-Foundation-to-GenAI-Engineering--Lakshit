"""
Ticket domain model.

A ``Ticket`` is immutable and validated on construction, so code that
receives one never needs to re-check it. Violations raise
``InvalidTicketField`` (a ``ValueError`` subclass) naming the field;
turning that into a row-level report is the parser's job.
"""

from __future__ import annotations

import math
import re
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
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InvalidTicketField(ValueError):
    """A ticket field breaks an invariant. ``field_name`` names the field."""

    def __init__(self, field_name: str, reason: str) -> None:
        self.field_name = field_name
        super().__init__(f"{field_name}: {reason}")


@dataclass(frozen=True)
class Ticket:
    """One support ticket.

    ``resolution_hours`` is ``None`` while a ticket is unresolved; it must be
    set only for RESOLVED or CLOSED tickets.
    """

    ticket_id: str
    customer_email: str = field(repr=False)  # personal data: kept out of repr()
    priority: Priority
    status: Status
    category: str
    created_at: datetime
    resolution_hours: float | None = None

    TICKET_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^TKT-\d{4}$")
    EMAIL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    FINISHED_STATUSES: ClassVar[frozenset[Status]] = frozenset({Status.RESOLVED, Status.CLOSED})

    def __post_init__(self) -> None:
        if not isinstance(self.ticket_id, str) or not self.TICKET_ID_PATTERN.match(self.ticket_id):
            raise InvalidTicketField("ticket_id", "must look like TKT-0001")
        if not isinstance(self.customer_email, str) or not self.EMAIL_PATTERN.match(
            self.customer_email
        ):
            # The value is deliberately not included: it is personal data.
            raise InvalidTicketField("customer_email", "is not a valid e-mail address")
        if not isinstance(self.priority, Priority):
            raise InvalidTicketField("priority", "must be a Priority member")
        if not isinstance(self.status, Status):
            raise InvalidTicketField("status", "must be a Status member")
        if not isinstance(self.category, str) or not self.category.strip():
            raise InvalidTicketField("category", "must not be empty")
        if not isinstance(self.created_at, datetime):
            raise InvalidTicketField("created_at", "must be a datetime")
        self._check_resolution_hours()

    def _check_resolution_hours(self) -> None:
        hours = self.resolution_hours
        if hours is None:
            return
        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            raise InvalidTicketField("resolution_hours", "must be a number")
        if not math.isfinite(hours) or hours < 0:
            raise InvalidTicketField("resolution_hours", "must be a finite number >= 0")
        if self.status not in self.FINISHED_STATUSES:
            raise InvalidTicketField(
                "resolution_hours", "is only allowed for resolved or closed tickets"
            )

    @property
    def is_open(self) -> bool:
        return self.status not in self.FINISHED_STATUSES

    def __str__(self) -> str:
        # Readable summary that intentionally omits the customer e-mail.
        return f"{self.ticket_id} [{self.priority.value}/{self.status.value}] {self.category}"
