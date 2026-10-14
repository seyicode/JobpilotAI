"use client";
import { useEffect, useState } from "react";
import { MatchView, ScoreBadge } from "@/components/match-view";
import { RequirementsForm } from "@/components/requirements-form";
import { RequirementsView } from "@/components/requirements-view";
import {
  createJob, deleteJob, emptyRequirements, EXTRACTION_LABELS, getJob, getMatch, type JobDetail, jobLabel, type JobListItem,
  listJobs, type MatchResult, type NewJob, reextractJob, saveRequirements, validateNewJob,
} from "@/lib/jobs";

const emptyJob = (): NewJob => ({ description: "", source_url: "", title: "", company: "" });

export function JobsManager() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [selected, setSelected] = useState<{ job: JobDetail; match: MatchResult } | null>(null);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<NewJob>(emptyJob);
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null); setNotice(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const refresh = async () => { setJobs(await listJobs()); setLoaded(true); };
  const show = async (job: JobDetail) => {
    setSelected({ job, match: await getMatch(job.id) }); setEditing(false); setConfirmingDelete(false); setAdding(false);
  };
  useEffect(() => { void run(refresh); }, []);

  function submit() {
    const problem = validateNewJob(draft);
    if (problem) { setError(problem); return; }
    void run(async () => {
      const { job, duplicate } = await createJob(draft);
      setDraft(emptyJob()); await show(job); await refresh();
      if (duplicate) setNotice("You already saved this job, so here it is.");
    });
  }
  const open = (id: string) => run(async () => show(await getJob(id)));
  const reextract = (id: string) => run(async () => { await show(await reextractJob(id)); await refresh(); });
  const save = (id: string, r: JobDetail["requirements"]) =>
    run(async () => { await show(await saveRequirements(id, r!)); await refresh(); });
  const remove = (id: string) => run(async () => { await deleteJob(id); setSelected(null); await refresh(); });

  const field = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  return <div className="mt-10 grid gap-8 lg:grid-cols-[20rem_1fr]">
    <aside className="space-y-4">
      <button onClick={() => { setAdding(true); setSelected(null); }} disabled={busy}
        className="w-full rounded-xl border-2 border-dashed border-teal-600 bg-white p-4 font-semibold text-teal-800 hover:bg-teal-50 disabled:opacity-60">
        Add a job
      </button>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <ul className="space-y-2">{jobs.map(j => <li key={j.id}>
        <button onClick={() => open(j.id)} disabled={busy}
          className={`w-full rounded-lg border p-3 text-left ${selected?.job.id === j.id ? "border-teal-600 bg-teal-50" : "border-slate-200 bg-white hover:border-slate-300"}`}>
          <span className="flex items-start justify-between gap-2">
            <span className="min-w-0 truncate font-medium">{jobLabel(j)}</span>
            <ScoreBadge score={j.match_score} eligible={j.eligible} />
          </span>
          <span className="text-xs text-slate-500">{new Date(j.created_at).toLocaleDateString()}</span>
        </button>
      </li>)}</ul>
      {loaded && jobs.length === 0 && <p className="text-sm text-slate-500">No jobs yet.</p>}
    </aside>

    <div className="min-w-0">
      {adding && <form className="space-y-4 rounded-xl border border-slate-200 bg-white p-6" onSubmit={e => { e.preventDefault(); submit(); }}>
        <h2 className="text-2xl font-semibold">Add a job</h2>
        <label className="block text-sm font-medium">Job description
          <textarea className={`${field} min-h-64`} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })}
            placeholder="Paste the full posting, including requirements and any salary or location details." />
        </label>
        <label className="block text-sm font-medium">Job URL (optional)
          <input className={field} type="url" value={draft.source_url} onChange={e => setDraft({ ...draft, source_url: e.target.value })} placeholder="https://" />
        </label>
        <p className="-mt-2 text-xs text-slate-500">Saved for your reference and to spot duplicates. JobPilot doesn&apos;t visit the page.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium">Job title (optional)
            <input className={field} value={draft.title} maxLength={200} onChange={e => setDraft({ ...draft, title: e.target.value })} />
          </label>
          <label className="block text-sm font-medium">Company (optional)
            <input className={field} value={draft.company} maxLength={200} onChange={e => setDraft({ ...draft, company: e.target.value })} />
          </label>
        </div>
        <div className="flex gap-2">
          <button disabled={busy} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">{busy ? "Analysing…" : "Save and analyse"}</button>
          <button type="button" onClick={() => setAdding(false)} className="px-4 py-2 text-slate-600">Cancel</button>
        </div>
      </form>}

      {!adding && selected && (() => {
        const { job, match } = selected;
        return <div className="space-y-6">
          {notice && <p role="status" className="rounded-lg bg-teal-50 p-3 text-sm text-teal-900">{notice}</p>}
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-2xl font-semibold">{jobLabel(job)}</h2>
              {job.source_url && <a href={job.source_url} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-sm text-teal-700 underline">{job.source_url}</a>}
            </div>
            <span className="flex flex-wrap gap-2">
              {confirmingDelete
                ? <><button onClick={() => remove(job.id)} disabled={busy} className="rounded-lg bg-red-700 px-3 py-1.5 text-sm font-medium text-white">Confirm delete</button>
                    <button onClick={() => setConfirmingDelete(false)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Cancel</button></>
                : <button onClick={() => setConfirmingDelete(true)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:text-red-700">Delete</button>}
            </span>
          </div>

          <section className="rounded-xl border border-slate-200 bg-white p-6">
            <h3 className="text-lg font-semibold">Match</h3>
            <div className="mt-4"><MatchView match={match} /></div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">Requirements</h3>
              {!editing && <span className="flex flex-wrap gap-2">
                <button onClick={() => setEditing(true)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Correct</button>
                <button onClick={() => reextract(job.id)} disabled={busy} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Extract again</button>
              </span>}
            </div>
            {job.extraction_method && <p className="mt-1 text-sm text-slate-600">{EXTRACTION_LABELS[job.extraction_method]}. {job.extraction_method !== "manual" && job.extraction_note}</p>}
            <div className="mt-4">{editing
              ? <RequirementsForm initial={job.requirements ?? emptyRequirements()} busy={busy} onSave={r => save(job.id, r)} onCancel={() => setEditing(false)} />
              : <RequirementsView requirements={job.requirements ?? emptyRequirements()} />}</div>
          </section>

          <details className="rounded-xl border border-slate-200 bg-white p-6">
            <summary className="cursor-pointer font-semibold">Original description</summary>
            <p className="mt-4 whitespace-pre-wrap text-slate-700">{job.description}</p>
          </details>
        </div>;
      })()}

      {!adding && !selected && <p className="rounded-xl border border-slate-200 bg-white p-8 text-slate-600">
        Add a job to see its requirements and how well it matches your verified experience, or pick one from the list.
      </p>}
    </div>
  </div>;
}
