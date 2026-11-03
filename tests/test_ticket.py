"""Tests for the SupportTicket domain model."""

import pytest
from datetime import datetime
from src.models.ticket import SupportTicket, Priority, Status, Category


def _make_ticket(**overrides) -> SupportTicket:
    defaults = dict(
        ticket_id="T001",
        customer="Alice",
        priority=Priority.HIGH,
        category=Category.BILLING,
        status=Status.OPEN,
        description="Test description",
        created_at=datetime(2024, 1, 15),
    )
    defaults.update(overrides)
    return SupportTicket(**defaults)


class TestSupportTicketCreation:
    def test_valid_ticket_is_created(self):
        t = _make_ticket()
        assert t.ticket_id == "T001"
        assert t.customer == "Alice"

    def test_empty_ticket_id_raises(self):
        with pytest.raises(ValueError, match="ticket_id"):
            _make_ticket(ticket_id="")

    def test_empty_customer_raises(self):
        with pytest.raises(ValueError, match="customer"):
            _make_ticket(customer="")

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="description"):
            _make_ticket(description="")

    def test_whitespace_only_customer_raises(self):
        with pytest.raises(ValueError, match="customer"):
            _make_ticket(customer="   ")


class TestSupportTicketProperties:
    def test_open_ticket_is_open(self):
        t = _make_ticket(status=Status.OPEN)
        assert t.is_open is True

    def test_closed_ticket_is_not_open(self):
        t = _make_ticket(status=Status.CLOSED)
        assert t.is_open is False

    def test_high_priority_flag(self):
        t = _make_ticket(priority=Priority.HIGH)
        assert t.is_high_priority is True

    def test_urgent_priority_flag(self):
        t = _make_ticket(priority=Priority.URGENT)
        assert t.is_high_priority is True

    def test_low_priority_not_high(self):
        t = _make_ticket(priority=Priority.LOW)
        assert t.is_high_priority is False

    def test_str_contains_ticket_id(self):
        t = _make_ticket()
        assert "T001" in str(t)
