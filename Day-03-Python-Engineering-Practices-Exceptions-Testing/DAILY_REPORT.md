# Daily Report — Day 03

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 03 — Python Engineering Practices, Exceptions & Testing |
| **Developer** | Lakshit (HALCER) |
| **Date** | 04 November 2026 |
| **Duration** | 8 hours — 4 hours study + 4 hours implementation |
| **Status** | Implementation complete; ready for code review |
| **Test result** | 127 passed, 0 failed; every test also passes alone (`logs/test_isolation.txt`) |
| **Coverage** | 100 % statements and branches (`logs/coverage.txt`) |
| **Static checks** | `ruff` clean; `mypy --strict` clean (`logs/static_checks.txt`) |

---

## 1. Topics Learned

| Study block | Topics | Required output — how it was produced |
|---|---|---|
| Type hints and structure (60 min) | Function annotations, optional values (`X \| None`), collection types, `src/` package layout, modules | Every public function and dataclass is annotated; `mypy --strict` passes on source and tests. Package split into `models`, `processing`, `analytics` and `config`. |
| Exceptions and context managers (60 min) | Raise vs catch, custom exception hierarchies, chaining with `from`, cleanup, `with` for files | Seven exception classes in `errors.py`. Low-level errors are translated with `raise … from exc` so the root cause is kept. The file is opened in a `with` block inside a generator. |
| Decorators, generators and logging (60 min) | Decorators with arguments, `functools.wraps`, `ParamSpec`; lazy iteration; logger hierarchy, handlers, levels | `@log_duration(stage)` decorator; `CSVLoader.iter_rows()` generator; `key=value` logs at stage boundaries, with a written policy on what must never be logged. |
| Testing fundamentals (60 min) | Unit vs integration tests, fixtures, parametrisation, mocking boundaries, test naming | 106 unit and 21 integration tests; `write_csv` and `sample_csv` fixtures; parametrised edge cases with readable IDs; mocks only for the clock, the OS and the environment. |

### 1.1 Key learnings

- **Raise vs catch.** Raise where a problem is detected; catch only where something useful can be done. The parser *raises* `InvalidRowError`, the pipeline *catches* it for that row, and the CLI *catches* only `TicketPipelineError` to choose an exit code.
- **Exception chaining.** `raise NewError(...) from exc` stores the original exception as `__cause__`; without it, the real root cause disappears from the traceback.
- **Generators and `with`.** A `with` block inside a generator closes the file when the generator finishes, when an exception passes through it, or when the caller stops early and the generator is closed.
- **Decorators.** `functools.wraps` keeps the wrapped function's name and docstring. `ParamSpec` lets mypy check the wrapped function's arguments. `try/finally` lets the decorator log a failure without swallowing it.
- **Logging.** A library creates loggers but never configures them; the application decides where logs go. Logs to stderr and the report to stdout keep the two separate.
- **Personal data hides in defaults.** A dataclass's automatic `__repr__` prints every field, including customer names. `field(repr=False)` keeps them out.
- **Testing.** A unit test checks one component alone; an integration test checks several together through real files. Mock only what is slow, non-deterministic or outside my control. A passing suite is not proof that tests are strong: deliberately breaking the code showed one assertion was too weak (Section 5.2, item 7).

---

## 2. What I Can Explain Without Notes

- Why each fatal error type has its own class and exit code, and why `InvalidRowError` is recoverable while `SchemaMismatchError` is not.
- How `raise … from exc` preserves the root cause, and where the code uses it.
- Why the CLI does not catch `Exception`, and what would be lost if it did.
- What the logs contain, what they must never contain, and how the tests prove it.
- How the loader's generator and `with` block guarantee that the file is closed.
- Why header names are normalised once and duplicates rejected, and why strict CSV mode is used.
- The difference between the unit and integration tests here, and why only the clock, the OS and the environment are mocked.
- How test independence and test strength were verified (isolation runs and deliberate defects).

---

## 3. Implementation Completed

| Task | Deliverable | Status |
|---|---|---|
| **A — Package structure** | `src/ticket_pipeline/` with `models`, `processing`, `analytics`, `config.py`, `errors.py`, `logging_config.py`, `pipeline.py`, `cli.py`; installable via `pyproject.toml`; runnable as `python -m ticket_pipeline` | Complete |
| **B — Error handling and logs** | Specific errors for invalid paths (`InputPathError`), malformed files (`MalformedFileError`) and schema mismatches (`SchemaMismatchError`), plus configuration, row-level and strict-mode errors; exit codes 2–6; stage-boundary logging without personal data | Complete |
| **C — Test suite** | 127 tests; fixtures for sample ticket CSV data; parametrised edge cases; mocks only at external boundaries; 100 % branch coverage | Complete |
| **D — Quality pass** | Full suite, coverage, `ruff` and `mypy --strict` clean; unused code removed (an unused `OPTIONAL_COLUMNS` constant and a duplicated `__version__`); README with verified setup; committed to Git | Complete |

### 3.1 Project context and peer-review check

The project context is *"Make the ticket pipeline testable and diagnosable."* A peer's Day 03 submission failed review for two blocking reasons:

1. it did not work on the existing ticket pipeline;
2. header names that became identical after trimming and lower-casing silently overwrote each other.

I checked my project against both points.

| Peer finding | Status in this project | Action |
|---|---|---|
| Must apply Day 03 practices to the **existing ticket pipeline** | My first version used a different ticket schema (no customer name, description or rating) and did not keep the established analytics | Switched to the existing ticket data contract and analytics contract. Added a regression test proving the sample dataset still gives the established results (README §8, §11.2) |
| Duplicate normalised headers must be rejected | Already rejected, but covered by only one test | Added a parametrised regression test (exact, case, whitespace, case + whitespace). The error message now shows the original spellings |

---

## 4. Tests / Experiment Results

```
$ python -m pytest
127 passed in 0.27s

$ python -m pytest --cov
TOTAL    498 statements    0 missed    98 branches    0 partial    100%

$ python -m ruff check .
All checks passed!

$ python -m mypy src tests
Success: no issues found in 22 source files
```

| Experiment | Result | Evidence |
|---|---|---|
| Full suite run three times in a row | 127 passed each time | `logs/test_isolation.txt` |
| Full suite in reverse order | 127 passed | `logs/test_isolation.txt` |
| Each of the 127 tests run alone in a fresh process | 127 passed, 0 failed | `logs/test_isolation.txt` |
| Ten deliberate defects introduced into the code | All ten detected | `logs/defect_detection.txt` |
| Sample ticket dataset | 10 rows, 7 valid, 3 rejected; established analytics unchanged | `logs/pipeline_output.txt` |
| One run per failure type | Exit codes 2–6 with actionable messages | `logs/error_scenarios.txt` |
| Fresh clone, new virtual environment, README setup steps | All checks pass | README §9 |

---

## 5. Bug or Challenge and Its Root Cause

### 5.1 Main bug — a duplicate of a rejected row was accepted

**Symptom:** while recording `logs/error_scenarios.txt`, line 2 (`T001`) was rejected for an infinite resolution time, and line 4 (`t001`) was then **accepted**. Once line 2 was fixed, the file would hold two copies of the same ticket.

**Root cause:** the pipeline recorded a ticket ID only *after* the row was parsed successfully. A rejected row never entered the duplicate register, so a later row with the same ID looked unique.

**Fix:** every row's ID is recorded before parsing, whether or not the row is valid. IDs are compared after trimming and case-folding, so `T001` and ` t001 ` match. If a duplicate row also has other problems, all issues are reported together and the original cause is kept.

**Verification:** added `test_duplicate_of_a_rejected_row_is_still_reported`, `test_duplicate_row_with_other_problems_reports_everything` and `test_rows_with_empty_ids_are_not_treated_as_duplicates`. Reran them, then the full suite (127 passed), then regenerated the evidence logs.

### 5.2 Other problems found and fixed during the day

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | An unbalanced quote swallowed the rest of the file and produced a misleading "field is empty" message | Python's CSV reader is lenient by default and treats everything after an open quote as one value | `csv.reader(..., strict=True)`; the error now names the quote and the line where the row starts |
| 2 | Rows with a multi-line quoted value were reported one line too late | `reader.line_num` is the line where a row *ends*. My first test asserted the wrong value, so it passed | Track the start line explicitly; test corrected to expect the start line |
| 3 | A NUL byte (binary content) was accepted as data | Python's CSV reader no longer rejects NUL bytes | Rows containing NUL are rejected as `MalformedFileError` |
| 4 | Whitespace-only lines were reported as tickets with seven empty fields | Only completely empty lines were treated as blank | Lines whose cells are all blank are skipped and logged at DEBUG |
| 5 | The strict-mode error said "fix the rows listed above" but listed nothing when logging was set to ERROR | The rows were reported only through WARNING logs | `RejectedRowsError` carries the rows and lists them in its own message |
| 6 | Three CLI tests failed: the empty, duplicate-header and schema cases all saw the wrong file | The test built every case's file eagerly in a dictionary; all wrote `tickets.csv`, so the last one won | Build only the selected case, using functions |
| 7 | Removing the parser's `isfinite` check did not fail any test | The model rejected the value anyway, and the test only checked for the word "finite" | Tests now require the message to quote the bad value (`value 'inf' must be finite`) |
| 8 | A logged or printed `Ticket` would reveal the customer and description | The dataclass-generated `__repr__` includes every field | `field(repr=False)` on both; tested |

---

## 6. Design Decision and Why

**Decision:** separate *recoverable* row errors from *fatal* file errors, and reject ambiguous input instead of guessing.

- `InvalidRowError` is caught one row at a time, so one bad row never blocks a file of valid tickets. All problems in the row are reported together, so it can be fixed in one pass.
- File-level errors (missing file, encoding, duplicate normalised headers, missing columns, unbalanced quotes) propagate to the CLI, because no trustworthy result can be produced.
- Each exception class carries its own `exit_code`, so the CLI needs one handler and no `if/elif` chain.
- No code catches `Exception`. An unexpected error is a bug, and keeping its traceback is more useful than converting it into an exit code.

**Alternative considered:** returning `None` or error codes instead of raising. Rejected, because every caller would have to remember to check, and a missed check would let bad data continue silently.

---

## 7. Blocker and What I Tried

**No open blocker.**

The main open question was **scope**: whether Day 03 should reuse the earlier ticket pipeline's contract. The assessment's project context and the peer review both pointed to the existing ticket pipeline. I kept this repository's code independent, adopted the established ticket data and analytics contracts, and proved the behaviour is unchanged with a regression test on the same sample dataset.

The technical challenge was **proving** that tests are independent and strong, not just green:

1. I ran the suite three times in a row, in reverse order, and ran each test alone in a fresh process. The first attempt reported false failures because some test IDs contained spaces; explicit IDs fixed this.
2. I introduced ten defects on purpose. The one that survived revealed a weak assertion (Section 5.2, item 7), which I then strengthened.

---

## 8. Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
|---|---|---|
| Errors are specific and actionable | Met | README §5; `logs/error_scenarios.txt` |
| Logs help diagnose failures without exposing sensitive data | Met | README §6; `test_logs_describe_stages_without_personal_data` |
| Tests are deterministic and independently runnable | Met | `logs/test_isolation.txt` |
| Type hints improve clarity without becoming noise | Met | `logs/static_checks.txt` |
| README gives reproducible setup instructions | Met | README §9, verified in a fresh clone |

**Submission checklist:**
- Source code committed to Git with a meaningful commit message ✔
- Actual test, coverage and pipeline output saved in `logs/` ✔
- README with setup, assumptions and limitations ✔
- Logs and results included ✔
- Implementation explainable without reading code line by line — to be demonstrated in the viva

---

## 9. Tomorrow's Plan

- Push the Day 03 repository and confirm the code-review result.
- Prepare for the Day 03 technical viva by explaining the error hierarchy, logging policy and test design without notes.
- Begin Day 04 only when it is released.
