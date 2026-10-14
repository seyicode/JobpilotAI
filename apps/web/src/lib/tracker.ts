import { API_URL, request, sendJson } from "@/lib/api";

export const STATUSES = [
  { value: "discovered", label: "Discovered" }, { value: "shortlisted", label: "Shortlisted" },
  { value: "ready_to_apply", label: "Ready to apply" }, { value: "applied", label: "Applied" },
  { value: "interviewing", label: "Interviewing" }, { value: "offered", label: "Offered" },
  { value: "rejected", label: "Rejected" }, { value: "archived", label: "Archived" },
] as const;
export type ApplicationStatus = (typeof STATUSES)[number]["value"];

export const VIEWS = [
  { value: "new", label: "New" }, { value: "saved", label: "Saved" }, { value: "in_progress", label: "In progress" },
  { value: "all", label: "All active" }, { value: "archived", label: "Archived" },
] as const;
export type View = (typeof VIEWS)[number]["value"];

export type TrackerRow = {
  id: string; title: string | null; company: string | null; application_status: ApplicationStatus;
  match_score: number | null; match_coverage: number; eligible: boolean; location: string | null; work_arrangement: string | null;
  salary_min: number | null; salary_max: number | null; salary_currency: string | null; salary_period: "year" | "month" | "hour" | null;
  found_at: string; posted_at: string | null; last_seen_at: string | null; closed: boolean; is_new: boolean;
  source_provider: string | null; source_url: string | null; resume_status: "none" | "draft" | "approved"; status_changed_at: string | null;
};
export type TrackerPage = { items: TrackerRow[]; next_cursor: string | null; total: number };
export type TrackerSummary = { new: number; by_status: Record<ApplicationStatus, number> };

export type TrackerFilters = {
  view: View; min_score: string; company: string; q: string; found_from: string; found_to: string;
  min_salary: string; salary_currency: string; include_unknown_salary: boolean;
  sort: "score" | "found" | "company" | "salary" | "status_changed"; order: "asc" | "desc";
};
export const defaultFilters = (): TrackerFilters => ({
  view: "new", min_score: "", company: "", q: "", found_from: "", found_to: "", min_salary: "", salary_currency: "",
  include_unknown_salary: true, sort: "score", order: "desc",
});

/** Query string for the API; blank fields are omitted. */
export function filterQuery(f: TrackerFilters): string {
  const params = new URLSearchParams();
  params.set("view", f.view);
  for (const key of ["min_score", "company", "q", "found_from", "found_to", "min_salary"] as const) {
    const raw = f[key].trim();
    const value = key === "min_salary" ? raw.replace(/[,\s]/g, "") : raw;
    if (value) params.set(key, value);
  }
  if (f.salary_currency.trim()) params.set("salary_currency", f.salary_currency.trim().toUpperCase());
  if (!f.include_unknown_salary) params.set("include_unknown_salary", "false");
  params.set("sort", f.sort);
  params.set("order", f.order);
  return params.toString();
}

export const statusLabel = (s: ApplicationStatus) => STATUSES.find(x => x.value === s)?.label ?? s;

export function rowSalary(r: TrackerRow): string | null {
  if (r.salary_min === null && r.salary_max === null) return null;
  const fmt = (n: number) => n.toLocaleString("en-US");
  const range = r.salary_min !== null && r.salary_max !== null && r.salary_min !== r.salary_max
    ? `${fmt(r.salary_min)}–${fmt(r.salary_max)}` : fmt((r.salary_max ?? r.salary_min)!);
  const period = r.salary_period ? ` / ${r.salary_period}` : "";
  return `${range}${r.salary_currency ? ` ${r.salary_currency}` : ""}${period}`;
}

export const listApplications = (f: TrackerFilters, cursor?: string | null) =>
  request<TrackerPage>(`/applications?${filterQuery(f)}&limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
export const getSummary = () => request<TrackerSummary>("/applications/summary");
export const exportCsvUrl = (f: TrackerFilters) => `${API_URL}/applications/export.csv?${filterQuery(f)}`;
export const updateApplication = (jobId: string, body: { status?: ApplicationStatus; seen?: boolean; notes?: string | null }) =>
  request<{ application_status: ApplicationStatus }>(`/jobs/${jobId}/application`, sendJson("PATCH", body));
