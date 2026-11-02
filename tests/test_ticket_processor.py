"""
test_ticket_processor.py
=========================
Automated tests for TicketDataProcessor and analytics.

Test inventory
--------------
1.  test_valid_csv_loads_and_cleans          — happy path: valid CSV processes correctly
2.  test_duplicate_ids_are_deduplicated      — duplicate ticket_id: only first kept
3.  test_missing_required_columns_raises     — missing column raises MissingColumnsError
4.  test_empty_dataset_raises                — CSV with header only raises EmptyDatasetError
5.  test_invalid_csv_raises                  — non-existent file raises InvalidFileError
6.  test_invalid_resolution_time_set_to_nan  — out-of-range resolution_time → NaN
7.  test_invalid_customer_rating_set_to_nan  — out-of-range customer_rating → NaN
8.  test_missing_category_filled             — missing category → "Unknown"
9.  test_analytics_report_structure         — report has all required keys
10. test_count_unresolved_correct           — unresolved count matches expected value
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ticket_analytics.processor import (
    EmptyDatasetError,
    InvalidFileError,
    MissingColumnsError,
    TicketDataProcessor,
)
from ticket_analytics.analytics import (
    average_customer_rating,
    average_resolution_time_by_category,
    build_analytics_report,
    build_data_quality_summary,
    count_tickets_by_priority,
    count_unresolved_tickets,
    missing_value_summary,
)


# ──────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────

VALID_CSV_CONTENT = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
    T001,Billing,High,Charged twice.,2.5,4.5,Resolved
    T002,Technical,Critical,App crash.,8.0,2.0,Open
    T003,Account,Medium,Password reset.,3.0,3.5,Resolved
    T004,Billing,Low,Invoice copy.,1.0,5.0,Resolved
    T005,Technical,High,API limit exceeded.,5.5,3.0,Open
""")

DUPLICATE_ID_CSV = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
    T001,Billing,High,First entry.,2.5,4.5,Resolved
    T001,Billing,High,Duplicate entry.,2.5,4.5,Resolved
    T002,Technical,Low,Normal ticket.,1.0,4.0,Open
""")

MISSING_COLUMN_CSV = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,status
    T001,Billing,High,Charged twice.,2.5,Resolved
""")

EMPTY_ROWS_CSV = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
""")

INVALID_NUMERIC_CSV = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
    T001,Billing,High,Charged twice.,999,6.5,Resolved
    T002,Technical,Low,App crash.,-5.0,-1,Open
    T003,Account,Medium,Password reset.,3.0,4.0,Resolved
""")

MISSING_CATEGORY_CSV = textwrap.dedent("""\
    ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
    T001,,High,Charged twice.,2.5,4.5,Resolved
    T002,Technical,Low,App crash.,1.0,4.0,Open
""")


def _make_processor_from_string(csv_content: str, tmp_path: Path) -> TicketDataProcessor:
    """Write csv_content to a temp file and return a TicketDataProcessor for it."""
    csv_file = tmp_path / "test_tickets.csv"
    csv_file.write_text(csv_content, encoding="utf-8")
    return TicketDataProcessor(csv_file)


# ──────────────────────────────────────────────────────────────
# Test 1: valid CSV processes correctly
# ──────────────────────────────────────────────────────────────

def test_valid_input_processes_with_float_measure_dtypes(tmp_path):
    """
    A well-formed CSV with no data-quality issues should load, validate,
    and return a DataFrame with the correct number of rows and all required columns.
    """
    processor = _make_processor_from_string(VALID_CSV_CONTENT, tmp_path)
    cleaned = processor.process()

    assert isinstance(cleaned, pd.DataFrame), "process() must return a DataFrame"
    assert len(cleaned) == 5, "All 5 valid rows should be retained"
    assert pd.api.types.is_float_dtype(cleaned["resolution_time_hours"])
    assert pd.api.types.is_float_dtype(cleaned["customer_rating"])
    for col in ["ticket_id", "category", "priority", "description",
                "resolution_time_hours", "customer_rating", "status"]:
        assert col in cleaned.columns, f"Column '{col}' missing from cleaned output"


# ──────────────────────────────────────────────────────────────
# Test 2: duplicate ticket IDs are deduplicated (keep first)
# ──────────────────────────────────────────────────────────────

def test_duplicate_ids_are_deduplicated(tmp_path):
    """
    When a ticket_id appears more than once, only the first occurrence is kept.
    The cleaned DataFrame must not contain duplicate ticket_ids.
    """
    processor = _make_processor_from_string(DUPLICATE_ID_CSV, tmp_path)
    cleaned = processor.process()

    assert cleaned["ticket_id"].is_unique, "ticket_id column must be unique after cleaning"
    assert len(cleaned) == 2, "Deduplication should reduce 3 rows to 2"
    # Confirm the first occurrence was kept (description = 'First entry.')
    t001_row = cleaned[cleaned["ticket_id"] == "T001"]
    assert "First entry" in t001_row["description"].values[0]
    assert processor.validation_report["duplicate_ticket_id_count"] == 1
    duplicate_issue = processor.quality_issues.loc[
        processor.quality_issues["issue"] == "duplicate_ticket_id"
    ]
    assert len(duplicate_issue) == 1
    assert duplicate_issue.iloc[0]["ticket_id"] == "T001"


# ──────────────────────────────────────────────────────────────
# Test 3: missing required columns raises MissingColumnsError
# ──────────────────────────────────────────────────────────────

def test_missing_required_columns_raises(tmp_path):
    """
    A CSV that is missing one or more required columns must raise
    MissingColumnsError with the list of missing column names.
    """
    processor = _make_processor_from_string(MISSING_COLUMN_CSV, tmp_path)
    with pytest.raises(MissingColumnsError) as exc_info:
        processor.process()

    assert "customer_rating" in exc_info.value.missing, (
        "MissingColumnsError.missing should list 'customer_rating'"
    )
    assert "customer_rating" in str(exc_info.value)


def test_processing_does_not_change_raw_file_bytes(tmp_path):
    csv_file = tmp_path / "immutable.csv"
    csv_file.write_text(VALID_CSV_CONTENT, encoding="utf-8")
    before = hashlib.sha256(csv_file.read_bytes()).digest()

    TicketDataProcessor(csv_file).process()

    after = hashlib.sha256(csv_file.read_bytes()).digest()
    assert after == before


def test_resolution_and_rating_boundary_values(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        T001,Billing,High,Zero resolution,0,4,Open
        T002,Billing,High,Maximum resolution,720,5,Open
        T003,Billing,High,Too long,720.01,1,Open
        T004,Billing,High,Low rating,1,0.9,Open
        T005,Billing,High,Upper rating,1,5.1,Open
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)
    cleaned = processor.process().set_index("ticket_id")

    assert pd.isna(cleaned.loc["T001", "resolution_time_hours"])
    assert cleaned.loc["T002", "resolution_time_hours"] == 720
    assert pd.isna(cleaned.loc["T003", "resolution_time_hours"])
    assert pd.isna(cleaned.loc["T004", "customer_rating"])
    assert cleaned.loc["T002", "customer_rating"] == 5
    assert cleaned.loc["T003", "customer_rating"] == 1
    assert pd.isna(cleaned.loc["T005", "customer_rating"])


# ──────────────────────────────────────────────────────────────
# Test 4: empty dataset raises EmptyDatasetError
# ──────────────────────────────────────────────────────────────

def test_header_only_csv_raises_empty_dataset_error(tmp_path):
    """
    A CSV with only a header row (zero data rows) must raise EmptyDatasetError.
    """
    processor = _make_processor_from_string(EMPTY_ROWS_CSV, tmp_path)
    with pytest.raises(EmptyDatasetError):
        processor.process()


# ──────────────────────────────────────────────────────────────
# Test 5: non-existent file raises InvalidFileError
# ──────────────────────────────────────────────────────────────

def test_nonexistent_csv_raises_invalid_file_error(tmp_path):
    """
    Pointing the processor at a file that does not exist must raise
    InvalidFileError, not a bare FileNotFoundError.
    """
    processor = TicketDataProcessor(tmp_path / "does_not_exist.csv")
    with pytest.raises(InvalidFileError):
        processor.process()


def test_unparseable_csv_raises_invalid_file_error(tmp_path):
    csv_file = tmp_path / "malformed.csv"
    csv_file.write_text('ticket_id,category\n"T001,Billing\n', encoding="utf-8")

    with pytest.raises(InvalidFileError, match="Cannot parse CSV"):
        TicketDataProcessor(csv_file).process()


def test_zero_byte_csv_raises_empty_dataset_error(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_bytes(b"")

    with pytest.raises(EmptyDatasetError):
        TicketDataProcessor(csv_file).process()


# ──────────────────────────────────────────────────────────────
# Test 6: invalid resolution_time_hours set to NaN
# ──────────────────────────────────────────────────────────────

def test_invalid_resolution_time_set_to_nan(tmp_path):
    """
    resolution_time_hours values that are ≤ 0 or > 720 must be replaced
    with NaN. Valid rows must retain their numeric value.
    """
    processor = _make_processor_from_string(INVALID_NUMERIC_CSV, tmp_path)
    cleaned = processor.process()

    # T001: 999 hours > 720 → NaN
    t001 = cleaned[cleaned["ticket_id"] == "T001"]["resolution_time_hours"].values[0]
    assert np.isnan(t001), "resolution_time_hours=999 should become NaN"

    # T002: -5.0 ≤ 0 → NaN
    t002 = cleaned[cleaned["ticket_id"] == "T002"]["resolution_time_hours"].values[0]
    assert np.isnan(t002), "resolution_time_hours=-5.0 should become NaN"

    # T003: 3.0 is valid → retained
    t003 = cleaned[cleaned["ticket_id"] == "T003"]["resolution_time_hours"].values[0]
    assert t003 == pytest.approx(3.0), "Valid resolution_time_hours=3.0 should be preserved"


# ──────────────────────────────────────────────────────────────
# Test 7: invalid customer_rating set to NaN
# ──────────────────────────────────────────────────────────────

def test_invalid_customer_rating_set_to_nan(tmp_path):
    """
    customer_rating values outside [1.0, 5.0] must be replaced with NaN.
    """
    processor = _make_processor_from_string(INVALID_NUMERIC_CSV, tmp_path)
    cleaned = processor.process()

    # T001: 6.5 > 5.0 → NaN
    t001_rating = cleaned[cleaned["ticket_id"] == "T001"]["customer_rating"].values[0]
    assert np.isnan(t001_rating), "customer_rating=6.5 should become NaN"

    # T002: -1 < 1.0 → NaN
    t002_rating = cleaned[cleaned["ticket_id"] == "T002"]["customer_rating"].values[0]
    assert np.isnan(t002_rating), "customer_rating=-1 should become NaN"

    # T003: 4.0 is valid → retained
    t003_rating = cleaned[cleaned["ticket_id"] == "T003"]["customer_rating"].values[0]
    assert t003_rating == pytest.approx(4.0)


# ──────────────────────────────────────────────────────────────
# Test 8: missing category filled with "Unknown"
# ──────────────────────────────────────────────────────────────

def test_missing_category_filled(tmp_path):
    """
    A blank category cell must be filled with the sentinel 'Unknown',
    keeping the row in the dataset.
    """
    processor = _make_processor_from_string(MISSING_CATEGORY_CSV, tmp_path)
    cleaned = processor.process()

    t001_category = cleaned[cleaned["ticket_id"] == "T001"]["category"].values[0]
    assert t001_category == "Unknown", "Blank category should be filled with 'Unknown'"
    assert len(cleaned) == 2, "Row with missing category must NOT be dropped"


# ──────────────────────────────────────────────────────────────
# Test 9: analytics report has all required keys
# ──────────────────────────────────────────────────────────────

def test_analytics_report_structure(tmp_path):
    """
    build_analytics_report() must return a dict containing exactly the
    documented keys with appropriate value types.
    """
    processor = _make_processor_from_string(VALID_CSV_CONTENT, tmp_path)
    cleaned = processor.process()
    report = build_analytics_report(cleaned)

    required_keys = {
        "total_tickets",
        "tickets_by_category",
        "tickets_by_priority",
        "tickets_by_status",
        "avg_resolution_time_hours",
        "avg_resolution_by_category",
        "avg_customer_rating",
        "open_count",
        "unresolved_count",
        "missing_values",
    }
    assert required_keys.issubset(report.keys()), (
        f"Report missing keys: {required_keys - report.keys()}"
    )
    assert isinstance(report["tickets_by_priority"], dict)
    assert isinstance(report["unresolved_count"], int)
    assert report["total_tickets"] == 5


# ──────────────────────────────────────────────────────────────
# Test 10: count_unresolved_tickets returns correct value
# ──────────────────────────────────────────────────────────────

def test_count_unresolved_correct(tmp_path):
    """
    Of the 5 valid rows in VALID_CSV_CONTENT, 2 have an active status,
    so count_unresolved_tickets should return 2.
    """
    processor = _make_processor_from_string(VALID_CSV_CONTENT, tmp_path)
    cleaned = processor.process()
    unresolved = count_unresolved_tickets(cleaned)
    assert unresolved == 2, f"Expected 2 unresolved tickets, got {unresolved}"


def test_nonnumeric_measurements_are_flagged_and_cleaned(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        T001,Billing,High,Refund,unknown,not-a-rating,Open
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)

    cleaned = processor.process()

    assert np.isnan(cleaned.loc[0, "resolution_time_hours"])
    assert np.isnan(cleaned.loc[0, "customer_rating"])
    rules = {issue["rule"] for issue in processor.validation_report["invalid_records"]}
    assert "invalid_resolution_time_hours" in rules
    assert "invalid_customer_rating" in rules


def test_missing_ticket_id_is_retained_and_row_issue_is_categorized(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        ,Billing,High,Refund,2,4,Open
        T002,Account,Low,Password,3,5,Resolved
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)

    cleaned = processor.process()

    assert len(cleaned) == 2
    issue = processor.quality_issues.iloc[0]
    assert issue["source_row"] == 2
    assert issue["issue_category"] == "identification"
    assert issue["issue"] == "missing_ticket_id"


def test_string_index_and_whitespace_missing_are_handled(tmp_path):
    frame = pd.DataFrame(
        [
            ["T001", "   ", "High", "Refund", "not-a-number", "4", "Open"],
            ["T002", "Account", "Low", "Password", "3", "5", "Resolved"],
        ],
        columns=[
            "ticket_id", "category", "priority", "description",
            "resolution_time_hours", "customer_rating", "status",
        ],
        index=["source-a", "source-b"],
    )
    processor = TicketDataProcessor(tmp_path / "source_ids.csv")

    cleaned = processor._clean(frame)

    assert len(cleaned) == 2
    assert cleaned.loc[0, "category"] == "Unknown"
    assert processor.validation_report["raw_missing_values_per_column"]["category"] == 1
    invalid_row = processor.quality_issues.loc[
        processor.quality_issues["issue"] == "invalid_resolution_time_hours"
    ].iloc[0]
    assert invalid_row["source_row"] == 2
    assert invalid_row["issue_category"] == "numeric_validity"
    assert frame.loc["source-a", "category"] == "   "


def test_unknown_status_is_reported_but_not_counted_as_unresolved(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        T001,Billing,Urgent,Refund,2,4,Waiting For Review
        T002,Account,Low,Password,3,5,In Progress
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)
    cleaned = processor.process()
    report = build_analytics_report(cleaned)

    assert report["tickets_by_status"]["Waiting For Review"] == 1
    assert report["unresolved_count"] == 1
    unknown_issues = processor.quality_issues.loc[
        processor.quality_issues["issue"].isin(
            {"unrecognized_priority", "unrecognized_status"}
        )
    ]
    assert set(unknown_issues["issue_category"]) == {"categorization"}


def test_status_synonyms_and_pending_status_follow_crm_lifecycle(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        T001,Billing,P1,Refund,2,4,New
        T002,Account,Low,Password,3,5,Solved
        T003,Technical,Medium,Timeout,4,3,Pending
        T004,Shipping,High,Parcel,3,4,Re-opened
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)
    cleaned = processor.process()

    assert cleaned["priority"].tolist() == ["Critical", "Low", "Medium", "High"]
    assert cleaned["status"].tolist() == ["Open", "Resolved", "Pending", "Reopened"]
    assert count_unresolved_tickets(cleaned) == 3


def test_optional_crm_fields_are_validated_and_typed(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status,customer_id,channel,assigned_team,created_at,updated_at,first_response_time_hours,reopen_count
        T001,Billing,High,Refund,2,4,Open,C001,email,Billing Ops,2025-01-01,2025-01-02,0.5,2
        T002,Account,Low,Password,3,5,Resolved,C002,phone,Account Support,bad-date,2025-01-01,-1,one
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)

    cleaned = processor.process()

    assert cleaned.loc[0, "first_response_time_hours"] == pytest.approx(0.5)
    assert cleaned.loc[0, "reopen_count"] == 2
    assert str(cleaned["reopen_count"].dtype) == "Int64"
    assert pd.isna(cleaned.loc[1, "first_response_time_hours"])
    assert pd.isna(cleaned.loc[1, "reopen_count"])
    assert pd.isna(cleaned.loc[1, "created_at"])
    assert processor.validation_report["raw_missing_values_per_column"][
        "first_response_time_hours"
    ] == 0
    issues = set(processor.quality_issues["issue"])
    assert {"invalid_first_response_time_hours", "invalid_reopen_count",
            "invalid_created_at"} <= issues


def test_optional_crm_metrics_are_reported_by_channel_and_team():
    frame = pd.DataFrame(
        {
            "ticket_id": ["T001", "T002", "T003"],
            "category": ["Billing", "Account", "Tech"],
            "priority": ["P1", "Low", "High"],
            "description": ["Refund", "Password", "Crash"],
            "resolution_time_hours": [2.0, 3.0, 8.0],
            "customer_rating": [4.0, 5.0, 3.0],
            "status": ["New", "Solved", "Reopened"],
            "channel": ["email", "Phone", "fax"],
            "assigned_team": ["Payments", "Account Services", "Engineering"],
            "first_response_time_hours": [0.5, 1.0, 2.5],
            "reopen_count": [0, 0, 2],
        }
    )
    processor = TicketDataProcessor("unused.csv")
    cleaned = processor._clean(frame)
    report = build_analytics_report(cleaned)

    assert cleaned["category"].tolist() == ["Billing", "Account", "Technical"]
    assert cleaned["priority"].tolist() == ["Critical", "Low", "High"]
    assert cleaned["status"].tolist() == ["Open", "Resolved", "Reopened"]
    assert report["unresolved_count"] == 2
    assert report["avg_first_response_time_hours"] == pytest.approx(1.33)
    assert report["tickets_reopened_count"] == 1
    assert report["total_reopen_count"] == 2
    assert report["tickets_by_channel"]["Fax"] == 1
    assert report["avg_first_response_by_channel"]["Email"] == 0.5
    assert "unrecognized_channel" in set(processor.quality_issues["issue"])


def test_missing_numeric_values_are_reported_as_completeness_issues(tmp_path):
    csv_content = textwrap.dedent("""\
        ticket_id,category,priority,description,resolution_time_hours,customer_rating,status
        T001,Billing,High,Refund,,4,Open
        T002,Account,Low,Password,3,,Resolved
    """)
    processor = _make_processor_from_string(csv_content, tmp_path)

    processor.process()

    missing_issues = processor.quality_issues.loc[
        processor.quality_issues["issue_category"] == "completeness"
    ]
    assert set(missing_issues["issue"]) == {
        "missing_resolution_time_hours",
        "missing_customer_rating",
    }


def test_required_dataset_analytics_match_manual_results():
    dataset = Path(__file__).resolve().parents[1] / "data" / "tickets.csv"
    processor = TicketDataProcessor(dataset)
    cleaned = processor.process()
    report = build_analytics_report(cleaned)
    data_quality = build_data_quality_summary(processor.validation_report)

    assert report["tickets_by_priority"] == {
        "High": 7,
        "Medium": 7,
        "Critical": 5,
        "Low": 4,
    }
    assert report["unresolved_count"] == 8
    assert report["avg_customer_rating"] == 3.67
    assert report["avg_resolution_by_category"] == {
        "Technical": 6.5,
        "Billing": 2.17,
        "Account": 2.2,
        "Shipping": 2.5,
        "Unknown": 1.0,
    }
    assert data_quality["duplicate_ticket_ids"] == 1
    assert data_quality["invalid_records"] == {
        "invalid_resolution_time_hours": 1,
        "invalid_customer_rating": 1,
    }
    assert sum(data_quality["invalid_records"].values()) == 2
    assert data_quality["missing_values_raw"]["category"] == 1
    assert processor.validation_report["invalid_records"] == [
        {
            "rule": "invalid_resolution_time_hours",
            "ticket_ids": ["T014"],
            "original_values": ["999"],
            "action": "replaced with NaN",
        },
        {
            "rule": "invalid_customer_rating",
            "ticket_ids": ["T021"],
            "original_values": ["-1"],
            "action": "replaced with NaN",
        },
    ]
