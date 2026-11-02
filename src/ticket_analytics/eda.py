"""Raw-data profiling and quality checks for support-ticket CSV datasets."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ticket_analytics.processor import (
    MAX_RESOLUTION_HOURS,
    RATING_MAX,
    RATING_MIN,
    REQUIRED_COLUMNS,
)

MISSING_TOKENS = {"", "na", "n/a", "nan", "none", "null"}
NUMERIC_COLUMNS = {"resolution_time_hours", "customer_rating"}


def _missing_mask(values: pd.Series) -> pd.Series:
    normalized = values.astype("string").str.strip().str.lower()
    return (values.isna() | normalized.isin(MISSING_TOKENS)).fillna(True)


def _numeric_profile(values: pd.Series, missing: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(values.mask(missing), errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    valid = numeric.dropna()
    if valid.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "q1": None,
            "q3": None,
            "max": None,
            "iqr_outlier_count": 0,
            "non_numeric_count": int((~missing & numeric.isna()).sum()),
        }

    q1 = float(valid.quantile(0.25))
    q3 = float(valid.quantile(0.75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    return {
        "count": int(valid.size),
        "mean": round(float(valid.mean()), 3),
        "median": round(float(valid.median()), 3),
        "std": round(float(valid.std()), 3) if valid.size > 1 else None,
        "min": round(float(valid.min()), 3),
        "q1": round(q1, 3),
        "q3": round(q3, 3),
        "max": round(float(valid.max()), 3),
        "iqr_outlier_count": int(
            ((valid < lower_bound) | (valid > upper_bound)).sum()
        ),
        "non_numeric_count": int((~missing & numeric.isna()).sum()),
    }


def _row_examples(
    df: pd.DataFrame,
    mask: pd.Series,
    value_column: str,
    limit: int,
) -> list[dict[str, Any]]:
    examples = []
    for position in np.flatnonzero(mask.to_numpy())[:limit]:
        row = df.iloc[position]
        example: dict[str, Any] = {"row": int(position) + 2}
        if "ticket_id" in df.columns:
            example["ticket_id"] = str(row["ticket_id"])
        if value_column in df.columns:
            value = row[value_column]
            example["value"] = None if pd.isna(value) else str(value)
        examples.append(example)
    return examples


def build_eda_report(df: pd.DataFrame, top_n: int = 10) -> dict[str, Any]:
    """Build JSON-serializable dataset, distribution, and data-quality profiles."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    rows, columns = df.shape
    profiles: dict[str, Any] = {}
    numeric_columns: dict[str, pd.Series] = {}
    categorical_columns: dict[str, dict[str, Any]] = {}

    for column in df.columns:
        values = df[column]
        missing = _missing_mask(values)
        non_missing_count = int((~missing).sum())
        converted = pd.to_numeric(values.mask(missing), errors="coerce")
        is_numeric = (
            column in NUMERIC_COLUMNS
            or (
                non_missing_count > 0
                and int(converted.notna().sum()) / non_missing_count >= 0.8
            )
        )
        profiles[column] = {
            "dtype": str(values.dtype),
            "non_missing_count": non_missing_count,
            "missing_count": int(missing.sum()),
            "missing_percent": round(float(missing.mean() * 100), 2)
            if rows
            else 0.0,
            "unique_count": int(values.mask(missing).nunique()),
        }

        if is_numeric:
            numeric_columns[column] = converted
            profiles[column]["numeric"] = _numeric_profile(values, missing)
        else:
            counts = values.mask(missing).astype("string").value_counts().head(top_n)
            categorical_columns[column] = {
                "unique_count": int(values.mask(missing).nunique()),
                "top_values": [
                    {"value": str(value), "count": int(count)}
                    for value, count in counts.items()
                ],
            }

    issues: dict[str, Any] = {
        "missing_required_columns": [
            column for column in REQUIRED_COLUMNS if column not in df.columns
        ],
        "duplicate_rows": int(df.duplicated().sum()),
    }

    if "ticket_id" in df.columns:
        id_missing = _missing_mask(df["ticket_id"])
        duplicate_ids = df.loc[
            ~id_missing & df["ticket_id"].duplicated(keep=False), "ticket_id"
        ]
        issues["missing_ticket_ids"] = int(id_missing.sum())
        issues["missing_ticket_id_examples"] = _row_examples(
            df, id_missing, "ticket_id", top_n
        )
        issues["duplicate_ticket_id_rows"] = int(len(duplicate_ids))
        issues["duplicate_ticket_ids"] = [
            str(value) for value in duplicate_ids.drop_duplicates().head(top_n)
        ]

    for column in ("category", "description", "priority", "status"):
        if column in df.columns:
            issues[f"blank_{column}_rows"] = int(_missing_mask(df[column]).sum())

    if "resolution_time_hours" in df.columns:
        values = df["resolution_time_hours"]
        missing = _missing_mask(values)
        numeric = pd.to_numeric(values.mask(missing), errors="coerce")
        invalid = (~missing & numeric.isna()) | (
            numeric.notna()
            & ((numeric <= 0) | (numeric > MAX_RESOLUTION_HOURS))
        )
        issues["invalid_resolution_time_rows"] = int(invalid.sum())
        issues["invalid_resolution_time_examples"] = _row_examples(
            df, invalid, "resolution_time_hours", top_n
        )

    if "customer_rating" in df.columns:
        values = df["customer_rating"]
        missing = _missing_mask(values)
        numeric = pd.to_numeric(values.mask(missing), errors="coerce")
        invalid = (~missing & numeric.isna()) | (
            numeric.notna() & ((numeric < RATING_MIN) | (numeric > RATING_MAX))
        )
        issues["invalid_customer_rating_rows"] = int(invalid.sum())
        issues["invalid_customer_rating_examples"] = _row_examples(
            df, invalid, "customer_rating", top_n
        )

    correlations: dict[str, dict[str, float | None]] = {}
    if len(numeric_columns) > 1:
        numeric_frame = pd.DataFrame(numeric_columns).replace(
            [np.inf, -np.inf], np.nan
        )
        correlation_frame = numeric_frame.corr()
        for column in correlation_frame.columns:
            correlations[column] = {
                other: (
                    round(float(correlation_frame.loc[column, other]), 3)
                    if pd.notna(correlation_frame.loc[column, other])
                    else None
                )
                for other in correlation_frame.columns
            }

    report: dict[str, Any] = {
        "dataset": {"rows": int(rows), "columns": int(columns)},
        "column_profiles": profiles,
        "categorical_distributions": categorical_columns,
        "numeric_correlations": correlations,
        "data_quality_issues": issues,
        "notes": [
            "IQR outliers are review candidates, not automatically invalid records.",
            "Quality checks describe the raw input before cleaning.",
        ],
    }

    if "created_at" in df.columns:
        dates = pd.to_datetime(
            df["created_at"], errors="coerce", format="mixed", utc=True
        ).dt.tz_localize(None)
        valid_dates = dates.dropna()
        report["time_series"] = {
            "valid_dates": int(valid_dates.size),
            "invalid_dates": int(dates.isna().sum()),
            "monthly_ticket_counts": {
                str(month): int(count)
                for month, count in valid_dates.dt.to_period("M")
                .value_counts()
                .sort_index()
                .items()
            },
        }

    return report
