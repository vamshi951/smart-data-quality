import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "./components/AppShell";
import type { PageName } from "./components/AppShell";
import { Alert, EmptyState, LoadingState } from "./components/Feedback";
import { Icon } from "./components/Icon";
import { CleaningPage } from "./features/cleaning/CleaningPage";
import { ExportPage } from "./features/cleaning/ExportPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DatasetDetailsPage } from "./features/quality/DatasetDetailsPage";
import { UploadPage } from "./features/upload/UploadPage";
import { api, ApiClientError } from "./lib/api";
import type { CleaningRun, Dataset, QualityReport } from "./lib/types";

const InsightsPage = lazy(() =>
  import("./features/insights/InsightsPage").then((module) => ({ default: module.InsightsPage })),
);

function DatasetRequired({ onUpload, onDashboard }: { onUpload: () => void; onDashboard: () => void }) {
  return (
    <div className="panel required-dataset">
      <EmptyState
        icon="database"
        title="Choose a dataset to continue"
        description="Select a dataset from your overview or upload a CSV to use this workspace."
        action={<div className="required-actions"><button className="button button-primary button-small" onClick={onUpload}><Icon name="upload" size={15} /> Upload CSV</button><button className="button button-quiet button-small" onClick={onDashboard}>Go to overview</button></div>}
      />
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<PageName>("dashboard");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [reports, setReports] = useState<Record<string, QualityReport>>({});
  const [runs, setRuns] = useState<Record<string, CleaningRun>>({});
  const [cleaningRunError, setCleaningRunError] = useState<string | null>(null);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [datasetsError, setDatasetsError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");

  const loadDatasets = useCallback(async () => {
    setLoadingDatasets(true);
    setDatasetsError(null);
    try {
      setDatasets(await api.listDatasets());
    } catch (error) {
      setDatasetsError(error instanceof ApiClientError ? error.message : "Could not load datasets.");
    } finally {
      setLoadingDatasets(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
  }, [loadDatasets]);

  useEffect(() => {
    let active = true;
    api.checkHealth()
      .then(() => { if (active) setApiStatus("online"); })
      .catch(() => { if (active) setApiStatus("offline"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedDatasetId || runs[selectedDatasetId]) return;
    let active = true;
    setCleaningRunError(null);
    api.getLatestCleaningRun(selectedDatasetId)
      .then((run) => {
        if (active) setRuns((current) => ({ ...current, [run.dataset_id]: run }));
      })
      .catch((error: unknown) => {
        if (!active || (error instanceof ApiClientError && error.status === 404)) return;
        setCleaningRunError(
          error instanceof ApiClientError
            ? error.message
            : "Could not load the latest cleaning run.",
        );
      });
    return () => { active = false; };
  }, [selectedDatasetId, runs]);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.dataset_id === selectedDatasetId),
    [datasets, selectedDatasetId],
  );

  const navigate = (nextPage: PageName) => {
    if (nextPage === "details" && !selectedDatasetId) {
      setPage("dashboard");
      return;
    }
    setPage(nextPage);
  };

  const openDataset = (dataset: Dataset) => {
    setSelectedDatasetId(dataset.dataset_id);
    setPage("details");
  };

  const uploaded = (dataset: Dataset) => {
    setDatasets((current) => [dataset, ...current.filter((item) => item.dataset_id !== dataset.dataset_id)]);
    setSelectedDatasetId(dataset.dataset_id);
    setPage("details");
  };

  const saveReport = useCallback((report: QualityReport) => {
    setReports((current) => ({ ...current, [report.dataset_id]: report }));
  }, []);

  const saveRun = useCallback((run: CleaningRun) => {
    setRuns((current) => ({ ...current, [run.dataset_id]: run }));
  }, []);

  let content;
  if (page === "dashboard") {
    content = <DashboardPage
      datasets={datasets}
      reports={reports}
      loading={loadingDatasets}
      error={datasetsError}
      onUpload={() => setPage("upload")}
      onOpenDataset={openDataset}
      onRetry={() => void loadDatasets()}
    />;
  } else if (page === "upload") {
    content = <UploadPage onUploaded={uploaded} onCancel={() => setPage("dashboard")} />;
  } else if (!selectedDataset) {
    content = <DatasetRequired onUpload={() => setPage("upload")} onDashboard={() => setPage("dashboard")} />;
  } else if (page === "details") {
    content = <DatasetDetailsPage
      dataset={selectedDataset}
      report={reports[selectedDataset.dataset_id]}
      onReport={saveReport}
      onClean={() => setPage("cleaning")}
    />;
  } else if (page === "cleaning") {
    content = <CleaningPage
      dataset={selectedDataset}
      report={reports[selectedDataset.dataset_id]}
      run={runs[selectedDataset.dataset_id]}
      onRun={saveRun}
      onAnalyze={saveReport}
    />;
  } else if (page === "insights") {
    content = <Suspense fallback={<div className="panel"><LoadingState label="Loading visualizations…" /></div>}>
      <InsightsPage
        dataset={selectedDataset}
        report={reports[selectedDataset.dataset_id]}
        run={runs[selectedDataset.dataset_id]}
        onReport={saveReport}
      />
    </Suspense>;
  } else {
    content = <ExportPage dataset={selectedDataset} run={runs[selectedDataset.dataset_id]} />;
  }

  return (
    <AppShell page={page} onNavigate={navigate} apiStatus={apiStatus} selectedFilename={page !== "dashboard" && page !== "upload" ? selectedDataset?.filename : undefined}>
      {datasetsError && page !== "dashboard" && (
        <div className="global-api-alert"><Alert>{datasetsError}</Alert></div>
      )}
      {cleaningRunError && page !== "dashboard" && (
        <div className="global-api-alert"><Alert>{cleaningRunError}</Alert></div>
      )}
      {loadingDatasets && page !== "dashboard" && datasets.length === 0 ? <div className="panel"><LoadingState label="Connecting to your workspace…" /></div> : content}
    </AppShell>
  );
}
