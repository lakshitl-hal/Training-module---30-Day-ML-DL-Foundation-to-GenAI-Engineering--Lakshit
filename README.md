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
│   └── processor.py                # CSV validation and cleaning
├── tests/                           # Processor, EDA, API, and output tests
├── outputs/                         # CSV reports and raw-data EDA JSON
└── pyproject.toml
```

## Setup

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Use the pipeline

The default dataset has 1,212 raw rows: 1,200 generated tickets plus intentional
duplicate records. After duplicate removal, tickets without IDs are retained for
review, so the cleaned dataset contains 1,200 rows. Run the cleaning pipeline and
summary metrics:

```powershell
ticket-analytics analyze
```

Choose the required small project dataset with `--input`:

```powershell
ticket-analytics analyze --input data\tickets.csv
ticket-analytics analyze --input data\tickets.csv --output-dir reports\sample
```

`analyze` writes `summary_metrics.csv`, ticket counts by category/priority/status,
average resolution time by category, row-level `quality_issues.csv`, and
`eda_report.json`. When CRM fields exist, it also writes channel/team breakdowns
and response-time summaries. Each quality row includes its source CSV line,
ticket context, issue category, issue, original value, and cleaning action.

## Exploratory data analysis

EDA profiles the uncleaned input: shape, per-column missingness and cardinality,
numeric summaries and IQR outlier counts, categorical frequencies, numeric
correlations, duplicate IDs, invalid values with source-row examples, and monthly
ticket volume when a `created_at` column is available. IQR outliers are review
candidates, not automatically treated as bad records.

Print the EDA report as JSON or save it:

```powershell
ticket-analytics eda
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
- Resolution times must be numeric, greater than zero, and no more than 720 hours.
- Ratings must be numeric and within 1–5.
- Missing numeric values are preserved as missing; non-numeric and out-of-range
  values are reported and replaced with missing values.
- Priority and status text are trimmed and title-cased. Unrecognized values are
  retained, categorized, and flagged instead of being silently dropped.
- Common CRM aliases are canonicalized (`P1` → `Critical`, `New` → `Open`,
  `Solved` → `Resolved`) before validation and reporting.
- Optional CRM response-time and reopen-count fields are converted to numeric
  types and invalid values are flagged. CRM dates are parsed to UTC timestamps;
  invalid dates and update-before-create ordering are reported.
- Unresolved tickets include active lifecycle states (`Open`, `Pending`,
  `In Progress`, `Reopened`, and `On Hold`). Unknown statuses remain visible in
  their own status counts and are not silently treated as active.
- Data-quality findings are classified as identification, duplication,
  categorization, completeness, numeric validity, temporal validity, or temporal
  consistency.

The generated `outputs/` directory is ignored by Git and can be recreated with
`ticket-analytics analyze`; use `--output-dir` to choose another location.

The raw input is never modified. EDA runs against the raw data so cleaning does
not hide data-quality problems.

## Tests

```powershell
python -m pytest
```

The test suite covers valid and invalid files, empty datasets, missing columns,
duplicate IDs, data-quality categorization, EDA, API responses, CLI behavior,
and report exports. The generated synthetic dataset and report files are
reproducible from the commands above.

Latest verification:

```text
python -m pytest -q
27 passed in 1.02s
```

For the 1,200-row cleaned synthetic dataset, the priority and channel report
totals each equal 1,200, the mean resolution time is 38.29 hours, and the raw
EDA monthly counts sum to its 1,208 valid creation dates. The generated run
reported 213 row-level quality findings.
