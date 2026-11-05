import type { ReactNode } from "react";
import { Icon } from "./Icon";

export type PageName = "dashboard" | "upload" | "details" | "cleaning" | "insights" | "export";

const navItems: { id: PageName; label: string; icon: "grid" | "database" | "sparkles" | "chart" | "download" }[] = [
  { id: "dashboard", label: "Overview", icon: "grid" },
  { id: "details", label: "Datasets", icon: "database" },
  { id: "cleaning", label: "Clean data", icon: "sparkles" },
  { id: "insights", label: "Insights", icon: "chart" },
  { id: "export", label: "Export", icon: "download" },
];

const titles: Record<PageName, string> = {
  dashboard: "Overview",
  upload: "Upload dataset",
  details: "Dataset details",
  cleaning: "Clean data",
  insights: "Insights",
  export: "Export",
};

export function AppShell({
  page,
  onNavigate,
  children,
  selectedFilename,
  apiStatus,
}: {
  page: PageName;
  onNavigate: (page: PageName) => void;
  children: ReactNode;
  selectedFilename?: string;
  apiStatus: "checking" | "online" | "offline";
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => onNavigate("dashboard")} aria-label="Go to overview">
          <span className="brand-mark"><Icon name="sparkles" size={19} /></span>
          <span className="brand-copy">clarity<span>DATA QUALITY</span></span>
        </button>

        <div className="nav-caption">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id || (page === "upload" && item.id === "dashboard") ? "nav-item-active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={page === item.id ? "page" : undefined}
              aria-label={item.label}
              title={item.label}
            >
              <Icon name={item.icon} size={18} />
              <span>{item.label}</span>
              {page === item.id && <span className="nav-active-dot" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="privacy-card">
            <span className="privacy-icon"><Icon name="shield" size={17} /></span>
            <div><strong>Your data stays yours</strong><span>Files stored locally</span></div>
          </div>
          <div className="user-profile">
            <span className="avatar">DQ</span>
            <span className="user-copy"><strong>Data workspace</strong><small>Local environment</small></span>
            <span className="status-dot" aria-label="Local workspace" />
          </div>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span><Icon name="chevron" size={15} /><strong>{titles[page]}</strong>
            {selectedFilename && <><Icon name="chevron" size={15} /><span className="crumb-file">{selectedFilename}</span></>}
          </div>
          <div className="topbar-actions">
            <span className={`api-status api-${apiStatus}`} role="status"><i /> {apiStatus === "checking" ? "Connecting" : apiStatus === "online" ? "API connected" : "API offline"}</span>
            <button className="icon-button" aria-label="Settings" title="Settings are not available yet" disabled>
              <Icon name="settings" size={18} />
            </button>
            <span className="avatar avatar-small">DQ</span>
          </div>
        </header>
        <main className="content-area">{children}</main>
      </div>
    </div>
  );
}
