"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ResumeEntryReview } from "@/components/resume-entry-review";
import { getJob, type JobDetail, jobLabel } from "@/lib/jobs";
import { type Experience, listExperiences, listSkills } from "@/lib/library";
import {
  addEntry, approveVersion, copyVersion, deleteVersion, entryFromLibrary, exportUrl, generateVersion, getAIStatus, getProfile,
  getVersion, listVersions, type ResumeContent, saveVersion, updateEntry, type VersionDetail, versionLabel, type VersionSummary,
} from "@/lib/tailored";

export function ResumeReview({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [current, setCurrent] = useState<VersionDetail | null>(null);
  const [draft, setDraft] = useState<ResumeContent | null>(null);
  const [library, setLibrary] = useState<Experience[]>([]);
  const [verifiedSkills, setVerifiedSkills] = useState<string[]>([]);
  const [profileSummary, setProfileSummary] = useState<string | null>(null);
  const [aiAvailable, setAIAvailable] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const show = (v: VersionDetail) => { setCurrent(v); setDraft(v.content); setAcknowledged(false); setConfirmingDelete(false); };
  const refreshVersions = async () => setVersions(await listVersions(jobId));
  useEffect(() => {
    void run(async () => {
      const [j, vs, exp, skills, profile, ai] = await Promise.all([
        getJob(jobId), listVersions(jobId), listExperiences(), listSkills(), getProfile(), getAIStatus(),
      ]);
      setJob(j); setVersions(vs); setLibrary(exp.filter(e => e.verified));
      setVerifiedSkills(skills.filter(s => s.verified).map(s => s.name));
      setProfileSummary(profile.summary); setAIAvailable(ai.available);
      if (vs.length) show(await getVersion(vs[0].id));
    });
  }, [jobId]);

  const generate = (method: "deterministic" | "ai") => run(async () => { show(await generateVersion(jobId, method)); await refreshVersions(); });
  const open = (id: string) => run(async () => show(await getVersion(id)));
  const save = () => run(async () => { show(await saveVersion(current!.id, draft!)); await refreshVersions(); });
  const approve = () => run(async () => { show(await approveVersion(current!.id, acknowledged)); await refreshVersions(); });
  const copy = () => run(async () => { show(await copyVersion(current!.id)); await refreshVersions(); });
  const remove = () => run(async () => {
    await deleteVersion(current!.id); const vs = await listVersions(jobId); setVersions(vs);
    if (vs.length) show(await getVersion(vs[0].id)); else { setCurrent(null); setDraft(null); }
  });

  const editable = current?.status === "draft";
  const dirty = !!current && JSON.stringify(current.content) !== JSON.stringify(draft);
  const used = new Set(draft?.sections.flatMap(s => s.entries.map(e => e.source_id)) ?? []);
  const addable = library.filter(e => !used.has(e.id));
  const button = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50";
  const primary = "rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50";

  return <div className="mt-8 space-y-6">
    {job && <p className="text-lg text-slate-700">For <Link href="/jobs" className="font-semibold text-teal-700 underline">{jobLabel(job)}</Link></p>}
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}

    <div className="flex flex-wrap items-center gap-2">
      <button onClick={() => generate("deterministic")} disabled={busy} className={primary}>Generate from library</button>
      <button onClick={() => generate("ai")} disabled={busy || !aiAvailable} className={button}
        title={aiAvailable ? "Rewords bullets with AI; every rewording is fact-checked" : "AI is not configured"}>Generate with AI rewording</button>
      {!aiAvailable && <span className="text-xs text-slate-500">AI rewording is off. Generated resumes use your verified wording.</span>}
    </div>

    {versions.length > 0 && <nav aria-label="Versions" className="flex flex-wrap gap-2">{versions.map(v =>
      <button key={v.id} onClick={() => open(v.id)} disabled={busy}
        className={`rounded-full border px-3 py-1 text-sm ${current?.id === v.id ? "border-teal-600 bg-teal-50" : "border-slate-300 bg-white"}`}>
        {versionLabel(v)}{v.warning_count > 0 && ` · ${v.warning_count} warning${v.warning_count === 1 ? "" : "s"}`}
      </button>)}</nav>}

    {!current && !busy && <p className="rounded-xl border border-slate-200 bg-white p-8 text-slate-600">
      No resume yet. Generate one: it uses only entries and skills you have verified in your <Link href="/library" className="text-teal-700 underline">library</Link>.
    </p>}

    {current && draft && <>
      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">{versionLabel(current)}</h2>
          <div className="flex flex-wrap gap-2">
            {editable && <button onClick={save} disabled={busy || !dirty} className={button}>Save changes</button>}
            {editable && !dirty && <button onClick={approve} disabled={busy || (current.warnings.length > 0 && !acknowledged)} className={primary}>Approve</button>}
            {current.status === "approved" && <>
              <a href={exportUrl(current.id, "pdf")} className={primary} download>Download PDF</a>
              <a href={exportUrl(current.id, "docx")} className={button} download>Download DOCX</a>
              <button onClick={copy} disabled={busy} className={button}>Copy to new draft</button>
            </>}
            {editable && (confirmingDelete
              ? <><button onClick={remove} disabled={busy} className="rounded-lg bg-red-700 px-3 py-1.5 text-sm font-medium text-white">Confirm delete</button>
                  <button onClick={() => setConfirmingDelete(false)} className={button}>Cancel</button></>
              : <button onClick={() => setConfirmingDelete(true)} disabled={busy} className={button}>Delete draft</button>)}
          </div>
        </div>
        {current.note && <p className="text-sm text-slate-600">{current.note}</p>}
        {editable && dirty && <p className="text-sm text-amber-800">Save your changes before approving.</p>}
        {current.status === "approved" && <p className="text-sm text-teal-800">Approved {new Date(current.approved_at!).toLocaleString()}. Approved versions are locked; copy one to make changes.</p>}
        {current.warnings.length > 0 && <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-semibold">Check these before approving. They may claim more than your verified library shows.</p>
          <ul className="mt-2 list-disc pl-5">{current.warnings.map((w, i) => <li key={i}><span className="font-medium">{w.location}:</span> {w.message}</li>)}</ul>
          {editable && <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} /> I&apos;ve checked these and they are accurate</label>}
        </div>}
      </section>

      <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 lg:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your profile summary</p>
          <p className="mt-2 whitespace-pre-line text-sm text-slate-800">{profileSummary ?? "No summary in your profile."}</p>
        </div>
        <div className="lg:border-l lg:pl-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Summary on your tailored resume</p>
          {editable
            ? <textarea aria-label="Summary" className="mt-2 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" rows={4} maxLength={1200}
                value={draft.summary ?? ""} onChange={e => setDraft({ ...draft, summary: e.target.value || null })} />
            : <p className="mt-2 whitespace-pre-line text-sm">{draft.summary ?? "None"}</p>}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Skills (verified only)</p>
        <div className="mt-2 flex flex-wrap gap-2">{verifiedSkills.map(name => {
          const on = draft.skills.some(s => s.toLowerCase() === name.toLowerCase());
          return <label key={name} className={`rounded-full border px-3 py-1 text-sm ${on ? "border-teal-600 bg-teal-50" : "border-slate-300 text-slate-500"} ${editable ? "cursor-pointer" : ""}`}>
            <input type="checkbox" className="sr-only" disabled={!editable} checked={on}
              onChange={() => setDraft({ ...draft, skills: on ? draft.skills.filter(s => s.toLowerCase() !== name.toLowerCase()) : [...draft.skills, name] })} />
            {name}
          </label>;
        })}</div>
      </section>

      {draft.sections.map(section => <section key={section.kind} className="space-y-3">
        <h3 className="text-lg font-semibold">{section.heading}</h3>
        {section.entries.map(entry => <ResumeEntryReview key={entry.source_id} entry={entry} editable={editable}
          source={library.find(e => e.id === entry.source_id)}
          onChange={next => setDraft(updateEntry(draft, entry.source_id, () => next))} />)}
      </section>)}

      {editable && addable.length > 0 && <label className="block max-w-xl text-sm font-medium">Add an entry from your verified library
        <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-2" value=""
          onChange={e => { const found = addable.find(x => x.id === e.target.value); if (found) setDraft(addEntry(draft, entryFromLibrary(found))); }}>
          <option value="">Choose…</option>{addable.map(e => <option key={e.id} value={e.id}>{e.title}{e.organization ? ` at ${e.organization}` : ""}</option>)}
        </select>
      </label>}
    </>}
  </div>;
}
