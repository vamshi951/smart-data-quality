import type { SVGProps } from "react";

type IconName =
  | "grid"
  | "database"
  | "upload"
  | "sparkles"
  | "chart"
  | "download"
  | "settings"
  | "arrow"
  | "chevron"
  | "search"
  | "file"
  | "check"
  | "alert"
  | "clock"
  | "rows"
  | "columns"
  | "shield"
  | "refresh"
  | "close";

const paths: Record<IconName, string> = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
  database: "M12 3c-4.97 0-9 1.34-9 3v12c0 1.66 4.03 3 9 3s9-1.34 9-3V6c0-1.66-4.03-3-9-3z M3 6c0 1.66 4.03 3 9 3s9-1.34 9-3 M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3",
  upload: "M12 16V4m0 0L7 9m5-5 5 5M4 16v4h16v-4",
  sparkles: "m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3zm7 12 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z",
  chart: "M4 19V5m0 14h17M8 15l3-4 3 2 5-7",
  download: "M12 4v12m0 0 5-5m-5 5-5-5M4 19h16",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm0-5v2m0 14v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M3 12h2m14 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  chevron: "m9 18 6-6-6-6",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm10 2-4.35-4.35",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M8 13h8m-8 4h8",
  check: "m5 12 4 4L19 6",
  alert: "M12 9v4m0 4h.01M10.3 3.9 2.5 17.4A1.8 1.8 0 0 0 4 20h16a1.8 1.8 0 0 0 1.5-2.6L13.7 3.9a2 2 0 0 0-3.4 0z",
  clock: "M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  rows: "M4 6h16M4 12h16M4 18h16",
  columns: "M4 4v16m8-16v16m8-16v16M4 4h16M4 12h16M4 20h16",
  shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z m-3-11 2 2 4-4",
  refresh: "M20 7v5h-5M4 17v-5h5m-4.1-3a8 8 0 0 1 13.2-3L20 12M4 12l1.9 6.1a8 8 0 0 0 13.2-3",
  close: "M18 6 6 18M6 6l12 12",
};

type Props = SVGProps<SVGSVGElement> & { name: IconName; size?: number };

export function Icon({ name, size = 20, ...props }: Props) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
