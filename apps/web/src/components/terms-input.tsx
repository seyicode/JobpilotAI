"use client";
import { useState } from "react";
import { parseTerms } from "@/lib/preferences";

type Props = { label: string; hint?: string; values: string[]; onChange: (values: string[]) => void; placeholder?: string };

/** A list of short phrases: type and press Enter or comma to add; × to remove. */
export function TermsInput({ label, hint, values, onChange, placeholder }: Props) {
  const [draft, setDraft] = useState("");
  const commit = (text = draft) => { if (text.trim()) onChange(parseTerms(text, values)); setDraft(""); };
  // Typing or pasting a comma adds everything before it.
  const onType = (text: string) => text.includes(",") ? commit(text) : setDraft(text);
  return <div>
    <label className="block text-sm font-medium">{label}
      <input value={draft} placeholder={placeholder} maxLength={100}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
        onChange={e => onType(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); commit(); } }}
        onBlur={() => commit()} />
    </label>
    {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    {values.length > 0 && <ul className="mt-2 flex flex-wrap gap-2">{values.map(v => <li key={v} className="flex items-center gap-1 rounded-full border border-slate-300 bg-white py-0.5 pl-3 pr-1 text-sm">
      {v}<button type="button" onClick={() => onChange(values.filter(x => x !== v))} aria-label={`Remove ${v}`} className="rounded-full px-1.5 text-slate-400 hover:text-red-700">×</button>
    </li>)}</ul>}
  </div>;
}
