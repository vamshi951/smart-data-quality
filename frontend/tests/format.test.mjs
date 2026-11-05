import assert from "node:assert/strict";
import { test } from "node:test";
import { formatBytes } from "../src/lib/format.ts";
import { getInsightsReport } from "../src/lib/insights.ts";

test("formats sub-kilobyte files as bytes instead of zero kilobytes", () => {
  assert.equal(formatBytes(145), "145 B");
});

test("keeps useful precision for kilobyte file sizes", () => {
  assert.equal(formatBytes(1536), "1.5 KB");
});

test("formats megabyte file sizes", () => {
  assert.equal(formatBytes(1.5 * 1024 * 1024), "1.5 MB");
});

test("prefers metrics from the latest cleaned output in insights", () => {
  const originalReport = { row_count: 4 };
  const cleanedReport = { row_count: 2 };
  assert.equal(
    getInsightsReport({ quality_after_report: cleanedReport }, originalReport),
    cleanedReport,
  );
  assert.equal(getInsightsReport(undefined, originalReport), originalReport);
});
