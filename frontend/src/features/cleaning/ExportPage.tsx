import { useState } from "react";
import { Alert, PageHeading } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { api, ApiClientError } from "../../lib/api";
import type { CleaningRun, Dataset } from "../../lib/types";

export function ExportPage({ dataset, run }: { dataset: Dataset; run?: CleaningRun }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);

  const download = async () => {
    setDownloading(true);
    setError(null);
    setDownloaded(false);
    try {
      await api.downloadCleanedDataset(dataset.dataset_id, dataset.filename);
      setDownloaded(true);
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "The cleaned CSV could not be downloaded.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="page-stack page-narrow">
      <PageHeading
        eyebrow="YOUR CLEANED DATA"
        title="Ready when you are."
        description="Download a formula-safe CSV from the latest successful cleaning run."
      />
      {error && <Alert>{error}</Alert>}
      {downloaded && <Alert tone="success">Your cleaned CSV download has started.</Alert>}

      <section className="panel export-card">
        <div className="export-art"><span className="export-art-sheet"><Icon name="file" size={35} /></span><span className="export-art-check"><Icon name="check" size={18} /></span></div>
        <p className="eyebrow">EXPORT DESTINATION</p>
        <h2>{dataset.filename.replace(/\.csv$/i, "")}_cleaned.csv</h2>
        <p className="export-description">Your original file remains unchanged. This export comes from the most recent cleaning run and escapes spreadsheet formula-leading values.</p>
        <div className="export-file-meta">
          <div><span>Source</span><strong>{dataset.filename}</strong></div>
          <div><span>Original rows</span><strong>{dataset.row_count.toLocaleString()}</strong></div>
          <div><span>Columns</span><strong>{dataset.column_count}</strong></div>
          {run && <div><span>Cleaned rows</span><strong>{run.row_count_after.toLocaleString()}</strong></div>}
        </div>
        {run ? (
          <div className="export-run-status"><span><Icon name="check" size={15} /></span><div><strong>Cleaned version available</strong><small>Created {new Date(run.created_at).toLocaleString()}</small></div></div>
        ) : (
          <div className="export-run-status export-run-pending"><span><Icon name="clock" size={15} /></span><div><strong>No cleaning run in this session yet</strong><small>If a prior run exists on the server, download will still find the latest one.</small></div></div>
        )}
        <button className="button button-primary export-button" onClick={download} disabled={downloading}>
          {downloading ? <><span className="button-spinner" /> Preparing download…</> : <><Icon name="download" size={17} /> Download cleaned CSV</>}
        </button>
        <p className="export-footnote"><Icon name="shield" size={14} /> Export only contains the cleaned result. Your uploaded original is never overwritten.</p>
      </section>
    </div>
  );
}
