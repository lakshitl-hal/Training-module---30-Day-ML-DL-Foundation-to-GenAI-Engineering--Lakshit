# Support Ticket Analytics

A beginner-friendly Python project that reads support tickets from CSV, cleans
data issues, and reports useful metrics. The required project data and the larger
CRM-style test data are kept in separate files.

## What is in this project?

- `data/tickets.csv` — the required 24-ticket assignment dataset.
- `data/tickets_synthetic.csv` — a larger dataset for testing additional cases.
- `src/ticket_analytics/processor.py` — loads and cleans ticket data.
- `src/ticket_analytics/analytics.py` — calculates ticket metrics.
- `src/ticket_analytics/reporting.py` — prints and saves reports.
- `src/ticket_analytics/eda.py` — profiles the original, uncleaned data.
- `src/ticket_analytics/api.py` — optional FastAPI endpoints.
- `tests/` — automated checks for the pipeline.

## Set up (Windows PowerShell)

Use Python 3.10 or newer. From the project folder, create and activate a virtual
environment, then install the project and its test dependencies:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The execution-policy command is only needed if PowerShell blocks activation.
`requirements.txt` installs the project, its dependencies, and pytest.

## Run the project

The default input is `data/tickets.csv`. Clean it and print the analysis:

```powershell
ticket-analytics analyze
```

To use the larger test dataset instead:

```powershell
ticket-analytics analyze --input data\tickets_synthetic.csv
```

The command saves reports in the ignored `outputs/` folder. These include the
summary metrics, ticket counts, category averages, quality findings, and EDA.
Choose another output folder with `--output-dir`.

## Run EDA

EDA (exploratory data analysis) summarizes the original CSV before cleaning.
It shows missing and invalid values, category counts, numeric summaries, and
monthly ticket counts when the file has creation dates.

```powershell
ticket-analytics eda
ticket-analytics eda --input data\tickets_synthetic.csv
```

Add `--output path\to\report.json` to save the EDA report instead of printing it.

## Cleaning rules in plain language

- The input CSV is never overwritten. The processor returns a cleaned copy.
- Rows with no ticket ID are kept and flagged. For duplicate IDs, the first row
  is kept and later rows are removed from the cleaned data.
- Missing category, priority, or status becomes `Unknown`; missing descriptions
  become empty text.
- Resolution time must be greater than 0 and at most 720 hours. Ratings must be
  between 1 and 5; fractional ratings such as 4.5 are valid.
- Blank numeric values stay missing. Invalid numeric values are reported and
  changed to missing rather than deleting the whole ticket.
- Common category, priority, and status aliases are normalized. Unrecognized
  labels are kept and flagged for review.
- Optional CRM fields are checked when present. Invalid timestamps and dates
  where an update precedes creation are reported.
- Unresolved tickets have status Open, Pending, In Progress, Reopened, or On Hold.
  Unknown statuses are counted in their own group, not as unresolved.
- Quality findings can refer to rows later removed as duplicates. `source_row`
  identifies the row in the raw CSV.

## Assumptions and limitations

- The first duplicate is treated as the canonical record.
- The category list is fixed: Account, Billing, Product, Shipping, Technical,
  and Unknown. New categories need review.
- The 720-hour limit is a project assumption, not a rule for every CRM system.
- Source row numbers match physical CSV lines only when cells do not contain
  quoted newlines.
- Synthetic data is only for testing and does not represent real customers.
- EDA, the CLI, and API are supporting extras; the core assignment is the
  dataset, processor, analytics, tests, and documentation.

## Optional: API

Start the API from the activated virtual environment:

```powershell
uvicorn ticket_analytics.api:app --reload
```

Open `http://127.0.0.1:8000/docs` to view and try the endpoints.

## Manually checked results

These results come from the required `data/tickets.csv` dataset:

- Priority counts: High 7, Medium 7, Critical 5, Low 4.
- Unresolved: 8 tickets.
- Average rating: 77 points / 21 valid ratings = 3.67.
- Technical average resolution: (8 + 5.5 + 6 + 12 + 0.5 + 7) / 6 = 6.5 hours.
- Other category averages: Billing 2.17, Account 2.2, Shipping 2.5, Unknown 1.0.
- Quality findings: one duplicate ID and two invalid numbers (T014 resolution
  time 999; T021 rating -1).

## Tests

```powershell
python -m pytest -v
```

The test suite covers valid and invalid files, empty datasets, missing columns,
duplicate IDs, data-quality categorization, EDA, API responses, CLI behavior,
and report exports. The generated synthetic dataset and report files are
reproducible from the commands above.

Complete output from `python -m pytest -v` is also saved in
[docs/test_output.txt](./docs/test_output.txt):

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\HALCER\Desktop\Day_1\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\HALCER\Desktop\Day_1
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 40 items

tests/test_api.py::test_sample_api_payload_is_strict_json_serializable PASSED [  2%]
tests/test_api.py::test_uploaded_csv_api_payload_is_strict_json_serializable PASSED [  5%]
tests/test_cli.py::test_analyze_and_eda_default_to_required_dataset PASSED [  7%]
tests/test_cli.py::test_analyze_command_writes_csv_reports_and_eda_json PASSED [ 10%]
tests/test_eda.py::test_eda_profiles_missing_duplicates_invalid_values_and_distribution PASSED [ 12%]
tests/test_eda.py::test_eda_requires_positive_top_n PASSED               [ 15%]
tests/test_eda.py::test_eda_profiles_mixed_and_invalid_creation_dates PASSED [ 17%]
tests/test_outputs.py::test_data_quality_summary_uses_raw_validation_counts PASSED [ 20%]
tests/test_outputs.py::test_pipeline_exports_category_status_summary_and_quality_outputs PASSED [ 22%]
tests/test_processor_edge_cases.py::test_malformed_csv_raises_invalid_file_error PASSED [ 25%]
tests/test_processor_edge_cases.py::test_non_finite_resolution_times_are_invalid PASSED [ 27%]
tests/test_processor_edge_cases.py::test_non_finite_ratings_are_invalid PASSED [ 30%]
tests/test_processor_edge_cases.py::test_blank_values_stay_missing_not_invalid PASSED [ 32%]
tests/test_processor_edge_cases.py::test_analytics_with_non_unique_index PASSED [ 35%]
tests/test_processor_edge_cases.py::test_unknown_status_not_counted_as_unresolved PASSED [ 37%]
tests/test_synthetic_data.py::test_synthetic_dataset_generation_is_repeatable_and_adds_duplicate_cases PASSED [ 40%]
tests/test_synthetic_data.py::test_required_tickets_csv_contains_minimum_dataset_contract PASSED [ 42%]
tests/test_ticket_processor.py::test_valid_input_processes_with_float_measure_dtypes PASSED [ 45%]
tests/test_ticket_processor.py::test_duplicate_ids_are_deduplicated PASSED [ 47%]
tests/test_ticket_processor.py::test_missing_required_columns_raises PASSED [ 50%]
tests/test_ticket_processor.py::test_processing_does_not_change_raw_file_bytes PASSED [ 52%]
tests/test_ticket_processor.py::test_resolution_and_rating_boundary_values PASSED [ 55%]
tests/test_ticket_processor.py::test_header_only_csv_raises_empty_dataset_error PASSED [ 57%]
tests/test_ticket_processor.py::test_nonexistent_csv_raises_invalid_file_error PASSED [ 60%]
tests/test_ticket_processor.py::test_unparseable_csv_raises_invalid_file_error PASSED [ 62%]
tests/test_ticket_processor.py::test_zero_byte_csv_raises_empty_dataset_error PASSED [ 65%]
tests/test_ticket_processor.py::test_invalid_resolution_time_set_to_nan PASSED [ 67%]
tests/test_ticket_processor.py::test_invalid_customer_rating_set_to_nan PASSED [ 70%]
tests/test_ticket_processor.py::test_missing_category_filled PASSED      [ 72%]
tests/test_ticket_processor.py::test_analytics_report_structure PASSED   [ 75%]
tests/test_ticket_processor.py::test_count_unresolved_correct PASSED     [ 77%]
tests/test_ticket_processor.py::test_nonnumeric_measurements_are_flagged_and_cleaned PASSED [ 80%]
tests/test_ticket_processor.py::test_missing_ticket_id_is_retained_and_row_issue_is_categorized PASSED [ 82%]
tests/test_ticket_processor.py::test_string_index_and_whitespace_missing_are_handled PASSED [ 85%]
tests/test_ticket_processor.py::test_unknown_status_is_reported_but_not_counted_as_unresolved PASSED [ 87%]
tests/test_ticket_processor.py::test_status_synonyms_and_pending_status_follow_crm_lifecycle PASSED [ 90%]
tests/test_ticket_processor.py::test_optional_crm_fields_are_validated_and_typed PASSED [ 92%]
tests/test_ticket_processor.py::test_optional_crm_metrics_are_reported_by_channel_and_team PASSED [ 95%]
tests/test_ticket_processor.py::test_missing_numeric_values_are_reported_as_completeness_issues PASSED [ 97%]
tests/test_ticket_processor.py::test_required_dataset_analytics_match_manual_results PASSED [100%]

============================= 40 passed in 1.08s ==============================
```
