import { API_URL, request, sendJson } from "@/lib/api";
import type { Experience } from "@/lib/library";

export type UserProfile = {
  full_name: string | null; headline: string | null; email: string | null; phone: string | null;
  location: string | null; links: string[]; summary: string | null;
};
export type SavedProfile = UserProfile & { updated_at: string | null };

export type ResumeBullet = { text: string; source_text: string; changed_by: "none" | "ai" | "user"; reason: string | null };
export type ResumeEntry = {
  source_id: string; kind: Experience["kind"]; title: string; organization: string | null; location: string | null;
  start_date: string | null; end_date: string | null; is_current: boolean; bullets: ResumeBullet[]; reason: string | null;
};
export type ResumeSection = { kind: Experience["kind"]; heading: string; entries: ResumeEntry[] };
export type ResumeContent = {
  header: { name: string | null; headline: string | null; email: string | null; phone: string | null; location: string | null; links: string[] };
  summary: string | null; skills: string[]; sections: ResumeSection[];
};
export type VersionSummary = {
  id: string; job_id: string; version: number; status: "draft" | "approved"; generation_method: "deterministic" | "ai";
  edited: boolean; based_on_version: number | null; warning_count: number; note: string | null;
  created_at: string; updated_at: string; approved_at: string | null;
};
export type ResumeWarning = { location: string; message: string };
export type VersionDetail = VersionSummary & { content: ResumeContent; warnings: ResumeWarning[] };

const SECTION_HEADINGS: Record<Experience["kind"], string> = {
  job: "Experience", project: "Projects", education: "Education", certification: "Certifications", volunteering: "Volunteering", other: "Other",
};

export function versionLabel(v: VersionSummary): string {
  const method = v.generation_method === "ai" ? "AI-reworded" : "Selected";
  return [`v${v.version}`, v.status === "approved" ? "Approved" : "Draft", method, v.edited ? "edited" : null].filter(Boolean).join(" · ");
}

export function moveItem<T>(items: T[], index: number, delta: -1 | 1): T[] {
  const target = index + delta;
  if (target < 0 || target >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

/** Verified highlights of the entry's library source that the tailored entry does not use. */
export function unusedHighlights(entry: ResumeEntry, source: Experience | undefined): string[] {
  const used = new Set(entry.bullets.map(b => b.source_text));
  return (source?.highlights ?? []).filter(h => !used.has(h));
}

/** A library entry as a tailored entry with all its highlights (facts are re-copied by the server). */
export function entryFromLibrary(e: Experience): ResumeEntry {
  return {
    source_id: e.id, kind: e.kind, title: e.title, organization: e.organization, location: e.location,
    start_date: e.start_date, end_date: e.end_date, is_current: e.is_current, reason: "Added by you.",
    bullets: e.highlights.map(h => ({ text: h, source_text: h, changed_by: "none", reason: "Added by you." })),
  };
}

export function addEntry(content: ResumeContent, entry: ResumeEntry): ResumeContent {
  const sections = content.sections.some(s => s.kind === entry.kind)
    ? content.sections.map(s => s.kind === entry.kind ? { ...s, entries: [...s.entries, entry] } : s)
    : [...content.sections, { kind: entry.kind, heading: SECTION_HEADINGS[entry.kind], entries: [entry] }];
  return { ...content, sections };
}

export function updateEntry(content: ResumeContent, sourceId: string, change: (e: ResumeEntry) => ResumeEntry | null): ResumeContent {
  return {
    ...content,
    sections: content.sections
      .map(s => ({ ...s, entries: s.entries.flatMap(e => e.source_id === sourceId ? (change(e) ?? []) : [e]) }))
      .filter(s => s.entries.length > 0),
  };
}

export const exportUrl = (id: string, format: "pdf" | "docx") => `${API_URL}/tailored-resumes/${id}/export?format=${format}`;

export const getProfile = () => request<SavedProfile>("/profile");
export const saveProfile = (p: UserProfile) => request<SavedProfile>("/profile", sendJson("PUT", p));
export const getAIStatus = () => request<{ available: boolean }>("/ai/status");
export const listVersions = (jobId: string) => request<VersionSummary[]>(`/jobs/${jobId}/resumes`);
export const generateVersion = (jobId: string, method: "deterministic" | "ai") =>
  request<VersionDetail>(`/jobs/${jobId}/resumes`, sendJson("POST", { method }));
export const getVersion = (id: string) => request<VersionDetail>(`/tailored-resumes/${id}`);
export const saveVersion = (id: string, content: ResumeContent) => request<VersionDetail>(`/tailored-resumes/${id}`, sendJson("PUT", content));
export const approveVersion = (id: string, acknowledge: boolean) =>
  request<VersionDetail>(`/tailored-resumes/${id}/approve`, sendJson("POST", { acknowledge_warnings: acknowledge }));
export const copyVersion = (id: string) => request<VersionDetail>(`/tailored-resumes/${id}/copy`, { method: "POST" });
export const deleteVersion = (id: string) => request<void>(`/tailored-resumes/${id}`, { method: "DELETE" });
