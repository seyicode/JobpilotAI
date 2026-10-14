import { request } from "@/lib/api";

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];

export type ResumeSection = { key: string; heading: string; content: string };
export type ResumeSummary = { id: string; filename: string; file_type: string; size_bytes: number; created_at: string };
export type ResumeDetail = ResumeSummary & { text: string; sections: ResumeSection[] };

/** Client-side pre-check; the API enforces the same rules. */
export function validateResumeFile(file: { name: string; size: number }): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some(ext => name.endsWith(ext))) return "Upload a PDF, DOCX, or TXT file.";
  if (file.size === 0) return "The selected file is empty.";
  if (file.size > MAX_RESUME_BYTES) return "Resumes must be 5 MB or smaller.";
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const listResumes = () => request<ResumeSummary[]>("/resumes");
export const getResume = (id: string) => request<ResumeDetail>(`/resumes/${id}`);
export const deleteResume = (id: string) => request<void>(`/resumes/${id}`, { method: "DELETE" });
export function uploadResume(file: File) {
  const body = new FormData();
  body.append("file", file);
  return request<ResumeDetail>("/resumes", { method: "POST", body });
}
export type ImportResult = { experiences_created: number; skills_created: number; skipped: number };
export const importResume = (id: string) => request<ImportResult>(`/resumes/${id}/import`, { method: "POST" });

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export function describeImport(r: ImportResult): string {
  const created = `Added ${count(r.experiences_created, "draft entry", "draft entries")} and ${count(r.skills_created, "draft skill", "draft skills")}`;
  return r.skipped ? `${created}; ${r.skipped} already in your library.` : `${created}.`;
}
