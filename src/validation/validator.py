"""
Validate raw ticket dictionaries before they become domain objects.

TicketValidator has one job: decide whether a raw row is usable.
It does NOT clean data (that is DataCleaner's job) and does NOT
load files (that is CSVLoader's job).

Allowed values are derived from the model enums, so the rules have a
single source of truth (no drift between model and validator).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from src.models.ticket import Category, Priority, Status, SupportTicket


REQUIRED_FIELDS: tuple[str, ...] = (
    "id", "customer", "priority", "category", "status", "description", "created_at",
)

VALID_PRIORITIES: frozenset[str] = frozenset(p.value for p in Priority)
VALID_STATUSES: frozenset[str] = frozenset(s.value for s in Status)
# DataCleaner maps unrecognised categories to "unknown", so only presence is
# required of a row; the known set is exposed for reference.
VALID_CATEGORIES: frozenset[str] = frozenset(c.value for c in Category)


@dataclass
class ValidationResult:
    """Carry the outcome of a single-row validation check."""

    row_index: int
    is_valid: bool
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.is_valid:
            return f"Row {self.row_index}: OK"
        return f"Row {self.row_index}: INVALID — {'; '.join(self.errors)}"


def _text(row: dict, key: str) -> str:
    """Return a stripped string for ``key``; missing or None becomes ''."""
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


class TicketValidator:
    """
    Check raw ticket rows for correctness.

    Instance state: none (all rules are stateless checks).
    The class is cheap to construct and safe to reuse across datasets.
    """

    # --- public interface ----------------------------------------------------

    def validate_all(
        self, rows: Sequence[dict[str, str]]
    ) -> list[ValidationResult]:
        """Validate every row and return a result for each."""
        return [self._validate_row(i, row) for i, row in enumerate(rows, start=1)]

    def filter_valid(
        self, rows: Sequence[dict[str, str]]
    ) -> list[dict[str, str]]:
        """Return only rows that pass all validation checks."""
        return [
            row
            for row, result in zip(rows, self.validate_all(rows))
            if result.is_valid
        ]

    def __repr__(self) -> str:
        return "TicketValidator()"

    # --- private helpers -----------------------------------------------------

    def _validate_row(self, index: int, row: dict[str, str]) -> ValidationResult:
        errors: list[str] = []

        for field_name in REQUIRED_FIELDS:
            if not _text(row, field_name):
                errors.append(f"missing or empty '{field_name}'")

        priority = _text(row, "priority").lower()
        if priority and priority not in VALID_PRIORITIES:
            errors.append(
                f"unknown priority '{priority}' "
                f"(expected one of {sorted(VALID_PRIORITIES)})"
            )

        status = _text(row, "status").lower()
        if status and status not in VALID_STATUSES:
            errors.append(
                f"unknown status '{status}' "
                f"(expected one of {sorted(VALID_STATUSES)})"
            )

        created = _text(row, "created_at")
        if created:
            try:
                datetime.fromisoformat(created)
            except ValueError:
                errors.append(f"invalid created_at '{created}' (expected ISO date)")

        if len(_text(row, "description")) > SupportTicket.MAX_DESCRIPTION_LENGTH:
            errors.append(
                f"description exceeds {SupportTicket.MAX_DESCRIPTION_LENGTH} characters"
            )

        self._check_resolution_time(row, errors)
        self._check_rating(row, errors)

        return ValidationResult(row_index=index, is_valid=not errors, errors=errors)

    @staticmethod
    def _check_resolution_time(row: dict, errors: list[str]) -> None:
        raw = _text(row, "resolution_time_hours")
        if not raw:
            return  # optional column
        if "_" in raw:  # float() would silently read '2_0' as 20.0
            errors.append(f"resolution_time_hours '{raw}' is not a number")
            return
        try:
            value = float(raw)
        except ValueError:
            errors.append(f"resolution_time_hours '{raw}' is not a number")
            return
        if not math.isfinite(value):  # float() accepts 'inf' and 'nan'
            errors.append(f"resolution_time_hours '{raw}' must be finite")
        elif value < 0:
            errors.append(f"resolution_time_hours '{raw}' must not be negative")

    @staticmethod
    def _check_rating(row: dict, errors: list[str]) -> None:
        raw = _text(row, "customer_rating")
        if not raw:
            return  # optional column
        try:
            if "_" in raw:  # int() would silently accept '1_0'
                raise ValueError(raw)
            value = int(raw)  # rejects '3.5', 'nan', 'inf'
        except ValueError:
            errors.append(f"customer_rating '{raw}' must be an integer")
            return
        if not SupportTicket.MIN_RATING <= value <= SupportTicket.MAX_RATING:
            errors.append(
                f"customer_rating {value} must be between "
                f"{SupportTicket.MIN_RATING} and {SupportTicket.MAX_RATING}"
            )
