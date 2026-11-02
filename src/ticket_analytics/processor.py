"""
processor.py
====================
TicketDataProcessor — loads, validates, and cleans a support-ticket CSV.

Cleaning rules (documented explicitly so every decision is traceable):
  1. Missing `ticket_id`       → row retained and flagged for follow-up.
  2. Duplicate `ticket_id`     → keep the FIRST occurrence, drop subsequent duplicates.
                                 Rationale: first record is assumed to be the canonical entry;
                                 later duplicates are likely re-submissions or logging errors.
                                 All duplicate IDs are logged for audit.
  3. Missing `category`        → filled with the sentinel string "Unknown".
                                 Rationale: category is used for grouping; losing the row
                                 discards valid resolution/rating data unnecessarily.
  4. Missing `description`     → filled with empty string ""; downstream NLP handles absence.
  5. `resolution_time_hours`   → coerced to float; values ≤ 0 or implausibly large (> 720 h,
                                 i.e., > 30 days) are replaced with NaN and flagged as invalid.
  6. `customer_rating`         → coerced to float; valid range [1.0, 5.0]; out-of-range values
                                 replaced with NaN and flagged.
  7. `priority` / `status`     → whitespace-stripped, title-cased for consistency; missing
                                 values filled with "Unknown".
  8. Raw input file is NEVER modified; cleaning always returns a new DataFrame.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────────────────────

class TicketProcessingError(Exception):
    """Base exception for all ticket-processing failures."""


class MissingColumnsError(TicketProcessingError):
    """Raised when required columns are absent from the CSV."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            f"Required column(s) missing from CSV: {missing}. "
            "Check the file header row."
        )


class EmptyDatasetError(TicketProcessingError):
    """Raised when the CSV contains no data rows."""


class InvalidFileError(TicketProcessingError):
    """Raised when the file cannot be parsed as a CSV."""


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

REQUIRED_COLUMNS: list[str] = [
    "ticket_id",
    "category",
    "priority",
    "description",
    "resolution_time_hours",
    "customer_rating",
    "status",
]

MAX_RESOLUTION_HOURS: float = 720.0   # 30 days
RATING_MIN: float = 1.0
RATING_MAX: float = 5.0
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_CATEGORIES = {
    "Account",
    "Billing",
    "Product",
    "Shipping",
    "Technical",
    "Unknown",
}
VALID_CHANNELS = {"Email", "Chat", "Phone", "Web Form", "Social"}
VALID_STATUSES = {
    "Open",
    "Pending",
    "In Progress",
    "Reopened",
    "On Hold",
    "Resolved",
    "Closed",
}
PRIORITY_ALIASES = {
    "p1": "Critical",
    "urgent": "Critical",
    "p2": "High",
    "normal": "Medium",
    "p3": "Medium",
    "p4": "Low",
}
CATEGORY_ALIASES = {
    "account services": "Account",
    "payments": "Billing",
    "payment": "Billing",
    "tech": "Technical",
    "tech support": "Technical",
    "delivery": "Shipping",
    "logistics": "Shipping",
}
STATUS_ALIASES = {
    "new": "Open",
    "working": "In Progress",
    "in progress": "In Progress",
    "re-opened": "Reopened",
    "reopened": "Reopened",
    "on hold": "On Hold",
    "solved": "Resolved",
    "complete": "Resolved",
    "completed": "Resolved",
}
CRM_TEXT_COLUMNS = ("customer_id", "channel", "assigned_team")
CRM_NUMERIC_COLUMNS = ("first_response_time_hours", "reopen_count")
CRM_DATETIME_COLUMNS = ("created_at", "updated_at")


# ──────────────────────────────────────────────────────────────
# TicketDataProcessor
# ──────────────────────────────────────────────────────────────

class TicketDataProcessor:
    """
    Loads, validates, and cleans a support-ticket CSV.

    Usage
    -----
    >>> processor = TicketDataProcessor("data/tickets.csv")
    >>> cleaned_df = processor.process()
    >>> report = processor.validation_report
    """

    def __init__(self, filepath: str | Path) -> None:
        self.filepath = Path(filepath)
        self._raw_df: pd.DataFrame | None = None
        self._cleaned_df: pd.DataFrame | None = None
        self.validation_report: dict[str, Any] = {}
        self.quality_issues = pd.DataFrame(
            columns=[
                "source_row",
                "ticket_id",
                "category",
                "priority",
                "status",
                "issue_category",
                "issue",
                "value",
                "action",
            ]
        )

    # ── Public API ─────────────────────────────────────────────

    def process(self) -> pd.DataFrame:
        """
        Run the full pipeline: load → validate → clean.

        Returns
        -------
        pd.DataFrame
            A cleaned copy of the data. The raw file and the in-memory
            raw DataFrame are left untouched.

        Raises
        ------
        InvalidFileError
            If the file does not exist or cannot be parsed.
        MissingColumnsError
            If required columns are absent.
        EmptyDatasetError
            If the file contains no data rows.
        """
        self._raw_df = self._load_csv()
        self._validate_columns(self._raw_df)
        self._validate_not_empty(self._raw_df)
        self._cleaned_df = self._clean(self._raw_df.copy())
        return self._cleaned_df

    @property
    def raw(self) -> pd.DataFrame | None:
        """The original, unmodified DataFrame (available after process())."""
        return self._raw_df

    @property
    def cleaned(self) -> pd.DataFrame | None:
        """The cleaned DataFrame (available after process())."""
        return self._cleaned_df

    # ── Private helpers ────────────────────────────────────────

    def _load_csv(self) -> pd.DataFrame:
        """Read the CSV from disk. Raises InvalidFileError on any I/O or parse error."""
        if not self.filepath.exists():
            raise InvalidFileError(f"File not found: {self.filepath}")
        try:
            df = pd.read_csv(self.filepath, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError as exc:
            raise EmptyDatasetError("The CSV file is completely empty.") from exc
        except Exception as exc:
            raise InvalidFileError(f"Cannot parse CSV: {exc}") from exc

        logger.info("Loaded %d row(s) from '%s'.", len(df), self.filepath)
        return df

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Raise MissingColumnsError if any required column is absent."""
        actual = set(df.columns)
        missing = [col for col in REQUIRED_COLUMNS if col not in actual]
        if missing:
            raise MissingColumnsError(missing)

    def _validate_not_empty(self, df: pd.DataFrame) -> None:
        """Raise EmptyDatasetError if the DataFrame has zero rows."""
        if df.empty:
            raise EmptyDatasetError(
                "The CSV file has the correct header but contains no data rows."
            )

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all cleaning rules in sequence and populate validation_report."""
        raw_df = df.copy(deep=True).reset_index(drop=True)
        df = df.copy(deep=True)
        df.index = raw_df.index
        row_count = len(raw_df)
        original_ids = raw_df["ticket_id"].copy()
        issues: list[dict[str, Any]] = []

        def record_issue(
            mask: pd.Series,
            issue: str,
            issue_category: str,
            value_column: str,
            action: str,
        ) -> None:
            for position in np.flatnonzero(mask.to_numpy()):
                row = raw_df.iloc[position]
                value = row[value_column] if value_column in raw_df.columns else None
                ticket_id = original_ids.iloc[position]
                issues.append(
                    {
                        "source_row": int(position) + 2,
                        "ticket_id": None if pd.isna(ticket_id) else str(ticket_id),
                        "category": (
                            "Unknown"
                            if pd.isna(row["category"]) or not str(row["category"]).strip()
                            else str(row["category"]).strip()
                        ),
                        "priority": (
                            "Unknown"
                            if pd.isna(row["priority"]) or not str(row["priority"]).strip()
                            else str(row["priority"]).strip().title()
                        ),
                        "status": (
                            "Unknown"
                            if pd.isna(row["status"]) or not str(row["status"]).strip()
                            else str(row["status"]).strip().title()
                        ),
                        "issue_category": issue_category,
                        "issue": issue,
                        "value": None if pd.isna(value) else str(value),
                        "action": action,
                    }
                )

        def blank_mask(column: str) -> pd.Series:
            return raw_df[column].astype("string").str.strip().eq("").fillna(True)

        id_blank = blank_mask("ticket_id") | raw_df["ticket_id"].isna()
        duplicate_ids = raw_df["ticket_id"].astype("string").str.strip()
        duplicate_mask = (
            ~id_blank & duplicate_ids.duplicated(keep="first")
        ).fillna(False)
        record_issue(
            id_blank,
            "missing_ticket_id",
            "identification",
            "ticket_id",
            "retained and flagged for follow-up",
        )
        record_issue(
            duplicate_mask,
            "duplicate_ticket_id",
            "duplication",
            "ticket_id",
            "dropped; first occurrence retained",
        )

        df["ticket_id"] = df["ticket_id"].astype("string").str.strip()
        for column in ("category", "description", "priority", "status"):
            df[column] = df[column].astype("string").str.strip()

        category_missing = blank_mask("category")
        description_missing = blank_mask("description")
        priority_missing = blank_mask("priority")
        status_missing = blank_mask("status")
        for column, mask, category in (
            ("category", category_missing, "categorization"),
            ("description", description_missing, "completeness"),
            ("priority", priority_missing, "categorization"),
            ("status", status_missing, "categorization"),
            ("resolution_time_hours", blank_mask("resolution_time_hours"), "completeness"),
            ("customer_rating", blank_mask("customer_rating"), "completeness"),
        ):
            record_issue(
                mask,
                f"missing_{column}",
                category,
                column,
                (
                    "filled with Unknown"
                    if column in {"category", "priority", "status"}
                    else "filled with an empty string"
                    if column == "description"
                    else "retained as missing"
                ),
            )

        def normalize_labels(
            values: pd.Series, aliases: dict[str, str]
        ) -> pd.Series:
            stripped = values.astype("string").str.strip()
            return stripped.map(
                lambda value: aliases.get(value.casefold(), value.title())
                if pd.notna(value)
                else value
            )

        normalized_category = normalize_labels(
            raw_df["category"], CATEGORY_ALIASES
        )
        normalized_priority = normalize_labels(
            raw_df["priority"], PRIORITY_ALIASES
        )
        normalized_status = normalize_labels(raw_df["status"], STATUS_ALIASES)
        categorical_values = [
            ("category", normalized_category, VALID_CATEGORIES)
        ]
        if "channel" in raw_df.columns:
            categorical_values.append(
                (
                    "channel",
                    raw_df["channel"].astype("string").str.strip().str.title(),
                    VALID_CHANNELS,
                )
            )
        for column, normalized, allowed_values in categorical_values:
            unrecognized = (
                ~blank_mask(column)
                & ~normalized.isin(allowed_values)
            ).fillna(False)
            record_issue(
                unrecognized,
                f"unrecognized_{column}",
                "categorization",
                column,
                "retained and flagged for review",
            )

        for column, normalized, allowed_values in (
            ("priority", normalized_priority, VALID_PRIORITIES),
            ("status", normalized_status, VALID_STATUSES),
        ):
            unrecognized = (
                ~blank_mask(column)
                & ~normalized.isin(allowed_values)
            ).fillna(False)
            record_issue(
                unrecognized,
                f"unrecognized_{column}",
                "categorization",
                column,
                "retained and flagged for review",
            )

        df["category"] = normalized_category.replace("", "Unknown").fillna("Unknown")
        df["description"] = df["description"].replace("", "").fillna("")
        df["priority"] = normalized_priority.replace("", "Unknown").fillna("Unknown")
        df["status"] = normalized_status.replace("", "Unknown").fillna("Unknown")

        for column in CRM_TEXT_COLUMNS:
            if column not in df.columns:
                continue
            missing = blank_mask(column) | raw_df[column].isna()
            record_issue(
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "filled with Unknown",
            )
            values = (
                df[column].astype("string").str.strip()
                .replace("", "Unknown")
                .fillna("Unknown")
            )
            df[column] = (
                raw_df[column].astype("string").str.strip().str.title()
                .replace("", "Unknown").fillna("Unknown")
                if column == "channel"
                else values
            )

        for column, rule in (
            ("resolution_time_hours", "resolution_time_hours"),
            ("customer_rating", "customer_rating"),
        ):
            numeric = pd.to_numeric(raw_df[column], errors="coerce")
            missing = blank_mask(column) | raw_df[column].isna()
            invalid = ~missing & numeric.isna()
            if column == "resolution_time_hours":
                invalid |= numeric.notna() & (
                    (numeric <= 0) | (numeric > MAX_RESOLUTION_HOURS)
                )
            else:
                invalid |= numeric.notna() & (
                    (numeric < RATING_MIN) | (numeric > RATING_MAX)
                )
            record_issue(
                invalid,
                f"invalid_{rule}",
                "numeric_validity",
                column,
                "replaced with missing value",
            )

        df, resolution_issues = self._clean_resolution_time(df)
        df, rating_issues = self._clean_customer_rating(df)

        for column in CRM_NUMERIC_COLUMNS:
            if column not in df.columns:
                continue
            values = pd.to_numeric(raw_df[column], errors="coerce")
            missing = blank_mask(column) | raw_df[column].isna()
            record_issue(
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "retained as missing",
            )
            invalid = ~missing & values.isna()
            invalid |= values.notna() & ~np.isfinite(values)
            if column == "first_response_time_hours":
                invalid |= values.notna() & ((values < 0) | (values > MAX_RESOLUTION_HOURS))
            else:
                invalid |= values.notna() & ((values < 0) | (values % 1 != 0))
            record_issue(
                invalid,
                f"invalid_{column}",
                "numeric_validity",
                column,
                "replaced with missing value",
            )
            values = values.mask(invalid)
            df[column] = (
                values.astype("Int64")
                if column == "reopen_count"
                else values.astype(float)
            )

        for column in CRM_DATETIME_COLUMNS:
            if column not in df.columns:
                continue
            missing = blank_mask(column) | raw_df[column].isna()
            record_issue(
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "retained as missing",
            )
            parsed = pd.to_datetime(
                raw_df[column], errors="coerce", utc=True, format="mixed"
            )
            invalid = ~missing & parsed.isna()
            record_issue(
                invalid,
                f"invalid_{column}",
                "temporal_validity",
                column,
                "retained as missing",
            )
            df[column] = parsed

        if {"created_at", "updated_at"} <= set(df.columns):
            invalid_order = (
                df["created_at"].notna()
                & df["updated_at"].notna()
                & (df["updated_at"] < df["created_at"])
            )
            record_issue(
                invalid_order,
                "updated_before_created",
                "temporal_consistency",
                "updated_at",
                "retained and flagged for review",
            )

        missing_after_cleaning = df.isna().sum().astype(int).to_dict()
        self.quality_issues = pd.DataFrame(issues, columns=self.quality_issues.columns)
        self.validation_report = {
            "rows_in_raw": row_count,
            "rows_after_cleaning": int(len(df) - duplicate_mask.sum()),
            "missing_values_per_column": missing_after_cleaning,
            "raw_missing_values_per_column": {
                column: int((blank_mask(column) | raw_df[column].isna()).sum())
                for column in raw_df.columns
            },
            "missing_ticket_id_count": int(id_blank.sum()),
            "duplicate_ticket_id_count": int(duplicate_mask.sum()),
            "issue_count": len(issues),
            "issue_counts_by_category": (
                self.quality_issues["issue_category"].value_counts().to_dict()
                if issues
                else {}
            ),
            "invalid_records": resolution_issues + rating_issues,
        }

        kept = df.loc[~duplicate_mask].copy()
        logger.info(
            "Cleaning complete. %d → %d row(s).",
            row_count,
            len(kept),
        )
        return kept.reset_index(drop=True)

    def _clean_resolution_time(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[dict]]:
        """
        Coerce resolution_time_hours to float.
        Set to NaN when value is non-numeric, <= 0, or > MAX_RESOLUTION_HOURS.
        """
        invalids: list[dict] = []
        col = "resolution_time_hours"

        # Coerce; non-numeric → NaN
        numeric = pd.to_numeric(df[col], errors="coerce")

        missing = df[col].astype(str).str.strip() == ""
        invalid = (~missing & numeric.isna()) | (
            numeric.notna()
            & ((numeric <= 0) | (numeric > MAX_RESOLUTION_HOURS))
        )
        if invalid.any():
            bad_ids = df.loc[invalid, "ticket_id"].tolist()
            bad_vals = df.loc[invalid, col].tolist()
            logger.warning(
                "Invalid %s for ticket(s) %s (values: %s) — set to NaN.",
                col, bad_ids, bad_vals,
            )
            invalids.append({
                "rule": f"invalid_{col}",
                "ticket_ids": bad_ids,
                "original_values": bad_vals,
                "action": "replaced with NaN",
            })
            numeric[invalid] = np.nan

        df[col] = numeric
        return df, invalids

    def _clean_customer_rating(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[dict]]:
        """
        Coerce customer_rating to float.
        Set to NaN when value is non-numeric or outside [RATING_MIN, RATING_MAX].
        """
        invalids: list[dict] = []
        col = "customer_rating"

        numeric = pd.to_numeric(df[col], errors="coerce")

        missing = df[col].astype(str).str.strip() == ""
        invalid = (~missing & numeric.isna()) | (
            numeric.notna() & ((numeric < RATING_MIN) | (numeric > RATING_MAX))
        )
        if invalid.any():
            bad_ids = df.loc[invalid, "ticket_id"].tolist()
            bad_vals = df.loc[invalid, col].tolist()
            logger.warning(
                "Invalid %s for ticket(s) %s (values: %s) — set to NaN.",
                col, bad_ids, bad_vals,
            )
            invalids.append({
                "rule": f"invalid_{col}",
                "ticket_ids": bad_ids,
                "original_values": bad_vals,
                "action": "replaced with NaN",
            })
            numeric[invalid] = np.nan

        df[col] = numeric
        return df, invalids
