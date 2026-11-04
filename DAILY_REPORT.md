# Daily Report — Day 03

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 03 — Python Engineering Practices, Exceptions & Testing |
| **Developer** | Lakshit (HALCER) |
| **Date** | 04 November 2026 |
| **Duration** | 8 hours — 4 hours study + 4 hours implementation |
| **Status** | Implementation complete; ready for code review |
| **Test result** | 94 passed, 0 failed; every test also passes alone (`logs/test_isolation.txt`) |
| **Static checks** | `ruff` clean; `mypy --strict` clean (`logs/static_checks.txt`) |

---

## 1. Topics Learned

| Study block | Topics | Required output — how it was produced |
|---|---|---|
| Type hints and structure (60 min) | Function annotations, optional values (`X \| None`), collection types, `src/` package layout, modules | Every public function and dataclass is annotated; `mypy --strict` passes on source and tests. Package split into `models`, `processing`, `analytics` and `config`. |
| Exceptions and context managers (60 min) | Raise vs catch, custom exception hierarchies, chaining with `from`, cleanup, `with` for files | Seven exception classes in `errors.py`. Low-level errors are translated with `raise … from exc`, so the root cause is kept. The file is opened in a `with` block inside a generator. |
| Decorators, generators and logging (60 min) | Decorators with arguments, `functools.wraps`, `ParamSpec`; lazy iteration; logger hierarchy, handlers, log levels | `@log_duration(stage)` decorator; `CSVLoader.iter_rows()` generator; `key=value` logs at stage boundaries, with a written policy on what must never be logged. |
| Testing fundamentals (60 min) | Unit vs integration tests, fixtures, parametrisation, mocking boundaries, test naming | 78 unit and 16 integration tests; `write_csv` and `sample_csv` fixtures; parametrised edge cases with readable IDs; mocks only for the clock, the OS and the environment. |

### 1.1 Key learnings

- **Raise vs catch.** Raise where the problem is detected; catch only where something useful can be done with it. The parser *raises* `InvalidRowError`, the pipeline *catches* it for that row, and the CLI *catches* only `TicketPipelineError` to choose an exit code.
- **Exception chaining.** `raise NewError(...) from exc` stores the original exception as `__cause__`. Without it the traceback would show only the new error and the real root cause would be lost.
- **Generators and `with`.** A `with` block inside a generator closes the file when the generator finishes, when an exception passes through it, or when the caller stops iterating early and the generator is closed.
- **Decorators.** `functools.wraps` keeps the wrapped function's name and docstring. `ParamSpec` lets mypy check the wrapped function's arguments. A `try/finally` lets the decorator log even when the function fails, without swallowing the exception.
- **Logging.** Libraries should only create loggers (`getLogger(__name__)`); the application decides where logs go. Sending logs to stderr keeps the report on stdout clean.
- **Personal data hides in defaults.** A dataclass's automatic `__repr__` prints every field, including e-mail addresses. `field(repr=False)` is needed for anything sensitive.
- **Testing.** A unit test checks one component alone; an integration test checks several together through real files. Mock only what is slow, non-deterministic or outside my control (clock, OS, network). Mocking my own code makes tests pass even when the real components no longer fit together.

---

## 2. What I Can Explain Without Notes

- Why each fatal error type has its own class and exit code, and why `InvalidRowError` is recoverable while `SchemaMismatchError` is not.
- How `raise … from exc` preserves the root cause, and where the code uses it.
- Why the CLI does not catch `Exception`, and what would be lost if it did.
- What the logs contain and what they must never contain, and how the tests prove that.
- How the loader's generator and `with` block guarantee that the file is closed.
- Why `reader.line_num` is used instead of counting rows with `enumerate()`.
- The difference between the unit and integration tests in this project, and why only the clock, the OS and the environment are mocked.
- How the autouse fixture keeps tests independent, and how this was verified.

---

## 3. Implementation Completed

| Task | Deliverable | Status |
|---|---|---|
| **A — Package structure** | `src/ticket_pipeline/` with `models`, `processing`, `analytics`, `config.py`, `errors.py`, `logging_config.py`, `pipeline.py`, `cli.py`; installable through `pyproject.toml`; runnable as `python -m ticket_pipeline` | Complete |
| **B — Error handling and logs** | Specific errors for invalid paths (`InputPathError`), malformed files (`MalformedFileError`) and schema mismatches (`SchemaMismatchError`), plus configuration, row-level and strict-mode errors; exit codes 2–6; stage-boundary logging without personal data | Complete |
| **C — Test suite** | 94 tests; fixtures for sample CSV data; parametrised edge cases; mocks only at external boundaries | Complete |
| **D — Quality pass** | Full suite, `ruff` and `mypy --strict` clean; unused code removed (`OPTIONAL_COLUMNS` constant and a duplicate `__version__`); README with reproducible setup; work committed to Git | Complete |

---

## 4. Tests / Experiment Results

```
$ python -m pytest
94 passed in 0.14s

$ python -m ruff check .
All checks passed!

$ python -m mypy src tests
Success: no issues found in 22 source files
```

| Experiment | Result | Evidence |
|---|---|---|
| Full suite run three times in a row | 94 passed each time | `logs/test_isolation.txt` |
| Full suite in reverse order | 94 passed | `logs/test_isolation.txt` |
| Each of the 94 tests run alone in a fresh process | 94 passed, 0 failed | `logs/test_isolation.txt` |
| Sample file run | 12 rows read, 6 valid, 6 rejected with line and column | `logs/pipeline_output.txt` |
| One run per failure type | Exit codes 3, 3, 4, 4, 5, 2, 6 with actionable messages | `logs/error_scenarios.txt` |
| Deliberate defects introduced into the code | All three detected (5, 7 and 2 failing tests) | README §10.2 |

---

## 5. Bug or Challenge and Its Root Cause

### 5.1 Main bug — the strict-mode error was not actionable

**Symptom:** while recording `logs/error_scenarios.txt`, I ran `--strict --log-level ERROR` on the sample file. The message said *"Fix the rows listed above"*, but no rows were listed above it.

**Root cause:** the rejected rows were reported only as WARNING log records. The error message assumed those records would be visible, so the error was actionable only at the default log level. Raising the level to ERROR hid exactly the information needed to fix the file.

**Fix:** `RejectedRowsError` now carries the rejected `InvalidRowError` objects and lists them in its own message. The information no longer depends on the logging configuration.

**Verification:** added the regression test `test_strict_mode_error_lists_rows_even_with_logging_off`, reran the relevant tests and then the full suite (94 passed), and regenerated `logs/error_scenarios.txt`.

### 5.2 Other problems found and fixed during the day

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | A logged or printed `Ticket` would reveal the customer's e-mail | The dataclass-generated `__repr__` includes every field | `customer_email` declared with `field(repr=False)`; test `test_repr_and_str_do_not_expose_email` |
| 2 | Many parametrised tests could not be run on their own from the shell | Test IDs were generated from strings containing spaces (`[missing-3-Input file not found]`), so the shell split each ID | Explicit `ids=` or `pytest.param(..., id=...)`, e.g. `[hours-nan]`; isolation check reran clean |
| 3 | Test modules failed to import shared constants (`ModuleNotFoundError: conftest`) | `conftest.py` is loaded by pytest as a plugin, not as an importable module | Constants moved to `tests/sample_data.py`; `tests` added to `pythonpath` |
| 4 | `mypy` error: `Iterator[RawRow]` has no attribute `close` | The loader returns a generator but was annotated as a plain iterator | Return type changed to `Generator[RawRow, None, None]` |
| 5 | `1_5` hours would be read as 15 | Python's `float()` accepts underscores as digit separators | Values containing `_` are rejected |

---

## 6. Design Decision and Why

**Decision:** separate *recoverable* row errors from *fatal* file errors, and let every exception class carry its own exit code.

- `InvalidRowError` is caught one row at a time, so one bad row never stops a file of valid tickets from being processed.
- File-level errors propagate to the CLI, because no meaningful result can be produced from a missing or wrongly structured file.
- The CLI has a single handler: `except TicketPipelineError as exc: return exc.exit_code`. Adding a new error type therefore needs no change to the CLI.
- No code catches `Exception`. An unexpected exception is a bug, and keeping its traceback is more useful than converting it into an exit code. `test_unexpected_bug_is_not_hidden` enforces this.

**Alternative considered:** returning error codes or `None` from functions instead of raising. Rejected, because every caller would have to remember to check the result, and an unchecked failure would continue silently.

---

## 7. Blocker and What I Tried

**No open blocker.**

The closest to a blocker was proving that the tests are independently runnable, rather than only stating it. A single full-suite run cannot show this, because a test that silently depends on another test's leftover state still passes. I therefore:

1. ran the suite three times in a row;
2. reversed the collection order with a small local pytest plugin;
3. ran each test alone in a new process.

The first attempt at step 3 reported 68 false failures. The cause was the space-separated test IDs described in Section 5.2, item 2, not the tests themselves. After renaming the IDs, all 94 tests passed alone.

---

## 8. Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
|---|---|---|
| Errors are specific and actionable | Met | README §5; `logs/error_scenarios.txt` |
| Logs help diagnose failures without exposing sensitive data | Met | README §6; `test_logs_describe_stages_without_personal_data` |
| Tests are deterministic and independently runnable | Met | `logs/test_isolation.txt` |
| Type hints improve clarity without becoming noise | Met | `logs/static_checks.txt` |
| README gives reproducible setup instructions | Met | README §8, tested in a clean virtual environment |

**Submission checklist:**
- Source code committed to Git with a meaningful commit message ✔
- Actual test and pipeline output saved in `logs/` ✔
- README with setup, assumptions and limitations ✔
- Logs and results included ✔
- Implementation explainable without reading code line by line — to be demonstrated in the viva

---

## 9. Tomorrow's Plan

- Push the Day 03 repository and confirm the code-review result.
- Prepare for the Day 03 technical viva by explaining the error hierarchy, logging policy and test design without notes.
- Begin Day 04 when released.
