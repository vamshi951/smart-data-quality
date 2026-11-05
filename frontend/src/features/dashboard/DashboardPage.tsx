import { useMemo } from "react";
import type { Dataset, QualityReport } from "../../lib/types";
import { EmptyState, LoadingState, PageHeading } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { formatBytes } from "../../lib/format";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export function DashboardPage({
  datasets,
  reports,
  loading,
  error,
  onUpload,
  onOpenDataset,
  onRetry,
}: {
  datasets: Dataset[];
  reports: Record<string, QualityReport>;
  loading: boolean;
  error: string | null;
  onUpload: () => void;
  onOpenDataset: (dataset: Dataset) => void;
  onRetry: () => void;
}) {
  const totalRows = useMemo(() => datasets.reduce((total, dataset) => total + dataset.row_count, 0), [datasets]);
  const scores = Object.values(reports).map((report) => report.quality_score);
  const averageScore = scores.length
    ? Math.round(scores.reduce((total, score) => total + score, 0) / scores.length)
    : null;
  const recentDatasets = datasets.slice(0, 5);

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="YOUR DATA WORKSPACE"
        title="Good data starts here."
        description="A clear view of your uploaded datasets, quality, and next steps."
        actions={<button className="button button-primary" onClick={onUpload}><Icon name="upload" size={17} /> Upload CSV</button>}
      />

      <section className="welcome-banner">
        <div className="welcome-copy">
          <span className="welcome-kicker"><span className="welcome-spark">✦</span> DATA CLARITY, WITHOUT THE BUSYWORK</span>
          <h2>Make every row<br /><em>count.</em></h2>
          <p>Find the gaps, understand the patterns, and prepare your data with confidence.</p>
          <button className="button button-light" onClick={onUpload}>Start with a CSV <Icon name="arrow" size={16} /></button>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" />
          <div className="art-card art-card-back"><span /><span /><span /></div>
          <div className="art-card art-card-front">
            <div className="art-card-head"><i /><i /><i /><b>DATA QUALITY</b></div>
            <div className="art-grid"><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /></div>
            <div className="art-check"><Icon name="check" size={16} /></div>
          </div>
          <div className="art-spark art-spark-a">✦</div><div className="art-spark art-spark-b">✧</div>
        </div>
      </section>

      {error && (
        <div className="alert alert-error" role="alert">
          <Icon name="alert" size={18} /><div className="flex-1">{error}</div>
          <button className="text-button" onClick={onRetry}>Try again</button>
        </div>
      )}

      <section className="metric-grid" aria-label="Workspace summary">
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon metric-purple"><Icon name="database" size={18} /></span><span className="metric-label">Datasets</span></div>
          <div className="metric-value">{loading ? "—" : datasets.length}</div>
          <div className="metric-foot">{loading ? "Loading workspace" : "Files in your workspace"}</div>
        </article>
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon metric-mint"><Icon name="rows" size={18} /></span><span className="metric-label">Rows available</span></div>
          <div className="metric-value">{loading ? "—" : totalRows.toLocaleString()}</div>
          <div className="metric-foot">Across all uploaded datasets</div>
        </article>
        <article className="metric-card">
          <div className="metric-top"><span className="metric-icon metric-amber"><Icon name="sparkles" size={18} /></span><span className="metric-label">Avg. quality score</span></div>
          <div className="metric-value">{averageScore === null ? "—" : `${averageScore}`}<small>{averageScore === null ? "" : "/100"}</small></div>
          <div className="metric-foot">{averageScore === null ? "Analyze a dataset to get started" : `From ${scores.length} analyzed ${scores.length === 1 ? "dataset" : "datasets"}`}</div>
        </article>
      </section>

      <section className="dashboard-lower">
        <div className="panel recent-panel">
          <div className="panel-heading">
            <div><h2>Recent datasets</h2><p>Your latest uploads, ready to explore.</p></div>
            {datasets.length > 0 && <button className="text-button" onClick={() => onOpenDataset(datasets[0])}>View all <Icon name="arrow" size={15} /></button>}
          </div>
          {loading ? <LoadingState label="Loading your datasets…" /> : recentDatasets.length === 0 ? (
            <EmptyState
              icon="file"
              title="Your workspace is ready"
              description="Upload a CSV to see its structure, check data quality, and discover insights."
              action={<button className="button button-primary button-small" onClick={onUpload}><Icon name="upload" size={15} /> Upload your first CSV</button>}
            />
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Dataset</th><th>Rows</th><th>Columns</th><th>Size</th><th>Uploaded</th><th><span className="sr-only">Open dataset</span></th></tr></thead>
                <tbody>
                  {recentDatasets.map((dataset) => (
                    <tr key={dataset.dataset_id} className="clickable-row" onClick={() => onOpenDataset(dataset)}>
                      <td><span className="file-cell"><span className="file-icon"><Icon name="file" size={17} /></span><span><strong>{dataset.filename}</strong><small>CSV dataset</small></span></span></td>
                      <td>{dataset.row_count.toLocaleString()}</td>
                      <td>{dataset.column_count}</td>
                      <td>{formatBytes(dataset.byte_size)}</td>
                      <td>{formatDate(dataset.created_at)}</td>
                      <td><button className="row-action" aria-label={`Open ${dataset.filename}`} onClick={(event) => { event.stopPropagation(); onOpenDataset(dataset); }}><Icon name="chevron" size={17} /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <aside className="panel activity-panel">
          <div className="panel-heading"><div><h2>Recent activity</h2><p>What’s happening in your workspace.</p></div></div>
          {loading ? <LoadingState label="Checking activity…" /> : datasets.length === 0 ? (
            <div className="activity-empty"><span className="activity-empty-icon"><Icon name="clock" size={19} /></span><p>Activity will appear here after your first upload.</p></div>
          ) : (
            <ul className="activity-list">
              {recentDatasets.slice(0, 4).map((dataset) => {
                const analyzed = reports[dataset.dataset_id];
                return (
                  <li key={dataset.dataset_id}>
                    <span className={`activity-icon ${analyzed ? "activity-icon-done" : ""}`}><Icon name={analyzed ? "check" : "upload"} size={15} /></span>
                    <span className="activity-copy"><strong>{analyzed ? "Quality report ready" : "Dataset uploaded"}</strong><small>{dataset.filename}</small><time>{formatDate(analyzed?.analyzed_at ?? dataset.created_at)}</time></span>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="privacy-note"><Icon name="shield" size={17} /><span>Your uploaded files remain in your local workspace.</span></div>
        </aside>
      </section>
    </div>
  );
}
