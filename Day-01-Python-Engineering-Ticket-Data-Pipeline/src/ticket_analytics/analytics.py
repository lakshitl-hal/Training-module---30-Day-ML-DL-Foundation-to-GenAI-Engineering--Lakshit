"""Analytics and CSV exports for cleaned support-ticket data."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ticket_analytics.processor import ACTIVE_STATUSES


def _normalized_labels(df: pd.DataFrame, column: str) -> pd.Series:
    return (
        df[column]
        .astype("string")
        .str.strip()
        .replace("", "Unknown")
        .fillna("Unknown")
    )


def _count_by(df: pd.DataFrame, column: str) -> dict[str, int]:
    counts = _normalized_labels(df, column).value_counts().to_dict()
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def count_tickets_by_priority(df: pd.DataFrame) -> dict[str, int]:
    """Count tickets by priority, including missing priorities as Unknown."""
    return _count_by(df, "priority")


def count_tickets_by_category(df: pd.DataFrame) -> dict[str, int]:
    """Count tickets by category, including missing categories as Unknown."""
    return _count_by(df, "category")


def count_tickets_by_status(df: pd.DataFrame) -> dict[str, int]:
    """Count tickets by status, including missing statuses as Unknown."""
    return _count_by(df, "status")


def _count_optional_dimension(df: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in df.columns:
        return {}
    return _count_by(df, column)


def average_resolution_time_by_category(
    df: pd.DataFrame,
) -> dict[str, float | None]:
    """Calculate average valid resolution time for each ticket category."""
    grouped = (
        df.assign(category=_normalized_labels(df, "category"))
        .groupby("category", dropna=False)["resolution_time_hours"]
        .mean()
        .round(2)
    )
    return {
        str(category): (None if pd.isna(average) else float(average))
        for category, average in grouped.items()
    }


def average_customer_rating(df: pd.DataFrame) -> float | None:
    """Calculate mean customer rating, returning None when no ratings exist."""
    valid = df["customer_rating"].dropna()
    if valid.empty:
        return None
    return round(float(valid.mean()), 2)


def count_unresolved_tickets(df: pd.DataFrame) -> int:
    """Count active lifecycle statuses; unrecognized statuses remain separately reported."""
    statuses = df["status"].astype("string").str.strip().str.title()
    return int(statuses.isin(ACTIVE_STATUSES).sum())


def missing_value_summary(df: pd.DataFrame) -> dict[str, int]:
    """Count null and whitespace-only values in each column."""
    missing = df.isnull().sum()
    for column in df.select_dtypes(include=["object", "string"]).columns:
        blank = df[column].notna() & df[column].astype("string").str.strip().eq("")
        missing[column] += int(blank.sum())
    return {
        str(column): int(count)
        for column, count in missing.items()
        if count > 0
    }


def build_data_quality_summary(validation_report: dict[str, Any]) -> dict[str, Any]:
    """Summarize raw missing values and invalid or duplicate record counts."""
    invalid_records = {
        record["rule"]: len(record["ticket_ids"])
        for record in validation_report["invalid_records"]
    }
    return {
        "missing_values_raw": validation_report["raw_missing_values_per_column"],
        "invalid_records": invalid_records,
        "duplicate_ticket_ids": validation_report["duplicate_ticket_id_count"],
        "missing_ticket_ids": validation_report["missing_ticket_id_count"],
    }


def build_analytics_report(df: pd.DataFrame) -> dict[str, Any]:
    """Aggregate summary metrics and category, priority, and status distributions."""
    average_resolution = (
        round(float(df["resolution_time_hours"].mean()), 2)
        if df["resolution_time_hours"].notna().any()
        else None
    )
    statuses = df["status"].astype("string").str.strip().str.casefold()
    first_response = (
        pd.to_numeric(df["first_response_time_hours"], errors="coerce")
        if "first_response_time_hours" in df.columns
        else pd.Series(dtype=float)
    )
    reopen_count = (
        pd.to_numeric(df["reopen_count"], errors="coerce").fillna(0)
        if "reopen_count" in df.columns
        else pd.Series(dtype=float)
    )

    return {
        "total_tickets": int(len(df)),
        "avg_resolution_time_hours": average_resolution,
        "avg_customer_rating": average_customer_rating(df),
        "open_count": int(statuses.eq("open").sum()),
        "unresolved_count": count_unresolved_tickets(df),
        "avg_first_response_time_hours": (
            round(float(first_response.mean()), 2)
            if first_response.notna().any()
            else None
        ),
        "tickets_reopened_count": int(reopen_count.gt(0).sum()),
        "total_reopen_count": int(reopen_count.sum()),
        "missing_values": missing_value_summary(df),
        "tickets_by_category": count_tickets_by_category(df),
        "tickets_by_priority": count_tickets_by_priority(df),
        "tickets_by_status": count_tickets_by_status(df),
        "tickets_by_channel": _count_optional_dimension(df, "channel"),
        "tickets_by_assigned_team": _count_optional_dimension(df, "assigned_team"),
        "avg_resolution_by_category": average_resolution_time_by_category(df),
        "avg_first_response_by_channel": (
            {
                str(channel): (
                    round(float(average), 2) if pd.notna(average) else None
                )
                for channel, average in df.assign(
                    first_response_time_hours=first_response,
                    channel=_normalized_labels(df, "channel"),
                )
                .groupby("channel")["first_response_time_hours"]
                .mean()
                .round(2)
                .items()
            }
            if "channel" in df.columns
            else {}
        ),
    }
