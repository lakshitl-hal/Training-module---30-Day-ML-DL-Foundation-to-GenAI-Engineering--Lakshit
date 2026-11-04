"""Unit tests: the ticket analytics contract."""

from __future__ import annotations

from datetime import datetime

import pytest

from ticket_pipeline.analytics.summary import format_summary, summarise, top_customers
from ticket_pipeline.models.ticket import Category, Priority, Status, Ticket


def ticket(tid: str, priority: Priority, status: Status, *, customer: str = "Alice",
           category: Category = Category.BILLING, day: int = 1,
           hours: float | None = None, rating: int | None = None) -> Ticket:
    return Ticket(tid, customer, priority, category, status, "A description",
                  datetime(2024, 1, day), hours, rating)


@pytest.fixture
def tickets() -> list[Ticket]:
    return [
        ticket("T01", Priority.HIGH, Status.OPEN, customer="Alice", day=1),
        ticket("T02", Priority.LOW, Status.CLOSED, customer="Bob", day=2, hours=2, rating=4),
        ticket("T03", Priority.URGENT, Status.PENDING, customer="Alice", day=2, hours=4),
        ticket("T04", Priority.MEDIUM, Status.RESOLVED, customer="Carol",
               category=Category.TECHNICAL, day=3, rating=5),
        ticket("T05", Priority.HIGH, Status.CLOSED, customer="Bob", day=3),
    ]


def test_counts(tickets: list[Ticket]) -> None:
    summary = summarise(tickets)
    assert summary.total == 5
    assert summary.by_priority == {"high": 2, "low": 1, "medium": 1, "urgent": 1}
    assert summary.by_status == {"closed": 2, "open": 1, "pending": 1, "resolved": 1}
    assert summary.by_category == {"billing": 4, "technical": 1}


def test_open_and_high_priority_open(tickets: list[Ticket]) -> None:
    summary = summarise(tickets)
    assert summary.open_count == 2
    assert summary.high_priority_open_ids == ("T01", "T03")  # T05 is high but closed


def test_daily_volume_is_sorted_by_date(tickets: list[Ticket]) -> None:
    assert summarise(tickets).daily_volume == {
        "2024-01-01": 1, "2024-01-02": 2, "2024-01-03": 2,
    }


def test_averages_ignore_missing_values(tickets: list[Ticket]) -> None:
    summary = summarise(tickets)
    assert summary.average_resolution_hours == 3.0
    assert summary.average_rating == 4.5


def test_top_customers_breaks_ties_alphabetically(tickets: list[Ticket]) -> None:
    assert top_customers(tickets) == [("Alice", 2), ("Bob", 2), ("Carol", 1)]
    assert top_customers(tickets, n=1) == [("Alice", 2)]
    assert top_customers(tickets, n=0) == []


def test_top_customers_rejects_negative_n(tickets: list[Ticket]) -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        top_customers(tickets, n=-1)


def test_empty_input_gives_zero_counts_and_no_averages() -> None:
    summary = summarise([])
    assert (summary.total, summary.open_count) == (0, 0)
    assert summary.average_resolution_hours is None and summary.average_rating is None
    text = format_summary(summary)
    assert "Average resolution time  : n/a" in text
    assert "High-priority open       : none" in text


def test_summary_accepts_a_generator(tickets: list[Ticket]) -> None:
    assert summarise(t for t in tickets).total == 5
