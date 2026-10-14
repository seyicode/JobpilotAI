"use client";
import { useEffect, useState } from "react";
import { SourceCard } from "@/components/source-card";
import {
  addSource, boardFromInput, deleteSource, describeRun, type DiscoveryStatus, getDiscoveryStatus, INTERVALS, listProviders,
  listRuns, listSources, type Provider, type ProviderInfo, runSource, type Source, type SourceRun, updateSource,
} from "@/lib/sources";

export function SourcesManager() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [runs, setRuns] = useState<Record<string, SourceRun[]>>({});
  const [status, setStatus] = useState<DiscoveryStatus | null>(null);
  const [form, setForm] = useState({ provider: "greenhouse" as Provider, board: "", company_name: "", interval_minutes: 360 });
  const [confirming, setConfirming] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null); setNotice(null);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Something went wrong."); }
    finally { setBusy(false); }
  }
  const refresh = async () => {
    const [list, state] = await Promise.all([listSources(), getDiscoveryStatus()]);
    setSources(list); setStatus(state);
  };
  useEffect(() => { void run(async () => { setProviders(await listProviders()); await refresh(); }); }, []);

  const add = () => run(async () => {
    const source = await addSource({ ...form, board: boardFromInput(form.board) });
    setForm({ ...form, board: "", company_name: "" });
    setNotice(`Following ${source.company_name}. Choose "Check now" to look for jobs.`);
    await refresh();
  });
  const check = (s: Source) => run(async () => {
    const result = await runSource(s.id);
    setNotice(`${s.company_name}: ${describeRun(result)}`);
    setRuns({ ...runs, [s.id]: await listRuns(s.id) });
    await refresh();
  });
  const patch = (s: Source, body: Parameters<typeof updateSource>[1]) => run(async () => { await updateSource(s.id, body); await refresh(); });
  const remove = (s: Source) => {
    if (confirming !== s.id) { setConfirming(s.id); return; }
    void run(async () => { await deleteSource(s.id); setConfirming(null); await refresh(); });
  };
  const showRuns = (s: Source) => run(async () => setRuns({ ...runs, [s.id]: await listRuns(s.id) }));

  const hint = providers.find(p => p.provider === form.provider);
  const field = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  return <div className="mt-8 space-y-6">
    {status && <div className={`rounded-xl p-4 text-sm ${status.scheduled ? "bg-teal-50 text-teal-900" : "bg-slate-100 text-slate-700"}`}>
      {status.scheduled
        ? <>Automatic checks are on. Next check {status.next_check_at ? new Date(status.next_check_at).toLocaleString() : "when a board is due"}.</>
        : <>Automatic checks are off, so boards are only checked when you choose &quot;Check now&quot;. To turn them on, set <code>DISCOVERY_ENABLED=true</code> in <code>.env</code> and restart the worker.</>}
      {" "}{status.requests_last_hour} of {status.hourly_request_limit} feed requests used in the last hour.
      {status.uses_ai ? " Discovered jobs use AI extraction." : " Discovered jobs use free local extraction."}
    </div>}

    <form className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); void add(); }}>
      <h2 className="text-xl font-semibold sm:col-span-2">Follow a company</h2>
      <label className="block text-sm font-medium">Job board provider
        <select className={field} value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value as Provider })}>
          {providers.map(p => <option key={p.provider} value={p.provider}>{p.label}</option>)}
        </select>
      </label>
      <label className="block text-sm font-medium">Board name or link
        <input className={field} value={form.board} required maxLength={300} onChange={e => setForm({ ...form, board: e.target.value })} placeholder="examplecorp" />
        {hint && <span className="mt-1 block text-xs font-normal text-slate-500">{hint.board_hint}</span>}
      </label>
      <label className="block text-sm font-medium">Company name
        <input className={field} value={form.company_name} required maxLength={200} onChange={e => setForm({ ...form, company_name: e.target.value })} />
      </label>
      <label className="block text-sm font-medium">Check
        <select className={field} value={form.interval_minutes} onChange={e => setForm({ ...form, interval_minutes: Number(e.target.value) })}>
          {INTERVALS.map(i => <option key={i.minutes} value={i.minutes}>{i.label}</option>)}
        </select>
      </label>
      <p className="text-xs text-slate-500 sm:col-span-2">JobPilot reads only the provider&apos;s public job-board feed for this company, at most as often as you choose. It never visits job pages, never sends anything about you, and never applies for you.</p>
      <div><button disabled={busy} className="rounded-lg bg-teal-700 px-4 py-2 font-medium text-white disabled:opacity-50">Follow</button></div>
    </form>

    {notice && <p role="status" className="rounded-lg bg-teal-50 p-3 text-sm text-teal-900">{notice}</p>}
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <ul className="space-y-3">{sources.map(s => <SourceCard key={s.id} source={s} runs={runs[s.id] ?? null} busy={busy}
      confirmingDelete={confirming === s.id} onRun={() => check(s)} onToggle={() => patch(s, { enabled: !s.enabled })}
      onInterval={minutes => patch(s, { interval_minutes: minutes })} onDelete={() => remove(s)}
      onCancelDelete={() => setConfirming(null)} onShowRuns={() => showRuns(s)} />)}</ul>
    {!busy && sources.length === 0 && <p className="text-slate-600">You don&apos;t follow any companies yet.</p>}
  </div>;
}
