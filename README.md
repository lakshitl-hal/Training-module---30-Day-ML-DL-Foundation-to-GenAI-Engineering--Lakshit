# Support Ticket Analytics

A backend-only Python project for cleaning, validating, analyzing, and exploring
support-ticket CSV data. It includes a command-line interface, a FastAPI service,
focused automated tests, a small hand-built fixture, and a deterministic synthetic
dataset with deliberate data-quality defects.

## Project layout

```text
Day_1/
├── data/
│   ├── tickets.csv                 # Required 24-row hand-built dataset
│   └── tickets_synthetic.csv       # Larger CRM-style stress dataset
├── scripts/
│   └── generate_synthetic_data.py  # Reproducible dataset generator
├── src/ticket_analytics/
│   ├── analytics.py                # Clean-data metrics
│   ├── api.py                      # JSON API; no web UI or static hosting
│   ├── cli.py                      # analyze and eda commands
│   ├── eda.py                      # Raw-data profiling and quality checks
│   ├── processor.py                # CSV validation and cleaning
│   └── reporting.py                # Console and CSV output
├── tests/                           # Processor, EDA, API, and output tests
├── outputs/                         # CSV reports and raw-data EDA JSON
└── pyproject.toml
```

## Setup

Python 3.10 or newer is required.

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Use the pipeline

The default dataset is the required 24-row hand-built project fixture. Run the
cleaning pipeline and summary metrics:

```powershell
ticket-analytics analyze
```

Use the larger CRM-style stress dataset explicitly with `--input`:

```powershell
ticket-analytics analyze --input data\tickets_synthetic.csv
ticket-analytics analyze --input data\tickets.csv --output-dir reports\sample
```

`analyze` writes `summary_metrics.csv`, ticket counts by category/priority/status,
average resolution time by category, row-level `quality_issues.csv`, and
`eda_report.json`. When CRM fields exist, it also writes channel/team breakdowns
and response-time summaries. Each quality row includes its source CSV line,
ticket context, issue category, issue, original value, and cleaning action.
Quality findings include rows later dropped as duplicates; `source_row` refers
to the raw CSV line.

## Exploratory data analysis

EDA profiles the uncleaned input: shape, per-column missingness and cardinality,
numeric summaries and IQR outlier counts, categorical frequencies, numeric
correlations, duplicate IDs, invalid values with source-row examples, and monthly
ticket volume when a `created_at` column is available. IQR outliers are review
candidates, not automatically treated as bad records.

Print the EDA report as JSON or save it:

```powershell
ticket-analytics eda
ticket-analytics eda --input data\tickets_synthetic.csv
ticket-analytics eda --input data\tickets.csv --output reports\sample_eda.json
```

## Regenerate stress data

The synthetic data is deterministic and includes all seven required project
columns plus optional CRM fields: customer ID, channel, assigned team, creation
and update dates, first-response time, and reopen count. It includes realistic
variation, date trends, duplicate IDs, blank fields, inconsistent casing,
non-numeric values, invalid timestamps, and out-of-range metrics.

```powershell
python scripts\generate_synthetic_data.py --rows 1200 --seed 42
```

The generated records are synthetic and must not be interpreted as real customer
data. Use a different seed or row count to exercise the pipeline with other data.

## API

Start the backend API:

```powershell
uvicorn ticket_analytics.api:app --reload
```

Endpoints:

- `GET /` — health check
- `GET /sample` — cleaned synthetic tickets, validation findings, EDA, and analytics
- `GET /eda/sample` — EDA on the raw synthetic dataset
- `POST /upload` — process an uploaded CSV

Interactive API documentation is available at `/docs`. The API does not serve a
frontend and does not enable permissive cross-origin access by default.

## Data cleaning rules

- Rows without a ticket ID are retained and flagged for follow-up; they are
  excluded from duplicate matching.
- Duplicate ticket IDs keep their first row and are reported.
- Missing categories become `Unknown`; missing descriptions become empty strings.
- Missing priorities and statuses become `Unknown`.
- Resolution times must be numeric, greater than zero, and no more than 720 hours.
- Ratings must be numeric and within 1–5.
- Missing numeric values are preserved as missing; non-numeric and out-of-range
  values are reported and replaced with missing values.
- Category, priority, status, description, and ticket ID are trimmed.
- Category aliases are normalized (`Payments` → `Billing`, `Tech` → `Technical`,
  and similar mappings). The category vocabulary is fixed to Account, Billing,
  Product, Shipping, Technical, and Unknown.
- Priority and status aliases are canonicalized (`P1` → `Critical`, `New` →
  `Open`, `Solved` → `Resolved`). Other labels are title-cased; unrecognized
  category, priority, status, and channel values are retained and flagged.
- Optional CRM response-time and reopen-count fields are converted to numeric
  types and invalid values are flagged. CRM dates are parsed to UTC timestamps;
  invalid dates and update-before-create ordering are reported, but not dropped.
- Unresolved tickets include `Open`, `Pending`, `In Progress`, `Reopened`, and
  `On Hold`. Unknown statuses remain visible in their own status counts and are
  not treated as active.
- Data-quality findings are classified as identification, duplication,
  categorization, completeness, numeric validity, temporal validity, or temporal
  consistency.
- Quality findings include rows later dropped as duplicates; `source_row` refers
  to the raw CSV line.

The generated `outputs/` directory is ignored by Git and can be recreated with
`ticket-analytics analyze`; use `--output-dir` to choose another location.

The raw input is never modified. EDA runs against the raw data so cleaning does
not hide data-quality problems.

## Assumptions

- The first occurrence of a duplicate ticket ID is the canonical row; later
  occurrences are dropped from the cleaned dataset.
- A missing status is filled with `Unknown` and is not counted as unresolved.
- Ratings may be fractional, such as `4.5`, provided they are within 1–5.
- The 720-hour resolution and first-response limit is a business assumption,
  not a universal CRM rule.
- The category vocabulary is fixed; new categories are flagged for review
  rather than added automatically.
- `source_row` is calculated as the CSV record index plus the header row. It
  corresponds to a physical CSV line only when records contain no quoted
  newlines.

## Limitations

- The fixed category vocabulary may need updating for another organization.
- Synthetic data is for repeatable testing and does not represent real customer
  behavior.
- EDA, the API, and the CLI are supporting extras; the core assignment scope is
  the required dataset, processor, analytics, tests, and documentation.

## Manual verification

These values were calculated from the cleaned `data/tickets.csv` fixture:

- Priority counts: High = 7, Medium = 7, Critical = 5, Low = 4.
- Unresolved tickets: 8 (all 8 unresolved rows have status `Open`).
- Average rating: 77 total rating points / 21 valid ratings = 3.666..., rounded
  to 3.67. The invalid `-1` rating is excluded.
- Average resolution time by category:
  - Technical: (8 + 5.5 + 6 + 12 + 0.5 + 7) / 6 = 39 / 6 = 6.5 hours. The
    invalid 999-hour value for T014 is excluded.
  - Billing: 13 / 6 = 2.17 hours.
  - Account: 11 / 5 = 2.2 hours.
  - Shipping: 10 / 4 = 2.5 hours.
  - Unknown: 1 / 1 = 1.0 hour.
- Data quality: one duplicate ticket ID; two invalid measurements (T014 has
  999 resolution hours and T021 has a -1 customer rating).

## Tests

```powershell
python -m pytest -v
```

The test suite covers valid and invalid files, empty datasets, missing columns,
duplicate IDs, data-quality categorization, EDA, API responses, CLI behavior,
and report exports. The generated synthetic dataset and report files are
reproducible from the commands above.

Actual output from `python -m pytest -v`:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\HALCER\Desktop\Day_1\venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\HALCER\Desktop\Day_1
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 34 items

tests/test_api.py::test_sample_api_payload_is_strict_json_serializable PASSED [  2%]
tests/test_api.py::test_uploaded_csv_api_payload_is_strict_json_serializable PASSED [  5%]
tests/test_cli.py::test_analyze_and_eda_default_to_required_dataset PASSED [  8%]
tests/test_cli.py::test_analyze_command_writes_csv_reports_and_eda_json PASSED [ 11%]
tests/test_eda.py::test_eda_profiles_missing_duplicates_invalid_values_and_distribution PASSED [ 14%]
tests/test_eda.py::test_eda_requires_positive_top_n PASSED               [ 17%]
tests/test_eda.py::test_eda_profiles_mixed_and_invalid_creation_dates PASSED [ 20%]
tests/test_outputs.py::test_data_quality_summary_uses_raw_validation_counts PASSED [ 23%]
tests/test_outputs.py::test_pipeline_exports_category_status_summary_and_quality_outputs PASSED [ 26%]
tests/test_synthetic_data.py::test_synthetic_dataset_generation_is_repeatable_and_adds_duplicate_cases PASSED [ 29%]
tests/test_synthetic_data.py::test_required_tickets_csv_contains_minimum_dataset_contract PASSED [ 32%]
tests/test_ticket_processor.py::test_valid_input_processes_with_float_measure_dtypes PASSED [ 35%]
tests/test_ticket_processor.py::test_duplicate_ids_are_deduplicated PASSED [ 38%]
tests/test_ticket_processor.py::test_missing_required_columns_raises PASSED [ 41%]
tests/test_ticket_processor.py::test_processing_does_not_change_raw_file_bytes PASSED [ 44%]
tests/test_ticket_processor.py::test_resolution_and_rating_boundary_values PASSED [ 47%]
tests/test_ticket_processor.py::test_header_only_csv_raises_empty_dataset_error PASSED [ 50%]
tests/test_ticket_processor.py::test_nonexistent_csv_raises_invalid_file_error PASSED [ 52%]
tests/test_ticket_processor.py::test_unparseable_csv_raises_invalid_file_error PASSED [ 55%]
tests/test_ticket_processor.py::test_zero_byte_csv_raises_empty_dataset_error PASSED [ 58%]
tests/test_ticket_processor.py::test_invalid_resolution_time_set_to_nan PASSED [ 61%]
tests/test_ticket_processor.py::test_invalid_customer_rating_set_to_nan PASSED [ 64%]
tests/test_ticket_processor.py::test_missing_category_filled PASSED      [ 67%]
tests/test_ticket_processor.py::test_analytics_report_structure PASSED   [ 70%]
tests/test_ticket_processor.py::test_count_unresolved_correct PASSED     [ 73%]
tests/test_ticket_processor.py::test_nonnumeric_measurements_are_flagged_and_cleaned PASSED [ 76%]
tests/test_ticket_processor.py::test_missing_ticket_id_is_retained_and_row_issue_is_categorized PASSED [ 79%]
tests/test_ticket_processor.py::test_string_index_and_whitespace_missing_are_handled PASSED [ 82%]
tests/test_ticket_processor.py::test_unknown_status_is_reported_but_not_counted_as_unresolved PASSED [ 85%]
tests/test_ticket_processor.py::test_status_synonyms_and_pending_status_follow_crm_lifecycle PASSED [ 88%]
tests/test_ticket_processor.py::test_optional_crm_fields_are_validated_and_typed PASSED [ 91%]
tests/test_ticket_processor.py::test_optional_crm_metrics_are_reported_by_channel_and_team PASSED [ 94%]
tests/test_ticket_processor.py::test_missing_numeric_values_are_reported_as_completeness_issues PASSED [ 97%]
tests/test_ticket_processor.py::test_required_dataset_analytics_match_manual_results PASSED [100%]

============================= 34 passed in 1.04s ==============================
```
