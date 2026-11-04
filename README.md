# Ticket Pipeline — Engineering Practices, Exceptions & Testing

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 03 — Python Engineering Practices, Exceptions & Testing |
| **Author** | Lakshit (HALCER) |
| **Date** | 04 November 2026 |
| **Status** | Submitted for code review |
| **Test result** | 127 passed, 0 failed — [`logs/test_results.txt`](logs/test_results.txt) |
| **Coverage** | 100 % statements and branches — [`logs/coverage.txt`](logs/coverage.txt) |
| **Static checks** | `ruff` clean · `mypy --strict` clean — [`logs/static_checks.txt`](logs/static_checks.txt) |

---

## Contents

1. [Purpose and Project Context](#1-purpose-and-project-context)
2. [Acceptance Criteria Mapping](#2-acceptance-criteria-mapping)
3. [Package Structure](#3-package-structure)
4. [Component Specifications](#4-component-specifications)
5. [Error Reference](#5-error-reference)
6. [Logging Policy](#6-logging-policy)
7. [Ticket Data Contract](#7-ticket-data-contract)
8. [Analytics Contract](#8-analytics-contract)
9. [Setup](#9-setup)
10. [Usage](#10-usage)
11. [Testing](#11-testing)
12. [Design Rationale](#12-design-rationale)
13. [Assumptions](#13-assumptions)
14. [Limitations](#14-limitations)
15. [Execution Evidence](#15-execution-evidence)

---

## 1. Purpose and Project Context

The Day 03 project context is: **"Make the ticket pipeline testable and diagnosable."**

This repository applies the Day 03 practices to the **existing support-ticket pipeline**:

- the same ticket data contract (§7): `id`, `customer`, `priority`, `category`, `status`, `description`, `resolution_time_hours`, `customer_rating`, `created_at`;
- the same analytics contract (§8): counts, open and high-priority tickets, top customers, daily volume, average resolution time and average rating;
- the same sample dataset, `data/tickets.csv`.

A regression test proves that this dataset still produces the established results (§11.2).

The Day 03 work adds to that pipeline:

- **Specific, actionable errors:** one exception class, message and exit code per failure type.
- **Diagnosable, privacy-safe logs:** stage boundaries, line numbers and counts, but never customer names or descriptions.
- **Deterministic, independent tests:** unit and integration tests with fixtures and parametrised edge cases, mocking only external boundaries.
- **Clear type hints:** `mypy --strict` passes.
- **A clean package layout:** separate modules for models, processing, analytics and configuration.

The code is written for this repository. It does not import from any other project, and it has no runtime dependencies beyond the Python standard library.

---

## 2. Acceptance Criteria Mapping

| # | Acceptance criterion (Day 03) | How it is met | Evidence |
|---|---|---|---|
| 1 | Errors are specific and actionable | Six exception classes under `TicketPipelineError`, one per failure type. Every message states *what* failed, *where* (file, line, column) and *how to fix it*. Each fatal type has its own exit code (2–6). All problems in a row are reported together. Original exceptions are preserved with `raise … from exc`. | §5, `logs/error_scenarios.txt` |
| 2 | Logs help diagnose failures without exposing sensitive data | `key=value` logs at each stage boundary (stage, status, file name, line, column names, counts, duration). Customer names, descriptions, raw row values and full file paths are never logged. `Ticket.__repr__` hides customer and description. Tests assert that these values are absent from logs and output. | §6 |
| 3 | Tests are deterministic and independently runnable | Each test uses its own `tmp_path`. An autouse fixture clears environment variables and restores logger state. The clock is mocked. All 127 tests pass three runs in a row, in reverse order, and **each one alone in a fresh process**. | §11, `logs/test_isolation.txt` |
| 4 | Type hints improve clarity without becoming noise | Public functions, dataclasses and return types are annotated (`float \| None`, `Generator[RawRow, None, None]`, `ParamSpec` for the decorator). Local variables are left to inference. `mypy --strict` passes on source and tests. | `logs/static_checks.txt` |
| 5 | README gives reproducible setup instructions | §9 lists exact commands with tool versions, verified in a fresh clone and a new virtual environment. | §9 |

**Task coverage**

| Task | Delivered by |
|---|---|
| A — Package structure | §3 |
| B — Error handling and logs | `errors.py`, `logging_config.py`, loader, parser, pipeline, CLI |
| C — Test suite | `tests/`: fixtures in `conftest.py`, parametrised edge cases, boundary-only mocks |
| D — Quality pass | Full suite, coverage, ruff and mypy run; dead code removed; this README |

---

## 3. Package Structure

```
Day3/
├── pyproject.toml                  Metadata, dependencies, pytest / coverage / mypy / ruff settings
├── data/tickets.csv                Ticket sample dataset: 10 rows, 3 intentionally invalid
├── src/ticket_pipeline/
│   ├── __main__.py                 Enables `python -m ticket_pipeline`
│   ├── cli.py                      Arguments, output streams, exit codes
│   ├── config.py                   PipelineConfig: CLI > environment > defaults
│   ├── errors.py                   Exception hierarchy (§5)
│   ├── logging_config.py           configure_logging() and the @log_duration decorator
│   ├── pipeline.py                 Orchestration: load → parse → duplicate check → summarise
│   ├── models/ticket.py            Ticket, Priority, Status, Category, InvalidTicketField
│   ├── processing/loader.py        CSVLoader: lazy reading and file-level checks
│   ├── processing/parser.py        parse_row(): raw strings → validated Ticket
│   └── analytics/summary.py        Analytics contract: pure functions (§8)
├── tests/
│   ├── conftest.py                 Shared fixtures and per-test isolation
│   ├── sample_data.py              Ticket CSV constants used by the tests
│   ├── unit/                       One component at a time (106 tests)
│   └── integration/                Real files through loader → parser → pipeline → CLI (21 tests)
└── logs/                           Saved evidence (§15)
```

**Dependency direction:** `models` imports nothing from the package. `processing` imports `models` and `errors`. `analytics` imports `models`. `pipeline` composes `processing` and `analytics`. Only `cli` configures logging and reads arguments. Only `config` reads environment variables.

---

## 4. Component Specifications

| Module | Responsibility | Raises |
|---|---|---|
| `config.PipelineConfig` | Frozen settings (`input_path`, `log_level`, `strict`). `from_sources()` applies CLI argument > environment variable > default; the environment is injectable for tests. | `ConfigurationError` |
| `processing.loader.CSVLoader` | Checks the path, then yields `RawRow(line, values)` lazily from inside a `with` block, so the file is always closed. Normalises header names **once** (trim and lower-case), then rejects blank or duplicate names. Parses in strict CSV mode, skips blank lines, pads short rows, records the line where each row starts. | `InputPathError`, `MalformedFileError`, `SchemaMismatchError` |
| `processing.parser.parse_row` | Converts one row to a `Ticket` and applies the normalisation rules in §7. Collects **every** problem in the row before raising. | `InvalidRowError` (chained to the original `ValueError`) |
| `models.ticket.Ticket` | Frozen dataclass validated in `__post_init__`. `ClassVar` constants for limits. `customer` and `description` excluded from `repr`. | `InvalidTicketField` (a `ValueError`) |
| `pipeline.run_pipeline` | Runs the stages, catches `InvalidRowError` per row, rejects duplicate IDs, logs each stage, returns a frozen `PipelineResult`. | File-level errors propagate; `RejectedRowsError` in strict mode |
| `analytics.summary` | The analytics contract (§8). No I/O and no logging. | `ValueError` for a negative `n` in `top_customers` |
| `logging_config` | `configure_logging()` attaches one stderr handler to the `ticket_pipeline` logger only. It is idempotent and does not touch the root logger. `@log_duration(stage)` logs outcome and duration at DEBUG and re-raises any exception unchanged. | — |
| `cli.main` | Parses arguments, prints the report to stdout, maps each `TicketPipelineError` to its exit code. Any other exception propagates with its traceback. | — |

---

## 5. Error Reference

| Exception | Exit code | Raised when | Example message (from `logs/error_scenarios.txt`) |
|---|---|---|---|
| `ConfigurationError` | 2 | `TICKET_PIPELINE_LOG_LEVEL` holds an unknown level | `Unknown log level 'LOUD'. Use one of: DEBUG, INFO, WARNING, ERROR.` |
| *(argparse usage error)* | 2 | Unknown option or invalid `--log-level` | `argument --log-level: invalid choice: 'LOUD'` |
| `InputPathError` | 3 | Path missing, a directory, not `.csv`, or permission denied | `Input file not found: 'missing.csv'. Check the path, or pass --input with the correct location.` |
| `MalformedFileError` | 4 | Empty file; not UTF-8; blank header name; **header names duplicated after trimming and lower-casing**; row with surplus fields; NUL byte; unbalanced or stray quote; oversized field | `Header repeats column(s) after ignoring case and spaces: 'id' appears as 'id', ' ID ' (duplicate_header.csv, line 1). Keep exactly one column for each name.` |
| `SchemaMismatchError` | 5 | Required ticket columns absent from the header | `old_format.csv is missing required column(s): category, created_at, customer, description, status. Found columns: id, priority. Add the missing column(s) to the header row.` |
| `RejectedRowsError` | 6 | `--strict` is set and at least one row was rejected; the message lists every rejected row | `3 of 10 row(s) were rejected and strict mode is on: …` |
| `InvalidRowError` | — | A row breaks one or more rules. Recoverable: caught per row and reported, never fatal on its own | `line 3: 'priority' value 'critical' is not one of: low, medium, high, urgent; 'created_at' value '2024-13-01' is not an ISO 8601 date (YYYY-MM-DD)` |

All classes derive from `TicketPipelineError`, so a caller can handle every expected failure with one `except` clause.

The CLI deliberately does **not** catch `Exception`. An unexpected error is a bug, and turning it into an exit code would hide the traceback needed to fix it. `test_unexpected_bug_is_not_hidden` enforces this.

---

## 6. Logging Policy

| Logged | Not logged |
|---|---|
| Stage and status (`stage=parse status=rejected`) | Customer names |
| File **name** (`file=tickets.csv`) | Ticket descriptions |
| Line number and **column names** of a rejected row | Raw row values |
| Counts (`rows=10 valid=7 rejected=3`) | Full file-system paths (they can contain user names) |
| Error class and exit code on failure | Tracebacks of expected, handled errors |
| Stage duration (DEBUG) | |

| Level | Used for |
|---|---|
| `DEBUG` | Header column count; skipped blank lines; stage duration |
| `INFO` | Start and completion of a stage, with counts |
| `WARNING` | A rejected row; a header-only file |
| `ERROR` | The run failed (error class and exit code) |

Logs go to **stderr** and the report goes to **stdout**, so `python -m ticket_pipeline > report.txt` saves a clean report. Library modules only create loggers (`logging.getLogger(__name__)`); only the CLI attaches a handler, and only to the package's own logger.

The printed **report** (stdout) lists top customers by name, because the operator running the tool needs them. That information is deliberately kept out of logs, which are often shipped to shared systems.

---

## 7. Ticket Data Contract

| Column | Required | Rule |
|---|---|---|
| `id` | Yes | Non-empty; unique within the file. IDs differing only by case or spaces (`T001`, ` t001 `) count as duplicates |
| `customer` | Yes | Non-empty text; stored title-cased; treated as personal data |
| `priority` | Yes | `low`, `medium`, `high`, `urgent` (any case) |
| `category` | Yes | `billing`, `technical`, `account`, `general` (any case). Any other value is stored as `unknown`, an explicit representation, not an error |
| `status` | Yes | `open`, `pending`, `resolved`, `closed` (any case) |
| `description` | Yes | Non-empty, at most 500 characters; treated as sensitive free text |
| `resolution_time_hours` | No | Empty, or a finite number ≥ 0. `inf`, `nan`, `1e400`, negatives and `2_0` are rejected |
| `customer_rating` | No | Empty, or a whole number 1–5. `3.5`, `4.0`, `0`, `6` and `1_0` are rejected |
| `created_at` | Yes | ISO 8601 date or date-time, e.g. `2024-01-15` |

**Header rules:** names are trimmed and lower-cased once, when the header is read. Two cells that become the same name (`id` and ` ID `) are rejected, because one would silently overwrite the other. Extra columns are allowed and ignored.

**Sample data:** `data/tickets.csv` has 10 rows. Rows on file lines 4, 7 and 9 are intentionally invalid (missing customer, missing description, missing customer and category).

---

## 8. Analytics Contract

| Output | Definition |
|---|---|
| `total` | Number of valid tickets |
| `by_priority` / `by_status` / `by_category` | Count per value, sorted by name |
| `open_count` | Tickets whose status is `open` or `pending` |
| `high_priority_open_ids` | IDs of open or pending tickets with priority `high` or `urgent` |
| `top_customers` | The three customers with most tickets; ties broken alphabetically |
| `daily_volume` | Tickets per `created_at` date, sorted by date |
| `average_resolution_hours` | Mean of recorded resolution times, rounded to 2 decimals; `None` if none recorded |
| `average_rating` | Mean of recorded ratings, rounded to 2 decimals; `None` if none recorded |

**Established results on `data/tickets.csv`** (asserted by `test_bundled_dataset_keeps_the_established_results`):

| Output | Value |
|---|---|
| Rows read / valid / rejected | 10 / 7 / 3 |
| `by_priority` | high 2, low 2, medium 2, urgent 1 |
| `by_status` | closed 2, open 2, pending 2, resolved 1 |
| `by_category` | account 1, billing 2, technical 3, unknown 1 |
| `open_count` | 4 |
| `high_priority_open_ids` | T001, T004, T009 |
| `average_resolution_hours` | 3.80 |
| `average_rating` | 3.83 |
| `daily_volume` | 7 dates, 1 ticket each |

---

## 9. Setup

**Prerequisites:** Python 3.11 or later (tested with Python 3.12.10 on Windows 11) and Git.

```bash
git clone <repository-url> Day3
cd Day3
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Windows (Git Bash):   source .venv/Scripts/activate
# macOS / Linux:        source .venv/bin/activate
python -m pip install -e ".[dev]"
```

`-e ".[dev]"` installs the package in editable mode with the development tools. The versions used were pytest 9.2.0, pytest-cov 7.1.0, mypy 2.4.1 and ruff 0.17.3.

The package uses a `src/` layout, so it must be installed (this step) before `python -m ticket_pipeline` will run. The tests run either way, because `pyproject.toml` adds `src` to pytest's path.

**Verify the setup:**

```bash
python -m pytest                 # expected: 127 passed
python -m pytest --cov           # expected: TOTAL ... 100%
python -m ruff check .           # expected: All checks passed!
python -m mypy src tests         # expected: Success: no issues found
python -m ticket_pipeline        # expected: Rows read: 10 | valid: 7 | rejected: 3
```

---

## 10. Usage

```bash
python -m ticket_pipeline                              # process data/tickets.csv
python -m ticket_pipeline --input path/to/file.csv    # process another file
python -m ticket_pipeline --log-level DEBUG           # include stage durations
python -m ticket_pipeline --strict                    # exit 6 if any row is rejected
ticket-pipeline --input path/to/file.csv              # installed console script, same options
```

| Setting | CLI option | Environment variable | Default |
|---|---|---|---|
| Input file | `--input` | `TICKET_PIPELINE_INPUT` | `data/tickets.csv` |
| Log level | `--log-level` | `TICKET_PIPELINE_LOG_LEVEL` | `INFO` |
| Strict mode | `--strict` | — | off |

Excerpt of actual output (full output in `logs/pipeline_output.txt`):

```
INFO    ticket_pipeline.pipeline | stage=load status=started file=tickets.csv
WARNING ticket_pipeline.pipeline | stage=parse status=rejected line=4 columns=customer
WARNING ticket_pipeline.pipeline | stage=parse status=rejected line=7 columns=description
WARNING ticket_pipeline.pipeline | stage=parse status=rejected line=9 columns=customer,category
INFO    ticket_pipeline.pipeline | stage=parse status=completed file=tickets.csv rows=10 valid=7 rejected=3
Source: tickets.csv
Rows read: 10 | valid: 7 | rejected: 3
Rejected rows:
  - line 4: 'customer' is required but empty
  - line 7: 'description' is required but empty
  - line 9: 'customer' is required but empty; 'category' is required but empty

TICKET SUMMARY
  Valid tickets            : 7
  Open / pending           : 4
  High-priority open       : T001, T004, T009
  Average resolution time  : 3.80 h
  Average customer rating  : 3.83 / 5
  ...
```

---

## 11. Testing

```bash
python -m pytest                    # all tests
python -m pytest tests/unit         # unit tests only
python -m pytest -m integration     # integration tests only
python -m pytest "tests/unit/test_parser.py::test_invalid_values_report_column_and_reason[hours-nan]"
```

| File | Type | Tests | What is covered |
|---|---|---|---|
| `unit/test_ticket.py` | Unit | 29 | Every field rule; `inf`/`-inf`/`nan`/negative/bool hours; ratings `0`, `6`, `3.5`, `4.0`, `True`; open = open or pending; immutability; customer and description hidden from `repr`/`str` |
| `unit/test_parser.py` | Unit | 31 | Normalisation; unknown category → `unknown`; absent optional columns; each empty required column; 16 named invalid-value cases; all issues in a row reported together; exception chaining; no personal data in messages |
| `unit/test_loader.py` | Unit | 28 | Line numbers (blank lines, multi-line quoted fields); blank and whitespace-only lines; lazy reading; BOM and header normalisation; **duplicate headers: exact, case, whitespace, case + whitespace**; three bad-path cases; eight malformed-file cases; schema mismatch; permission denied; `repr` without full path |
| `unit/test_config_and_logging.py` | Unit | 10 | Configuration precedence; invalid log level; `@log_duration` success, failure and metadata; idempotent logging setup |
| `unit/test_summary.py` | Unit | 8 | Every analytics output; tie-breaking; negative `n`; empty input; generator input |
| `integration/test_pipeline_and_cli.py` | Integration | 21 | **Established results on the ticket dataset**; mixed valid and invalid files; duplicate IDs (including a duplicate of a rejected row); strict mode; log content without personal data; stdout/stderr separation; one exit code per failure type; unexpected bugs not hidden; installed package run in a subprocess |
| **Total** | | **127** | **127 passed, 0 failed · 100 % branch coverage** |

### 11.1 Test design rules

| Rule | How it is applied |
|---|---|
| Assert behaviour, not implementation | Tests check returned values, exception types and attributes, messages, exit codes and log text, not private functions or call order. |
| Fixtures for sample data | `write_csv` (factory that writes a ticket CSV into `tmp_path`) and `sample_csv` (three valid tickets), in `conftest.py`. |
| Parametrise edge cases | Invalid values, bad paths, malformed files, duplicate headers and exit codes are parametrised, each with a readable ID such as `[hours-nan]`. |
| Mock only external boundaries | Mocked: the clock (`time.perf_counter`), the operating system (`Path.open` raising `PermissionError`) and the environment (injected mapping or `monkeypatch`). The file system is **not** mocked; tests use real temporary files. Internal components are never mocked, except one test that simulates a bug to prove it is not hidden. |
| Determinism and independence | An autouse fixture clears `TICKET_PIPELINE_*` variables and restores logger state after every test. No test depends on another test, the working directory, the real clock or the network. |

### 11.2 Behaviour preserved from the existing pipeline

`test_bundled_dataset_keeps_the_established_results` runs the full pipeline on `data/tickets.csv` and asserts every value in the §8 results table. Any change that alters the established ticket behaviour fails this test.

### 11.3 Verifying that the tests detect defects

Ten defects were introduced into the code one at a time, and the full suite was run after each. **All ten were detected** (`logs/defect_detection.txt`), among them: accepting `inf`/`nan`, truncating a 3.5 rating, accepting duplicate normalised headers, accepting case-variant duplicate IDs, writing row values to the log, parsing unbalanced quotes leniently, and catching every `Exception` in the CLI.

---

## 12. Design Rationale

### 12.1 Recoverable vs fatal errors

A bad **row** is expected in real data, so it is raised as `InvalidRowError`, caught for that row only and reported, and processing continues. A bad **file** (missing, unreadable, ambiguous header, wrong schema) means no trustworthy result is possible, so the error propagates to the CLI, which prints it and exits with that error's code. `--strict` lets a caller such as a scheduled job treat any bad row as fatal.

### 12.2 Catch narrowly, chain always

Every `except` names a specific exception (`UnicodeDecodeError`, `PermissionError`, `csv.Error`, `ValueError`, `InvalidTicketField`, `InvalidRowError`, `TicketPipelineError`). No code catches `Exception`. When a low-level error is translated, `raise … from exc` keeps the original as `__cause__`.

### 12.3 Reject ambiguity instead of guessing

Header names are normalised once, and two names that collide are rejected rather than letting the last one win. The same principle applies to ticket IDs (case-insensitive duplicates), unbalanced quotes (strict CSV mode), NUL bytes and day-first dates.

### 12.4 Exit codes belong to the exception

Each exception class declares `exit_code`. The CLI has one handler, `except TicketPipelineError as exc: return exc.exit_code`, so adding an error type needs no CLI change.

### 12.5 Configuration and laziness

Only `config.py` reads environment variables; other modules receive a `PipelineConfig`. `CSVLoader.iter_rows()` is a generator, so the pipeline holds one row at a time and the `with` block closes the file in every case.

---

## 13. Assumptions

| # | Assumption |
|---|---|
| 1 | Input files are UTF-8, with or without a byte-order mark. |
| 2 | The first line of the file is the header row. |
| 3 | Dates are ISO 8601. Day-first formats such as `15/01/2024` are rejected rather than guessed. |
| 4 | The first row using a ticket ID is the authoritative one; later rows with the same ID are rejected. |
| 5 | An empty optional cell means "not recorded" and is stored as `None`. |
| 6 | The person running the CLI may see the path they supplied in error messages; logs contain only the file name. |

---

## 14. Limitations

| # | Limitation | Impact |
|---|---|---|
| 1 | Logs are plain `key=value` text, not JSON | Easy to read and search; a log platform would need a parser or a JSON formatter |
| 2 | Duplicate detection is within one file | Duplicates across separate runs are not detected |
| 3 | Unrecognised categories become `unknown` rather than being rejected | Deliberate, to keep the established behaviour; visible in the category counts |
| 4 | Only CSV input is supported | Other formats need a new loader |
| 5 | Fields larger than Python's CSV limit (131,072 characters) are rejected | Very large free-text fields cannot be processed |
| 6 | The default input path is relative to the source tree | When installed without `-e`, pass `--input` or set `TICKET_PIPELINE_INPUT` |

---

## 15. Execution Evidence

| File | Content |
|---|---|
| [`logs/test_results.txt`](logs/test_results.txt) | Full verbose test output — 127 passed |
| [`logs/coverage.txt`](logs/coverage.txt) | Statement and branch coverage — 100 % |
| [`logs/test_isolation.txt`](logs/test_isolation.txt) | Three repeated runs, a reverse-order run, and each test run alone — all pass |
| [`logs/defect_detection.txt`](logs/defect_detection.txt) | Ten deliberate defects — all detected |
| [`logs/static_checks.txt`](logs/static_checks.txt) | `ruff check .` and `mypy src tests` (strict) — both clean |
| [`logs/pipeline_output.txt`](logs/pipeline_output.txt) | Full run on `data/tickets.csv`: logs and report |
| [`logs/error_scenarios.txt`](logs/error_scenarios.txt) | Ten prepared inputs showing each failure type, its message and its exit code |

Environment: Windows 11, Python 3.12.10, pytest 9.2.0, pytest-cov 7.1.0, mypy 2.4.1, ruff 0.17.3.
