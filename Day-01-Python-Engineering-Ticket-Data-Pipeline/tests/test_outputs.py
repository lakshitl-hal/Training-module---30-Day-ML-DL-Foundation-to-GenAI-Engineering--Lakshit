import pandas as pd

from ticket_analytics.analytics import (
    build_analytics_report,
    build_data_quality_summary,
)
from ticket_analytics.reporting import export_pipeline_outputs


def test_data_quality_summary_uses_raw_validation_counts():
    summary = build_data_quality_summary(
        {
            "raw_missing_values_per_column": {"category": 1, "status": 0},
            "invalid_records": [
                {"rule": "invalid_resolution_time_hours", "ticket_ids": ["T014"]},
                {"rule": "invalid_customer_rating", "ticket_ids": ["T021"]},
            ],
            "duplicate_ticket_id_count": 1,
            "missing_ticket_id_count": 0,
        }
    )

    assert summary == {
        "missing_values_raw": {"category": 1, "status": 0},
        "invalid_records": {
            "invalid_resolution_time_hours": 1,
            "invalid_customer_rating": 1,
        },
        "duplicate_ticket_ids": 1,
        "missing_ticket_ids": 0,
    }


def test_pipeline_exports_category_status_summary_and_quality_outputs(tmp_path):
    cleaned = pd.DataFrame(
        {
            "ticket_id": ["T001", "T002", "T003"],
            "category": ["Billing", "Billing", "Unknown"],
            "priority": ["High", "Low", "Medium"],
            "description": ["Refund", "Invoice", "Unknown issue"],
            "resolution_time_hours": [2.0, 4.0, None],
            "customer_rating": [4.0, 5.0, 3.0],
            "status": ["Open", "Resolved", "Waiting"],
        }
    )
    quality_issues = pd.DataFrame(
        [
            {
                "source_row": 4,
                "ticket_id": "T003",
                "category": "Unknown",
                "priority": "Medium",
                "status": "Waiting",
                "issue_category": "categorization",
                "issue": "missing_category",
                "value": "",
                "action": "filled with Unknown",
            }
        ]
    )

    written = export_pipeline_outputs(
        build_analytics_report(cleaned),
        quality_issues,
        tmp_path / "outputs",
    )

    assert {path.name for path in written} == {
        "summary_metrics.csv",
        "tickets_by_category.csv",
        "tickets_by_priority.csv",
        "tickets_by_status.csv",
        "tickets_by_channel.csv",
        "tickets_by_assigned_team.csv",
        "average_resolution_time_by_category.csv",
        "quality_issues.csv",
    }
    categories = pd.read_csv(tmp_path / "outputs" / "tickets_by_category.csv")
    statuses = pd.read_csv(tmp_path / "outputs" / "tickets_by_status.csv")
    issues = pd.read_csv(tmp_path / "outputs" / "quality_issues.csv")
    assert dict(zip(categories["category"], categories["ticket_count"])) == {
        "Billing": 2,
        "Unknown": 1,
    }
    assert "Waiting" in statuses["status"].tolist()
    assert issues.loc[0, "issue_category"] == "categorization"
