"""Unit tests: analytics summary."""

from __future__ import annotations

from datetime import datetime

from ticket_pipeline.analytics.summary import format_summary, summarise
from ticket_pipeline.models.ticket import Priority, Status, Ticket


def ticket(tid: str, priority: Priority, status: Status, hours: float | None = None,
           category: str = "billing") -> Ticket:
    return Ticket(tid, "a@example.com", priority, status, category,
                  datetime(2026, 10, 1), hours)


def test_summary_counts_and_mean() -> None:
    summary = summarise([
        ticket("TKT-0001", Priority.HIGH, Status.OPEN),
        ticket("TKT-0002", Priority.LOW, Status.RESOLVED, 2.0, "technical"),
        ticket("TKT-0003", Priority.URGENT, Status.CLOSED, 5.0),
        ticket("TKT-0004", Priority.URGENT, Status.IN_PROGRESS),
    ])
    assert summary.total == 4
    assert summary.by_priority == {"high": 1, "low": 1, "urgent": 2}
    assert summary.by_status == {"closed": 1, "in_progress": 1, "open": 1, "resolved": 1}
    assert summary.by_category == {"billing": 3, "technical": 1}
    assert summary.open_urgent_ids == ("TKT-0001", "TKT-0004")
    assert summary.mean_resolution_hours == 3.5


def test_empty_input_gives_zero_counts_and_no_mean() -> None:
    summary = summarise([])
    assert summary.total == 0
    assert summary.mean_resolution_hours is None
    assert "n/a" in format_summary(summary)
    assert "Open high/urgent       : none" in format_summary(summary)


def test_summary_accepts_a_generator() -> None:
    tickets = (ticket(f"TKT-000{i}", Priority.LOW, Status.OPEN) for i in range(1, 4))
    assert summarise(tickets).total == 3
