# Ticket Pipeline — Engineering Practices, Exceptions & Testing

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 03 — Python Engineering Practices, Exceptions & Testing |
| **Author** | Lakshit (HALCER) |
| **Date** | 04 November 2026 |
| **Status** | Submitted for code review |
| **Test result** | 94 passed, 0 failed — see [`logs/test_results.txt`](logs/test_results.txt) |
| **Static checks** | `ruff` clean · `mypy --strict` clean — see [`logs/static_checks.txt`](logs/static_checks.txt) |

---

## Contents

1. [Purpose](#1-purpose)
2. [Acceptance Criteria Mapping](#2-acceptance-criteria-mapping)
3. [Package Structure](#3-package-structure)
4. [Component Specifications](#4-component-specifications)
5. [Error Reference](#5-error-reference)
6. [Logging Policy](#6-logging-policy)
7. [Data Contract](#7-data-contract)
8. [Setup](#8-setup)
9. [Usage](#9-usage)
10. [Testing](#10-testing)
11. [Design Rationale](#11-design-rationale)
12. [Assumptions](#12-assumptions)
13. [Limitations](#13-limitations)
14. [Execution Evidence](#14-execution-evidence)

---

## 1. Purpose

This project makes a support-ticket pipeline **testable and diagnosable**. It reads a CSV file of tickets, validates every row, and prints a summary. It is built to show the four Day 03 practices:

- **Specific, actionable errors:** each failure type has its own exception class, message and exit code.
- **Safe, useful logging:** logs record stage boundaries, line numbers and counts, and never personal data.
- **Deterministic, independent tests:** unit and integration tests use fixtures and parametrisation, and mock only external boundaries.
- **Clear type hints:** the source passes `mypy --strict`.

The package has no runtime dependencies beyond the Python standard library.

---

## 2. Acceptance Criteria Mapping

| # | Acceptance criterion (Day 03) | How it is met | Evidence |
|---|---|---|---|
| 1 | Errors are specific and actionable | Six exception classes under `TicketPipelineError`, one per failure type. Every message states *what* failed, *where* (file, line, column) and *how to fix it*. Each fatal type maps to its own exit code. Original exceptions are preserved with `raise … from exc`. | §5, `logs/error_scenarios.txt` |
| 2 | Logs help diagnose failures without exposing sensitive data | Logs at stage boundaries in `key=value` form (stage, status, file name, line, column, counts, duration). Customer e-mail addresses, raw row values and full file-system paths are never logged. `Ticket.__repr__` excludes the e-mail. Tests assert that no e-mail address appears in logs or output. | §6, `test_logs_describe_stages_without_personal_data` |
| 3 | Tests are deterministic and independently runnable | Each test uses its own `tmp_path`; environment variables and logger state are reset by an autouse fixture; the clock is mocked. All 94 tests pass three runs in a row, in reverse order, and **each one alone in a fresh process**. | §10, `logs/test_isolation.txt` |
| 4 | Type hints improve clarity without becoming noise | Public functions, dataclasses and return types are annotated (`float \| None`, `Generator[RawRow, None, None]`, `ParamSpec` for the decorator). Local variables are left to inference. `mypy --strict` passes on source and tests. | `logs/static_checks.txt` |
| 5 | README gives reproducible setup instructions | §8 lists exact commands, tested in a clean virtual environment, with the tool versions used. | §8 |

**Task coverage:** Task A — package layout in §3; Task B — `errors.py`, `logging_config.py` and the loader, parser and pipeline; Task C — `tests/` (fixtures in `conftest.py`, parametrised edge cases, mocks only at external boundaries); Task D — full suite, ruff and mypy run, dead code removed, this README.

---

## 3. Package Structure

```
Day3/
├── pyproject.toml                  Package metadata, dependencies, pytest/mypy/ruff settings
├── data/tickets.csv                Sample file: 12 rows, 6 intentionally invalid
├── src/ticket_pipeline/
│   ├── __main__.py                 Enables `python -m ticket_pipeline`
│   ├── cli.py                      Arguments, output streams, exit codes
│   ├── config.py                   PipelineConfig: settings from CLI > environment > defaults
│   ├── errors.py                   Exception hierarchy (§5)
│   ├── logging_config.py           configure_logging() and the @log_duration decorator
│   ├── pipeline.py                 Orchestration: load → parse → de-duplicate → summarise
│   ├── models/ticket.py            Ticket, Priority, Status, InvalidTicketField
│   ├── processing/loader.py        CSVLoader: lazy reading and file-level checks
│   ├── processing/parser.py        parse_row(): raw strings → validated Ticket
│   └── analytics/summary.py        summarise() and format_summary(): pure functions
├── tests/
│   ├── conftest.py                 Shared fixtures and per-test isolation
│   ├── sample_data.py              CSV constants used by the tests
│   ├── unit/                       One component at a time (78 tests)
│   └── integration/                Real files through loader → parser → pipeline → CLI (16 tests)
└── logs/                           Saved evidence (§14)
```

**Dependency direction:** `models` imports nothing from the package. `processing` imports `models` and `errors`. `analytics` imports `models`. `pipeline` composes `processing` and `analytics`. Only `cli` configures logging or reads arguments. Only `config` reads environment variables.

The `src/` layout means the tests run against the package as installed, not against loose files in the working directory.

---

## 4. Component Specifications

| Module | Responsibility | Raises |
|---|---|---|
| `config.PipelineConfig` | Frozen settings object (`input_path`, `log_level`, `strict`). `from_sources()` applies the precedence CLI argument > environment variable > default. The environment is injectable for tests. | `ConfigurationError` |
| `processing.loader.CSVLoader` | Checks the path, then yields `RawRow(line, values)` lazily. The file is opened in a `with` block, so it is closed on success, on error, or when iteration stops early. Removes an Excel BOM; normalises header names; pads short rows. | `InputPathError`, `MalformedFileError`, `SchemaMismatchError` |
| `processing.parser.parse_row` | Converts one row to a `Ticket`, normalising case. The first problem in a row is reported. | `InvalidRowError` (chained to the original `ValueError`) |
| `models.ticket.Ticket` | Frozen dataclass, validated in `__post_init__`. `ClassVar` patterns for ticket ID and e-mail. `resolution_hours` must be finite, ≥ 0, and set only on resolved or closed tickets. | `InvalidTicketField` (a `ValueError`) |
| `pipeline.run_pipeline` | Runs the stages, catches `InvalidRowError` per row, rejects duplicate IDs, logs each stage, returns a frozen `PipelineResult`. | File-level errors propagate; `RejectedRowsError` in strict mode |
| `analytics.summary` | `summarise()` returns counts, open high/urgent ticket IDs and mean resolution time. No I/O and no logging. | — |
| `logging_config` | `configure_logging()` (stderr handler, idempotent). `@log_duration(stage)` logs outcome and duration at DEBUG and re-raises any exception unchanged. | — |
| `cli.main` | Parses arguments, prints the report to stdout, maps each `TicketPipelineError` to its exit code. Any other exception propagates with its traceback. | — |

---

## 5. Error Reference

| Exception | Exit code | Raised when | Example message |
|---|---|---|---|
| `ConfigurationError` | 2 | `TICKET_PIPELINE_LOG_LEVEL` holds an unknown level | `Unknown log level 'LOUD'. Use one of: DEBUG, INFO, WARNING, ERROR.` |
| *(argparse usage error)* | 2 | Unknown option or invalid `--log-level` | `argument --log-level: invalid choice: 'LOUD'` |
| `InputPathError` | 3 | Path missing, a directory, not `.csv`, or permission denied | `Input file not found: 'missing.csv'. Check the path, or pass --input with the correct location.` |
| `MalformedFileError` | 4 | Empty file, not UTF-8, blank or duplicate header, row with surplus fields, unparsable CSV | `Row has 8 fields but the header defines 7 (surplus.csv, line 2). Remove the extra field(s) or quote values that contain commas.` |
| `SchemaMismatchError` | 5 | Required columns absent from the header | `old_format.csv is missing required column(s): category, created_at, customer_email, status. Found columns: ticket_id, priority. Add the missing column(s) to the header row.` |
| `RejectedRowsError` | 6 | `--strict` is set and at least one row was rejected; the message lists every rejected row | `6 of 12 row(s) were rejected and strict mode is on: …` |
| `InvalidRowError` | — | One row breaks a rule. Recoverable: caught per row and reported, never fatal on its own | `line 7, column 'priority': 'critical' is not one of: low, medium, high, urgent` |

All classes derive from `TicketPipelineError`, so a caller can handle every expected failure with one `except` clause. The CLI deliberately does **not** catch `Exception`: an unexpected error is a bug, and hiding it behind an exit code would remove the traceback needed to fix it (verified by `test_unexpected_bug_is_not_hidden`).

---

## 6. Logging Policy

| Logged | Not logged |
|---|---|
| Stage and status (`stage=parse status=rejected`) | Customer e-mail addresses |
| File **name** (`file=tickets.csv`) | Full file-system paths (they can contain user names) |
| Line number and column of a rejected row | Raw row values |
| Counts (`rows=12 valid=6 rejected=6`) | Exception tracebacks for expected, handled errors |
| Error class and exit code on failure | |
| Stage duration (DEBUG) | |

| Level | Used for |
|---|---|
| `DEBUG` | Column count of the header; duration of each stage |
| `INFO` | Start and completion of a stage, with counts |
| `WARNING` | A rejected row; a header-only file |
| `ERROR` | The run failed (error class and exit code) |

Logs go to **stderr** and the report goes to **stdout**, so `python -m ticket_pipeline > report.txt` saves a clean report. Library modules only create loggers (`logging.getLogger(__name__)`); only the CLI attaches a handler.

---

## 7. Data Contract

| Column | Required | Rule |
|---|---|---|
| `ticket_id` | Yes | `TKT-` followed by four digits (case-insensitive on input); unique within the file |
| `customer_email` | Yes | A valid e-mail address; treated as personal data |
| `priority` | Yes | `low`, `medium`, `high`, `urgent` (any case) |
| `status` | Yes | `open`, `in_progress`, `resolved`, `closed` (any case; `In Progress` and `in-progress` are accepted) |
| `category` | Yes | Any non-empty text; stored in lower case |
| `created_at` | Yes | ISO 8601 date or date-time, e.g. `2026-10-01` |
| `resolution_hours` | No | Empty, or a finite number ≥ 0; allowed only when status is `resolved` or `closed` |

Header names are matched after trimming spaces and lower-casing. Extra columns are allowed and ignored.

`data/tickets.csv` contains six valid rows and six rows that are invalid on purpose: a bad e-mail, an unknown priority, hours on an open ticket, a duplicate ID, an impossible date, and an infinite duration.

---

## 8. Setup

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

`-e ".[dev]"` installs the package in editable mode with the development tools: pytest 9.2.0, mypy 2.4.1 and ruff 0.17.3 were the versions used.

**Verify the setup:**

```bash
python -m pytest            # expected: 94 passed
python -m ruff check .      # expected: All checks passed!
python -m mypy src tests    # expected: Success: no issues found
```

---

## 9. Usage

```bash
python -m ticket_pipeline                              # process data/tickets.csv
python -m ticket_pipeline --input path/to/file.csv    # process another file
python -m ticket_pipeline --log-level DEBUG           # include stage durations
python -m ticket_pipeline --strict                    # exit 6 if any row is rejected
ticket-pipeline --input path/to/file.csv              # console script, same options
```

| Setting | CLI option | Environment variable | Default |
|---|---|---|---|
| Input file | `--input` | `TICKET_PIPELINE_INPUT` | `data/tickets.csv` |
| Log level | `--log-level` | `TICKET_PIPELINE_LOG_LEVEL` | `INFO` |
| Strict mode | `--strict` | — | off |

Excerpt of actual output on the sample file (full output in `logs/pipeline_output.txt`):

```
INFO    ticket_pipeline.pipeline | stage=load status=started file=tickets.csv
WARNING ticket_pipeline.pipeline | stage=parse status=rejected line=6 column=customer_email
WARNING ticket_pipeline.pipeline | stage=parse status=rejected line=7 column=priority
...
INFO    ticket_pipeline.pipeline | stage=parse status=completed file=tickets.csv rows=12 valid=6 rejected=6
Source: tickets.csv
Rows read: 12 | valid: 6 | rejected: 6
Rejected rows:
  - line 6, column 'customer_email': is not a valid e-mail address
  - line 7, column 'priority': 'critical' is not one of: low, medium, high, urgent
...
TICKET SUMMARY
  Valid tickets          : 6
  Mean resolution time   : 6.25 h
  Open high/urgent       : TKT-0001, TKT-0003, TKT-0011
```

---

## 10. Testing

```bash
python -m pytest                    # all tests
python -m pytest tests/unit         # unit tests only
python -m pytest -m integration     # integration tests only
python -m pytest "tests/unit/test_parser.py::test_invalid_values_report_column_and_reason[hours-inf]"
```

| File | Type | Tests | What is covered |
|---|---|---|---|
| `unit/test_ticket.py` | Unit | 23 | Every field rule; `inf`/`-inf`/`nan`/negative/bool hours; hours on unfinished tickets; immutability; e-mail kept out of `repr`, `str` and error messages |
| `unit/test_parser.py` | Unit | 24 | Normalisation; every empty required column; 12 named invalid-value cases; exception chaining; no e-mail in messages |
| `unit/test_loader.py` | Unit | 18 | Physical line numbers (blank lines, multi-line quoted fields); lazy reading; BOM and header normalisation; three bad-path cases; five malformed-file cases; schema mismatch; permission denied |
| `unit/test_config_and_logging.py` | Unit | 10 | Configuration precedence; invalid log level; `@log_duration` success and failure; idempotent logging setup |
| `unit/test_summary.py` | Unit | 3 | Counts and mean; empty input; generator input |
| `integration/test_pipeline_and_cli.py` | Integration | 16 | Valid and mixed files end to end; strict mode; log content without personal data; stdout/stderr separation; one exit code per failure type; unexpected bugs not hidden |
| **Total** | | **94** | **94 passed, 0 failed** |

### 10.1 Test design rules

| Rule | How it is applied |
|---|---|
| Assert behaviour, not implementation | Tests check returned values, raised exception types and attributes, messages, exit codes and log text, not private methods or internal call order. |
| Fixtures for sample data | `write_csv` (factory that writes a CSV into `tmp_path`) and `sample_csv` (three valid rows), in `conftest.py`. |
| Parametrise edge cases | Invalid values, bad paths, malformed files and exit codes are parametrised, each with a readable ID such as `[hours-nan]`. |
| Mock only external boundaries | Mocked: the clock (`time.perf_counter`), the operating system (`Path.open` raising `PermissionError`) and the environment (injected mapping or `monkeypatch`). The file system is **not** mocked; tests use real temporary files. Internal components are never mocked, except one test that simulates a bug to prove it is not hidden. |
| Determinism and independence | An autouse fixture clears `TICKET_PIPELINE_*` variables and restores logger state after every test. No test depends on another test, the current directory, the real clock or the network. |

### 10.2 Verifying that the tests detect defects

Three defects were introduced on purpose and the suite was run each time. Every change was detected; the code was then restored.

| Deliberate defect | Result |
|---|---|
| Remove the `math.isfinite` check from `Ticket` | 5 tests failed |
| Drop rejected rows silently instead of recording them | 7 tests failed |
| Add raw row values to the rejection log line (personal-data leak) | 2 tests failed |

---

## 11. Design Rationale

### 11.1 Recoverable vs fatal errors

A bad **row** is expected in real data, so it is raised as `InvalidRowError`, caught for that row only, reported, and processing continues. A bad **file** (missing, unreadable, wrong schema) means no useful result is possible, so the error propagates to the CLI, which prints the message and exits with that error's code. `--strict` lets a caller such as a scheduled job treat any bad row as fatal.

### 11.2 Catch narrowly, chain always

Every `except` clause names a specific exception (`UnicodeDecodeError`, `PermissionError`, `csv.Error`, `ValueError`, `InvalidTicketField`, `InvalidRowError`, `TicketPipelineError`). No code catches `Exception`. When a low-level error is translated, `raise … from exc` keeps the original as `__cause__`, so the root cause stays available in a debugger or traceback.

### 11.3 Exit codes belong to the exception

Each exception class declares `exit_code`. The CLI uses one `except TicketPipelineError as exc: return exc.exit_code` instead of an `if/elif` chain, so adding a new error type does not require changing the CLI.

### 11.4 Configuration in one place

Only `config.py` reads environment variables. Other modules receive a `PipelineConfig`, so they can be tested without touching the real environment.

### 11.5 Lazy reading

`CSVLoader.iter_rows()` is a generator: the pipeline holds one row at a time, and the file closes automatically through the `with` block.

---

## 12. Assumptions

| # | Assumption |
|---|---|
| 1 | Input files are UTF-8, with or without a byte-order mark. |
| 2 | The first line of the file is the header row. |
| 3 | Dates are ISO 8601. Day-first formats such as `01/10/2026` are rejected rather than guessed. |
| 4 | The first occurrence of a duplicated ticket ID is the valid one. |
| 5 | An empty `resolution_hours` cell means the ticket has not been resolved. |
| 6 | The person running the CLI may see the path they supplied in error messages; logs contain only the file name. |

---

## 13. Limitations

| # | Limitation | Impact |
|---|---|---|
| 1 | Only the first problem in a row is reported | A row with several problems needs more than one fix-and-rerun cycle |
| 2 | Logs are plain `key=value` text, not JSON | Easy to read and grep; a log platform would need a parser or a JSON formatter |
| 3 | Duplicate detection is within one file | Duplicates across separate runs are not detected |
| 4 | E-mail validation is a pattern check | It does not prove an address exists |
| 5 | Only CSV input is supported | Other formats need a new loader |
| 6 | The default input path is relative to the source tree | When installed without `-e`, pass `--input` or set `TICKET_PIPELINE_INPUT` |

---

## 14. Execution Evidence

| File | Content | Command |
|---|---|---|
| [`logs/test_results.txt`](logs/test_results.txt) | Full verbose test output — 94 passed | `python -m pytest -v -p no:cacheprovider` |
| [`logs/test_isolation.txt`](logs/test_isolation.txt) | Three repeated runs, reverse-order run, and every test run alone — all pass | Determinism check |
| [`logs/static_checks.txt`](logs/static_checks.txt) | `ruff check .` and `mypy src tests` (strict) — both clean | |
| [`logs/pipeline_output.txt`](logs/pipeline_output.txt) | Full run on `data/tickets.csv`, logs and report | `python -m ticket_pipeline` |
| [`logs/error_scenarios.txt`](logs/error_scenarios.txt) | Each failure type with its message and exit code | Seven prepared bad inputs |

Environment: Windows 11, Python 3.12.10, pytest 9.2.0, mypy 2.4.1, ruff 0.17.3.
