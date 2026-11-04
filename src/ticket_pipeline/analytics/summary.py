"""Analytics over validated tickets. Pure functions: no I/O, no logging."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from ticket_pipeline.models.ticket import Priority, Ticket

URGENT_PRIORITIES: frozenset[Priority] = frozenset({Priority.HIGH, Priority.URGENT})


@dataclass(frozen=True)
class TicketSummary:
    total: int
    by_priority: dict[str, int]
    by_status: dict[str, int]
    by_category: dict[str, int]
    open_urgent_ids: tuple[str, ...]
    mean_resolution_hours: float | None  # None when no ticket has been resolved


def summarise(tickets: Iterable[Ticket]) -> TicketSummary:
    """Compute counts and averages for a collection of tickets."""
    items = tuple(tickets)
    hours = [t.resolution_hours for t in items if t.resolution_hours is not None]
    return TicketSummary(
        total=len(items),
        by_priority=dict(sorted(Counter(t.priority.value for t in items).items())),
        by_status=dict(sorted(Counter(t.status.value for t in items).items())),
        by_category=dict(sorted(Counter(t.category for t in items).items())),
        open_urgent_ids=tuple(
            sorted(t.ticket_id for t in items if t.is_open and t.priority in URGENT_PRIORITIES)
        ),
        mean_resolution_hours=round(sum(hours) / len(hours), 2) if hours else None,
    )


def format_summary(summary: TicketSummary) -> str:
    """Render a summary as plain text for the terminal."""

    def block(title: str, counts: dict[str, int]) -> list[str]:
        return [f"  {title}:"] + [f"    {key:<12} {value}" for key, value in counts.items()]

    mean = (
        "n/a" if summary.mean_resolution_hours is None
        else f"{summary.mean_resolution_hours:.2f} h"
    )
    lines = [
        "TICKET SUMMARY",
        f"  Valid tickets          : {summary.total}",
        f"  Mean resolution time   : {mean}",
        f"  Open high/urgent       : {', '.join(summary.open_urgent_ids) or 'none'}",
        *block("By priority", summary.by_priority),
        *block("By status", summary.by_status),
        *block("By category", summary.by_category),
    ]
    return "\n".join(lines)
