import pandas as pd
import pytest

from ticket_analytics.eda import build_eda_report


def test_eda_profiles_missing_duplicates_invalid_values_and_distribution():
    raw = pd.DataFrame(
        {
            "ticket_id": ["T001", "T001", ""],
            "category": ["Billing", "Technical", "Billing"],
            "priority": ["High", "Low", "Medium"],
            "description": ["Charged twice", "", "Wrong invoice"],
            "resolution_time_hours": ["1.5", "not-a-number", "999"],
            "customer_rating": ["5", "0", ""],
            "status": ["Resolved", "Open", "Pending"],
        }
    )

    report = build_eda_report(raw)

    assert report["dataset"] == {"rows": 3, "columns": 7}
    issues = report["data_quality_issues"]
    assert issues["duplicate_ticket_id_rows"] == 2
    assert issues["duplicate_ticket_ids"] == ["T001"]
    assert issues["missing_ticket_ids"] == 1
    assert issues["missing_ticket_id_examples"] == [
        {"row": 4, "ticket_id": "", "value": ""}
    ]
    assert issues["invalid_resolution_time_rows"] == 2
    assert issues["invalid_resolution_time_examples"] == [
        {"row": 3, "ticket_id": "T001", "value": "not-a-number"},
        {"row": 4, "ticket_id": "", "value": "999"},
    ]
    assert issues["invalid_customer_rating_rows"] == 1
    assert issues["invalid_customer_rating_examples"] == [
        {"row": 3, "ticket_id": "T001", "value": "0"}
    ]
    assert report["column_profiles"]["category"]["missing_count"] == 0
    assert report["column_profiles"]["resolution_time_hours"]["numeric"][
        "non_numeric_count"
    ] == 1
    assert report["categorical_distributions"]["status"]["unique_count"] == 3


def test_eda_requires_positive_top_n():
    with pytest.raises(ValueError, match="top_n"):
        build_eda_report(pd.DataFrame({"category": ["Billing"]}), top_n=0)


def test_eda_profiles_mixed_and_invalid_creation_dates():
    report = build_eda_report(
        pd.DataFrame(
            {"created_at": ["2025-01-03", "2025/02/04", "not-a-date"]}
        )
    )

    assert report["time_series"]["valid_dates"] == 2
    assert report["time_series"]["invalid_dates"] == 1
    assert report["time_series"]["monthly_ticket_counts"] == {
        "2025-01": 1,
        "2025-02": 1,
    }
