"""Unit tests: Ticket invariants."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

import pytest

from ticket_pipeline.models.ticket import InvalidTicketField, Priority, Status, Ticket


def make_ticket(**overrides: Any) -> Ticket:
    fields: dict[str, Any] = {
        "ticket_id": "TKT-0001",
        "customer_email": "asha@example.com",
        "priority": Priority.HIGH,
        "status": Status.OPEN,
        "category": "billing",
        "created_at": datetime(2026, 10, 1),
    }
    fields.update(overrides)
    return Ticket(**fields)


def test_valid_ticket_is_created_and_open() -> None:
    ticket = make_ticket()
    assert ticket.is_open
    assert ticket.resolution_hours is None


def test_resolved_ticket_with_hours_is_not_open() -> None:
    ticket = make_ticket(status=Status.RESOLVED, resolution_hours=2.5)
    assert not ticket.is_open


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("ticket_id", "T1"),
        ("ticket_id", "tkt-0001"),
        ("ticket_id", 1),
        ("customer_email", "no-at-sign"),
        ("customer_email", "a@b"),
        ("customer_email", ""),
        ("priority", "high"),  # a plain str is not a Priority member
        ("status", None),
        pytest.param("category", "   ", id="category-whitespace"),
        ("created_at", "2026-10-01"),
    ],
)
def test_invalid_field_raises_with_field_name(field_name: str, bad_value: object) -> None:
    with pytest.raises(InvalidTicketField) as info:
        make_ticket(**{field_name: bad_value})
    assert info.value.field_name == field_name


@pytest.mark.parametrize("hours", [float("inf"), float("-inf"), float("nan"), -1.0, True, "4"])
def test_invalid_resolution_hours_rejected(hours: object) -> None:
    with pytest.raises(InvalidTicketField, match="resolution_hours"):
        make_ticket(status=Status.CLOSED, resolution_hours=hours)


@pytest.mark.parametrize("status", [Status.OPEN, Status.IN_PROGRESS])
def test_unfinished_ticket_cannot_have_resolution_hours(status: Status) -> None:
    with pytest.raises(InvalidTicketField, match="only allowed for resolved or closed"):
        make_ticket(status=status, resolution_hours=1.0)


def test_ticket_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_ticket().status = Status.CLOSED  # type: ignore[misc]


def test_repr_and_str_do_not_expose_email() -> None:
    ticket = make_ticket()
    assert "asha@example.com" not in repr(ticket)
    assert "asha@example.com" not in str(ticket)


def test_invalid_email_error_does_not_echo_value() -> None:
    with pytest.raises(InvalidTicketField) as info:
        make_ticket(customer_email="secret-person.example.com")
    assert "secret-person" not in str(info.value)
