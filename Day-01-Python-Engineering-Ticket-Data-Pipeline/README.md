# Support Ticket Analytics

## Project overview

Support Ticket Analytics is a Python application for validating, cleaning, and
analyzing support-ticket data stored in CSV files. It produces ticket metrics,
data-quality findings, and an exploratory data analysis (EDA) profile.

The project is designed to preserve the original input file. Data cleaning is
performed in memory, and reports are written separately to an output directory.

## Project objectives

The application is intended to:

1. Load a support-ticket CSV and validate its structure.
2. Clean supported fields without changing the source file.
3. Identify missing, duplicate, invalid, and unrecognized values.
4. Calculate ticket and service metrics.
5. Export analysis and data-quality results in reusable formats.
6. Verify behavior through automated tests.

## Project structure

| Path | Description |
|---|---|
| `data/tickets.csv` | Required assignment dataset and default CLI input. |
| `data/tickets_synthetic.csv` | Synthetic dataset for exercising additional cases. |
| `src/ticket_analytics/processor.py` | CSV loading, schema checks, validation, and cleaning. |
| `src/ticket_analytics/analytics.py` | Metric calculations and data-quality summaries. |
| `src/ticket_analytics/reporting.py` | Console output and CSV report exports. |
| `src/ticket_analytics/eda.py` | Profiles the source data before cleaning. |
| `src/ticket_analytics/cli.py` | Command-line interface. |
| `src/ticket_analytics/api.py` | Optional FastAPI service. |
| `tests/` | Automated tests for the processor, analytics, CLI, EDA, API, and outputs. |
| `outputs/` | Default destination for generated analysis reports. |

## Requirements

- Python 3.10 or later
- pip

Project dependencies are declared in `pyproject.toml`. The development
dependency group includes pytest.

## Installation

Run the following commands in PowerShell from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell prevents virtual-environment activation, update the execution
policy for the current user as appropriate for your environment:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Command-line usage

After installation, run the analysis pipeline with the default dataset:

```powershell
ticket-analytics analyze
```

The `analyze` command is the default when no command is specified. It validates
and cleans the input, prints summary metrics, and writes reports to `outputs/`.
To select another input file or output directory:

```powershell
ticket-analytics analyze --input data\tickets_synthetic.csv --output-dir outputs\synthetic
```

To profile a CSV without cleaning it, run EDA:

```powershell
ticket-analytics eda
ticket-analytics eda --input data\tickets_synthetic.csv
```

EDA prints a JSON report to the console by default. To save it to a file:

```powershell
ticket-analytics eda --input data\tickets.csv --output outputs\eda.json
```

The `--output` option applies to EDA. The `--output-dir` option applies to
analysis. Run `ticket-analytics --help` for command-line help.

## Input data contract

The input must be a readable CSV file with a header row. The following columns
are required:

| Column | Description |
|---|---|
| `ticket_id` | Ticket identifier. Blank identifiers are retained and flagged. |
| `category` | Ticket category. |
| `priority` | Ticket priority. |
| `description` | Ticket description. |
| `resolution_time_hours` | Resolution duration in hours. |
| `customer_rating` | Customer rating. |
| `status` | Ticket lifecycle status. |

CSV records must have the same number of fields as the header. Rows with an
extra or missing field, or malformed CSV quoting, are rejected with a processing
error rather than silently reinterpreted.

The following CRM fields are optional and validated when present:

| Column | Validation |
|---|---|
| `customer_id` | Trimmed; blank values are represented as `Unknown`. |
| `channel` | Trimmed and checked against the supported channel labels. |
| `assigned_team` | Trimmed; blank values are represented as `Unknown`. |
| `first_response_time_hours` | Numeric and within the inclusive range 0–720. |
| `reopen_count` | A nonnegative integer. |
| `created_at`, `updated_at` | Parsed as UTC timestamps; invalid dates and an update before creation are reported. |

## Cleaning and validation rules

- The source CSV is read but never overwritten.
- Required-column and CSV record-width checks run before cleaning.
- Text fields are trimmed. Missing category, priority, and status values become
  `Unknown`; missing descriptions become empty text.
- Missing ticket IDs are retained and flagged.
- Duplicate ticket IDs are compared after trimming whitespace. The first
  occurrence is retained; subsequent occurrences are removed from the cleaned
  data and recorded as quality issues.
- Resolution time must be greater than 0 and no more than 720 hours. Customer
  ratings must be between 1 and 5, inclusive; fractional ratings are accepted.
- Blank numeric values remain missing. Nonnumeric, non-finite, and out-of-range
  numeric values are reported and set to missing; the entire ticket is not
  discarded for these issues.
- Common category, priority, and status aliases are normalized. Unrecognized
  labels are retained and flagged for review.
- Quality issues may refer to a duplicate row that is not present in the
  cleaned dataset. The `source_row` field identifies its row in the raw input.
- The validation report distinguishes `raw_missing_values_per_column` from
  `missing_values_per_column`. The former counts missing source values; the
  latter describes the final cleaned, deduplicated dataset.

### Supported labels and aliases

- Categories: Account, Billing, Product, Shipping, Technical, and Unknown.
  Examples of aliases include Account Services → Account, Payments → Billing,
  Tech Support → Technical, and Delivery → Shipping.
- Priorities: Low, Medium, High, and Critical. P1/Urgent map to Critical; P2
  maps to High; Normal/P3 map to Medium; P4 maps to Low.
- Status aliases include New → Open, Working → In Progress, Re-opened →
  Reopened, and Solved/Complete/Completed → Resolved.
- Supported channels are Email, Chat, Phone, Web Form, and Social.

Unrecognized categories, priorities, statuses, and channels are preserved and
flagged rather than silently dropped.

## Metrics

The analytics report includes:

- Total cleaned tickets.
- Average resolution time and average customer rating.
- Open and unresolved ticket counts.
- Ticket counts by category, priority, status, channel, and assigned team.
- Average resolution time by category.
- Average first-response time by channel when that field is available.
- Reopened ticket count and total reopen events when that field is available.
- Missing-value counts for the cleaned data and raw-data quality findings.

Unresolved tickets are those with status Open, Pending, In Progress, Reopened,
or On Hold. Unrecognized statuses remain in the status distribution and are not
counted as unresolved.

## Generated analysis files

The `analyze` command writes the following files to the selected output
directory:

| File | Contents |
|---|---|
| `summary_metrics.csv` | Scalar summary metrics, including data-quality totals. |
| `tickets_by_category.csv` | Ticket counts by category. |
| `tickets_by_priority.csv` | Ticket counts by priority. |
| `tickets_by_status.csv` | Ticket counts by status. |
| `tickets_by_channel.csv` | Ticket counts by channel, when available. |
| `tickets_by_assigned_team.csv` | Ticket counts by assigned team, when available. |
| `average_resolution_time_by_category.csv` | Average resolution time for each category. |
| `quality_issues.csv` | Row-level validation findings and the action taken. |
| `average_first_response_time_by_channel.csv` | First-response averages, when data is available. |
| `eda_report.json` | EDA profile of the uncleaned source data. |

The first-response CSV is generated only when first-response data is available.

## Reference results

The bundled assignment dataset contains 24 source rows. The current pipeline
retains 23 rows after removing one duplicate ticket ID. The following results
provide a reference check for `data/tickets.csv`:

| Check | Result |
|---|---|
| Priority counts | High: 7; Medium: 7; Critical: 5; Low: 4 |
| Unresolved tickets | 8 |
| Average customer rating | 3.67 (77 points across 21 valid ratings) |
| Average Technical resolution time | 6.50 hours |
| Duplicate ticket IDs | 1 |
| Invalid numeric values | T014 resolution time (999 hours); T021 customer rating (-1) |

These are dataset-specific reference values. Results will differ when another
input CSV is supplied.

## Exploratory data analysis

EDA profiles the input before cleaning. The report includes dataset dimensions,
column information, missing and invalid values, duplicate identifiers,
distributions for selected fields, numeric summaries, and monthly ticket counts
when creation dates are available.

## Optional API

The project includes a FastAPI application. Start it from the project root
after installation:

```powershell
uvicorn ticket_analytics.api:app --reload
```

The API uses `data/tickets_synthetic.csv` for its sample endpoints. Available
routes are:

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Health check. |
| `GET` | `/sample` | Analyze the bundled synthetic dataset. |
| `GET` | `/eda/sample` | Return an EDA profile of the bundled synthetic dataset. |
| `POST` | `/upload` | Validate and analyze an uploaded CSV file. |

Interactive API documentation is available at `http://127.0.0.1:8000/docs`
while the local server is running.

## Tests

Run the complete test suite from the project root:

```powershell
python -m pytest -q
```

The tests cover valid and invalid input, malformed CSV records, required
columns, empty files, numeric boundaries, non-finite values, missing data,
duplicate handling, raw-file preservation, analytics, report exports, EDA,
CLI behavior, and API responses.

## Assumptions and limitations

- The first row for a duplicate ticket ID is considered the canonical record.
- The supported category list is fixed; new labels are retained and flagged for
  review rather than added automatically.
- The maximum resolution duration of 720 hours is a project validation rule,
  not a universal customer-support policy.
- `source_row` identifies a CSV reader record. A record containing quoted
  newlines may span more than one physical text line.
- The synthetic dataset is intended for testing and does not represent real
  customer data.
