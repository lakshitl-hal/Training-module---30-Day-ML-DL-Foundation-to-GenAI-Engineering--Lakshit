"""Generate a deterministic, intentionally imperfect ticket dataset."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from math import log
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "tickets_synthetic.csv"
FIELDNAMES = [
    "ticket_id",
    "customer_id",
    "channel",
    "assigned_team",
    "created_at",
    "updated_at",
    "category",
    "priority",
    "description",
    "first_response_time_hours",
    "resolution_time_hours",
    "customer_rating",
    "reopen_count",
    "status",
]

CATEGORIES = {
    "Billing": [
        "charged twice for subscription",
        "refund has not arrived",
        "invoice total is incorrect",
        "discount did not apply",
    ],
    "Technical": [
        "application crashes during startup",
        "request times out under load",
        "background worker uses excessive memory",
        "login endpoint returns an error",
    ],
    "Account": [
        "password reset link has expired",
        "account is locked after sign-in attempts",
        "verification code was not delivered",
        "profile details cannot be updated",
    ],
    "Shipping": [
        "package arrived later than expected",
        "wrong item was delivered",
        "tracking status has not changed",
        "package arrived damaged",
    ],
    "Product": [
        "customer requests a missing feature",
        "documentation is difficult to follow",
        "mobile layout is hard to use",
        "customer asks about product availability",
    ],
}
PRIORITIES = ["Critical", "High", "Medium", "Low"]
MEDIAN_HOURS = {"Critical": 12, "High": 20, "Medium": 32, "Low": 44}
CHANNELS = ["Email", "Chat", "Phone", "Web Form", "Social"]
TEAMS = {
    "Billing": ["Billing Operations", "Payments"],
    "Technical": ["Technical Support", "Engineering"],
    "Account": ["Account Services", "Identity Support"],
    "Shipping": ["Fulfillment", "Logistics"],
    "Product": ["Product Support", "Customer Success"],
}


def _make_record(index: int, rng: random.Random) -> dict[str, str]:
    category = rng.choice(list(CATEGORIES))
    priority = rng.choices(PRIORITIES, weights=[8, 24, 42, 26], k=1)[0]
    resolution_hours = min(
        600,
        round(rng.lognormvariate(log(MEDIAN_HOURS[priority]), 0.7), 2),
    )
    status = rng.choices(
        ["Resolved", "Open", "Pending", "In Progress"],
        weights=[68, 17, 9, 6],
        k=1,
    )[0]
    rating_center = 4.2 if status == "Resolved" else 3.2
    rating_center -= min(resolution_hours / 100, 1.5)
    rating = round(min(5, max(1, rng.gauss(rating_center, 0.75))), 1)
    created = datetime(2025, 1, 1) + timedelta(
        days=rng.randrange(365),
        hours=rng.randrange(24),
        minutes=rng.choice([0, 15, 30, 45]),
    )
    first_response = round(rng.lognormvariate(log(0.8), 0.9), 2)
    if status in {"Open", "Pending"} and rng.random() < 0.18:
        first_response_value = ""
    else:
        first_response_value = f"{first_response:.2f}"
    reopen_count = rng.choices([0, 1, 2, 3], weights=[88, 9, 2, 1], k=1)[0]
    updated = created + timedelta(
        hours=(
            resolution_hours
            if status == "Resolved"
            else rng.uniform(0.1, 96)
        )
    )

    return {
        "ticket_id": f"T{index + 1:06d}",
        "customer_id": f"C{rng.randrange(1, max(2, int(index * 0.7) + 2)):06d}",
        "channel": rng.choices(CHANNELS, weights=[35, 30, 18, 14, 3], k=1)[0],
        "assigned_team": rng.choice(TEAMS[category]),
        "created_at": created.strftime("%Y-%m-%d"),
        "updated_at": updated.strftime("%Y-%m-%d"),
        "category": category,
        "priority": priority,
        "description": rng.choice(CATEGORIES[category]).capitalize() + ".",
        "first_response_time_hours": first_response_value,
        "resolution_time_hours": f"{resolution_hours:.2f}",
        "customer_rating": f"{rating:.1f}",
        "reopen_count": str(reopen_count),
        "status": status,
    }


def generate_dataset(
    rows: int = 1200, seed: int = 42
) -> list[dict[str, str]]:
    """Return records with realistic variation and repeatable data-quality defects."""
    if rows < 1:
        raise ValueError("rows must be at least 1")

    rng = random.Random(seed)
    records = [_make_record(index, rng) for index in range(rows)]

    for index, record in enumerate(records):
        if index % 401 == 0:
            record["ticket_id"] = ""
        if index % 53 == 0:
            record["category"] = ""
        if index % 71 == 0:
            record["description"] = ""
        if index % 89 == 0:
            record["priority"] = f" {record['priority'].upper()} "
        if index % 97 == 0:
            record["status"] = f" {record['status'].upper()} "
        if index % 331 == 0:
            record["created_at"] = "not-a-date"
        elif index % 359 == 0:
            record["updated_at"] = "2024-01-01"
        if index % 137 == 0:
            record["channel"] = "fax"
        elif index % 181 == 0:
            record["category"] = "tech"
        if index % 149 == 0:
            record["assigned_team"] = ""
        if index % 113 == 0:
            record["resolution_time_hours"] = ""
        elif index % 211 == 0:
            record["resolution_time_hours"] = "999"
        elif index % 229 == 0:
            record["resolution_time_hours"] = "-2"
        elif index % 307 == 0:
            record["resolution_time_hours"] = "not-a-number"
        if index % 197 == 0:
            record["first_response_time_hours"] = "-1"
        elif index % 293 == 0:
            record["first_response_time_hours"] = "unknown"
        if index % 79 == 0:
            record["customer_rating"] = ""
        elif index % 173 == 0:
            record["customer_rating"] = "6.5"
        elif index % 191 == 0:
            record["customer_rating"] = "-1"
        elif index % 283 == 0:
            record["customer_rating"] = "unknown"
        if index % 223 == 0:
            record["reopen_count"] = "-1"
        elif index % 317 == 0:
            record["reopen_count"] = "one"

    duplicate_records = [
        {**records[index], "description": "Intentional duplicate ticket ID."}
        for index in range(96, rows, 97)
    ]
    return records + duplicate_records


def write_dataset(path: Path, rows: int = 1200, seed: int = 42) -> int:
    """Write generated records to CSV and return the number of written rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = generate_dataset(rows=rows, seed=seed)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    written = write_dataset(args.output, rows=args.rows, seed=args.seed)
    print(f"Wrote {written} synthetic tickets to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
