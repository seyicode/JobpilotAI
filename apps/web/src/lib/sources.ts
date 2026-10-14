import { request, sendJson } from "@/lib/api";

export type Provider = "greenhouse" | "lever" | "ashby";
export type ProviderInfo = { provider: Provider; label: string; docs_url: string; board_hint: string };
export type SourceHealth = "new" | "healthy" | "degraded" | "failing";
export type Source = {
  id: string; provider: Provider; board: string; company_name: string; enabled: boolean; interval_minutes: number;
  status: SourceHealth; consecutive_failures: number; last_run_at: string | null; last_success_at: string | null;
  next_run_at: string | null; last_error_code: string | null; last_error_message: string | null; created_at: string;
};
export type SourceRun = {
  id: string; trigger: "manual" | "scheduled"; status: "running" | "success" | "failed" | "skipped";
  started_at: string; finished_at: string | null; attempts: number; http_status: number | null;
  fetched: number; new_jobs: number; seen_again: number; filtered_out: number; archived: number; closed: number;
  error_code: string | null; error_message: string | null;
};
export type DiscoveryStatus = {
  scheduled: boolean; uses_ai: boolean; requests_last_hour: number; hourly_request_limit: number;
  next_check_at: string | null; sources_failing: number;
};

export const INTERVALS = [
  { minutes: 60, label: "Every hour" }, { minutes: 180, label: "Every 3 hours" }, { minutes: 360, label: "Every 6 hours" },
  { minutes: 720, label: "Every 12 hours" }, { minutes: 1440, label: "Daily" },
];

/** Accepts a board name or a pasted board URL, returning just the board name. */
export function boardFromInput(input: string): string {
  const value = input.trim();
  const match = value.match(/^https?:\/\/(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.lever\.co|jobs\.ashbyhq\.com)\/([^/?#]+)/i);
  return match ? match[1] : value;
}

export function describeRun(r: SourceRun): string {
  if (r.status === "failed" || r.status === "skipped") return r.error_message ?? "Did not complete.";
  const parts = [`${r.fetched} listed`, `${r.new_jobs} new`];
  if (r.filtered_out) parts.push(`${r.filtered_out} skipped by your preferences`);
  if (r.archived) parts.push(`${r.archived} archived (must-match)`);
  if (r.closed) parts.push(`${r.closed} no longer listed`);
  return parts.join(" · ");
}

export const listProviders = () => request<ProviderInfo[]>("/sources/providers");
export const listSources = () => request<Source[]>("/sources");
export const getDiscoveryStatus = () => request<DiscoveryStatus>("/sources/status");
export const addSource = (body: { provider: Provider; board: string; company_name: string; interval_minutes: number }) =>
  request<Source>("/sources", sendJson("POST", body));
export const updateSource = (id: string, body: Partial<Pick<Source, "enabled" | "interval_minutes" | "company_name">>) =>
  request<Source>(`/sources/${id}`, sendJson("PATCH", body));
export const deleteSource = (id: string) => request<void>(`/sources/${id}`, { method: "DELETE" });
export const runSource = (id: string) => request<SourceRun>(`/sources/${id}/run`, { method: "POST" });
export const listRuns = (id: string) => request<SourceRun[]>(`/sources/${id}/runs?limit=10`);
