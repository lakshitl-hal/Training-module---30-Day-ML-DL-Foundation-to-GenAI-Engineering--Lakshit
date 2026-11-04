"""
Ticket analytics. Pure functions: no I/O and no logging.

The analytics contract (unchanged from the existing ticket pipeline):
    total, count by priority / status / category, open tickets (OPEN or
    PENDING), high-priority open tickets (HIGH or URGENT and open),
    top customers, daily volume, average resolution time, average rating.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from ticket_pipeline.models.ticket import Ticket


@dataclass(frozen=True)
class TicketSummary:
    total: int
    by_priority: dict[str, int]
    by_status: dict[str, int]
    by_category: dict[str, int]
    open_count: int
    high_priority_open_ids: tuple[str, ...]
    daily_volume: dict[str, int]
    top_customers: tuple[tuple[str, int], ...]
    average_resolution_hours: float | None  # None when no ticket has a value
    average_rating: float | None            # None when no ticket is rated


def top_customers(tickets: Iterable[Ticket], n: int = 3) -> list[tuple[str, int]]:
    """The ``n`` customers with most tickets; ties are broken alphabetically."""
    if n < 0:
        raise ValueError("n must not be negative")
    counts = Counter(t.customer for t in tickets)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def summarise(tickets: Iterable[Ticket]) -> TicketSummary:
    """Compute the analytics contract for a collection of tickets."""
    items = tuple(tickets)

    def count(key: str) -> dict[str, int]:
        return dict(sorted(Counter(str(getattr(t, key).value) for t in items).items()))

    return TicketSummary(
        total=len(items),
        by_priority=count("priority"),
        by_status=count("status"),
        by_category=count("category"),
        open_count=sum(t.is_open for t in items),
        high_priority_open_ids=tuple(t.ticket_id for t in items
                                     if t.is_open and t.is_high_priority),
        daily_volume=dict(sorted(Counter(
            t.created_at.strftime("%Y-%m-%d") for t in items).items())),
        top_customers=tuple(top_customers(items)),
        average_resolution_hours=_mean(
            [t.resolution_time_hours for t in items if t.resolution_time_hours is not None]),
        average_rating=_mean(
            [float(t.customer_rating) for t in items if t.customer_rating is not None]),
    )


def format_summary(summary: TicketSummary) -> str:
    """Render a summary as plain ASCII text for the terminal."""

    def block(title: str, counts: dict[str, int]) -> list[str]:
        width = max((len(key) for key in counts), default=0) + 2
        return [f"  {title}:"] + [f"    {key:<{width}}{value}" for key, value in counts.items()]

    def fmt(value: float | None, unit: str) -> str:
        return "n/a" if value is None else f"{value:.2f}{unit}"

    return "\n".join([
        "TICKET SUMMARY",
        f"  Valid tickets            : {summary.total}",
        f"  Open / pending           : {summary.open_count}",
        f"  High-priority open       : {', '.join(summary.high_priority_open_ids) or 'none'}",
        f"  Average resolution time  : {fmt(summary.average_resolution_hours, ' h')}",
        f"  Average customer rating  : {fmt(summary.average_rating, ' / 5')}",
        *block("By priority", summary.by_priority),
        *block("By status", summary.by_status),
        *block("By category", summary.by_category),
        *block("Top customers", dict(summary.top_customers)),
        *block("Daily volume", summary.daily_volume),
    ])
