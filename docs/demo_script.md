# Three-minute demo walkthrough

## Before the demo

1. Follow the [README setup](../README.md#clean-setup) and start the backend and frontend in separate terminals.
2. Confirm `GET http://127.0.0.1:8000/health` returns `{"status":"ok"}` and the frontend header says the API is connected.
3. Keep [demo_quality_sample.csv](../data/demo_quality_sample.csv) ready for upload.
4. Start from the dashboard. If a previous demo dataset is present, either open it or use a clean local database/storage directory so the upload story starts empty. Do not delete user data to reset a demo.

## Walkthrough (about 3 minutes)

### 0:00-0:25 — Set the context

**Say:** "Teams receive CSVs with different schemas and inconsistent values. This MVP lets an analyst inspect a source, see explainable quality signals, apply explicit cleaning rules, and export a separate result without overwriting the original."

Point out the dashboard and the API connection status.

### 0:25-0:55 — Upload and inspect

Upload `data/demo_quality_sample.csv`. On Dataset Details, point out that the application discovers its unfamiliar column names rather than expecting a fixed customer schema. Show the paginated preview and schema panel.

**Say:** "The uploaded source is preserved. Empty cells appear as empty, and preview does not coerce values into guessed types."

### 0:55-1:35 — Analyze and explain

Click **Analyze quality**. Point to the missing-cell and duplicate counts, the mixed/inconsistent values, and the numerical summary. Open the score explanation.

**Say:** "The score is an explicitly weighted heuristic, not a guarantee of domain correctness. The report shows its penalty components so a judge can audit how it was calculated."

### 1:35-2:15 — Clean and compare

Click **Clean dataset**. Keep duplicate removal enabled, choose **Drop rows with any missing cell**, and enable **Trim whitespace in all columns**. Run cleaning. Show the before/after row, missing-cell, and duplicate counts, as well as export-safe escapes if any appear.

**Say:** "Each run starts from the immutable original. This result is separate, and the comparison shows what these exact rules changed."

Avoid applying numeric or date standardization to a column containing an invalid value; the API rejects conversions it cannot safely complete.

### 2:15-2:40 — Visualize the cleaned output

Open **Insights**. Show that its description says the metrics come from the latest cleaned output. Point to the missing-values chart, type mix, and numeric summaries.

**Say:** "These charts and summaries are generated from the cleaned result after cleaning, not from hard-coded demo values. Without a cleaning run, Insights uses analysis of the original."

### 2:40-3:00 — Export and close

Open **Export**, click **Download cleaned CSV**, and mention that the original remains unchanged and that formula-leading output cells are escaped.

**Say:** "The download is the latest successful run. This demo is local-first and intentionally small; it is not claiming authentication, multi-user isolation, or production-scale ingestion."

## If something goes wrong

- If the UI says the API is offline, check the backend terminal and `GET /health`.
- If the browser already has demo data, select the correct dataset by filename; do not delete stored records during a live demo.
- If upload fails, verify the sample file is UTF-8 CSV, the backend is running, and the configured upload limits have not been lowered.
- If the cleaned metrics do not appear in Insights after a refresh, verify `GET /api/datasets/{dataset_id}/cleaning-runs/latest` returns a run. Show the API result rather than claiming persistence if that endpoint fails.
- Do not use any real or sensitive data in a public demo.
