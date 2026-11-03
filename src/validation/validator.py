"""
Validate raw ticket dictionaries before they become domain objects.

TicketValidator has one job: decide whether a raw row is usable.
It does NOT clean data (that is DataCleaner's job) and does NOT
load files (that is CSVLoader's job).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"id", "customer", "priority", "category", "status", "description", "created_at"}
)

VALID_PRIORITIES: frozenset[str] = frozenset({"low", "medium", "high", "urgent"})
VALID_STATUSES: frozenset[str] = frozenset({"open", "pending", "resolved", "closed"})


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

        # Check required fields are present and non-empty
        for field_name in REQUIRED_FIELDS:
            if not row.get(field_name, "").strip():
                errors.append(f"missing or empty '{field_name}'")

        # Check priority is a known value (after stripping)
        priority = row.get("priority", "").strip().lower()
        if priority and priority not in VALID_PRIORITIES:
            errors.append(
                f"unknown priority '{priority}' "
                f"(expected one of {sorted(VALID_PRIORITIES)})"
            )

        # Check status is a known value
        status = row.get("status", "").strip().lower()
        if status and status not in VALID_STATUSES:
            errors.append(
                f"unknown status '{status}' "
                f"(expected one of {sorted(VALID_STATUSES)})"
            )

        return ValidationResult(
            row_index=index,
            is_valid=len(errors) == 0,
            errors=errors,
        )
