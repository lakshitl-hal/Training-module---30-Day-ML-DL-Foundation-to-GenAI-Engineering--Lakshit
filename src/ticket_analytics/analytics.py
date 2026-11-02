"""Analytics and CSV exports for cleaned support-ticket data."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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
    statuses = df["status"].astype("string").str.strip().str.casefold()
    return int(
        statuses.isin({"open", "pending", "in progress", "reopened", "on hold"}).sum()
    )


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


def export_pipeline_outputs(
    report: dict[str, Any],
    quality_issues: pd.DataFrame,
    output_dir: str | Path,
) -> list[Path]:
    """Export the analytics summary, grouped tables, and quality issue details."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame(
        [
            {"metric": name, "value": value}
            for name, value in report.items()
            if not isinstance(value, dict)
        ],
        columns=["metric", "value"],
    )
    exports = {
        "summary_metrics.csv": summary,
        "tickets_by_category.csv": pd.DataFrame(
            [
                {"category": category, "ticket_count": count}
                for category, count in report["tickets_by_category"].items()
            ],
            columns=["category", "ticket_count"],
        ),
        "tickets_by_priority.csv": pd.DataFrame(
            [
                {"priority": priority, "ticket_count": count}
                for priority, count in report["tickets_by_priority"].items()
            ],
            columns=["priority", "ticket_count"],
        ),
        "tickets_by_status.csv": pd.DataFrame(
            [
                {"status": status, "ticket_count": count}
                for status, count in report["tickets_by_status"].items()
            ],
            columns=["status", "ticket_count"],
        ),
        "tickets_by_channel.csv": pd.DataFrame(
            [
                {"channel": channel, "ticket_count": count}
                for channel, count in report["tickets_by_channel"].items()
            ],
            columns=["channel", "ticket_count"],
        ),
        "tickets_by_assigned_team.csv": pd.DataFrame(
            [
                {"assigned_team": team, "ticket_count": count}
                for team, count in report["tickets_by_assigned_team"].items()
            ],
            columns=["assigned_team", "ticket_count"],
        ),
        "average_resolution_time_by_category.csv": pd.DataFrame(
            [
                {
                    "category": category,
                    "average_resolution_time_hours": average,
                }
                for category, average in report[
                    "avg_resolution_by_category"
                ].items()
            ],
            columns=["category", "average_resolution_time_hours"],
        ),
        "quality_issues.csv": quality_issues.copy(),
    }
    if report["avg_first_response_by_channel"]:
        exports["average_first_response_time_by_channel.csv"] = pd.DataFrame(
            [
                {
                    "channel": channel,
                    "average_first_response_time_hours": average,
                }
                for channel, average in report[
                    "avg_first_response_by_channel"
                ].items()
            ],
            columns=["channel", "average_first_response_time_hours"],
        )

    paths: list[Path] = []
    for filename, frame in exports.items():
        path = destination / filename
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def print_report(report: dict[str, Any]) -> None:
    """Print summary metrics and distributions to stdout."""
    separator = "-" * 55
    print(f"\n{'SUPPORT TICKET ANALYTICS':^55}")
    print(separator)
    print(f"  Total tickets (after cleaning) : {report['total_tickets']}")
    print(f"  Average resolution time (hours): {report['avg_resolution_time_hours']}")
    print(f"  Unresolved tickets             : {report['unresolved_count']}")
    print(f"  Overall average customer rating: {report['avg_customer_rating']}")

    for title, key in (
        ("Tickets by Category", "tickets_by_category"),
        ("Tickets by Priority", "tickets_by_priority"),
        ("Tickets by Status", "tickets_by_status"),
    ):
        print(f"\n  {title}:")
        for label, count in report[key].items():
            print(f"    {label:<18} {count}")

    print(f"\n  Average First Response Time (hours): {report['avg_first_response_time_hours']}")
    print(f"  Tickets Reopened                 : {report['tickets_reopened_count']}")
    print(f"  Total Reopen Events              : {report['total_reopen_count']}")

    for title, key in (
        ("Tickets by Channel", "tickets_by_channel"),
        ("Tickets by Assigned Team", "tickets_by_assigned_team"),
    ):
        if report[key]:
            print(f"\n  {title}:")
            for label, count in report[key].items():
                print(f"    {label:<22} {count}")

    print("\n  Average Resolution Time by Category (hours):")
    for category, average in report["avg_resolution_by_category"].items():
        print(f"    {category:<18} {average if average is not None else 'N/A'}")

    print("\n  Missing Values:")
    if report["missing_values"]:
        for column, count in report["missing_values"].items():
            print(f"    {column:<30} {count}")
    else:
        print("    None")
    print(f"\n{separator}\n")


if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
