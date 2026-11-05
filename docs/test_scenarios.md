# Test scenarios

This document is a test plan, not a claim that every row below has been run. Automated coverage and the exact command output for a run should be reported separately.

## Normal workflow

| Scenario | Input/action | Expected behavior |
|---|---|---|
| Upload supplied demo data | Upload `data/demo_quality_sample.csv`. | `201`; metadata has the file's detected columns and row count; no server path is exposed. |
| Paginated preview | Request preview with `limit=2`, then a later `offset`. | String-valued rows match source values, with empty cells represented as empty strings; columns stay consistent. |
| Analyze | Analyze the sample dataset. | Report includes per-column missing counts, duplicate count, inferred types, issues/actions, score components, and applicable numerical summaries. Original file bytes remain unchanged. |
| Clean duplicates and missing rows | Set `remove_duplicate_rows=true`, `missing_values.action=drop_rows`, and `trim_whitespace=true`. | A separate run is stored; before/after row counts and missing/duplicate metrics differ as expected; original is unchanged. |
| Fill missing values | Use `missing_values.action=fill` and `value` or per-column `values`. | Missing cells are filled only in the output; run parameters and counts are returned. |
| Statistical imputation | Use a selected numeric column with mean/median or a categorical column with mode. | Correct statistic/mode is applied; invalid mixed numeric data is rejected for mean/median. |
| Visualize cleaned data | Open Insights after a cleaning run. | Charts and numerical metrics come from `quality_after_report`, not the original report. |
| Restore a run | Reload/reopen a dataset after cleaning. | Latest-run endpoint restores cleaning metrics and cleaned-output insights. |
| Download | Download after cleaning. | Attachment is a CSV from the latest successful run; formula-leading values are escaped; original remains intact. |

## Edge cases and invalid input

| Scenario | Input/action | Expected behavior |
|---|---|---|
| Empty file | Zero-byte CSV. | Rejected with a structured 422 error; no dataset or artifact is persisted. |
| Header-only file | Header but no data rows. | Rejected with a structured invalid-CSV error. |
| Missing/blank header | Blank header field. | Rejected; no dataset is persisted. |
| Duplicate headers | Repeated header name, including whitespace-normalized duplicates. | Rejected rather than silently renaming columns. |
| Ragged row | A row has fewer or more cells than the header. | Rejected with an invalid-CSV error. |
| Malformed quoting | Unterminated quote or invalid quoting. | Rejected with a structured invalid-CSV error. |
| Invalid encoding | Non-UTF-8 input. | Rejected with an unsupported-encoding error. |
| Wrong extension | Non-`.csv` filename. | Rejected with an unsupported-media-type error. |
| Oversize upload | Bytes exceed `MAX_UPLOAD_SIZE_BYTES`. | Rejected with 413; no dataset is persisted. |
| Row/column caps | Exceed `MAX_CSV_ROWS` or `MAX_CSV_COLUMNS`. | Rejected with a limit-specific validation code. |
| Large cell | One field is larger than 128 KiB but below the file cap. | Accepted if otherwise valid; preview, analysis, clean, and download remain usable. |
| Very small input | One header and one data row. | Upload, analysis, and no-op cleaning work; summary standard deviation may be null for a single value. |
| Whitespace-only missing cell | Empty or space-only data. | Counts as missing and can be dropped/filled. |
| Literal null token | `NA`, `null`, or `N/A`. | Remains literal text; not treated as missing automatically. |
| Inconsistent numeric value | Numbers mixed with text. | Analyzer reports detectable inconsistency; numeric conversion/statistical mean or median rejects if it cannot safely process the values. |
| Unexpected dates | ISO, slash-separated, month-name, invalid, or ambiguous date values. | Analyzer uses date heuristics; selected date conversion rejects values it cannot parse. Ambiguous dates require human review. |
| Locale-formatted number | `1,234.50` or `8,25` without a locale rule. | Standardization rejects rather than guesses. |
| Invalid cleaning request | Unknown column, extra option, missing fill values, or wrong type. | 422 response; no successful run/download is created. |
| Unknown dataset | Use an unknown ID in any dataset route. | Stable not-found envelope; no filesystem paths are revealed. |
| Download before cleaning | Download a dataset with no run. | 404 response with a cleaned-run-not-found code. |

## Changed-input / schema-agnostic scenarios

Use distinct synthetic files rather than relying only on the supplied demo:

1. **Two columns, all strings:** arbitrary names such as `glyph_code,zone_9`; upload, preview, and analysis should not depend on known names.
2. **Six columns with changing order:** reorder columns and add an unfamiliar column; report and chart data should follow the new schema, not a fixed mapping.
3. **Mixed numeric column:** values such as `3.5`, empty, `unknown`, `12`; inspect mixed/inconsistent counts, then verify numeric standardization fails without saving a partial run.
4. **Different date convention:** use `Jan 3 2024`, `2024/01/04`, and an invalid date. Verify generic profiling and explicitly check the date conversion result before export.
5. **Small dataset:** one row, one numeric column, and no duplicates. Check denominator-zero/single-value behavior and download output.
6. **Changed missing-value rules:** repeat a run with fill, then drop rows; both runs must start from the original rather than from each other.
7. **Large but in-limit file:** generate valid rows close to `MAX_UPLOAD_SIZE_BYTES`; confirm upload, bounded preview, and configured row/column limits. Do not assume a large-file upload is a load/performance certification.

## Current automated coverage

The repository includes backend tests under `backend/tests` for health/database setup, upload validation, quality reports, cleaning strategies/validation, and full API workflows. Frontend tests under `frontend/tests` currently cover file-size formatting and selection of cleaned-output insights. The frontend build runs TypeScript checking plus Vite bundling. Use the actual test commands and results in the [README](../README.md#test-and-build) when presenting verification.
