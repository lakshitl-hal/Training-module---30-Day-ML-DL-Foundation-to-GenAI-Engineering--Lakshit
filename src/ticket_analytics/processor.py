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
ACTIVE_STATUSES = {"Open", "Pending", "In Progress", "Reopened", "On Hold"}
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


def _coerce_bounded(
    series: pd.Series,
    lo: float,
    hi: float,
    *,
    lo_exclusive: bool = False,
) -> tuple[pd.Series, pd.Series]:
    """Return numeric values and an invalid mask; blank values are not invalid."""
    values = pd.to_numeric(series, errors="coerce")
    blank = series.astype("string").str.strip().eq("").fillna(True)
    invalid = (~blank & values.isna()) | (
        values.notna() & ~np.isfinite(values)
    )
    if lo_exclusive:
        invalid |= values.notna() & (values <= lo)
    else:
        invalid |= values.notna() & (values < lo)
    invalid |= values.notna() & (values > hi)
    return values.mask(invalid), invalid


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
        self._cleaned_df = self._clean(self._raw_df)
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
        except pd.errors.ParserError as exc:
            raise InvalidFileError(f"Cannot parse CSV '{self.filepath}': {exc}") from exc
        except UnicodeDecodeError as exc:
            raise InvalidFileError(
                f"CSV '{self.filepath}' is not valid UTF-8 text: {exc}"
            ) from exc
        except OSError as exc:
            raise InvalidFileError(
                f"Could not read CSV '{self.filepath}': {exc}"
            ) from exc

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
        """Clean a copy of the input and populate validation reports."""
        raw_df = df.reset_index(drop=True).copy(deep=True)
        cleaned = raw_df.copy(deep=True)
        issues: list[dict[str, Any]] = []
        id_blank, duplicate_mask = self._flag_missing_and_duplicate_ids(
            raw_df, issues
        )
        self._clean_text_fields(cleaned, raw_df, issues)
        self._normalize_labels(cleaned, raw_df, issues)
        self._clean_optional_crm_text_fields(cleaned, raw_df, issues)
        invalid_records = self._clean_numeric_fields(cleaned, raw_df, issues)
        self._clean_optional_crm_dates(cleaned, raw_df, issues)
        return self._build_validation_report(
            raw_df, cleaned, id_blank, duplicate_mask, issues, invalid_records
        )

    @staticmethod
    def _blank_mask(df: pd.DataFrame, column: str) -> pd.Series:
        return df[column].astype("string").str.strip().eq("").fillna(True)

    @staticmethod
    def _record_issue(
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
        mask: pd.Series,
        issue: str,
        issue_category: str,
        value_column: str,
        action: str,
    ) -> None:
        for position in np.flatnonzero(mask.to_numpy()):
            row = raw_df.iloc[position]
            value = row[value_column] if value_column in raw_df.columns else None
            ticket_id = row["ticket_id"]
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

    def _flag_missing_and_duplicate_ids(
        self, raw_df: pd.DataFrame, issues: list[dict[str, Any]]
    ) -> tuple[pd.Series, pd.Series]:
        id_blank = self._blank_mask(raw_df, "ticket_id") | raw_df["ticket_id"].isna()
        duplicate_ids = raw_df["ticket_id"].astype("string").str.strip()
        duplicate_mask = (~id_blank & duplicate_ids.duplicated(keep="first")).fillna(
            False
        )
        self._record_issue(
            raw_df,
            issues,
            id_blank,
            "missing_ticket_id",
            "identification",
            "ticket_id",
            "retained and flagged for follow-up",
        )
        self._record_issue(
            raw_df,
            issues,
            duplicate_mask,
            "duplicate_ticket_id",
            "duplication",
            "ticket_id",
            "dropped; first occurrence retained",
        )
        return id_blank, duplicate_mask

    def _clean_text_fields(
        self,
        cleaned: pd.DataFrame,
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
    ) -> None:
        cleaned["ticket_id"] = cleaned["ticket_id"].astype("string").str.strip()
        for column in ("category", "description", "priority", "status"):
            cleaned[column] = cleaned[column].astype("string").str.strip()
        cleaned["description"] = cleaned["description"].fillna("")

        for column, issue_category, action in (
            ("category", "categorization", "filled with Unknown"),
            ("description", "completeness", "filled with an empty string"),
            ("priority", "categorization", "filled with Unknown"),
            ("status", "categorization", "filled with Unknown"),
            ("resolution_time_hours", "completeness", "retained as missing"),
            ("customer_rating", "completeness", "retained as missing"),
        ):
            self._record_issue(
                raw_df,
                issues,
                self._blank_mask(raw_df, column),
                f"missing_{column}",
                issue_category,
                column,
                action,
            )

    @staticmethod
    def _normalize_label(values: pd.Series, aliases: dict[str, str]) -> pd.Series:
        stripped = values.astype("string").str.strip()
        return stripped.map(
            lambda value: aliases.get(value.casefold(), value.title())
            if pd.notna(value)
            else value
        )

    def _normalize_labels(
        self,
        cleaned: pd.DataFrame,
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
    ) -> None:
        normalized_category = self._normalize_label(
            raw_df["category"], CATEGORY_ALIASES
        )
        unrecognized_category = (
            ~self._blank_mask(raw_df, "category")
            & ~normalized_category.isin(VALID_CATEGORIES)
        ).fillna(False)
        self._record_issue(
            raw_df,
            issues,
            unrecognized_category,
            "unrecognized_category",
            "categorization",
            "category",
            "retained and flagged for review",
        )
        cleaned["category"] = normalized_category.replace("", "Unknown").fillna(
            "Unknown"
        )

        if "channel" in raw_df.columns:
            normalized_channel = (
                raw_df["channel"].astype("string").str.strip().str.title()
            )
            unrecognized_channel = (
                ~self._blank_mask(raw_df, "channel")
                & ~normalized_channel.isin(VALID_CHANNELS)
            ).fillna(False)
            self._record_issue(
                raw_df,
                issues,
                unrecognized_channel,
                "unrecognized_channel",
                "categorization",
                "channel",
                "retained and flagged for review",
            )

        for column, aliases, allowed_values in (
            ("priority", PRIORITY_ALIASES, VALID_PRIORITIES),
            ("status", STATUS_ALIASES, VALID_STATUSES),
        ):
            normalized = self._normalize_label(raw_df[column], aliases)
            unrecognized = (
                ~self._blank_mask(raw_df, column)
                & ~normalized.isin(allowed_values)
            ).fillna(False)
            self._record_issue(
                raw_df,
                issues,
                unrecognized,
                f"unrecognized_{column}",
                "categorization",
                column,
                "retained and flagged for review",
            )
            cleaned[column] = normalized.replace("", "Unknown").fillna("Unknown")

    def _clean_optional_crm_text_fields(
        self,
        cleaned: pd.DataFrame,
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
    ) -> None:
        for column in CRM_TEXT_COLUMNS:
            if column not in raw_df.columns:
                continue
            missing = self._blank_mask(raw_df, column) | raw_df[column].isna()
            self._record_issue(
                raw_df,
                issues,
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "filled with Unknown",
            )
            values = raw_df[column].astype("string").str.strip()
            cleaned[column] = (
                values.str.title().replace("", "Unknown").fillna("Unknown")
                if column == "channel"
                else values.replace("", "Unknown").fillna("Unknown")
            )

    def _clean_numeric_fields(
        self,
        cleaned: pd.DataFrame,
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        invalid_records: list[dict[str, Any]] = []
        core_fields = (
            ("resolution_time_hours", 0, MAX_RESOLUTION_HOURS, True),
            ("customer_rating", RATING_MIN, RATING_MAX, False),
        )
        for column, lower, upper, lower_exclusive in core_fields:
            values, invalid = _coerce_bounded(
                raw_df[column], lower, upper, lo_exclusive=lower_exclusive
            )
            self._record_issue(
                raw_df,
                issues,
                invalid,
                f"invalid_{column}",
                "numeric_validity",
                column,
                "replaced with missing value",
            )
            if invalid.any():
                bad_ids = cleaned.loc[invalid, "ticket_id"].tolist()
                bad_values = raw_df.loc[invalid, column].tolist()
                logger.warning(
                    "Invalid %s for ticket(s) %s (values: %s) — set to NaN.",
                    column,
                    bad_ids,
                    bad_values,
                )
                invalid_records.append(
                    {
                        "rule": f"invalid_{column}",
                        "ticket_ids": bad_ids,
                        "original_values": bad_values,
                        "action": "replaced with NaN",
                    }
                )
            cleaned[column] = values

        for column in CRM_NUMERIC_COLUMNS:
            if column not in raw_df.columns:
                continue
            missing = self._blank_mask(raw_df, column) | raw_df[column].isna()
            self._record_issue(
                raw_df,
                issues,
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "retained as missing",
            )
            if column == "first_response_time_hours":
                values, invalid = _coerce_bounded(
                    raw_df[column], 0, MAX_RESOLUTION_HOURS
                )
            else:
                values = pd.to_numeric(raw_df[column], errors="coerce")
                invalid = ~missing & values.isna()
                invalid |= values.notna() & ~np.isfinite(values)
                invalid |= values.notna() & ((values < 0) | (values % 1 != 0))
            self._record_issue(
                raw_df,
                issues,
                invalid,
                f"invalid_{column}",
                "numeric_validity",
                column,
                "replaced with missing value",
            )
            values = values.mask(invalid)
            cleaned[column] = (
                values.astype("Int64")
                if column == "reopen_count"
                else values.astype(float)
            )

        return invalid_records

    def _clean_optional_crm_dates(
        self,
        cleaned: pd.DataFrame,
        raw_df: pd.DataFrame,
        issues: list[dict[str, Any]],
    ) -> None:
        for column in CRM_DATETIME_COLUMNS:
            if column not in raw_df.columns:
                continue
            missing = self._blank_mask(raw_df, column) | raw_df[column].isna()
            self._record_issue(
                raw_df,
                issues,
                missing,
                f"missing_{column}",
                "completeness",
                column,
                "retained as missing",
            )
            parsed = pd.to_datetime(
                raw_df[column], errors="coerce", utc=True, format="mixed"
            )
            self._record_issue(
                raw_df,
                issues,
                ~missing & parsed.isna(),
                f"invalid_{column}",
                "temporal_validity",
                column,
                "retained as missing",
            )
            cleaned[column] = parsed

        if {"created_at", "updated_at"} <= set(cleaned.columns):
            invalid_order = (
                cleaned["created_at"].notna()
                & cleaned["updated_at"].notna()
                & (cleaned["updated_at"] < cleaned["created_at"])
            )
            self._record_issue(
                raw_df,
                issues,
                invalid_order,
                "updated_before_created",
                "temporal_consistency",
                "updated_at",
                "retained and flagged for review",
            )

    def _build_validation_report(
        self,
        raw_df: pd.DataFrame,
        cleaned: pd.DataFrame,
        id_blank: pd.Series,
        duplicate_mask: pd.Series,
        issues: list[dict[str, Any]],
        invalid_records: list[dict[str, Any]],
    ) -> pd.DataFrame:
        self.quality_issues = pd.DataFrame(issues, columns=self.quality_issues.columns)
        self.validation_report = {
            "rows_in_raw": len(raw_df),
            "rows_after_cleaning": int(len(cleaned) - duplicate_mask.sum()),
            "missing_values_per_column": cleaned.isna().sum().astype(int).to_dict(),
            "raw_missing_values_per_column": {
                column: int(
                    (self._blank_mask(raw_df, column) | raw_df[column].isna()).sum()
                )
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
            "invalid_records": invalid_records,
        }
        kept = cleaned.loc[~duplicate_mask].copy()
        logger.info("Cleaning complete. %d → %d row(s).", len(raw_df), len(kept))
        return kept.reset_index(drop=True)
