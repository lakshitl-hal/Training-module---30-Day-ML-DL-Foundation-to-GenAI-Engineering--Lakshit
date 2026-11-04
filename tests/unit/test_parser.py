"""Unit tests: parse_row turns raw strings into Tickets or InvalidRowError."""

from __future__ import annotations

import pytest

from ticket_pipeline.errors import InvalidRowError
from ticket_pipeline.models.ticket import Category, Priority, Status
from ticket_pipeline.processing.loader import RawRow
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS, parse_row


def raw(line: int = 2, /, **overrides: str) -> RawRow:
    values = {
        "id": "T001",
        "customer": "Alice Johnson",
        "priority": "high",
        "category": "billing",
        "status": "open",
        "description": "Cannot access invoice",
        "resolution_time_hours": "",
        "customer_rating": "",
        "created_at": "2024-01-15",
    }
    values.update(overrides)
    return RawRow(line=line, values=values)


def test_valid_row_becomes_ticket() -> None:
    ticket = parse_row(raw(resolution_time_hours="4.5", customer_rating="4"))
    assert ticket.ticket_id == "T001"
    assert ticket.priority is Priority.HIGH
    assert (ticket.resolution_time_hours, ticket.customer_rating) == (4.5, 4)


def test_values_are_normalised() -> None:
    ticket = parse_row(raw(
        customer=" alice johnson ", priority=" URGENT ", status="Pending",
        category="Technical", created_at=" 2024-01-15",
    ))
    assert ticket.customer == "Alice Johnson"
    assert ticket.priority is Priority.URGENT
    assert ticket.status is Status.PENDING
    assert ticket.category is Category.TECHNICAL


def test_unrecognised_category_is_represented_as_unknown() -> None:
    assert parse_row(raw(category="Shipping")).category is Category.UNKNOWN


def test_optional_columns_may_be_absent() -> None:
    row = raw()
    del row.values["resolution_time_hours"], row.values["customer_rating"]
    assert parse_row(row).customer_rating is None


@pytest.mark.parametrize("column", REQUIRED_COLUMNS)
def test_each_empty_required_column_is_reported(column: str) -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(7, **{column: "  "}))
    assert info.value.line == 7
    assert info.value.columns == (column,)
    assert "required" in info.value.issues[0].reason


@pytest.mark.parametrize(
    ("overrides", "column", "reason_part"),
    [
        pytest.param({"priority": "critical"}, "priority",
                     "not one of: low, medium, high, urgent", id="unknown-priority"),
        pytest.param({"status": "done"}, "status", "not one of", id="unknown-status"),
        pytest.param({"created_at": "2024-13-01"}, "created_at", "ISO 8601", id="impossible-date"),
        pytest.param({"created_at": "15/01/2024"}, "created_at", "ISO 8601", id="non-iso-date"),
        pytest.param({"resolution_time_hours": "abc"}, "resolution_time_hours",
                     "not a number", id="hours-text"),
        pytest.param({"resolution_time_hours": "2_0"}, "resolution_time_hours",
                     "not a number", id="hours-underscore"),
        pytest.param({"resolution_time_hours": "inf"}, "resolution_time_hours",
                     "value 'inf' must be finite", id="hours-inf"),
        pytest.param({"resolution_time_hours": "nan"}, "resolution_time_hours",
                     "value 'nan' must be finite", id="hours-nan"),
        pytest.param({"resolution_time_hours": "1e400"}, "resolution_time_hours",
                     "value '1e400' must be finite", id="hours-overflow"),
        pytest.param({"resolution_time_hours": "-2"}, "resolution_time_hours",
                     "negative", id="hours-negative"),
        pytest.param({"customer_rating": "3.5"}, "customer_rating",
                     "whole number", id="rating-fraction"),
        pytest.param({"customer_rating": "4.0"}, "customer_rating",
                     "whole number", id="rating-float-whole"),
        pytest.param({"customer_rating": "1_0"}, "customer_rating",
                     "whole number", id="rating-underscore"),
        pytest.param({"customer_rating": "0"}, "customer_rating",
                     "between 1 and 5", id="rating-zero"),
        pytest.param({"customer_rating": "6"}, "customer_rating",
                     "between 1 and 5", id="rating-six"),
        pytest.param({"description": "x" * 501}, "description",
                     "longer than 500", id="description-too-long"),
    ],
)
def test_invalid_values_report_column_and_reason(
    overrides: dict[str, str], column: str, reason_part: str
) -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(**overrides))
    assert info.value.columns == (column,)
    assert reason_part in info.value.issues[0].reason


def test_all_problems_in_a_row_are_reported_together() -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(customer="", category="", customer_rating="9"))
    assert info.value.columns == ("customer", "category", "customer_rating")
    assert str(info.value).startswith("line 2: 'customer' is required but empty;")


def test_conversion_error_is_chained_as_cause() -> None:
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(created_at="yesterday"))
    assert isinstance(info.value.__cause__, ValueError)


def test_error_message_never_contains_customer_or_description() -> None:
    long_text = "Private details " * 40
    with pytest.raises(InvalidRowError) as info:
        parse_row(raw(customer="Secret Person", description=long_text, priority="bad"))
    assert "Secret Person" not in str(info.value)
    assert "Private details" not in str(info.value)


def test_invalid_row_error_requires_at_least_one_issue() -> None:
    with pytest.raises(ValueError, match="at least one issue"):
        InvalidRowError(2, [])
