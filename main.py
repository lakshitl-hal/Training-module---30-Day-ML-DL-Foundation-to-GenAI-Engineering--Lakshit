"""
Entry point — demonstrates the full pipeline:

  CSVLoader → TicketValidator → DataCleaner → SupportTicket → AnalyticsEngine
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.io.loader import CSVLoader
from src.validation.validator import TicketValidator
from src.processing.cleaner import DataCleaner
from src.models.ticket import SupportTicket, Priority, Status, Category
from src.analytics.engine import AnalyticsEngine


def _optional(raw: str | None, cast):
    """Convert an optional CSV cell; empty means 'not provided' (None)."""
    raw = (raw or "").strip()
    return cast(raw) if raw else None


def build_ticket(row: dict[str, str]) -> SupportTicket:
    """Convert a cleaned string-dict into a SupportTicket."""
    return SupportTicket(
        ticket_id=row["id"],
        customer=row["customer"],
        priority=Priority(row["priority"]),
        category=Category(row["category"]),
        status=Status(row["status"]),
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolution_time_hours=_optional(row.get("resolution_time_hours"), float),
        customer_rating=_optional(row.get("customer_rating"), int),
    )


def main() -> None:
    data_path = Path(__file__).parent / "data" / "tickets.csv"

    # Step 1 — Load raw rows
    loader = CSVLoader(data_path)
    raw_rows = loader.load()
    print(f"Loaded {len(raw_rows)} raw rows from {data_path.name}")

    # Step 2 — Validate
    validator = TicketValidator()
    results = validator.validate_all(raw_rows)
    valid_rows = [row for row, r in zip(raw_rows, results) if r.is_valid]
    invalid_rows = [r for r in results if not r.is_valid]

    print(f"\nValidation: {len(valid_rows)} valid, {len(invalid_rows)} invalid")
    for r in invalid_rows:
        print(f"  {r}")

    # Step 3 — Clean
    cleaner = DataCleaner()
    cleaned_rows = cleaner.clean_all(valid_rows)

    # Step 4 — Build domain objects
    tickets: list[SupportTicket] = []
    for row in cleaned_rows:
        try:
            tickets.append(build_ticket(row))
        except (ValueError, KeyError) as exc:
            print(f"  Skipping row {row.get('id', '?')}: {exc}")

    print(f"\nConstructed {len(tickets)} SupportTicket objects")

    # Step 5 — Analytics
    engine = AnalyticsEngine(tickets)
    print("\n" + engine.summary_report())

    # Show high-priority open tickets
    urgent = engine.high_priority_open()
    if urgent:
        print("\nHigh-priority open tickets needing attention:")
        for t in urgent:
            print(f"  {t}")

    # Extended analytics — resolution time and satisfaction
    avg_time = engine.average_resolution_time()
    avg_rating = engine.average_rating()
    print("\nAverage resolution time:",
          "n/a" if avg_time is None else f"{avg_time:.2f} h")
    print("Average customer rating:",
          "n/a" if avg_rating is None else f"{avg_rating:.2f} / 5")

    # Extended analytics — daily volume
    print("\nDaily ticket volume:")
    for day, count in engine.daily_volume().items():
        print(f"  {day}: {'#' * count} ({count})")


if __name__ == "__main__":
    main()
