"use client";
import { useEffect, useState } from "react";
import { ExperienceCard, StatusBadge } from "@/components/experience-card";
import { ExperienceForm } from "@/components/experience-form";
import {
  createExperience, createSkill, deleteExperience, deleteSkill, emptyForm, type Experience, type ExperiencePayload,
  groupByKind, listExperiences, listSkills, type Skill, toForm, updateExperience, updateSkill,
} from "@/lib/library";

export function LibraryManager() {
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [newSkill, setNewSkill] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const refresh = async () => {
    const [e, s] = await Promise.all([listExperiences(), listSkills()]);
    setExperiences(e); setSkills(s); setLoaded(true);
  };
  useEffect(() => { void run(refresh); }, []);

  const save = (id: string | "new", payload: ExperiencePayload, verified: boolean) => run(async () => {
    await (id === "new" ? createExperience({ ...payload, verified }) : updateExperience(id, { ...payload, verified }));
    setEditing(null); await refresh();
  });
  const verifyExperience = (id: string) => run(async () => { await updateExperience(id, { verified: true }); await refresh(); });
  function removeExperience(id: string) {
    if (confirmingDelete !== id) { setConfirmingDelete(id); return; }
    void run(async () => { await deleteExperience(id); setConfirmingDelete(null); await refresh(); });
  }
  const addSkill = () => run(async () => { await createSkill(newSkill.trim()); setNewSkill(""); await refresh(); });
  const toggleSkill = (s: Skill) => run(async () => { await updateSkill(s.id, { verified: !s.verified }); await refresh(); });
  const removeSkill = (s: Skill) => run(async () => { await deleteSkill(s.id); await refresh(); });

  const drafts = experiences.filter(e => !e.verified).length + skills.filter(s => !s.verified).length;
  return <div className="mt-8 space-y-10">
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {loaded && drafts > 0 && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{drafts} draft{drafts === 1 ? "" : "s"} to review. Imported entries are best guesses from your resume, so check titles, dates, and wording before you verify.</p>}

    <section>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold">Experience</h2>
        {editing !== "new" && <button onClick={() => setEditing("new")} disabled={busy} className="rounded-lg border border-teal-600 px-3 py-1.5 text-sm font-medium text-teal-800 hover:bg-teal-50">Add entry</button>}
      </div>
      <div className="mt-4 space-y-6">
        {editing === "new" && <ExperienceForm initial={emptyForm()} busy={busy} onSave={(p, v) => save("new", p, v)} onCancel={() => setEditing(null)} />}
        {groupByKind(experiences).map(group => <div key={group.value} className="space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{group.label}</h3>
          {group.items.map(e => editing === e.id
            ? <ExperienceForm key={e.id} initial={toForm(e)} busy={busy} onSave={(p, v) => save(e.id, p, v)} onCancel={() => setEditing(null)} />
            : <ExperienceCard key={e.id} experience={e} actions={{
                busy, confirmingDelete: confirmingDelete === e.id, onVerify: () => verifyExperience(e.id),
                onEdit: () => { setEditing(e.id); setConfirmingDelete(null); }, onDelete: () => removeExperience(e.id), onCancelDelete: () => setConfirmingDelete(null),
              }} />)}
        </div>)}
        {loaded && experiences.length === 0 && editing !== "new" && <p className="text-slate-600">No entries yet. Import a resume, or add an entry yourself.</p>}
      </div>
    </section>

    <section>
      <h2 className="text-2xl font-semibold">Skills</h2>
      <p className="mt-1 text-sm text-slate-600">Click a skill to verify it or mark it as a draft again. Skills you add yourself are saved as verified.</p>
      <ul className="mt-4 flex flex-wrap gap-2">{skills.map(s => <li key={s.id} className={`flex items-center gap-1 rounded-full border bg-white py-1 pl-3 pr-1 text-sm ${s.verified ? "border-teal-600" : "border-dashed border-amber-400"}`}>
        <button onClick={() => toggleSkill(s)} disabled={busy} title={s.verified ? "Mark as draft" : "Verify"} className="flex items-center gap-2">{s.name} <StatusBadge verified={s.verified} /></button>
        <button onClick={() => removeSkill(s)} disabled={busy} aria-label={`Delete ${s.name}`} className="rounded-full px-2 text-slate-400 hover:text-red-700">×</button>
      </li>)}</ul>
      <form className="mt-4 flex max-w-md gap-2" onSubmit={e => { e.preventDefault(); if (newSkill.trim()) void addSkill(); }}>
        <input value={newSkill} onChange={e => setNewSkill(e.target.value)} maxLength={100} placeholder="Add a skill" className="w-full rounded-lg border border-slate-300 px-3 py-2" />
        <button disabled={busy || !newSkill.trim()} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">Add</button>
      </form>
    </section>
  </div>;
}
