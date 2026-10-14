"use client";
import { useEffect, useState } from "react";
import { TrackerRowCard } from "@/components/tracker-row";
import {
  type ApplicationStatus, defaultFilters, exportCsvUrl, getSummary, listApplications, type TrackerFilters, type TrackerRow,
  type TrackerSummary, updateApplication, VIEWS, type View,
} from "@/lib/tracker";

function viewCount(view: View, summary: TrackerSummary | null): number | null {
  if (!summary) return null;
  const s = summary.by_status;
  return {
    new: summary.new,
    saved: s.shortlisted + s.ready_to_apply,
    in_progress: s.applied + s.interviewing + s.offered,
    all: Object.entries(s).filter(([k]) => k !== "archived").reduce((n, [, v]) => n + v, 0),
    archived: s.archived,
  }[view];
}

export function TrackerDashboard() {
  const [filters, setFilters] = useState<TrackerFilters>(defaultFilters);
  const [draft, setDraft] = useState<TrackerFilters>(defaultFilters);
  const [rows, setRows] = useState<TrackerRow[]>([]);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [summary, setSummary] = useState<TrackerSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const load = (f: TrackerFilters) => run(async () => {
    const [page, counts] = await Promise.all([listApplications(f), getSummary()]);
    setRows(page.items); setTotal(page.total); setCursor(page.next_cursor); setSummary(counts);
  });
  useEffect(() => { void load(filters); }, [filters]);

  const apply = (changes: Partial<TrackerFilters>) => { const next = { ...draft, ...changes }; setDraft(next); setFilters(next); };
  const more = () => run(async () => { const page = await listApplications(filters, cursor); setRows([...rows, ...page.items]); setCursor(page.next_cursor); });
  const setStatus = (id: string, status: ApplicationStatus) => run(async () => {
    await updateApplication(id, { status });
    setRows(rows.map(r => r.id === id ? { ...r, application_status: status, is_new: false } : r));
    setSummary(await getSummary());
  });
  const markSeen = (row: TrackerRow) => { if (row.is_new) void updateApplication(row.id, { seen: true }).catch(() => undefined); };

  const field = "mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm";
  return <div className="mt-8 space-y-6">
    <nav aria-label="Views" className="flex flex-wrap gap-2">{VIEWS.map(v => {
      const count = viewCount(v.value, summary);
      return <button key={v.value} onClick={() => apply({ view: v.value })}
        className={`rounded-full border px-3 py-1.5 text-sm ${filters.view === v.value ? "border-teal-600 bg-teal-50 font-semibold" : "border-slate-300 bg-white"}`}>
        {v.label}{count !== null && <span className="ml-1 text-slate-500">{count}</span>}
      </button>;
    })}</nav>

    <form className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      onSubmit={e => { e.preventDefault(); setFilters(draft); }}>
      <label className="text-sm">Search title or company<input className={field} value={draft.q} onChange={e => setDraft({ ...draft, q: e.target.value })} /></label>
      <label className="text-sm">Company<input className={field} value={draft.company} onChange={e => setDraft({ ...draft, company: e.target.value })} /></label>
      <label className="text-sm">Minimum score
        <select className={field} value={draft.min_score} onChange={e => apply({ min_score: e.target.value })}>
          <option value="">Any</option>{[40, 50, 60, 70, 80, 90].map(n => <option key={n} value={n}>{n}%+</option>)}
        </select>
      </label>
      <label className="text-sm">Sort by
        <select className={field} value={`${draft.sort}:${draft.order}`} onChange={e => { const [sort, order] = e.target.value.split(":"); apply({ sort: sort as TrackerFilters["sort"], order: order as "asc" | "desc" }); }}>
          <option value="score:desc">Best match</option><option value="found:desc">Newest</option>
          <option value="salary:desc">Highest salary</option><option value="company:asc">Company A–Z</option>
          <option value="status_changed:desc">Recently updated</option>
        </select>
      </label>
      <label className="text-sm">Found from<input type="date" className={field} value={draft.found_from} onChange={e => setDraft({ ...draft, found_from: e.target.value })} /></label>
      <label className="text-sm">Found to<input type="date" className={field} value={draft.found_to} onChange={e => setDraft({ ...draft, found_to: e.target.value })} /></label>
      <div className="grid grid-cols-[1fr_5rem] gap-2">
        <label className="text-sm">Minimum yearly salary<input inputMode="numeric" className={field} value={draft.min_salary} onChange={e => setDraft({ ...draft, min_salary: e.target.value })} /></label>
        <label className="text-sm">Currency<input maxLength={3} className={`${field} uppercase`} value={draft.salary_currency} onChange={e => setDraft({ ...draft, salary_currency: e.target.value })} /></label>
      </div>
      <div className="flex flex-col justify-end gap-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.include_unknown_salary} onChange={e => setDraft({ ...draft, include_unknown_salary: e.target.checked })} /> Include jobs with no comparable salary</label>
        <span className="flex gap-2">
          <button disabled={busy} className="rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">Apply filters</button>
          <button type="button" onClick={() => { const reset = { ...defaultFilters(), view: filters.view }; setDraft(reset); setFilters(reset); }} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Reset</button>
        </span>
      </div>
    </form>

    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-slate-600" role="status">{busy && rows.length === 0 ? "Loading…" : `${total} job${total === 1 ? "" : "s"}`}</p>
      <a href={exportCsvUrl(filters)} download className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm">Export CSV</a>
    </div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <ul className="space-y-3">{rows.map(row => <TrackerRowCard key={row.id} row={row} busy={busy}
      onStatus={status => setStatus(row.id, status)} onOpen={() => markSeen(row)} />)}</ul>
    {!busy && rows.length === 0 && !error && <p className="rounded-xl border border-slate-200 bg-white p-8 text-slate-600">
      No jobs here yet. Follow companies on the sources page to discover jobs, or paste one on the jobs page.
    </p>}
    {cursor && <button onClick={more} disabled={busy} className="w-full rounded-lg border border-slate-300 bg-white py-2 text-sm">Show more</button>}
    <p className="text-xs text-slate-500">Scores are estimates, not guarantees. JobPilot never applies for you; update a job&apos;s status after you act on it.</p>
  </div>;
}
