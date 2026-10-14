"use client";
import { useEffect, useState } from "react";
import { TermsInput } from "@/components/terms-input";
import { getProfile, saveProfile, type UserProfile } from "@/lib/tailored";

const FIELDS: { key: "full_name" | "headline" | "email" | "phone" | "location"; label: string; type?: string }[] = [
  { key: "full_name", label: "Full name" }, { key: "headline", label: "Headline" },
  { key: "email", label: "Email", type: "email" }, { key: "phone", label: "Phone", type: "tel" },
  { key: "location", label: "Location" },
];

/** Contact details and summary used at the top of every tailored resume. */
export function ProfileForm() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getProfile().then(({ updated_at: _, ...p }) => setProfile(p), e => setStatus(e.message)); }, []);
  if (!profile) return status ? <p role="alert" className="text-sm text-red-800">{status}</p> : null;

  const set = (changes: Partial<UserProfile>) => { setProfile({ ...profile, ...changes }); setStatus("Unsaved changes"); };
  async function save() {
    setBusy(true);
    try { const { updated_at: _, ...saved } = await saveProfile(profile!); setProfile(saved); setStatus("Saved"); }
    catch (e) { setStatus(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  return <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-6" onSubmit={e => { e.preventDefault(); void save(); }}>
    <div>
      <h2 className="text-2xl font-semibold">Contact details and summary</h2>
      <p className="mt-1 text-sm text-slate-600">Shown at the top of your tailored resumes, exactly as you write them here.</p>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">{FIELDS.map(f => <label key={f.key} className="block text-sm font-medium">{f.label}
      <input type={f.type ?? "text"} className={input} value={profile[f.key] ?? ""} onChange={e => set({ [f.key]: e.target.value || null })} />
    </label>)}</div>
    <TermsInput label="Links" values={profile.links} onChange={links => set({ links })} placeholder="https://" hint="Up to 5, e.g. your portfolio or professional profile." />
    <label className="block text-sm font-medium">Summary
      <textarea className={`${input} min-h-28`} maxLength={1200} value={profile.summary ?? ""} onChange={e => set({ summary: e.target.value || null })} />
    </label>
    <div className="flex items-center gap-3">
      <button disabled={busy} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">Save details</button>
      {status && <span role="status" className="text-sm text-slate-600">{status}</span>}
    </div>
  </form>;
}
