import { request, sendJson } from "@/lib/api";

export const KINDS = [
  { value: "job", label: "Work experience" },
  { value: "education", label: "Education" },
  { value: "project", label: "Projects" },
  { value: "certification", label: "Certifications" },
  { value: "volunteering", label: "Volunteering" },
  { value: "other", label: "Other" },
] as const;
export type Kind = (typeof KINDS)[number]["value"];

export type Experience = {
  id: string; kind: Kind; title: string; organization: string | null; location: string | null;
  start_date: string | null; end_date: string | null; is_current: boolean; highlights: string[];
  verified: boolean; source_resume_id: string | null; created_at: string; updated_at: string;
};
export type Skill = { id: string; name: string; verified: boolean; source_resume_id: string | null; created_at: string };

/** Editable form state: every field is a string or boolean so inputs stay controlled. */
export type ExperienceForm = {
  kind: Kind; title: string; organization: string; location: string;
  start_date: string; end_date: string; is_current: boolean; highlights: string;
};
export type ExperiencePayload = Omit<Experience, "id" | "verified" | "source_resume_id" | "created_at" | "updated_at">;

export const emptyForm = (): ExperienceForm =>
  ({ kind: "job", title: "", organization: "", location: "", start_date: "", end_date: "", is_current: false, highlights: "" });

export function toForm(e: Experience): ExperienceForm {
  return {
    kind: e.kind, title: e.title, organization: e.organization ?? "", location: e.location ?? "",
    start_date: e.start_date ?? "", end_date: e.end_date ?? "", is_current: e.is_current, highlights: e.highlights.join("\n"),
  };
}

export function toPayload(form: ExperienceForm): ExperiencePayload {
  const text = (value: string) => value.trim() || null;
  return {
    kind: form.kind, title: form.title.trim(), organization: text(form.organization), location: text(form.location),
    start_date: text(form.start_date), end_date: form.is_current ? null : text(form.end_date), is_current: form.is_current,
    highlights: form.highlights.split("\n").map(line => line.replace(/^\s*[•\-*]\s*/, "").trim()).filter(Boolean),
  };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function formatDate(value: string): string {
  const [year, month] = value.split("-");
  return month ? `${MONTHS[Number(month) - 1]} ${year}` : year;
}

export function formatDateRange(e: Pick<Experience, "start_date" | "end_date" | "is_current">): string {
  const end = e.is_current ? "Present" : e.end_date ? formatDate(e.end_date) : "";
  if (!e.start_date) return end;
  return `${formatDate(e.start_date)} – ${end || "?"}`;
}

export function groupByKind(experiences: Experience[]) {
  return KINDS.map(kind => ({ ...kind, items: experiences.filter(e => e.kind === kind.value) })).filter(g => g.items.length > 0);
}

export const listExperiences = () => request<Experience[]>("/experiences");
export const createExperience = (body: ExperiencePayload & { verified: boolean }) => request<Experience>("/experiences", sendJson("POST", body));
export const updateExperience = (id: string, body: Partial<ExperiencePayload> & { verified?: boolean }) =>
  request<Experience>(`/experiences/${id}`, sendJson("PATCH", body));
export const deleteExperience = (id: string) => request<void>(`/experiences/${id}`, { method: "DELETE" });

export const listSkills = () => request<Skill[]>("/skills");
export const createSkill = (name: string) => request<Skill>("/skills", sendJson("POST", { name, verified: true }));
export const updateSkill = (id: string, body: { name?: string; verified?: boolean }) => request<Skill>(`/skills/${id}`, sendJson("PATCH", body));
export const deleteSkill = (id: string) => request<void>(`/skills/${id}`, { method: "DELETE" });
