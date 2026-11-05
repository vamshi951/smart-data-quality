import { useEffect, useState } from "react";
import { Alert, EmptyState, LoadingState, PageHeading, QualityScore } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { api, ApiClientError } from "../../lib/api";
import { formatBytes } from "../../lib/format";
import type { Dataset, DatasetPreview, QualityReport } from "../../lib/types";

function issueLabel(code: string) {
  return code.replaceAll("_", " ");
}

export function DatasetDetailsPage({
  dataset,
  report,
  onReport,
  onClean,
}: {
  dataset: Dataset;
  report?: QualityReport;
  onReport: (report: QualityReport) => void;
  onClean: () => void;
}) {
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [offset, setOffset] = useState(0);
  const [loadingPreview, setLoadingPreview] = useState(true);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [showScoreInfo, setShowScoreInfo] = useState(false);

  useEffect(() => {
    let active = true;
    setLoadingPreview(true);
    setPreviewError(null);
    api.getPreview(dataset.dataset_id, 10, offset)
      .then((result) => { if (active) setPreview(result); })
      .catch((error: unknown) => {
        if (active) setPreviewError(error instanceof ApiClientError ? error.message : "Could not load preview.");
      })
      .finally(() => { if (active) setLoadingPreview(false); });
    return () => { active = false; };
  }, [dataset.dataset_id, offset]);

  const analyze = async () => {
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      onReport(await api.analyzeDataset(dataset.dataset_id));
    } catch (error) {
      setAnalysisError(error instanceof ApiClientError ? error.message : "Could not analyze this dataset.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="DATASET PROFILE"
        title={dataset.filename}
        description="Inspect the source structure and review its data quality."
        actions={
          <>
            <button className="button button-secondary" onClick={analyze} disabled={analyzing}>
              {analyzing ? <><span className="button-spinner button-spinner-dark" /> Analyzing…</> : <><Icon name="refresh" size={16} /> {report ? "Refresh analysis" : "Analyze quality"}</>}
            </button>
            <button className="button button-primary" onClick={onClean}><Icon name="sparkles" size={16} /> Clean dataset</button>
          </>
        }
      />
      {analysisError && <Alert>{analysisError}</Alert>}

      <div className="dataset-summary-strip">
        <div className="summary-file"><span className="file-icon file-icon-large"><Icon name="file" size={20} /></span><span><strong>{dataset.filename}</strong><small>Original file · {formatBytes(dataset.byte_size)}</small></span></div>
        <span className="summary-divider" />
        <div className="summary-stat"><strong>{dataset.row_count.toLocaleString()}</strong><small>Rows</small></div>
        <div className="summary-stat"><strong>{dataset.column_count}</strong><small>Columns</small></div>
        <div className="summary-stat"><strong>{new Date(dataset.created_at).toLocaleDateString()}</strong><small>Uploaded</small></div>
        <span className="status-pill"><i /> {dataset.status}</span>
      </div>

      <section className="details-grid">
        <div className="panel preview-panel">
          <div className="panel-heading">
            <div><h2>Data preview</h2><p>First-hand look at the original records.</p></div>
            <span className="subtle-count">{dataset.row_count.toLocaleString()} total rows</span>
          </div>
          {loadingPreview ? <LoadingState label="Loading preview…" /> : previewError ? <Alert>{previewError}</Alert> : preview?.rows.length ? (
            <>
              <div className="table-scroll">
                <table className="data-table preview-table">
                  <thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>{preview.rows.map((row, index) => (
                    <tr key={`${offset + index}-${dataset.dataset_id}`}>
                      {preview.columns.map((column) => <td key={column}>{row[column] || <span className="missing-cell">Empty</span>}</td>)}
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="pagination">
                <span>Showing {offset + 1}–{Math.min(offset + preview.rows.length, preview.total_rows)} of {preview.total_rows.toLocaleString()}</span>
                <div><button className="pagination-button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 10))}>Previous</button><button className="pagination-button" disabled={offset + 10 >= preview.total_rows} onClick={() => setOffset(offset + 10)}>Next</button></div>
              </div>
            </>
          ) : <EmptyState title="No preview rows" description="This dataset has no rows available to preview." />}
        </div>

        <aside className="panel schema-panel">
          <div className="panel-heading"><div><h2>Schema</h2><p>Columns detected in your file.</p></div><span className="subtle-count">{dataset.columns.length}</span></div>
          <div className="schema-list">
            {dataset.columns.map((column) => {
              const profile = report?.columns.find((item) => item.name === column);
              return (
                <div className="schema-row" key={column}>
                  <span className="schema-col-icon"><Icon name="columns" size={15} /></span>
                  <span className="schema-col-copy"><strong>{column}</strong><small>{profile ? profile.inferred_type : "Type not analyzed"}</small></span>
                  {profile?.missing_count ? <span className="schema-missing">{profile.missing_count} empty</span> : <span className="schema-clean"><Icon name="check" size={14} /></span>}
                </div>
              );
            })}
          </div>
        </aside>
      </section>

      <section className="panel quality-panel">
        <div className="panel-heading">
          <div><h2>Quality report</h2><p>Understand the signals in your source data. Nothing is changed by analysis.</p></div>
          {report && <time className="analysis-time">Analyzed {new Date(report.analyzed_at).toLocaleString()}</time>}
        </div>
        {!report ? (
          <EmptyState
            icon="sparkles"
            title="Your quality report is waiting"
            description="Analyze this dataset to identify missing values, exact duplicates, mixed formats, and numerical summaries."
            action={<button className="button button-secondary button-small" onClick={analyze} disabled={analyzing}>{analyzing ? "Analyzing…" : "Analyze dataset"}</button>}
          />
        ) : (
          <div className="quality-report-content">
            <div className="quality-score-block">
              <QualityScore score={report.quality_score} />
              <div><strong>Overall quality</strong><p>A transparent heuristic score, not a domain-specific validation. See how each issue contributes.</p>
                <button className="text-button score-info-toggle" onClick={() => setShowScoreInfo((value) => !value)} aria-expanded={showScoreInfo}>{showScoreInfo ? "Hide score details" : "How is this calculated?"}</button>
              </div>
            </div>
            {showScoreInfo && (
              <div className="score-explanation">
                <p>Score starts at 100. Penalties scale with affected rates: missing cells are weighted up to 40 points, duplicate rows up to 30, and inconsistent values up to 30. A higher score means fewer detected issues, but does not guarantee domain correctness.</p>
                <ul>{report.score_breakdown.map((part) => <li key={part.issue}><span>{issueLabel(part.issue)}</span><strong>−{part.penalty.toFixed(2)}</strong><small>{part.rule}</small></li>)}</ul>
              </div>
            )}
            <div className="quality-issue-grid">
              {report.issues.length ? report.issues.map((issue) => (
                <article className="quality-issue-card" key={issue.code}>
                  <div className="issue-card-top"><span className={`issue-dot issue-${issue.code}`} /><strong>{issueLabel(issue.code)}</strong><b>{issue.count.toLocaleString()}</b></div>
                  <p>{issue.suggested_action}</p>
                  <div className="affected-columns"><span>Affected</span>{issue.affected_columns.map((column) => <code key={column}>{column}</code>)}</div>
                </article>
              )) : <div className="clean-state"><span><Icon name="check" size={19} /></span><div><strong>No detectable issues found</strong><p>Analysis found no missing values, exact duplicates, or detectable type inconsistencies.</p></div></div>}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
