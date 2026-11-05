import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Alert, EmptyState, LoadingState, PageHeading, QualityScore } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { ApiClientError, api } from "../../lib/api";
import { getInsightsReport } from "../../lib/insights";
import type { CleaningRun, Dataset, QualityReport } from "../../lib/types";

const chartColors = ["#6d63d8", "#33a18a", "#e7a14d", "#dc6b79", "#4a8cc7", "#929caf"];

export function InsightsPage({
  dataset,
  report,
  run,
  onReport,
}: {
  dataset: Dataset;
  report?: QualityReport;
  run?: CleaningRun;
  onReport: (report: QualityReport) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const displayReport = getInsightsReport(run, report);

  useEffect(() => {
    if (displayReport) return;
    let active = true;
    setLoading(true);
    api.analyzeDataset(dataset.dataset_id)
      .then((result) => { if (active) onReport(result); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof ApiClientError ? caught.message : "Could not analyze the dataset."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [dataset.dataset_id, displayReport, onReport]);

  const typeData = useMemo(() => {
    if (!displayReport) return [];
    const counts = new Map<string, number>();
    displayReport.columns.forEach((column) => counts.set(column.inferred_type, (counts.get(column.inferred_type) ?? 0) + 1));
    return Array.from(counts, ([name, value]) => ({ name, value }));
  }, [displayReport]);
  const numericColumns = displayReport?.columns.filter((column) => column.numerical_summary) ?? [];

  const analyze = async () => {
    setLoading(true);
    setError(null);
    try {
      onReport(await api.analyzeDataset(dataset.dataset_id));
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "Could not analyze the dataset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeading
        eyebrow="DATA, MADE VISIBLE"
        title="Insights."
        description={`Explore detected patterns in ${dataset.filename}. Summaries are calculated from the ${run ? "latest cleaned output" : "original dataset"}.`}
        actions={!run && <button className="button button-secondary" onClick={analyze} disabled={loading}><Icon name="refresh" size={16} /> Refresh analysis</button>}
      />
      {error && <Alert>{error}</Alert>}
      {loading && !displayReport ? <div className="panel"><LoadingState label="Profiling columns and calculating summaries…" /></div> : !displayReport ? (
        <div className="panel"><EmptyState icon="sparkles" title="No insights to show yet" description="Analyze this dataset to calculate data quality and column summaries." action={<button className="button button-primary button-small" onClick={analyze}>Analyze dataset</button>} /></div>
      ) : (
        <>
          <section className="insights-summary-grid">
            <article className="panel insight-score-card"><div><span className="metric-label">QUALITY SCORE</span><h2>{displayReport.quality_score.toFixed(2)}<small> / 100</small></h2><p>Explainable heuristic based on detected missing values, duplicates, and type inconsistencies.</p></div><QualityScore score={displayReport.quality_score} /></article>
            <article className="panel insight-stat"><span className="metric-icon metric-purple"><Icon name="rows" size={18} /></span><span className="metric-label">Rows analyzed</span><strong>{displayReport.row_count.toLocaleString()}</strong><small>Across {displayReport.column_count} columns</small></article>
            <article className="panel insight-stat"><span className="metric-icon metric-amber"><Icon name="alert" size={18} /></span><span className="metric-label">Missing cells</span><strong>{displayReport.issue_counts.missing_cells.toLocaleString()}</strong><small>Empty or whitespace-only</small></article>
            <article className="panel insight-stat"><span className="metric-icon metric-mint"><Icon name="sparkles" size={18} /></span><span className="metric-label">Exact duplicates</span><strong>{displayReport.issue_counts.duplicate_rows.toLocaleString()}</strong><small>Rows matching across all columns</small></article>
          </section>

          <section className="charts-grid">
            <article className="panel chart-panel">
              <div className="panel-heading"><div><h2>Missing values by column</h2><p>Empty cells detected in each field.</p></div></div>
              {displayReport.columns.length ? (
                <>
                  <div className="chart-area">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={displayReport.columns.map((column) => ({ column: column.name, missing: column.missing_count }))} margin={{ top: 8, right: 12, bottom: 40, left: 0 }}>
                        <CartesianGrid stroke="#edf0f5" vertical={false} />
                        <XAxis dataKey="column" tick={{ fill: "#718096", fontSize: 11 }} angle={-30} textAnchor="end" interval={0} />
                        <YAxis allowDecimals={false} tick={{ fill: "#8a94a6", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <Tooltip cursor={{ fill: "#f7f8fc" }} />
                        <Bar dataKey="missing" name="Missing cells" fill="#8176df" radius={[5, 5, 0, 0]} maxBarSize={44} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="chart-text-summary">Text summary: {displayReport.columns.map((column) => `${column.name}: ${column.missing_count.toLocaleString()}`).join(" · ")}</p>
                </>
              ) : <EmptyState title="No columns available" description="This dataset has no column summaries." />}
            </article>

            <article className="panel chart-panel type-chart-panel">
              <div className="panel-heading"><div><h2>Column type mix</h2><p>Automatically inferred from values.</p></div></div>
              {typeData.length ? (
                <>
                  <div className="type-chart-wrap">
                    <div className="type-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={typeData} dataKey="value" nameKey="name" innerRadius={61} outerRadius={89} paddingAngle={3} stroke="none">
                            {typeData.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]} />)}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <ul className="type-legend">{typeData.map((item, index) => <li key={item.name}><i style={{ backgroundColor: chartColors[index % chartColors.length] }} /><span>{item.name}</span><strong>{item.value}</strong></li>)}</ul>
                  </div>
                  <p className="chart-text-summary">Type inference is heuristic and does not validate domain-specific rules.</p>
                </>
              ) : <EmptyState title="No type profile" description="Column types could not be inferred." />}
            </article>
          </section>

          <section className="panel numerical-panel">
            <div className="panel-heading"><div><h2>Numerical summaries</h2><p>Descriptive statistics for columns detected as numeric.</p></div><span className="subtle-count">{numericColumns.length} numeric {numericColumns.length === 1 ? "column" : "columns"}</span></div>
            {numericColumns.length ? (
              <div className="table-scroll"><table className="data-table">
                <thead><tr><th>Column</th><th>Count</th><th>Minimum</th><th>Maximum</th><th>Mean</th><th>Median</th><th>Std. dev.</th></tr></thead>
                <tbody>{numericColumns.map((column) => <tr key={column.name}>
                  <td><strong>{column.name}</strong></td><td>{column.numerical_summary?.count.toLocaleString()}</td>
                  <td>{column.numerical_summary?.minimum.toLocaleString()}</td><td>{column.numerical_summary?.maximum.toLocaleString()}</td>
                  <td>{column.numerical_summary?.mean.toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                  <td>{column.numerical_summary?.median.toLocaleString(undefined, { maximumFractionDigits: 3 })}</td>
                  <td>{column.numerical_summary?.standard_deviation?.toLocaleString(undefined, { maximumFractionDigits: 3 }) ?? "—"}</td>
                </tr>)}</tbody>
              </table></div>
            ) : <EmptyState title="No numerical columns detected" description="The report did not find columns suitable for numerical summaries." />}
            <div className="method-note"><Icon name="shield" size={15} /> Statistics are descriptive only. Values are not changed or coerced in the original file.</div>
          </section>
        </>
      )}
    </div>
  );
}
