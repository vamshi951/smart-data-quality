# Product requirements

## Product goal

Give a user a simple, trustworthy way to upload one CSV, understand its data-quality problems, apply explicit cleaning rules, compare the result with the original, and download the cleaned CSV.

## Users

- **Primary — analyst or operations user:** receives CSV exports and needs to assess and prepare them without writing code.
- **Secondary — data steward or team lead:** needs to explain what changed and assess whether a dataset is fit for downstream analysis.
- **Administrator / developer (initial deployment):** runs a self-hosted instance and manages its local database and stored files. The MVP has no account or role-management UI.

## User journeys

1. **Inspect a file:** open the application, select a CSV, receive a clear validation error or see a bounded preview and initial quality report.
2. **Understand quality:** review missing and duplicate counts, per-column summaries, and simple charts; inspect enough sample rows to decide what action is appropriate.
3. **Clean deliberately:** select supported rules, review the proposed output and change counts, then create a cleaning run. The original remains available and unchanged.
4. **Compare and export:** compare before/after quality metrics for a run, preview the cleaned data, and download that run's CSV.
5. **Remove data:** delete a dataset and its associated cleaning runs/files when it is no longer needed.

## Functional requirements

### MVP

- **FR-01 Upload:** accept one `.csv` file per request; validate the file by content as well as extension, enforce the configured size/row limits, and return a dataset ID.
- **FR-02 Validate and parse:** report actionable errors for empty, malformed, unsupported-encoding, or invalid-header files. Support UTF-8 and UTF-8 with BOM; do not silently guess a different encoding.
- **FR-03 Preview:** show a bounded page of original or cleaned rows, column names, row count, and pagination information. Never require the browser to load the whole dataset.
- **FR-04 Detect quality:** report total rows/columns, missing cells per column, exact duplicate rows, schema-agnostic inferred display type, detectable inconsistent values, and basic numerical summaries. Include affected columns and suggested actions.
- **FR-04a Explain score:** calculate a 0–100 score from missing-cell, duplicate-row, and inconsistent-value rates. The score is a transparent heuristic, not a statistical guarantee or a substitute for domain rules.
- **FR-05 Clean explicitly:** support trimming leading/trailing whitespace, dropping exact duplicate rows, missing-value handling by keeping, dropping affected rows, filling with explicit values, or using mean/median/mode, and selected-column standardization for string case, numeric/integer, and ISO datetime formats. Validate the complete rule set before applying it.
- **FR-06 Preserve provenance:** leave the uploaded source unchanged; create an identifiable cleaning run with its selected rules and before/after quality reports.
- **FR-07 Compare:** show comparable row, missing-cell, and duplicate-row metrics before and after a selected cleaning run.
- **FR-08 Visualize:** display a small set of useful Recharts views, such as missing values by column and a numeric/categorical summary. Charts must have a textual equivalent.
- **FR-09 Download:** download the cleaned CSV belonging to the selected run, with a meaningful filename and safe spreadsheet-export handling.
- **FR-10 Delete:** allow deletion of a dataset and all its associated runs and stored artifacts.
- **FR-11 API errors:** return stable, documented error codes and a useful message for expected validation, missing-resource, and server errors.

### Optional / post-MVP

- XLSX and database connectors; multiple-file ingestion and scheduled imports.
- User accounts, authorization, team sharing, audit log, and managed/cloud deployment.
- Configurable quality rules, reusable cleaning recipes, column mapping, custom type/date parsing, and advanced anomaly detection.
- More advanced visualizations, profiling distributions, correlation analysis, and report export.
- Background processing, job status/progress, cancellation, and large-file streaming.
- Dataset version history beyond retaining the original and individual cleaning runs.

## Non-functional requirements

- **Privacy:** keep uploaded data within the configured application storage; do not send row contents to external services. Make retention/deletion behavior visible.
- **Integrity:** never overwrite the source file; a run's output and metrics must refer to the same applied rules and data.
- **Usability:** provide understandable names, units, empty states, accessible keyboard/focus behavior, and tabular alternatives to charts.
- **Performance:** bound upload size and preview rows; target a responsive interaction for a 25 MiB / 100,000-row CSV on a typical development machine. Treat this as an initial test target, not a measured guarantee.
- **Reliability:** validate before persistence; use transactions for metadata changes; enable SQLite foreign keys; surface storage and parse errors instead of showing success-shaped fallbacks.
- **Security:** validate uploads server-side, generate storage names rather than trusting filenames, prevent path traversal, enforce limits, avoid exposing internal paths/stack traces, and neutralize spreadsheet formula injection on downloaded exports.
- **Maintainability:** keep parsing, profiling, cleaning, persistence, and API presentation in separate modules; test deterministic transformation rules.
- **Compatibility:** current evergreen desktop browsers; UTF-8 CSV output; responsive layout for narrower screens.

## Assumptions and data-handling rules

1. The MVP is a single-user, self-hosted application. Authentication and multi-tenant isolation are out of scope.
2. CSV is the only supported source. The initial configurable limits are 25 MiB and 100,000 data rows; implementation may tune them after measuring.
3. A CSV is parsed with comma delimiter and standard CSV quoting. UTF-8 and UTF-8 BOM are supported. Other encodings, delimiter detection, and malformed-row repair are not automatic.
4. Treat imported cell values as text for cleaning and export. Type inference is for reporting only; do not silently coerce date, numeric, or identifier values.
5. Empty and whitespace-only cells count as missing. Strings such as `NA`, `null`, and `N/A` remain literal values unless a future explicit null-token setting is introduced.
6. Exact duplicate means identical values in every data column; the header is not a data row. When duplicates are removed, keep the first occurrence and preserve source row order for the remaining rows.
7. Cleaning order is trim surrounding whitespace, apply the selected missing-value action, then remove exact duplicate rows. Missing-value fill values are explicit per-column literals; no implicit mean, median, or mode imputation.
8. The original upload is immutable. Cleaned files are separate artifacts linked to a cleaning run. Dataset deletion removes the original, all run artifacts, and metadata.
9. Keep data files on local application storage and metadata/reports in SQLite. Retention is until user deletion or operator cleanup; no automatic expiry in MVP.
10. Downloads must prevent formula execution in spreadsheet software. Escape formula-leading text values in the export and report the behavior; never alter the retained original.
11. SQLite is intended for a single application instance and modest local workloads. Multi-instance deployment and concurrent large jobs need a different persistence/job design.
12. Generic type-inconsistency detection is heuristic: it reports minority values that do not match a predominant detectable type, but cannot determine domain validity without a user-provided schema.

## Edge cases and expected behavior

| Case | Expected behavior |
|---|---|
| Zero-byte file, header-only file, or no usable columns | Reject with a specific validation error; do not create a ready dataset. |
| Extension says `.csv` but content is not parseable CSV | Reject after content/parser validation; do not trust MIME type or filename alone. |
| UTF-8 BOM | Parse and remove BOM from the first header without changing other header text. |
| Unsupported encoding or malformed quoting/rows | Return a clear validation error; do not silently replace characters or skip bad lines. |
| Duplicate, blank, or whitespace-only column names | Reject ambiguous headers and ask the user to correct the source. |
| Columns with identical names after BOM/whitespace normalization | Reject rather than silently rename or merge them. |
| Very wide or oversized/over-row-limit input | Reject with the applicable configured limit and no partial dataset. |
| Values containing commas, quotes, or newlines | Parse and export with CSV quoting; preview as cell values. |
| All cells missing, all rows duplicates, or cleaning removes every row | Show an explicit empty-result state; allow a zero-row cleaned file only if the resulting CSV still has its valid header. |
| Unknown column in a fill rule or missing fill value | Reject the cleaning request with field-level validation details; do not create a run. |
| Repeated cleaning request | Create a distinct run from the immutable original using the submitted rules; do not clean a previous output implicitly. |
| Dataset or run does not exist | Return 404 without leaking filesystem paths. |
| Storage failure or interrupted write | Return an explicit server error and clean up partial artifacts where possible; never mark an incomplete run successful. |
| Formula-like or control-character-leading text | Escape on download, preserve the original, and include export-safety counts/notes. |
