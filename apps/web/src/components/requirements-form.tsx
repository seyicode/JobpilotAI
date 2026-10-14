"use client";
import { useState } from "react";
import { TermsInput } from "@/components/terms-input";
import type { JobRequirements } from "@/lib/jobs";
import { EMPLOYMENT_TYPES, parseSalary, SALARY_PERIODS, SENIORITY_LEVELS, WORK_ARRANGEMENTS } from "@/lib/preferences";

type Props = { initial: JobRequirements; busy: boolean; onSave: (r: JobRequirements) => void; onCancel: () => void };

/** Correct extracted requirements. Leave a field blank or "Unknown" when the posting doesn't say. */
export function RequirementsForm({ initial, busy, onSave, onCancel }: Props) {
  const [r, setR] = useState(initial);
  const [salaryMin, setSalaryMin] = useState(initial.salary.min?.toString() ?? "");
  const [salaryMax, setSalaryMax] = useState(initial.salary.max?.toString() ?? "");
  const [years, setYears] = useState(initial.years_experience_min?.toString() ?? "");
  const [qualifications, setQualifications] = useState(initial.qualifications.join("\n"));
  const set = (changes: Partial<JobRequirements>) => setR({ ...r, ...changes });
  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";

  const min = parseSalary(salaryMin), max = parseSalary(salaryMax), yearsValue = parseSalary(years);
  const invalid = min === undefined || max === undefined || yearsValue === undefined || (yearsValue ?? 0) > 50;
  const save = () => onSave({
    ...r, years_experience_min: yearsValue ?? null,
    salary: { ...r.salary, min: min ?? null, max: max ?? null, currency: r.salary.currency?.trim().toUpperCase() || null },
    qualifications: qualifications.split("\n").map(q => q.trim()).filter(Boolean),
  });
  const select = <T extends string>(labelText: string, value: T | null, options: readonly { value: T; label: string }[], onChange: (v: T | null) => void) =>
    <label className="block text-sm font-medium">{labelText}
      <select className={input} value={value ?? ""} onChange={e => onChange((e.target.value || null) as T | null)}>
        <option value="">Unknown</option>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>;

  return <form className="space-y-4" onSubmit={e => { e.preventDefault(); if (!invalid) save(); }}>
    <TermsInput label="Required skills" values={r.required_skills} onChange={v => set({ required_skills: v })} />
    <TermsInput label="Preferred skills" values={r.preferred_skills} onChange={v => set({ preferred_skills: v })} />
    <div className="grid gap-4 sm:grid-cols-2">
      {select("Seniority", r.seniority, SENIORITY_LEVELS, v => set({ seniority: v }))}
      {select("Work arrangement", r.work_arrangement, WORK_ARRANGEMENTS, v => set({ work_arrangement: v }))}
      {select("Employment type", r.employment_type, EMPLOYMENT_TYPES, v => set({ employment_type: v }))}
      <label className="block text-sm font-medium">Location
        <input className={input} value={r.location ?? ""} onChange={e => set({ location: e.target.value || null })} placeholder="Unknown" />
      </label>
      <label className="block text-sm font-medium">Salary from
        <input className={input} inputMode="numeric" value={salaryMin} onChange={e => setSalaryMin(e.target.value)} placeholder="Unknown" />
      </label>
      <label className="block text-sm font-medium">Salary to
        <input className={input} inputMode="numeric" value={salaryMax} onChange={e => setSalaryMax(e.target.value)} placeholder="Unknown" />
      </label>
      <label className="block text-sm font-medium">Currency
        <input className={`${input} uppercase`} maxLength={3} value={r.salary.currency ?? ""} onChange={e => set({ salary: { ...r.salary, currency: e.target.value || null } })} placeholder="GBP" />
      </label>
      {select("Pay period", r.salary.period, SALARY_PERIODS, v => set({ salary: { ...r.salary, period: v } }))}
      <label className="block text-sm font-medium">Minimum years of experience
        <input className={input} inputMode="numeric" value={years} onChange={e => setYears(e.target.value)} placeholder="Unknown" />
      </label>
    </div>
    <label className="block text-sm font-medium">Qualifications, one per line
      <textarea className={`${input} min-h-24`} value={qualifications} onChange={e => setQualifications(e.target.value)} />
    </label>
    {invalid && <p className="text-sm text-red-700">Salary and years must be whole numbers (years at most 50), or blank.</p>}
    <div className="flex flex-wrap gap-2">
      <button disabled={busy || invalid} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">Save corrections</button>
      <button type="button" onClick={onCancel} className="px-4 py-2 text-slate-600">Cancel</button>
    </div>
  </form>;
}
