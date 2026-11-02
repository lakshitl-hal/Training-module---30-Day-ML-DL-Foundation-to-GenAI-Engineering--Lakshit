import json
from pathlib import Path

from fastapi.encoders import jsonable_encoder

from ticket_analytics.api import DEFAULT_CSV, _process_path


def test_sample_api_payload_is_strict_json_serializable():
    payload = _process_path(DEFAULT_CSV)

    encoded = jsonable_encoder(payload)
    rendered = json.dumps(encoded, allow_nan=False)

    assert '"analytics"' in rendered
    assert '"eda"' in rendered
    assert '"quality_issues"' in rendered
    assert '"avg_first_response_time_hours"' in rendered
    assert '"tickets"' in rendered


def test_uploaded_csv_api_payload_is_strict_json_serializable(tmp_path: Path):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text(
        "ticket_id,category,priority,description,resolution_time_hours,"
        "customer_rating,status\n"
        "T001,Billing,High,Refund,not-a-number,unknown,Open\n",
        encoding="utf-8",
    )

    payload = _process_path(csv_path)

    assert json.dumps(jsonable_encoder(payload), allow_nan=False)
