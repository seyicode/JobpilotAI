"use client";
import { type ReactNode, useEffect, useState } from "react";
import { TermsInput } from "@/components/terms-input";
import {
  EMPLOYMENT_TYPES, getPreferences, type HardFilter, parseSalary, type Preferences, SALARY_PERIODS, savePreferences,
  SENIORITY_LEVELS, toggle, withoutUpdatedAt, WORK_ARRANGEMENTS,
} from "@/lib/preferences";

export function PreferencesForm() {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [salaryText, setSalaryText] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (saved: Awaited<ReturnType<typeof getPreferences>>) => {
    setPrefs(withoutUpdatedAt(saved)); setSalaryText(saved.min_salary?.toLocaleString() ?? ""); setSavedAt(saved.updated_at); setDirty(false);
  };
  useEffect(() => { getPreferences().then(load, e => setError(e.message)); }, []);
  if (!prefs) return <p className="mt-8 text-slate-600">{error ?? "Loading…"}</p>;

  const update = (changes: Partial<Preferences>) => { setPrefs({ ...prefs, ...changes }); setDirty(true); };
  const salary = parseSalary(salaryText);
  async function save() {
    if (!prefs || salary === undefined) return;
    setBusy(true); setError(null);
    try { load(await savePreferences({ ...prefs, min_salary: salary })); }
    catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const mustMatch = (filter: HardFilter) => <MustMatch checked={prefs.hard_filters.includes(filter)} onChange={() => update({ hard_filters: toggle(prefs.hard_filters, filter) })} />;
  const choices = <T extends string>(options: readonly { value: T; label: string }[], selected: T[], onChange: (v: T[]) => void) =>
    <div className="flex flex-wrap gap-2">{options.map(o => <label key={o.value} className={`cursor-pointer rounded-full border px-3 py-1 text-sm ${selected.includes(o.value) ? "border-teal-600 bg-teal-50 text-teal-900" : "border-slate-300 bg-white"}`}>
      <input type="checkbox" className="sr-only" checked={selected.includes(o.value)} onChange={() => onChange(toggle(selected, o.value))} />{o.label}
    </label>)}</div>;

  return <form className="mt-8 space-y-6" onSubmit={e => { e.preventDefault(); void save(); }}>
    <Card title="Roles">
      <TermsInput label="Job titles you're targeting" values={prefs.target_titles} onChange={v => update({ target_titles: v })} placeholder="Backend Engineer" hint="Press Enter or type a comma to add each one." />
      <Field label="Seniority" action={mustMatch("seniority")}>{choices(SENIORITY_LEVELS, prefs.seniority_levels, v => update({ seniority_levels: v }))}</Field>
    </Card>

    <Card title="Where you'll work">
      <Field label="Work arrangement" action={mustMatch("work_arrangement")}>{choices(WORK_ARRANGEMENTS, prefs.work_arrangements, v => update({ work_arrangements: v }))}</Field>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1"><TermsInput label="Locations" values={prefs.locations} onChange={v => update({ locations: v })} placeholder="London" hint="Remote jobs always pass the location check." /></div>
        <div className="pt-6">{mustMatch("location")}</div>
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={prefs.willing_to_relocate} onChange={e => update({ willing_to_relocate: e.target.checked })} /> I&apos;m willing to relocate</label>
    </Card>

    <Card title="Employment">
      <Field label="Employment type" action={mustMatch("employment_type")}>{choices(EMPLOYMENT_TYPES, prefs.employment_types, v => update({ employment_types: v }))}</Field>
      <Field label="Minimum salary" action={mustMatch("min_salary")}>
        <div className="flex flex-wrap gap-2">
          <input inputMode="numeric" value={salaryText} onChange={e => { setSalaryText(e.target.value); setDirty(true); }} placeholder="No minimum" aria-label="Minimum salary" className="w-40 rounded-lg border border-slate-300 px-3 py-2" />
          <input value={prefs.salary_currency} onChange={e => update({ salary_currency: e.target.value.toUpperCase().slice(0, 3) })} aria-label="Currency" className="w-20 rounded-lg border border-slate-300 px-3 py-2 uppercase" />
          <select value={prefs.salary_period} onChange={e => update({ salary_period: e.target.value as Preferences["salary_period"] })} aria-label="Pay period" className="rounded-lg border border-slate-300 px-3 py-2">
            {SALARY_PERIODS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
        {salary === undefined && <p className="mt-1 text-sm text-red-700">Enter a whole number, or leave it blank.</p>}
        <p className="mt-1 text-xs text-slate-500">Compared with the top of a job&apos;s range. Jobs in another currency or with no salary listed are never filtered out.</p>
      </Field>
    </Card>

    <Card title="Keywords and companies">
      <TermsInput label="Keywords you'd like to see" values={prefs.include_keywords} onChange={v => update({ include_keywords: v })} placeholder="Python" hint="Used to rank matches, not to filter." />
      <TermsInput label="Keywords to avoid" values={prefs.exclude_keywords} onChange={v => update({ exclude_keywords: v })} placeholder="on-call" hint="Always applied: jobs that mention these are filtered out." />
      <TermsInput label="Companies to skip" values={prefs.excluded_companies} onChange={v => update({ excluded_companies: v })} hint="Always applied." />
    </Card>

    <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-slate-50/95 py-4" style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom, 0px))" }}>
      <button disabled={busy || !dirty || salary === undefined} className="rounded-lg bg-teal-700 px-5 py-2 font-medium text-white disabled:opacity-50">{busy ? "Saving…" : "Save preferences"}</button>
      {error ? <p role="alert" className="text-sm text-red-800">{error}</p>
        : <p className="text-sm text-slate-600">{dirty ? "Unsaved changes" : savedAt ? `Saved ${new Date(savedAt).toLocaleString()}` : "Not saved yet"}</p>}
    </div>
  </form>;
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return <fieldset className="space-y-4 rounded-xl border border-slate-200 bg-white p-6"><legend className="px-1 text-lg font-semibold">{title}</legend>{children}</fieldset>;
}

function Field({ label, action, children }: { label: string; action?: ReactNode; children: ReactNode }) {
  return <div><div className="mb-2 flex items-center justify-between gap-4"><span className="text-sm font-medium">{label}</span>{action}</div>{children}</div>;
}

export function MustMatch({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return <label className="flex shrink-0 items-center gap-2 text-xs font-medium text-slate-600" title="Must match: jobs that clearly conflict are filtered out. Otherwise this only affects ranking.">
    <input type="checkbox" checked={checked} onChange={onChange} /> Must match
  </label>;
}
