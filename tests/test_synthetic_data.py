from pathlib import Path

import pandas as pd

from scripts.generate_synthetic_data import generate_dataset


REQUIRED_FIELDS = {
    "ticket_id",
    "category",
    "priority",
    "description",
    "resolution_time_hours",
    "customer_rating",
    "status",
}


def test_synthetic_dataset_generation_is_repeatable_and_adds_duplicate_cases():
    first = generate_dataset(rows=200, seed=7)
    second = generate_dataset(rows=200, seed=7)

    assert first == second
    assert len(first) == 202
    assert first[0]["ticket_id"] == ""
    assert first[-1]["description"] == "Intentional duplicate ticket ID."
    assert REQUIRED_FIELDS <= first[0].keys()
    assert {
        "customer_id",
        "channel",
        "assigned_team",
        "created_at",
        "updated_at",
        "first_response_time_hours",
        "reopen_count",
    } <= first[0].keys()


def test_required_tickets_csv_contains_minimum_dataset_contract():
    dataset = Path(__file__).resolve().parents[1] / "data" / "tickets.csv"

    frame = pd.read_csv(dataset)

    assert len(frame) >= 20
    assert REQUIRED_FIELDS <= set(frame.columns)
