"""
Transform raw string rows into normalised, ready-to-use dictionaries.

DataCleaner assumes the rows have already been validated.
It strips whitespace, normalises casing, and maps unknown enum values
to sensible defaults.
"""

from __future__ import annotations

from typing import Sequence

from src.models.ticket import Priority, Status, Category

# Mapping from non-standard priority strings to canonical ones
_PRIORITY_MAP: dict[str, str] = {
    "urgent": Priority.URGENT.value,
    "high": Priority.HIGH.value,
    "medium": Priority.MEDIUM.value,
    "low": Priority.LOW.value,
}

_STATUS_MAP: dict[str, str] = {
    "open": Status.OPEN.value,
    "pending": Status.PENDING.value,
    "resolved": Status.RESOLVED.value,
    "closed": Status.CLOSED.value,
}

_CATEGORY_MAP: dict[str, str] = {
    "billing": Category.BILLING.value,
    "technical": Category.TECHNICAL.value,
    "account": Category.ACCOUNT.value,
    "general": Category.GENERAL.value,
}


class DataCleaner:
    """
    Normalise a sequence of raw ticket rows.

    Each public method returns a new list — the input is never mutated.
    """

    # --- public interface ----------------------------------------------------

    def clean_all(self, rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        """Apply all cleaning steps to every row."""
        return [self._clean_row(dict(row)) for row in rows]

    def __repr__(self) -> str:
        return "DataCleaner()"

    # --- private helpers -----------------------------------------------------

    def _clean_row(self, row: dict[str, str]) -> dict[str, str]:
        row = {k: v.strip() for k, v in row.items()}          # strip whitespace

        # Normalise priority
        priority_raw = row.get("priority", "").lower()
        row["priority"] = _PRIORITY_MAP.get(priority_raw, Priority.LOW.value)

        # Normalise status
        status_raw = row.get("status", "").lower()
        row["status"] = _STATUS_MAP.get(status_raw, Status.OPEN.value)

        # Normalise category
        category_raw = row.get("category", "").lower()
        row["category"] = _CATEGORY_MAP.get(category_raw, Category.UNKNOWN.value)

        # Capitalise customer name
        if row.get("customer"):
            row["customer"] = row["customer"].title()

        return row
