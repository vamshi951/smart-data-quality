# API design

## Conventions

- Base path for dataset APIs: `/api`.
- JSON uses `snake_case`; dataset/run identifiers are UUID strings.
- Timestamps are ISO 8601 UTC strings.
- Upload uses `multipart/form-data`; downloads return `text/csv` with `Content-Disposition: attachment`.
- Preview is paginated and capped by the server (initial maximum 100 rows per page).
- All input validation is server-side. Do not return local paths, stack traces, or uploaded cell contents in error messages.

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| `GET` | `/health` | Liveness check; no dataset details | `200` |
| `POST` | `/api/datasets` | Validate and persist one CSV | `201` |
| `GET` | `/api/datasets` | List uploaded datasets | `200` |
| `GET` | `/api/datasets/{dataset_id}` | Retrieve dataset metadata | `200` |
| `GET` | `/api/datasets/{dataset_id}/preview` | Page through original rows | `200` |
| `POST` | `/api/datasets/{dataset_id}/analyze` | Analyze original and return a quality report | `200` |
| `POST` | `/api/datasets/{dataset_id}/clean` | Create a run from the immutable original | `201` |
| `GET` | `/api/datasets/{dataset_id}/cleaning-runs/latest` | Retrieve the latest run and its cleaned-output report | `200` |
| `GET` | `/api/datasets/{dataset_id}/download` | Download the latest cleaned CSV | `200` |

Preview query parameters: `limit` (default 50, range 1–100) and `offset` (default 0, non-negative). Invalid values return `422`.

## Representative requests and responses

### Upload

`POST /api/datasets` with multipart field `file`.

```json
{
  "dataset_id": "c1b15d3d-53bc-4ac4-a311-91e3cc6df674",
  "filename": "customers.csv",
  "status": "ready",
  "byte_size": 48320,
  "row_count": 1200,
  "column_count": 5,
  "columns": ["name", "city", "age", "email", "joined_at"],
  "created_at": "2026-11-05T14:59:00+00:00",
  "updated_at": "2026-11-05T14:59:00+00:00"
}
```

Upload returns dataset metadata only; quality analysis is an explicit separate request. Upload responses do not include file rows.

### Preview

`GET /api/datasets/{dataset_id}/preview?limit=50&offset=0`

```json
{
  "dataset_id": "c1b15d3d-53bc-4ac4-a311-91e3cc6df674",
  "columns": ["name", "city", "age", "email", "joined_at"],
  "rows": [{"name": "A. User", "city": "Austin", "age": "34", "email": "", "joined_at": "2024-01-03"}],
  "total_rows": 1200,
  "limit": 50,
  "offset": 0
}
```

Rows are represented as string-valued cells; a missing cell is represented as an empty string in the preview.

### Analyze quality

`POST /api/datasets/{dataset_id}/analyze` re-reads the immutable original and stores the resulting report snapshot in metadata. It does not change the original CSV.

The response contains one column entry per uploaded column with inferred type (`integer`, `number`, `boolean`, `datetime`, `string`, `mixed`, or `unknown`), missing/inconsistent counts, and numerical summary where values are numeric. Issues contain counts, affected column names, and suggested actions.

```json
{
  "dataset_id": "c1b15d3d-53bc-4ac4-a311-91e3cc6df674",
  "analyzed_at": "2026-11-05T15:05:00+00:00",
  "row_count": 1200,
  "column_count": 5,
  "quality_score": 99.85,
  "issue_counts": {
    "missing_cells": 9,
    "duplicate_rows": 3,
    "inconsistent_values": 1
  },
  "columns": [
    {
      "name": "age",
      "inferred_type": "integer",
      "non_missing_count": 1198,
      "missing_count": 2,
      "inconsistent_value_count": 1,
      "numerical_summary": {
        "count": 1197,
        "minimum": 18,
        "maximum": 92,
        "mean": 43.2,
        "median": 41,
        "standard_deviation": 12.1
      }
    }
  ],
  "issues": [
    {
      "code": "missing_values",
      "count": 9,
      "affected_columns": ["age"],
      "suggested_action": "Review affected columns; fill values explicitly or drop rows only when appropriate for the analysis."
    },
    {
      "code": "duplicate_rows",
      "count": 3,
      "affected_columns": ["name", "city", "age", "email", "joined_at"],
      "suggested_action": "Review exact duplicate rows and remove them only if repeated records are not meaningful."
    },
    {
      "code": "inconsistent_values",
      "count": 1,
      "affected_columns": ["age"],
      "suggested_action": "Inspect values that differ from the predominant detectable type; correct them only after checking the source semantics."
    }
  ],
  "score_breakdown": [
    {
      "issue": "missing_values",
      "affected_rate": 0.0015,
      "maximum_penalty": 40,
      "penalty": 0.06,
      "rule": "Deduct 40 × affected rate (9/6000)."
    },
    {
      "issue": "duplicate_rows",
      "affected_rate": 0.0025,
      "maximum_penalty": 30,
      "penalty": 0.08,
      "rule": "Deduct 30 × affected rate (3/1200)."
    },
    {
      "issue": "inconsistent_values",
      "affected_rate": 0.000167,
      "maximum_penalty": 30,
      "penalty": 0.01,
      "rule": "Deduct 30 × affected rate (1/6000)."
    }
  ]
}
```

The explainable score starts at 100. Deduct up to 40 points proportional to missing cells / all cells, up to 30 proportional to exact duplicate rows / all rows, and up to 30 proportional to inconsistent values / all cells. Each deduction is rounded half-up to two decimals; clamp the final score at zero. Empty and whitespace-only cells count as missing; `NA`, `null`, and `N/A` remain literal values. Type inference is schema-agnostic: numeric, boolean, and recognizable date values are classified; when one detectable type is at least 60% of non-missing values, other values are counted as inconsistent; otherwise a column with multiple detected types is reported as `mixed`. These heuristics cannot decide domain-specific validity.

### Create a cleaning run

`POST /api/datasets/{dataset_id}/clean`

```json
{
  "remove_duplicate_rows": true,
  "trim_whitespace": true,
  "missing_values": {"action": "fill", "values": {"city": "Unknown", "email": "Not provided"}},
  "standardize_columns": {"age": "integer", "joined_at": "date_iso"}
}
```

`missing_values.action` is `keep` (default), `drop_rows`, `fill`, or `statistical`. Fill accepts either a shared `value` or per-column `values`; all columns with missing cells must be covered by per-column values. Statistical filling supports `mean`, `median`, or `mode`; mean/median require numeric values and mode chooses the first sorted mode in a tie. Options are rejected if they reference unknown columns or cannot be applied without loss. `standardize_columns` supports `trim`, `lowercase`, `uppercase`, `number`, `integer`, and `date_iso`; unsupported conversions return a validation error rather than silently corrupting values. `trim_whitespace` applies trimming to every column. Duplicate removal keeps the first row.

```json
{
  "run_id": "24dbec54-11c1-4fe8-97cb-970d2818cb5c",
  "dataset_id": "c1b15d3d-53bc-4ac4-a311-91e3cc6df674",
  "rules": {},
  "row_count_before": 1200,
  "row_count_after": 1186,
  "dropped_duplicate_rows": 3,
  "dropped_missing_rows": 0,
  "filled_missing_cells": 11,
  "standardized_cells": 17,
  "escaped_formula_cells": 0,
  "quality_before": {
    "row_count": 1200,
    "missing_cell_count": 9,
    "duplicate_row_count": 3
  },
  "quality_after": {
    "row_count": 1186,
    "missing_cell_count": 0,
    "duplicate_row_count": 0
  },
  "created_at": "2026-11-05T15:00:00+00:00"
}
```

`GET /api/datasets/{dataset_id}/download` downloads the most recently created successful cleaned run for that dataset as a formula-safe CSV attachment. It returns `404` until at least one cleaning run has completed. Each clean operation uses the original upload, and the original file is never overwritten.

The cleaning response includes `quality_after_report`, a full quality report calculated from the formula-safe cleaned output. Insights should use this report after a cleaning run so charts and numerical summaries reflect the downloadable data; before a run, they use analysis of the original upload.

`GET /api/datasets/{dataset_id}/cleaning-runs/latest` returns the same cleaning-run response shape. It enables the frontend to restore the latest cleaning metrics and cleaned-output report after a page reload. It returns `404 cleaning_run_not_found` when no successful run exists.

Quality report objects include total rows/columns, total missing cells, exact duplicate-row count, and per-column missing count, inferred display type, and applicable numeric/category summary. Chart series should be derived from these bounded summaries, not from shipping an entire dataset to the browser.

### Error envelope

```json
{
  "error": {
    "code": "invalid_csv",
    "message": "The uploaded file could not be parsed as a supported CSV.",
    "details": []
  }
}
```

`details` is optional and contains safe field-level validation information. Common codes include `file_too_large`, `row_limit_exceeded`, `column_limit_exceeded`, `unsupported_encoding`, `unsupported_media_type`, `invalid_csv`, `invalid_headers`, `invalid_cleaning_rules`, `validation_error`, `dataset_not_found`, `cleaning_run_not_found`, `cleaned_dataset_not_found`, and `storage_error`.

## Status codes

- `200` successful read/health; `201` dataset or cleaning run created.
- `404` dataset or cleaning run not found; `413` configured upload limit exceeded; `415` unsupported file type/encoding; `422` parse or field validation failure.
- `500` unexpected processing/storage failure. Return a generic message and request correlation ID; log diagnostic details server-side without logging CSV cell contents.

## API behavior notes

- Upload is synchronous in the MVP and returns only after validation, row counting, and durable persistence succeed. Quality profiling is performed by the separate analyze endpoint.
- Cleaning always starts from the original upload. A retry creates a distinct run; clients should not assume an idempotency key.
- Run comparison uses before/after metrics captured for that run and the dataset's immutable original.
- Dataset deletion and retention controls are not implemented in this MVP.
- The health endpoint reports service liveness only; it must not expose local configuration or storage paths.
