import { describeRun, INTERVALS, type Source, type SourceHealth, type SourceRun } from "@/lib/sources";

const HEALTH: Record<SourceHealth, { label: string; style: string }> = {
  new: { label: "Not checked yet", style: "bg-slate-100 text-slate-700" },
  healthy: { label: "Healthy", style: "bg-teal-100 text-teal-800" },
  degraded: { label: "Having problems", style: "bg-amber-100 text-amber-900" },
  failing: { label: "Failing", style: "bg-red-100 text-red-800" },
};

type Props = {
  source: Source; runs: SourceRun[] | null; busy: boolean; confirmingDelete: boolean;
  onRun: () => void; onToggle: () => void; onInterval: (minutes: number) => void;
  onDelete: () => void; onCancelDelete: () => void; onShowRuns: () => void;
};

const when = (value: string | null) => value ? new Date(value).toLocaleString() : "—";

export function SourceCard({ source: s, runs, busy, confirmingDelete, onRun, onToggle, onInterval, onDelete, onCancelDelete, onShowRuns }: Props) {
  const health = HEALTH[s.status];
  const button = "rounded-lg border border-slate-300 px-3 py-1 text-sm disabled:opacity-50";
  return <li className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">{s.company_name}</h3>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${health.style}`}>{health.label}</span>
          {!s.enabled && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700">Paused</span>}
        </div>
        <p className="text-sm text-slate-600">{s.provider[0].toUpperCase() + s.provider.slice(1)} · {s.board}</p>
        <p className="mt-1 text-xs text-slate-500">Last checked {when(s.last_run_at)} · Last success {when(s.last_success_at)}{s.enabled && ` · Next ${when(s.next_run_at)}`}</p>
        {s.last_error_message && <p className="mt-1 text-sm text-red-800">{s.last_error_message}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        <button onClick={onRun} disabled={busy} className="rounded-lg bg-teal-700 px-3 py-1 text-sm font-medium text-white disabled:opacity-50">Check now</button>
        <button onClick={onToggle} disabled={busy} className={button}>{s.enabled ? "Pause" : "Resume"}</button>
        <select aria-label={`Check ${s.company_name}`} value={s.interval_minutes} disabled={busy}
          onChange={e => onInterval(Number(e.target.value))} className="rounded-lg border border-slate-300 px-2 py-1 text-sm">
          {INTERVALS.some(i => i.minutes === s.interval_minutes) ? null : <option value={s.interval_minutes}>Every {s.interval_minutes} min</option>}
          {INTERVALS.map(i => <option key={i.minutes} value={i.minutes}>{i.label}</option>)}
        </select>
        {confirmingDelete
          ? <><button onClick={onDelete} disabled={busy} className="rounded-lg bg-red-700 px-3 py-1 text-sm font-medium text-white">Confirm unfollow</button>
              <button onClick={onCancelDelete} className={button}>Cancel</button></>
          : <button onClick={onDelete} disabled={busy} className={button}>Unfollow</button>}
      </div>
    </div>
    <div className="mt-3">
      {runs === null
        ? <button onClick={onShowRuns} className="text-sm text-teal-700 underline">Show recent checks</button>
        : runs.length === 0 ? <p className="text-sm text-slate-500">No checks yet.</p>
        : <ul className="space-y-1 text-sm">{runs.map(r => <li key={r.id} className="flex flex-wrap gap-2">
            <span className="text-slate-500">{when(r.started_at)}</span>
            <span className={r.status === "success" ? "text-teal-800" : r.status === "skipped" ? "text-slate-600" : "text-red-800"}>{r.status}</span>
            <span className="text-slate-700">{describeRun(r)}</span>
            <span className="text-xs text-slate-400">({r.trigger})</span>
          </li>)}</ul>}
    </div>
  </li>;
}
