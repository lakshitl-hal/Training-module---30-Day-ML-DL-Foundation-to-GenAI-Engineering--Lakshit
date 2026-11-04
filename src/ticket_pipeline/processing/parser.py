"""
Row parsing: convert one ``RawRow`` (strings) into one ``Ticket`` (typed).

Every problem in a row is collected and raised together as one
``InvalidRowError`` (file line + list of column/reason issues), so a user can
fix a row in one pass. When a lower-level exception caused an issue, it is
chained with ``raise ... from`` so the root cause stays available.

Normalisation rules (the ticket data contract):
    * all cells are trimmed;
    * priority and status are case-insensitive;
    * an unrecognised category becomes ``Category.UNKNOWN`` (not an error);
    * customer names are title-cased.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import TypeVar

from ticket_pipeline.errors import InvalidRowError, RowIssue
from ticket_pipeline.models.ticket import (
    Category,
    InvalidTicketField,
    Priority,
    Status,
    Ticket,
)
from ticket_pipeline.processing.loader import RawRow

REQUIRED_COLUMNS: tuple[str, ...] = (
    "id", "customer", "priority", "category", "status", "description", "created_at",
)

E = TypeVar("E", bound=Enum)


class _Collector:
    """Accumulates issues for one row and remembers the first underlying cause."""

    def __init__(self) -> None:
        self.issues: list[RowIssue] = []
        self.cause: Exception | None = None

    def add(self, column: str, reason: str, cause: Exception | None = None) -> None:
        self.issues.append(RowIssue(column, reason))
        if self.cause is None and cause is not None:
            self.cause = cause


def parse_row(row: RawRow) -> Ticket:
    """Build a validated ``Ticket`` from a raw row, or raise ``InvalidRowError``."""
    values = {key: value.strip() for key, value in row.values.items()}
    found = _Collector()

    for column in REQUIRED_COLUMNS:
        if not values.get(column):
            found.add(column, "is required but empty")

    priority = _parse_enum(values.get("priority", ""), "priority", Priority, found)
    status = _parse_enum(values.get("status", ""), "status", Status, found)
    category = _parse_category(values.get("category", ""))
    created_at = _parse_date(values.get("created_at", ""), found)
    hours = _parse_hours(values.get("resolution_time_hours", ""), found)
    rating = _parse_rating(values.get("customer_rating", ""), found)

    description = values.get("description", "")
    if len(description) > Ticket.MAX_DESCRIPTION_LENGTH:
        found.add("description", f"is longer than {Ticket.MAX_DESCRIPTION_LENGTH} characters")

    if found.issues:
        raise InvalidRowError(row.line, found.issues) from found.cause

    if priority is None or status is None or created_at is None:  # pragma: no cover
        # Unreachable when the checks above are complete; fail loudly if not.
        raise RuntimeError(f"internal error: unchecked field on line {row.line}")
    try:
        return Ticket(
            ticket_id=values["id"],
            customer=values["customer"].title(),
            priority=priority,
            category=category,
            status=status,
            description=description,
            created_at=created_at,
            resolution_time_hours=hours,
            customer_rating=rating,
        )
    except InvalidTicketField as exc:  # pragma: no cover - defence in depth
        # Reached only if the parser and the model rules ever disagree.
        raise InvalidRowError(row.line, [RowIssue(exc.field_name, exc.reason)]) from exc


def _parse_enum(raw: str, column: str, enum_type: type[E], found: _Collector) -> E | None:
    if not raw:
        return None  # already reported as empty
    try:
        return enum_type(raw.lower())
    except ValueError as exc:
        allowed = ", ".join(str(member.value) for member in enum_type)
        found.add(column, f"value '{raw}' is not one of: {allowed}", exc)
        return None


def _parse_category(raw: str) -> Category:
    try:
        category = Category(raw.lower())
    except ValueError:
        return Category.UNKNOWN
    return category


def _parse_date(raw: str, found: _Collector) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        found.add("created_at", f"value '{raw}' is not an ISO 8601 date (YYYY-MM-DD)", exc)
        return None


def _parse_hours(raw: str, found: _Collector) -> float | None:
    if not raw:
        return None  # optional: not recorded
    try:
        if "_" in raw:  # float() would silently read '2_0' as 20.0
            raise ValueError(f"underscore in {raw!r}")
        hours = float(raw)
    except ValueError as exc:
        found.add("resolution_time_hours", f"value '{raw}' is not a number", exc)
        return None
    if not math.isfinite(hours):  # float() accepts 'inf', 'nan' and '1e400'
        found.add("resolution_time_hours", f"value '{raw}' must be finite")
    elif hours < 0:
        found.add("resolution_time_hours", f"value '{raw}' must not be negative")
    else:
        return hours
    return None


def _parse_rating(raw: str, found: _Collector) -> int | None:
    if not raw:
        return None  # optional: not rated
    try:
        if "_" in raw:
            raise ValueError(f"underscore in {raw!r}")
        rating = int(raw)  # rejects '3.5', '4.0', 'nan'
    except ValueError as exc:
        found.add("customer_rating", f"value '{raw}' must be a whole number", exc)
        return None
    if not Ticket.MIN_RATING <= rating <= Ticket.MAX_RATING:
        found.add(
            "customer_rating",
            f"value {rating} must be between {Ticket.MIN_RATING} and {Ticket.MAX_RATING}",
        )
        return None
    return rating
