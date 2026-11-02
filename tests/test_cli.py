from ticket_analytics.cli import main


def test_analyze_command_writes_csv_reports_and_eda_json(tmp_path, capsys):
    csv_path = tmp_path / "tickets.csv"
    csv_path.write_text(
        "ticket_id,category,priority,description,resolution_time_hours,"
        "customer_rating,status\n"
        "T001,Billing,High,Refund,2,4,Open\n"
        "T002,Account,Low,Password,3,5,Resolved\n"
        "T002,Technical,Medium,Duplicate,4,2,Open\n"
        ",Shipping,Low,No ticket ID,1,3,Pending\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "pipeline_outputs"

    exit_code = main(
        [
            "analyze",
            "--input",
            str(csv_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    expected = {
        "summary_metrics.csv",
        "tickets_by_category.csv",
        "tickets_by_priority.csv",
        "tickets_by_status.csv",
        "tickets_by_channel.csv",
        "tickets_by_assigned_team.csv",
        "average_resolution_time_by_category.csv",
        "quality_issues.csv",
        "eda_report.json",
    }
    assert {path.name for path in output_dir.iterdir()} == expected
    output = capsys.readouterr().out
    assert "Tickets by Category" in output
    assert "Reports written to" in output
