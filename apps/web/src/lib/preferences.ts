import { request, sendJson } from "@/lib/api";

export const WORK_ARRANGEMENTS = [
  { value: "remote", label: "Remote" }, { value: "hybrid", label: "Hybrid" }, { value: "onsite", label: "On-site" },
] as const;
export const EMPLOYMENT_TYPES = [
  { value: "full_time", label: "Full-time" }, { value: "part_time", label: "Part-time" }, { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" }, { value: "temporary", label: "Temporary" },
] as const;
export const SENIORITY_LEVELS = [
  { value: "intern", label: "Intern" }, { value: "entry", label: "Entry" }, { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" }, { value: "lead", label: "Lead" }, { value: "manager", label: "Manager" },
  { value: "director", label: "Director" }, { value: "executive", label: "Executive" },
] as const;
export const SALARY_PERIODS = [
  { value: "year", label: "per year" }, { value: "month", label: "per month" }, { value: "hour", label: "per hour" },
] as const;

type Values<T extends readonly { value: string }[]> = T[number]["value"];
export type HardFilter = "work_arrangement" | "location" | "employment_type" | "seniority" | "min_salary";

export type Preferences = {
  target_titles: string[]; seniority_levels: Values<typeof SENIORITY_LEVELS>[];
  locations: string[]; willing_to_relocate: boolean; work_arrangements: Values<typeof WORK_ARRANGEMENTS>[];
  employment_types: Values<typeof EMPLOYMENT_TYPES>[];
  min_salary: number | null; salary_currency: string; salary_period: Values<typeof SALARY_PERIODS>;
  include_keywords: string[]; exclude_keywords: string[]; excluded_companies: string[];
  hard_filters: HardFilter[];
};
export type SavedPreferences = Preferences & { updated_at: string | null };

/** Split typed text on commas and new lines, trimming and dropping blanks and duplicates. */
export function parseTerms(text: string, existing: string[] = []): string[] {
  const result = [...existing];
  for (const term of text.split(/[,\n]/).map(t => t.trim().replace(/\s+/g, " "))) {
    if (term && !result.some(r => r.toLowerCase() === term.toLowerCase())) result.push(term);
  }
  return result;
}

export function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter(v => v !== value) : [...list, value];
}

/** Parse the salary input; blank means no minimum. Returns undefined for invalid input. */
export function parseSalary(text: string): number | null | undefined {
  const cleaned = text.replace(/[,\s]/g, "");
  if (!cleaned) return null;
  return /^\d+$/.test(cleaned) ? Number(cleaned) : undefined;
}

export function withoutUpdatedAt({ updated_at: _, ...preferences }: SavedPreferences): Preferences {
  return preferences;
}

export const getPreferences = () => request<SavedPreferences>("/preferences");
export const savePreferences = (body: Preferences) => request<SavedPreferences>("/preferences", sendJson("PUT", body));
