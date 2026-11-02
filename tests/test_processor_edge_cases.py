import pandas as pd
import pytest

from ticket_analytics.analytics import build_analytics_report
from ticket_analytics.processor import InvalidFileError, TicketDataProcessor


CSV_HEADER = (
    "ticket_id,category,priority,description,resolution_time_hours,"
    "customer_rating,status\n"
)


def _write_tickets(path, measurements):
    rows = [
        f"T{index},Billing,High,Issue,{resolution},{rating},Open"
        for index, (resolution, rating) in enumerate(measurements, start=1)
    ]
    path.write_text(CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return TicketDataProcessor(path)


def test_malformed_csv_raises_invalid_file_error(tmp_path):
    path = tmp_path / "malformed.csv"
    path.write_text(
        'ticket_id,category,priority,description,resolution_time_hours,'
        'customer_rating,status\nT1,"unterminated,High,x,1,3,Open\n',
        encoding="utf-8",
    )

    with pytest.raises(InvalidFileError):
        TicketDataProcessor(path).process()


def test_non_finite_resolution_times_are_invalid(tmp_path):
    processor = _write_tickets(
        tmp_path / "resolution.csv",
        [("inf", "4"), ("-inf", "4"), ("nan", "4"), ("2.0", "4")],
    )

    cleaned = processor.process()
    invalid = next(
        record
        for record in processor.validation_report["invalid_records"]
        if record["rule"] == "invalid_resolution_time_hours"
    )

    assert cleaned["resolution_time_hours"].iloc[:3].isna().all()
    assert cleaned["resolution_time_hours"].iloc[3] == 2.0
    assert invalid["ticket_ids"] == ["T1", "T2", "T3"]
    assert invalid["original_values"] == ["inf", "-inf", "nan"]
    assert build_analytics_report(cleaned)["avg_resolution_time_hours"] == 2.0


def test_non_finite_ratings_are_invalid(tmp_path):
    processor = _write_tickets(
        tmp_path / "ratings.csv",
        [("2", "inf"), ("2", "-inf"), ("2", "nan"), ("2", "4")],
    )

    cleaned = processor.process()
    invalid = next(
        record
        for record in processor.validation_report["invalid_records"]
        if record["rule"] == "invalid_customer_rating"
    )

    assert cleaned["customer_rating"].iloc[:3].isna().all()
    assert cleaned["customer_rating"].iloc[3] == 4.0
    assert invalid["ticket_ids"] == ["T1", "T2", "T3"]
    assert invalid["original_values"] == ["inf", "-inf", "nan"]


def test_blank_values_stay_missing_not_invalid(tmp_path):
    processor = _write_tickets(tmp_path / "blanks.csv", [("", "",)])

    cleaned = processor.process()

    assert pd.isna(cleaned.loc[0, "resolution_time_hours"])
    assert pd.isna(cleaned.loc[0, "customer_rating"])
    assert processor.validation_report["invalid_records"] == []


def test_analytics_with_non_unique_index():
    frame = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2", "T3"],
            "category": ["Billing", "Account", "Billing"],
            "priority": ["High", "Low", "High"],
            "description": ["One", "Two", "Three"],
            "resolution_time_hours": [2.0, 4.0, 6.0],
            "customer_rating": [3.0, 5.0, 4.0],
            "status": ["Open", "Resolved", "Banana"],
        },
        index=[1, 1, 2],
    )

    assert build_analytics_report(frame) == build_analytics_report(
        frame.reset_index(drop=True)
    )


def test_unknown_status_not_counted_as_unresolved():
    frame = pd.DataFrame(
        {
            "ticket_id": ["T1", "T2"],
            "category": ["Billing", "Account"],
            "priority": ["High", "Low"],
            "description": ["One", "Two"],
            "resolution_time_hours": [2.0, 4.0],
            "customer_rating": [3.0, 5.0],
            "status": ["Banana", "Open"],
        }
    )

    report = build_analytics_report(frame)

    assert report["tickets_by_status"]["Banana"] == 1
    assert report["unresolved_count"] == 1
