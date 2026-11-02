"""Console and CSV output for ticket analytics reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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
