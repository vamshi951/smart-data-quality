import { useState } from "react";
import type { ColumnFormat, CleaningRequest, CleaningRun, Dataset, MissingAction, QualityReport, StatisticalStrategy } from "../../lib/types";
import { Alert, PageHeading } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { api, ApiClientError } from "../../lib/api";

const formatOptions: { value: ColumnFormat; label: string }[] = [
  { value: "trim", label: "Trim whitespace" },
  { value: "lowercase", label: "Lowercase" },
  { value: "uppercase", label: "Uppercase" },
  { value: "number", label: "Number" },
  { value: "integer", label: "Integer" },
  { value: "date_iso", label: "ISO date" },
];

export function CleaningPage({
  dataset,
  report,
  run,
  onRun,
  onAnalyze,
}: {
  dataset: Dataset;
  report?: QualityReport;
  run?: CleaningRun;
  onRun: (run: CleaningRun) => void;
  onAnalyze: (report: QualityReport) => void;
}) {
  const [removeDuplicates, setRemoveDuplicates] = useState(true);
  const [trimWhitespace, setTrimWhitespace] = useState(false);
  const [missingAction, setMissingAction] = useState<MissingAction>("keep");
  const [fillValue, setFillValue] = useState("Unknown");
  const [strategy, setStrategy] = useState<StatisticalStrategy>("median");
  const [statColumns, setStatColumns] = useState<string[] | null>(null);
  const [standardize, setStandardize] = useState<Record<string, ColumnFormat>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const missingColumns = report?.columns.filter((column) => column.missing_count > 0) ?? [];
  const canRun = removeDuplicates || trimWhitespace || missingAction !== "keep" || Object.keys(standardize).length > 0;

  const analyze = async () => {
    setBusy(true);
    setError(null);
    try {
      onAnalyze(await api.analyzeDataset(dataset.dataset_id));
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "Could not analyze the dataset.");
    } finally {
      setBusy(false);
    }
  };

  const runCleaning = async () => {
    if (!canRun || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    const request: CleaningRequest = {
      remove_duplicate_rows: removeDuplicates,
      trim_whitespace: trimWhitespace,
      missing_values: { action: missingAction },
      standardize_columns: standardize,
    };
    if (missingAction === "fill") request.missing_values.value = fillValue;
    if (missingAction === "statistical") {
      request.missing_values.strategy = strategy;
      request.missing_values.columns = statColumns ?? missingColumns.map((column) => column.name);
    }
    try {
      const completedRun = await api.cleanDataset(dataset.dataset_id, request);
      onRun(completedRun);
      setNotice("Cleaning complete. The original dataset is unchanged; your cleaned version is saved separately.");
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "The cleaning operation could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="TRANSFORM WITH CONFIDENCE"
        title="Clean your data."
        description={`Choose clear, reversible rules for ${dataset.filename}. Every run starts from your untouched original.`}
      />
      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="cleaning-layout">
        <div className="cleaning-options-column">
          {!report && (
            <div className="panel analyze-callout">
              <span className="callout-icon"><Icon name="sparkles" size={18} /></span>
              <div><strong>Analyze first for smarter choices</strong><p>A quality report helps you choose columns and strategies based on detected missing values.</p></div>
              <button className="button button-secondary button-small" onClick={analyze} disabled={busy}>{busy ? "Analyzing…" : "Analyze"}</button>
            </div>
          )}

          <section className="panel cleaning-card">
            <div className="section-title-row"><span className="step-number">01</span><div><h2>Remove duplicates</h2><p>Keep the first occurrence of identical rows.</p></div></div>
            <label className="toggle-row">
              <span><strong>Remove exact duplicate rows</strong><small>Rows are duplicates only when every column matches.</small></span>
              <input type="checkbox" checked={removeDuplicates} onChange={(event) => setRemoveDuplicates(event.target.checked)} />
            </label>
          </section>

          <section className="panel cleaning-card">
            <div className="section-title-row"><span className="step-number">02</span><div><h2>Handle missing values</h2><p>Select what to do with empty and whitespace-only cells.</p></div></div>
            <label className="field-label" htmlFor="missing-action">Missing value action</label>
            <select id="missing-action" className="form-select" value={missingAction} onChange={(event) => setMissingAction(event.target.value as MissingAction)}>
              <option value="keep">Keep as-is</option>
              <option value="drop_rows">Drop rows with any missing cell</option>
              <option value="fill">Fill with a value</option>
              <option value="statistical">Statistical fill</option>
            </select>
            {missingAction === "fill" && (
              <div className="field-block">
                <label className="field-label" htmlFor="fill-value">Value to use for all missing cells</label>
                <input id="fill-value" className="form-input" value={fillValue} onChange={(event) => setFillValue(event.target.value)} />
                <p className="field-help">The value is kept as text, even in a numeric-looking column.</p>
              </div>
            )}
            {missingAction === "statistical" && (
              <div className="field-block">
                <label className="field-label" htmlFor="stat-strategy">Statistical strategy</label>
                <select id="stat-strategy" className="form-select" value={strategy} onChange={(event) => setStrategy(event.target.value as StatisticalStrategy)}>
                  <option value="mean">Mean — numeric columns</option>
                  <option value="median">Median — numeric columns</option>
                  <option value="mode">Mode — most frequent value</option>
                </select>
                {report ? (
                  <div className="selected-columns"><span className="field-label">Columns with detected missing values</span>
                    {missingColumns.length ? missingColumns.map((column) => {
                      const selected = statColumns ?? missingColumns.map((item) => item.name);
                      return <label key={column.name} className="selected-column"><input
                        type="checkbox"
                        checked={selected.includes(column.name)}
                        disabled={selected.length === 1 && selected.includes(column.name)}
                        onChange={(event) => setStatColumns((current) => {
                          const currentSelection = current ?? missingColumns.map((item) => item.name);
                          return event.target.checked
                            ? [...currentSelection, column.name]
                            : currentSelection.filter((name) => name !== column.name);
                        })}
                      /><span>{column.name}</span><small>{column.missing_count} empty</small></label>;
                    }) : <p className="field-help">The report found no missing values. Statistical fill will not change this dataset.</p>}
                  </div>
                ) : <p className="field-help">All columns containing missing values will be selected. Analyze for a preview of affected columns.</p>}
              </div>
            )}
            {missingAction === "drop_rows" && <div className="inline-explanation"><Icon name="alert" size={16} /><span>A row will be removed if one or more cells are empty. Review before running.</span></div>}
          </section>

          <section className="panel cleaning-card">
            <div className="section-title-row"><span className="step-number">03</span><div><h2>Standardize columns</h2><p>Apply a consistent format to selected columns.</p></div></div>
            <label className="toggle-row standardize-all">
              <span><strong>Trim whitespace in all columns</strong><small>Remove leading and trailing spaces.</small></span>
              <input type="checkbox" checked={trimWhitespace} onChange={(event) => setTrimWhitespace(event.target.checked)} />
            </label>
            <div className="format-list">
              {dataset.columns.map((column) => (
                <label key={column} className="format-row">
                  <span><Icon name="columns" size={15} /><strong>{column}</strong></span>
                  <select className="form-select form-select-compact" aria-label={`Format for ${column}`} value={standardize[column] ?? ""} onChange={(event) => setStandardize((previous) => {
                    const next = { ...previous };
                    if (event.target.value) next[column] = event.target.value as ColumnFormat;
                    else delete next[column];
                    return next;
                  })}>
                    <option value="">No change</option>
                    {formatOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                  </select>
                </label>
              ))}
            </div>
            <div className="inline-explanation"><Icon name="shield" size={16} /><span>If values cannot be converted without loss, the operation is rejected and no run is saved.</span></div>
          </section>

          <div className="clean-run-actions">
            <button className="button button-primary" onClick={runCleaning} disabled={!canRun || busy}>
              {busy ? <><span className="button-spinner" /> Applying rules…</> : <><Icon name="sparkles" size={17} /> Run cleaning</>}
            </button>
            <span>Creates a separate result. Original stays untouched.</span>
          </div>
        </div>

        <aside className="cleaning-side-column">
          <section className="panel operation-summary">
            <div className="panel-heading"><div><h2>Operation summary</h2><p>Rules selected for this run.</p></div></div>
            <ul className="rule-summary">
              <li><span className={removeDuplicates ? "rule-check active" : "rule-check"}>{removeDuplicates && <Icon name="check" size={13} />}</span><span>Remove exact duplicates</span></li>
              <li><span className={trimWhitespace ? "rule-check active" : "rule-check"}>{trimWhitespace && <Icon name="check" size={13} />}</span><span>Trim whitespace</span></li>
              <li><span className={missingAction !== "keep" ? "rule-check active" : "rule-check"}>{missingAction !== "keep" && <Icon name="check" size={13} />}</span><span>{missingAction === "keep" ? "Keep missing values" : `Missing values: ${missingAction.replace("_", " ")}`}</span></li>
              <li><span className={Object.keys(standardize).length ? "rule-check active" : "rule-check"}>{Object.keys(standardize).length > 0 && <Icon name="check" size={13} />}</span><span>Standardize {Object.keys(standardize).length} selected columns</span></li>
            </ul>
            <div className="summary-callout"><Icon name="shield" size={17} /><span>No changes are applied to the uploaded original.</span></div>
          </section>

          {run ? (
            <section className="panel comparison-panel">
              <div className="panel-heading"><div><h2>Before & after</h2><p>Latest cleaning run comparison.</p></div><span className="comparison-badge"><Icon name="check" size={13} /> Complete</span></div>
              <div className="comparison-columns">
                <div><span className="comparison-label">BEFORE</span><strong>{run.quality_before.row_count.toLocaleString()}</strong><small>rows</small><span className="comparison-sub">{run.quality_before.missing_cell_count} missing · {run.quality_before.duplicate_row_count} duplicates</span></div>
                <div className="comparison-arrow"><Icon name="arrow" size={17} /></div>
                <div className="comparison-after"><span className="comparison-label">AFTER</span><strong>{run.quality_after.row_count.toLocaleString()}</strong><small>rows</small><span className="comparison-sub">{run.quality_after.missing_cell_count} missing · {run.quality_after.duplicate_row_count} duplicates</span></div>
              </div>
              <div className="change-counts">
                <span>Rows dropped <b>{(run.dropped_missing_rows + run.dropped_duplicate_rows).toLocaleString()}</b></span>
                <span>Cells filled <b>{run.filled_missing_cells.toLocaleString()}</b></span>
                <span>Cells standardized <b>{run.standardized_cells.toLocaleString()}</b></span>
                <span>Export-safe escapes <b>{run.escaped_formula_cells.toLocaleString()}</b></span>
              </div>
            </section>
          ) : (
            <section className="panel comparison-placeholder">
              <span className="compare-illustration"><Icon name="rows" size={25} /></span>
              <h3>Your comparison will appear here</h3>
              <p>Run a cleaning operation to compare row, missing value, and duplicate counts before and after.</p>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
