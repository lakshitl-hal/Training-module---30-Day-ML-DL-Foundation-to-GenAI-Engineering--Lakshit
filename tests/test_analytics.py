"""Tests for AnalyticsEngine."""

import pytest
from datetime import datetime
from src.models.ticket import SupportTicket, Priority, Status, Category
from src.analytics.engine import AnalyticsEngine


def _ticket(tid, priority=Priority.LOW, status=Status.OPEN, customer="Alice",
            day: int = 1):
    return SupportTicket(
        ticket_id=tid,
        customer=customer,
        priority=priority,
        category=Category.BILLING,
        status=status,
        description="A test ticket description",
        created_at=datetime(2024, 1, day),
    )


class TestAnalyticsEngine:
    def setup_method(self):
        self.tickets = [
            _ticket("T01", Priority.HIGH,   Status.OPEN,     "Alice", day=1),
            _ticket("T02", Priority.LOW,    Status.CLOSED,   "Bob",   day=2),
            _ticket("T03", Priority.URGENT, Status.PENDING,  "Alice", day=3),
            _ticket("T04", Priority.MEDIUM, Status.RESOLVED, "Carol", day=4),
        ]
        self.engine = AnalyticsEngine(self.tickets)

    def test_total_count(self):
        assert self.engine.total_count() == 4

    def test_count_by_priority(self):
        counts = self.engine.count_by_priority()
        assert counts["high"] == 1
        assert counts["urgent"] == 1

    def test_count_by_status(self):
        counts = self.engine.count_by_status()
        assert counts["open"] == 1
        assert counts["closed"] == 1

    def test_count_by_category(self):
        counts = self.engine.count_by_category()
        assert counts["billing"] == 4

    def test_open_tickets(self):
        open_t = self.engine.open_tickets()
        assert len(open_t) == 2  # OPEN + PENDING

    def test_open_tickets_excludes_resolved(self):
        resolved = [t for t in self.engine.open_tickets() if t.status == Status.RESOLVED]
        assert resolved == []

    def test_open_tickets_excludes_closed(self):
        closed = [t for t in self.engine.open_tickets() if t.status == Status.CLOSED]
        assert closed == []

    def test_high_priority_open(self):
        hp = self.engine.high_priority_open()
        assert len(hp) == 2  # HIGH open + URGENT pending

    def test_high_priority_open_excludes_closed_high(self):
        tickets = [
            _ticket("X01", Priority.HIGH, Status.CLOSED, "Dave", day=5),
        ]
        engine = AnalyticsEngine(tickets)
        assert engine.high_priority_open() == []

    def test_top_customers(self):
        top = self.engine.top_customers(n=1)
        assert top[0][0] == "Alice"
        assert top[0][1] == 2

    def test_top_customers_default_n(self):
        # Default is n=3; with 3 unique customers we get all 3
        top = self.engine.top_customers()
        assert len(top) == 3

    def test_daily_volume_correct_dates(self):
        vol = self.engine.daily_volume()
        assert "2024-01-01" in vol
        assert "2024-01-04" in vol
        assert vol["2024-01-01"] == 1

    def test_daily_volume_sorted(self):
        vol = self.engine.daily_volume()
        keys = list(vol.keys())
        assert keys == sorted(keys)

    def test_summary_report_contains_total(self):
        report = self.engine.summary_report()
        assert "4" in report

    def test_summary_report_is_string(self):
        assert isinstance(self.engine.summary_report(), str)

    def test_repr_contains_ticket_count(self):
        assert "4" in repr(self.engine)

    def test_empty_engine(self):
        engine = AnalyticsEngine([])
        assert engine.total_count() == 0
        assert engine.open_tickets() == []
        assert engine.count_by_priority() == {}
        assert engine.daily_volume() == {}

    def test_engine_does_not_mutate_input_list(self):
        """AnalyticsEngine must not change the original list passed to it."""
        tickets = [_ticket("M01"), _ticket("M02")]
        original_len = len(tickets)
        engine = AnalyticsEngine(tickets)
        engine.open_tickets()
        assert len(tickets) == original_len
