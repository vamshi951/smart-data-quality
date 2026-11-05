import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { Alert, PageHeading } from "../../components/Feedback";
import { Icon } from "../../components/Icon";
import { ApiClientError, api } from "../../lib/api";
import type { Dataset } from "../../lib/types";

const MAX_FILE_BYTES = 25 * 1024 * 1024;

export function UploadPage({ onUploaded, onCancel }: { onUploaded: (dataset: Dataset) => void; onCancel: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectFile = (selected: File | undefined) => {
    if (!selected) return;
    setError(null);
    setSuccess(null);
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Choose a .csv file. Other file formats are not supported yet.");
      return;
    }
    if (selected.size > MAX_FILE_BYTES) {
      setFile(null);
      setError("This file is larger than the 25 MB upload limit.");
      return;
    }
    setFile(selected);
  };

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => selectFile(event.target.files?.[0]);
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files[0]);
  };

  const upload = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setProgress(0);
    try {
      const dataset = await api.uploadDataset(file, setProgress);
      setSuccess(`${dataset.filename} uploaded and validated successfully.`);
      onUploaded(dataset);
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "The file could not be uploaded.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page-stack page-narrow">
      <PageHeading
        eyebrow="ADD A DATASET"
        title="Bring your data in."
        description="Upload a CSV and get an instant view of its structure and quality."
        actions={<button className="button button-quiet" onClick={onCancel}>Cancel</button>}
      />
      {error && <Alert>{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}

      <section
        className={`drop-zone ${dragging ? "drop-zone-active" : ""} ${file ? "drop-zone-selected" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        aria-label="CSV file upload area"
      >
        <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" onChange={onInputChange} aria-label="Choose a CSV file" />
        {file ? (
          <div className="selected-file">
            <span className="selected-file-icon"><Icon name="file" size={22} /></span>
            <div className="selected-file-copy"><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB · CSV file</small></div>
            {!busy && <button className="icon-button" aria-label="Remove selected file" onClick={() => setFile(null)}><Icon name="close" size={17} /></button>}
          </div>
        ) : (
          <>
            <span className="upload-cloud"><Icon name="upload" size={24} /></span>
            <h2>Drop your CSV file here</h2>
            <p>or <button className="inline-link" onClick={() => inputRef.current?.click()}>browse files</button> from your computer</p>
            <span className="upload-hint">CSV format · Up to 25 MB</span>
          </>
        )}
        {busy && (
          <div className="upload-progress">
            <div className="progress-meta"><span>{progress < 100 ? "Uploading file…" : "Validating and saving…"}</span><strong>{progress}%</strong></div>
            <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
          </div>
        )}
      </section>

      <div className="upload-actions">
        <button className="button button-primary" onClick={upload} disabled={!file || busy}>
          {busy ? <><span className="button-spinner" /> Uploading…</> : <><Icon name="upload" size={17} /> Upload dataset</>}
        </button>
        <span className="upload-secure"><Icon name="shield" size={15} /> Your data stays in your local workspace</span>
      </div>

      <section className="upload-guidance">
        <div className="guidance-heading"><span className="guidance-bulb">✦</span><div><h3>For a smooth upload</h3><p>A couple of things to know before you begin.</p></div></div>
        <ul>
          <li><span><Icon name="check" size={14} /></span> Use a UTF-8 encoded CSV with a clear header row.</li>
          <li><span><Icon name="check" size={14} /></span> Each row should have the same number of columns.</li>
          <li><span><Icon name="check" size={14} /></span> Your original file is preserved and never modified.</li>
        </ul>
      </section>
    </div>
  );
}
