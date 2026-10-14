"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ResumeSections } from "@/components/resume-sections";
import { ACCEPTED_EXTENSIONS, deleteResume, formatBytes, getResume, describeImport, importResume, type ImportResult, listResumes, type ResumeDetail, type ResumeSummary, uploadResume, validateResumeFile } from "@/lib/resumes";

export function ResumeManager() {
  const [resumes, setResumes] = useState<ResumeSummary[]>([]);
  const [selected, setSelected] = useState<ResumeDetail | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imported, setImported] = useState<ImportResult | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null); setImported(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const refresh = async () => setResumes(await listResumes());
  useEffect(() => { void run(refresh); }, []);

  function onFileChosen(input: HTMLInputElement) {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const problem = validateResumeFile(file);
    if (problem) { setError(problem); return; }
    void run(async () => { setSelected(await uploadResume(file)); setConfirmingDelete(false); await refresh(); });
  }
  const open = (id: string) => run(async () => { setSelected(await getResume(id)); setConfirmingDelete(false); });
  const importDrafts = (id: string) => run(async () => setImported(await importResume(id)));
  const remove = (id: string) => run(async () => { await deleteResume(id); setSelected(null); setConfirmingDelete(false); await refresh(); });

  return <div className="mt-10 grid gap-8 md:grid-cols-[18rem_1fr]">
    <aside className="space-y-4">
      <label className={`block cursor-pointer rounded-xl border-2 border-dashed border-teal-600 bg-white p-5 text-center ${busy ? "opacity-60" : "hover:bg-teal-50"}`}>
        <span className="font-semibold text-teal-800">{busy ? "Working…" : "Upload a resume"}</span>
        <span className="mt-1 block text-sm text-slate-500">PDF, DOCX, or TXT up to 5 MB</span>
        <input type="file" className="sr-only" accept={ACCEPTED_EXTENSIONS.join(",")} disabled={busy} onChange={e => onFileChosen(e.currentTarget)} />
      </label>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <ul className="space-y-2">{resumes.map(r => <li key={r.id}>
        <button onClick={() => open(r.id)} disabled={busy} className={`w-full rounded-lg border p-3 text-left ${selected?.id === r.id ? "border-teal-600 bg-teal-50" : "border-slate-200 bg-white hover:border-slate-300"}`}>
          <span className="block truncate font-medium">{r.filename}</span>
          <span className="text-xs text-slate-500">{r.file_type.toUpperCase()} · {formatBytes(r.size_bytes)} · {new Date(r.created_at).toLocaleDateString()}</span>
        </button>
      </li>)}</ul>
      {!busy && resumes.length === 0 && !error && <p className="text-sm text-slate-500">No resumes yet.</p>}
    </aside>
    <div>{selected ? <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="truncate text-2xl font-semibold">{selected.filename}</h2>
        <span className="flex flex-wrap items-center gap-2">
        <button onClick={() => importDrafts(selected.id)} disabled={busy} className="rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">Import into library</button>
        {confirmingDelete
          ? <span className="flex items-center gap-2 text-sm">Delete this resume?
              <button onClick={() => remove(selected.id)} disabled={busy} className="rounded-lg bg-red-700 px-3 py-1.5 font-medium text-white">Delete</button>
              <button onClick={() => setConfirmingDelete(false)} className="rounded-lg border border-slate-300 px-3 py-1.5">Cancel</button></span>
          : <button onClick={() => setConfirmingDelete(true)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:border-red-400 hover:text-red-700">Delete</button>}
        </span>
      </div>
      {imported && <p role="status" className="mb-4 rounded-lg bg-teal-50 p-3 text-sm text-teal-900">{describeImport(imported)} <Link href="/library" className="font-semibold underline">Review them in your library →</Link></p>}
      <ResumeSections resume={selected} />
    </> : <p className="rounded-xl border border-slate-200 bg-white p-8 text-slate-600">Upload or select a resume to see what we extracted.</p>}</div>
  </div>;
}
