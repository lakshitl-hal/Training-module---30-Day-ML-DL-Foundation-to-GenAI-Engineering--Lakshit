"""Unit tests: parse_row turns raw strings into Tickets or InvalidRowError."""

from __future__ import annotations

import pytest

from ticket_pipeline.errors import InvalidRowError
from ticket_pipeline.models.ticket import InvalidTicketField, Priority, Status
from ticket_pipeline.processing.loader import RawRow
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS, parse_row


def raw(line: int = 2, /, **overrides: str) -> RawRow:
    values = {
        "ticket_id": "TKT-0001",
        "customer_email": "asha@example.com",
        "priority": "high",
        "status": "open",
        "category": "billing",
        "created_at": "2026-10-01",
        "resolution_hours": "",
    }
    values.update(overrides)
    return RawRow(line=line, values=values)


def test_valid_row_becomes_ticket() -> None:
    ticket = parse_row(raw())
    assert ticket.ticket_id == "TKT-0001"
    assert ticket.priority is Priority.HIGH
    assert ticket.resolution_hours is None


def test_values_are_normalised() -> None:
    ticket = parse_row(raw(
        ticket_id=" tkt-0001 ", customer_email="Asha@Example.COM", priority=" HIGH ",
        status="In Progress", category="Billing",
    ))
    assert ticket.ticket_id == "TKT-0001"
    assert ticket.customer_email == "asha@example.com"
    assert ticket.status is Status.IN_PROGRESS
    assert ticket.category == "billing"


def test_finished_ticket_hours_are_parsed() -> None:
    assert parse_row(raw(status="closed", resolution_hours="4.5")).resolution_hours == 4.5


@pytest.mark.parametrize("column", REQUIRED_COLUMNS)
def test_each_empty_required_column_is_reported(column: str) -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(7, **{column: "  "}))
    assert (info.value.line, info.value.column) == (7, column)
    assert "required" in info.value.reason


@pytest.mark.parametrize(
    ("overrides", "column", "reason_part"),
    [
        ({"priority": "critical"}, "priority", "not one of: low, medium, high, urgent"),
        ({"status": "done"}, "status", "not one of"),
        ({"created_at": "2026-13-01"}, "created_at", "ISO 8601"),
        ({"created_at": "01/10/2026"}, "created_at", "ISO 8601"),
        ({"status": "closed", "resolution_hours": "abc"}, "resolution_hours", "not a number"),
        ({"status": "closed", "resolution_hours": "1_5"}, "resolution_hours", "not a number"),
        ({"status": "closed", "resolution_hours": "inf"}, "resolution_hours", "finite"),
        ({"status": "closed", "resolution_hours": "nan"}, "resolution_hours", "finite"),
        ({"status": "closed", "resolution_hours": "-2"}, "resolution_hours", "finite"),
        ({"status": "open", "resolution_hours": "3"}, "resolution_hours", "resolved or closed"),
        ({"ticket_id": "12"}, "ticket_id", "TKT-0001"),
        ({"customer_email": "nope"}, "customer_email", "valid e-mail"),
    ],
    ids=[
        "unknown-priority", "unknown-status", "impossible-date", "non-iso-date",
        "hours-not-number", "hours-underscore", "hours-inf", "hours-nan", "hours-negative",
        "hours-on-open-ticket", "bad-ticket-id", "bad-email",
    ],
)
def test_invalid_values_report_column_and_reason(
    overrides: dict[str, str], column: str, reason_part: str
) -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(**overrides))
    assert info.value.column == column
    assert reason_part in info.value.reason


def test_model_error_is_chained_as_cause() -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(customer_email="nope"))
    assert isinstance(info.value.__cause__, InvalidTicketField)


def test_conversion_error_is_chained_as_cause() -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(created_at="yesterday"))
    assert isinstance(info.value.__cause__, ValueError)


def test_error_message_never_contains_email() -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(customer_email="private.person@nowhere"))
    assert "private.person" not in str(info.value)
