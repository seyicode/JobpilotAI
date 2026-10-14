"use client";
import { useState } from "react";
import { type ExperienceForm as FormState, type ExperiencePayload, KINDS, type Kind, toPayload } from "@/lib/library";

type Props = { initial: FormState; busy: boolean; onSave: (payload: ExperiencePayload, verify: boolean) => void; onCancel: () => void };

export function ExperienceForm({ initial, busy, onSave, onCancel }: Props) {
  const [form, setForm] = useState(initial);
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm(f => ({ ...f, [key]: value }));
  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  const text = (key: "title" | "organization" | "location" | "start_date" | "end_date", label: string, placeholder = "") =>
    <label className="block text-sm font-medium">{label}
      <input className={input} value={form[key]} placeholder={placeholder} disabled={key === "end_date" && form.is_current} onChange={e => set(key, e.target.value)} />
    </label>;
  return <form className="space-y-4 rounded-xl border border-teal-600 bg-white p-5" onSubmit={e => e.preventDefault()}>
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block text-sm font-medium">Type
        <select className={input} value={form.kind} onChange={e => set("kind", e.target.value as Kind)}>
          {KINDS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
      </label>
      {text("title", "Title", "Software Engineer")}
      {text("organization", "Organization", "Example Corp")}
      {text("location", "Location")}
      {text("start_date", "Start (YYYY or YYYY-MM)", "2021-03")}
      {text("end_date", "End (YYYY or YYYY-MM)", "2024-06")}
    </div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_current} onChange={e => set("is_current", e.target.checked)} /> I currently do this</label>
    <label className="block text-sm font-medium">Highlights, one per line
      <textarea className={`${input} min-h-32`} value={form.highlights} onChange={e => set("highlights", e.target.value)} />
    </label>
    <p className="text-sm text-slate-600">Only verify what you can back up. Verified entries are the only ones JobPilot will use when tailoring resumes.</p>
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={busy || !form.title.trim()} onClick={() => onSave(toPayload(form), true)} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">Save and verify</button>
      <button type="button" disabled={busy || !form.title.trim()} onClick={() => onSave(toPayload(form), false)} className="rounded-lg border border-slate-300 px-4 py-2 disabled:opacity-50">Save as draft</button>
      <button type="button" onClick={onCancel} className="px-4 py-2 text-slate-600">Cancel</button>
    </div>
  </form>;
}
