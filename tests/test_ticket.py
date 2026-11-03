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


class TestOptionalNumericFields:
    """Regression: non-finite / non-integer values must never be accepted."""

    @pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
    def test_non_finite_resolution_time_raises(self, bad):
        with pytest.raises(ValueError, match="resolution_time_hours"):
            _make_ticket(resolution_time_hours=bad)

    def test_negative_resolution_time_raises(self):
        with pytest.raises(ValueError, match="resolution_time_hours"):
            _make_ticket(resolution_time_hours=-1.0)

    def test_non_numeric_resolution_time_raises(self):
        with pytest.raises(ValueError, match="resolution_time_hours"):
            _make_ticket(resolution_time_hours="4.5")

    @pytest.mark.parametrize("good", [0, 2, 4.5])
    def test_finite_resolution_time_accepted(self, good):
        assert _make_ticket(resolution_time_hours=good).resolution_time_hours == good

    @pytest.mark.parametrize("bad", [3.5, 4.0, "3", True, 0, 6, -1])
    def test_invalid_rating_raises(self, bad):
        with pytest.raises(ValueError, match="customer_rating"):
            _make_ticket(customer_rating=bad)

    @pytest.mark.parametrize("good", [1, 3, 5])
    def test_valid_rating_accepted(self, good):
        assert _make_ticket(customer_rating=good).customer_rating == good

    def test_optional_fields_default_to_none(self):
        t = _make_ticket()
        assert t.resolution_time_hours is None and t.customer_rating is None


class TestImmutabilityAndClassState:
    def test_ticket_is_frozen(self):
        t = _make_ticket()
        with pytest.raises(Exception):
            t.customer = "Mallory"

    def test_constants_are_class_level_not_fields(self):
        from dataclasses import fields
        names = {f.name for f in fields(SupportTicket)}
        assert "MAX_DESCRIPTION_LENGTH" not in names
        assert SupportTicket.MAX_DESCRIPTION_LENGTH == 500

    def test_overlong_description_raises(self):
        with pytest.raises(ValueError, match="exceeds"):
            _make_ticket(description="x" * 501)


class TestFieldTypesAreEnforced:
    """Regression: wrong-typed values must not create an invalid ticket."""

    @pytest.mark.parametrize("field_name, bad", [
        ("priority", "high"),     # plain str, not a Priority member
        ("priority", "zzz"),
        ("status", None),
        ("status", "open"),
        ("category", 3),
    ])
    def test_non_enum_values_raise(self, field_name, bad):
        with pytest.raises(ValueError, match=field_name):
            _make_ticket(**{field_name: bad})

    @pytest.mark.parametrize("field_name", ["ticket_id", "customer", "description"])
    def test_non_string_text_fields_raise_value_error(self, field_name):
        with pytest.raises(ValueError):
            _make_ticket(**{field_name: 123})
