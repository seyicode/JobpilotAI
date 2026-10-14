import { request, sendJson } from "@/lib/api";
import { EMPLOYMENT_TYPES, SALARY_PERIODS, SENIORITY_LEVELS, WORK_ARRANGEMENTS } from "@/lib/preferences";

export type Salary = { min: number | null; max: number | null; currency: string | null; period: "year" | "month" | "hour" | null };
export type JobRequirements = {
  title: string | null; company: string | null; required_skills: string[]; preferred_skills: string[];
  seniority: (typeof SENIORITY_LEVELS)[number]["value"] | null; location: string | null;
  work_arrangement: (typeof WORK_ARRANGEMENTS)[number]["value"] | null;
  employment_type: (typeof EMPLOYMENT_TYPES)[number]["value"] | null;
  salary: Salary; years_experience_min: number | null; qualifications: string[];
};
export type ExtractionMethod = "openai" | "rules" | "manual";
export type JobListItem = {
  id: string; title: string | null; company: string | null; source_url: string | null;
  extraction_method: ExtractionMethod | null; created_at: string;
  match_score: number | null; match_coverage: number; eligible: boolean;
};
export type JobDetail = Omit<JobListItem, "match_score" | "match_coverage" | "eligible"> & {
  description: string; requirements: JobRequirements | null; extraction_note: string | null; extracted_at: string | null;
  application_status: string; seen_at: string | null;
};
export type FilterResult = { filter: string; status: "pass" | "fail" | "unknown"; reason: string };
export type ScoreComponent = { key: string; label: string; weight: number; status: "scored" | "unknown"; value: number | null; points: number | null; detail: string };
export type Evidence = { requirement: string; kind: string; source: "skill" | "experience"; source_label: string; quote: string | null };
export type Gap = { requirement: string; kind: string; hint: string | null };
export type MatchResult = {
  eligible: boolean; score: number | null; coverage: number; summary: string;
  filters: FilterResult[]; preference_checks: FilterResult[]; components: ScoreComponent[]; evidence: Evidence[]; gaps: Gap[];
};
export type NewJob = { description: string; source_url: string; title: string; company: string };

export const MIN_DESCRIPTION = 50;
export const MAX_DESCRIPTION = 50_000;

export function validateNewJob(job: NewJob): string | null {
  const length = job.description.trim().length;
  if (length < MIN_DESCRIPTION) return `Paste the full job description (at least ${MIN_DESCRIPTION} characters).`;
  if (length > MAX_DESCRIPTION) return "That description is too long (50,000 characters at most).";
  if (job.source_url.trim() && !/^https?:\/\/\S+$/i.test(job.source_url.trim())) return "Job URLs must start with http:// or https://.";
  return null;
}

const label = (options: readonly { value: string; label: string }[], value: string | null) =>
  value ? options.find(o => o.value === value)?.label ?? value : null;
export const seniorityLabel = (v: JobRequirements["seniority"]) => label(SENIORITY_LEVELS, v);
export const arrangementLabel = (v: JobRequirements["work_arrangement"]) => label(WORK_ARRANGEMENTS, v);
export const employmentLabel = (v: JobRequirements["employment_type"]) => label(EMPLOYMENT_TYPES, v);

export function formatSalary(s: Salary): string | null {
  if (s.min === null && s.max === null) return null;
  const fmt = (n: number) => n.toLocaleString("en-US");
  const amount = s.min !== null && s.max !== null && s.min !== s.max ? `${fmt(s.min)}–${fmt(s.max)}` : fmt((s.max ?? s.min)!);
  const period = s.period ? ` ${SALARY_PERIODS.find(p => p.value === s.period)!.label}` : "";
  return `${amount}${s.currency ? ` ${s.currency}` : ""}${period}`;
}

export const EXTRACTION_LABELS: Record<ExtractionMethod, string> = {
  openai: "Extracted with AI", rules: "Extracted with local rules", manual: "Corrected by you",
};

export const emptyRequirements = (): JobRequirements => ({
  title: null, company: null, required_skills: [], preferred_skills: [], seniority: null, location: null,
  work_arrangement: null, employment_type: null, salary: { min: null, max: null, currency: null, period: null },
  years_experience_min: null, qualifications: [],
});

export function jobLabel(job: Pick<JobListItem, "title" | "company">): string {
  return [job.title ?? "Untitled job", job.company].filter(Boolean).join(" · ");
}

export const listJobs = () => request<JobListItem[]>("/jobs");
export const getJob = (id: string) => request<JobDetail>(`/jobs/${id}`);
export const getMatch = (id: string) => request<MatchResult>(`/jobs/${id}/match`);
export const deleteJob = (id: string) => request<void>(`/jobs/${id}`, { method: "DELETE" });
export const reextractJob = (id: string) => request<JobDetail>(`/jobs/${id}/extract`, { method: "POST" });
export const saveRequirements = (id: string, body: JobRequirements) => request<JobDetail>(`/jobs/${id}/requirements`, sendJson("PUT", body));
export function createJob(job: NewJob) {
  const optional = (v: string) => v.trim() || null;
  return request<{ job: JobDetail; duplicate: boolean }>("/jobs", sendJson("POST", {
    description: job.description.trim(), source_url: optional(job.source_url), title: optional(job.title), company: optional(job.company),
  }));
}
