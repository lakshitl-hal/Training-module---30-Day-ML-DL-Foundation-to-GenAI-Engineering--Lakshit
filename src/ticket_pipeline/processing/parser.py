"""
Row parsing: convert one ``RawRow`` (strings) into one ``Ticket`` (typed).

Every failure is raised as ``InvalidRowError`` carrying the file line, the
column and an actionable reason. Low-level exceptions (``ValueError`` from
``float()``, ``datetime.fromisoformat()`` or the model) are chained with
``raise ... from exc`` so the original cause is preserved for debugging.

The first problem found in a row is reported; one row produces one error.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TypeVar

from ticket_pipeline.errors import InvalidRowError
from ticket_pipeline.models.ticket import InvalidTicketField, Priority, Status, Ticket
from ticket_pipeline.processing.loader import RawRow

REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticket_id", "customer_email", "priority", "status", "category", "created_at",
)

E = TypeVar("E", bound=Enum)


def parse_row(row: RawRow) -> Ticket:
    """Build a validated ``Ticket`` from a raw row, or raise ``InvalidRowError``."""
    values = {key: value.strip() for key, value in row.values.items()}

    for column in REQUIRED_COLUMNS:
        if not values.get(column):
            raise InvalidRowError(row.line, column, "value is required but empty")

    priority = _parse_enum(row.line, "priority", values["priority"], Priority)
    status = _parse_enum(row.line, "status", values["status"], Status)
    created_at = _parse_date(row.line, values["created_at"])
    hours = _parse_hours(row.line, values.get("resolution_hours", ""))

    try:
        return Ticket(
            ticket_id=values["ticket_id"].upper(),
            customer_email=values["customer_email"].lower(),
            priority=priority,
            status=status,
            category=values["category"].lower(),
            created_at=created_at,
            resolution_hours=hours,
        )
    except InvalidTicketField as exc:
        reason = str(exc).split(": ", 1)[-1]
        raise InvalidRowError(row.line, exc.field_name, reason) from exc


def _parse_enum(line: int, column: str, raw: str, enum_type: type[E]) -> E:
    allowed = [member.value for member in enum_type]
    try:
        return enum_type(raw.lower().replace(" ", "_").replace("-", "_"))
    except ValueError as exc:
        raise InvalidRowError(
            line, column, f"'{raw}' is not one of: {', '.join(allowed)}"
        ) from exc


def _parse_date(line: int, raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidRowError(
            line, "created_at", f"'{raw}' is not an ISO 8601 date such as 2026-01-31"
        ) from exc


def _parse_hours(line: int, raw: str) -> float | None:
    if not raw:
        return None
    try:
        if "_" in raw:  # float() would silently read '1_5' as 15.0
            raise ValueError(raw)
        return float(raw)
    except ValueError as exc:
        raise InvalidRowError(line, "resolution_hours", f"'{raw}' is not a number") from exc
