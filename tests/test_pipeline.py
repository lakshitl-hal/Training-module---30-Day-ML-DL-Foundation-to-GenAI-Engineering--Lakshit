"""End-to-end: malformed CSV flows loader -> validator -> cleaner -> model safely."""

from main import build_ticket
from src.io.loader import CSVLoader
from src.processing.cleaner import DataCleaner
from src.validation.validator import TicketValidator

HEADER = ("id,customer,priority,category,status,description,"
          "resolution_time_hours,customer_rating,created_at\n")


def _run(tmp_path, body):
    f = tmp_path / "t.csv"
    f.write_text(HEADER + body)
    rows = CSVLoader(f).load()
    results = TicketValidator().validate_all(rows)
    valid = [r for r, res in zip(rows, results) if res.is_valid]
    tickets = [build_ticket(r) for r in DataCleaner().clean_all(valid)]
    return results, tickets


def test_truncated_rows_are_reported_not_crashed(tmp_path):
    results, tickets = _run(
        tmp_path,
        "T1,Alice,high,billing,open,Issue,,,2024-01-15\n"
        "T2,Bob,low\n"
        "T3\n",
    )
    assert [r.is_valid for r in results] == [True, False, False]
    assert len(tickets) == 1


def test_non_finite_and_fractional_values_never_reach_model(tmp_path):
    results, tickets = _run(
        tmp_path,
        "T1,A,low,billing,closed,d,inf,3,2024-01-15\n"
        "T2,B,low,billing,closed,d,nan,3,2024-01-15\n"
        "T3,C,low,billing,closed,d,2,3.5,2024-01-15\n"
        "T4,D,low,billing,closed,d,2.5,4,2024-01-15\n",
    )
    assert [r.is_valid for r in results] == [False, False, False, True]
    assert len(tickets) == 1
    assert tickets[0].resolution_time_hours == 2.5 and tickets[0].customer_rating == 4


def test_loader_normalises_missing_cells_to_empty_string(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("a,b,c\n1,2\n")
    assert CSVLoader(f).load() == [{"a": "1", "b": "2", "c": ""}]
