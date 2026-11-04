"""Unit tests: Ticket invariants."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

import pytest

from ticket_pipeline.models.ticket import Category, InvalidTicketField, Priority, Status, Ticket


def make_ticket(**overrides: Any) -> Ticket:
    fields: dict[str, Any] = {
        "ticket_id": "T001",
        "customer": "Alice Johnson",
        "priority": Priority.HIGH,
        "category": Category.BILLING,
        "status": Status.OPEN,
        "description": "Cannot access invoice",
        "created_at": datetime(2024, 1, 15),
    }
    fields.update(overrides)
    return Ticket(**fields)


def test_valid_ticket_has_expected_derived_state() -> None:
    ticket = make_ticket()
    assert ticket.is_open and ticket.is_high_priority
    assert ticket.resolution_time_hours is None and ticket.customer_rating is None


@pytest.mark.parametrize(
    ("status", "is_open"),
    [(Status.OPEN, True), (Status.PENDING, True), (Status.RESOLVED, False), (Status.CLOSED, False)],
)
def test_open_means_open_or_pending(status: Status, is_open: bool) -> None:
    assert make_ticket(status=status).is_open is is_open


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        pytest.param("ticket_id", "", id="empty-id"),
        pytest.param("ticket_id", 1, id="non-text-id"),
        pytest.param("customer", "   ", id="blank-customer"),
        pytest.param("description", "", id="empty-description"),
        pytest.param("description", "x" * 501, id="description-501-chars"),
        pytest.param("priority", "high", id="priority-plain-str"),
        pytest.param("category", 3, id="category-int"),
        pytest.param("status", None, id="status-none"),
        pytest.param("created_at", "2024-01-15", id="created-at-str"),
    ],
)
def test_invalid_field_raises_with_field_name(field_name: str, bad_value: object) -> None:
    with pytest.raises(InvalidTicketField) as info:
        make_ticket(**{field_name: bad_value})
    assert info.value.field_name == field_name


@pytest.mark.parametrize(
    "hours",
    [float("inf"), float("-inf"), float("nan"), -1.0, True, "4"],
    ids=["inf", "minus-inf", "nan", "negative", "bool", "str"],
)
def test_invalid_resolution_time_rejected(hours: object) -> None:
    with pytest.raises(InvalidTicketField, match="resolution_time_hours"):
        make_ticket(resolution_time_hours=hours)


@pytest.mark.parametrize(
    "rating", [0, 6, 3.5, 4.0, True, "4"],
    ids=["zero", "six", "fraction", "float-whole", "bool", "str"],
)
def test_invalid_rating_rejected(rating: object) -> None:
    with pytest.raises(InvalidTicketField, match="customer_rating"):
        make_ticket(customer_rating=rating)


def test_valid_optional_values_accepted() -> None:
    ticket = make_ticket(resolution_time_hours=0, customer_rating=5)
    assert (ticket.resolution_time_hours, ticket.customer_rating) == (0, 5)


def test_ticket_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_ticket().status = Status.CLOSED  # type: ignore[misc]


def test_repr_and_str_hide_customer_and_description() -> None:
    ticket = make_ticket()
    for text in (repr(ticket), str(ticket)):
        assert "Alice Johnson" not in text
        assert "Cannot access invoice" not in text
        assert "T001" in text
