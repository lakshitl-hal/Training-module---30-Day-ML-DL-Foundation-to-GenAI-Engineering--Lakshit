"""
Analytics engine built with the composition pattern.

AnalyticsEngine owns a list of SupportTicket objects and
delegates every specific analysis to a small, focused function.
Adding a new analysis never requires modifying existing code.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Sequence

from src.models.ticket import SupportTicket, Priority, Status


class AnalyticsEngine:
    """
    Run analytics over a collection of SupportTicket objects.

    Instance state:
        _tickets  – the tickets this engine operates on.

    All analytics methods are pure: they read _tickets and return
    new data structures without mutating anything.
    """

    def __init__(self, tickets: Sequence[SupportTicket]) -> None:
        self._tickets: tuple[SupportTicket, ...] = tuple(tickets)

    # --- basic summaries -----------------------------------------------------

    def total_count(self) -> int:
        """Return the total number of tickets."""
        return len(self._tickets)

    def count_by_priority(self) -> dict[str, int]:
        """Return a frequency map of tickets per priority level."""
        return dict(Counter(t.priority.value for t in self._tickets))

    def count_by_status(self) -> dict[str, int]:
        """Return a frequency map of tickets per status."""
        return dict(Counter(t.status.value for t in self._tickets))

    def count_by_category(self) -> dict[str, int]:
        """Return a frequency map of tickets per category."""
        return dict(Counter(t.category.value for t in self._tickets))

    # --- filtered views ------------------------------------------------------

    def open_tickets(self) -> list[SupportTicket]:
        """Return tickets that are still open or pending."""
        return [t for t in self._tickets if t.is_open]

    def high_priority_open(self) -> list[SupportTicket]:
        """Return open tickets with HIGH or URGENT priority."""
        return [t for t in self._tickets if t.is_open and t.is_high_priority]

    # --- extended analytics (Task C) ----------------------------------------

    def top_customers(self, n: int = 3) -> list[tuple[str, int]]:
        """Return the n customers who submitted the most tickets."""
        counts = Counter(t.customer for t in self._tickets)
        return counts.most_common(n)

    def daily_volume(self) -> dict[str, int]:
        """Return ticket count grouped by calendar date (YYYY-MM-DD)."""
        counter: Counter[str] = Counter()
        for ticket in self._tickets:
            day = ticket.created_at.strftime("%Y-%m-%d")
            counter[day] += 1
        return dict(sorted(counter.items()))

    def summary_report(self) -> str:
        """Return a human-readable summary of the current ticket set."""
        lines = [
            "=" * 50,
            "       SUPPORT TICKET ANALYTICS REPORT",
            "=" * 50,
            f"  Total tickets      : {self.total_count()}",
            f"  Open / Pending     : {len(self.open_tickets())}",
            f"  High-priority open : {len(self.high_priority_open())}",
            "",
            "  By Priority:",
            *[f"    {k:10s} : {v}" for k, v in sorted(self.count_by_priority().items())],
            "",
            "  By Status:",
            *[f"    {k:10s} : {v}" for k, v in sorted(self.count_by_status().items())],
            "",
            "  By Category:",
            *[f"    {k:10s} : {v}" for k, v in sorted(self.count_by_category().items())],
            "=" * 50,
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"AnalyticsEngine(tickets={len(self._tickets)})"
