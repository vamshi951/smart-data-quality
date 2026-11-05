# Likely judge questions

## What problem does the application solve?

It gives an analyst one local workflow to upload a CSV, inspect rows and columns, identify a few generic quality signals, select explicit cleaning rules, compare counts, visualize a report, and download a separate cleaned CSV.

## How is it built?

The browser UI is React and TypeScript with Tailwind CSS and Recharts. It calls a FastAPI API. The backend uses Pandas for CSV parsing, profiling, and transformation; Pydantic for request/response validation; SQLAlchemy and SQLite for dataset/run metadata; and a local filesystem directory for original and cleaned CSV artifacts. See the [architecture diagram](../README.md#architecture) and [architecture document](./architecture.md).

## How do you handle unfamiliar schemas?

No business column names are required. The analyzer loops over the uploaded columns and classifies values generically as detectable numeric, boolean, date, string, mixed, or unknown. The UI builds charts and summaries from returned column reports. This does not infer a business meaning such as "age" or "account balance," and it does not validate organization-specific rules.

## How is the quality score computed?

It begins at 100. It subtracts up to 40 points proportional to missing cells divided by all cells, up to 30 proportional to exact duplicate rows divided by all rows, and up to 30 proportional to inconsistent values divided by all cells. Each penalty is rounded half-up to two decimals and the final score is clamped at zero. The API returns the components and formulas. It is a transparent heuristic, not a statistical confidence measure or a data-quality standard.

## What counts as missing or duplicate?

Empty and whitespace-only cells are missing; literal strings such as `NA`, `null`, and `N/A` are retained as literal data. Duplicate count is exact whole-row equality, not a key-based or fuzzy match. Duplicate removal keeps the first matching row.

## Does analysis alter data?

No. Analysis reads the original and saves a report snapshot. Cleaning also starts from the original every time and writes a separate artifact and run record. The original upload is not overwritten.

## How is cleaning made auditable?

The API persists the rule parameters, counts, before/after metrics, output file reference, timestamp, and cleaned-output quality report for each run. The latest-run endpoint can restore the frontend's cleaned insights after a reload.

## What happens when conversion is uncertain?

For selected number/date/integer standardization, conversion errors or non-integral values are rejected with a validation response; the application does not silently replace unparseable values. Statistical mean/median also require numeric values. Locale-specific numeric conventions are not inferred. Users should inspect the source and choose a safe rule.

## How are errors handled?

The API validates file extension, UTF-8 encoding, headers, row widths, configured file/row/column limits, and cleaning rules. API errors use a consistent JSON envelope with a code/message and request ID header. Unexpected failures are logged server-side and return a generic response; local filesystem paths are not returned as dataset metadata.

## Is the data sent to a third party?

The implemented application has no external data-processing integration. The browser sends the file to the configured FastAPI server; that host stores the original, cleaned artifacts, and SQLite metadata locally. Do not interpret that as a security certification: the MVP has no authentication, authorization, encryption-at-rest setup, or tenant isolation.

## Can it process Excel or databases?

Not currently. Uploads are CSV-only and UTF-8-only. XLSX and database connectors would be future work.

## Is it ready for production?

No production-readiness claim is made. It is a hackathon MVP with automated tests for implemented API paths, a frontend build, and frontend helper tests. It has not been certified by load, deployment, penetration, privacy, backup/restore, or operational resilience testing. SQLite and local files are for a single-host demo, not shared multi-host use.

## What would you build next?

Add authentication and dataset ownership, explicit privacy/retention controls, user-defined schema constraints, more robust locale-aware parsing with explicit locale selection, background processing for larger inputs, richer column previews, and deployment/load/security/backup testing.

## What evidence supports the demo claims?

Run the backend pytest suite and frontend tests/build using the commands in the [README](../README.md#test-and-build). For a specific live dataset, the API endpoints under `/api/datasets/{dataset_id}` expose preview, analysis, cleaning comparisons, latest cleaned-output report, and download behavior. State the actual output of the commands run for the current build; do not quote example numbers from design documents as test results.
