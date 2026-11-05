import type { CSSProperties } from "react";
import type { ReactNode } from "react";
import { Icon } from "./Icon";

export function LoadingState({ label = "Loading data…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-12 text-sm text-slate-500" role="status">
      <span className="loading-spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function EmptyState({
  icon = "database",
  title,
  description,
  action,
}: {
  icon?: "database" | "file" | "sparkles";
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon">
        <Icon name={icon} size={25} />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function Alert({
  children,
  tone = "error",
}: {
  children: ReactNode;
  tone?: "error" | "success" | "info";
}) {
  const icon = tone === "success" ? "check" : tone === "info" ? "sparkles" : "alert";
  return (
    <div className={`alert alert-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name={icon} size={18} />
      <div>{children}</div>
    </div>
  );
}

export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-heading-actions">{actions}</div>}
    </div>
  );
}

export function QualityScore({ score }: { score: number }) {
  const tone = score >= 85 ? "good" : score >= 65 ? "moderate" : "poor";
  return (
    <div
      className={`score-ring score-${tone}`}
      style={{ "--score": `${Math.min(100, Math.max(0, score))}%` } as CSSProperties}
      aria-label={`Quality score ${score} out of 100`}
    >
      <span>{Math.round(score)}</span>
      <small>/ 100</small>
    </div>
  );
}
