import Link from "next/link";
import { ScoreBadge } from "@/components/match-view";
import { type ApplicationStatus, rowSalary, STATUSES, type TrackerRow } from "@/lib/tracker";

const RESUME_LABEL = { none: null, draft: "Resume draft", approved: "Resume approved" } as const;

type Props = { row: TrackerRow; busy: boolean; onStatus: (status: ApplicationStatus) => void; onOpen: () => void };

export function TrackerRowCard({ row, busy, onStatus, onOpen }: Props) {
  const facts = [row.location, row.work_arrangement && row.work_arrangement[0].toUpperCase() + row.work_arrangement.slice(1), rowSalary(row)]
    .filter(Boolean).join(" · ");
  return <li className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-[1fr_auto]">
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-2">
        <ScoreBadge score={row.match_score} eligible={row.eligible} />
        {row.is_new && <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-semibold text-sky-800">New</span>}
        {row.closed && <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700">No longer listed</span>}
        {RESUME_LABEL[row.resume_status] && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-800">{RESUME_LABEL[row.resume_status]}</span>}
      </div>
      <h3 className="mt-1 truncate font-semibold">
        <Link href={`/jobs?job=${row.id}`} onClick={onOpen} className="hover:text-teal-700">{row.title ?? "Untitled job"}</Link>
      </h3>
      <p className="truncate text-sm text-slate-600">{[row.company, facts].filter(Boolean).join(" · ")}</p>
      <p className="mt-1 text-xs text-slate-500">
        Found {new Date(row.found_at).toLocaleDateString()}
        {row.source_provider && ` via ${row.source_provider[0].toUpperCase()}${row.source_provider.slice(1)}`}
        {row.match_score !== null && ` · score based on ${row.match_coverage}% of factors`}
      </p>
    </div>
    <div className="flex flex-wrap items-start gap-2 sm:flex-col sm:items-end">
      <label className="text-xs text-slate-500">Status
        <select aria-label={`Status for ${row.title ?? "job"}`} value={row.application_status} disabled={busy}
          onChange={e => onStatus(e.target.value as ApplicationStatus)}
          className="ml-2 rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900">
          {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </label>
      <span className="flex gap-2 text-sm">
        <Link href={`/jobs/${row.id}/resume`} className="text-teal-700 underline">Tailor resume</Link>
        {row.source_url && <a href={row.source_url} target="_blank" rel="noopener noreferrer nofollow" className="text-teal-700 underline">Posting</a>}
      </span>
    </div>
  </li>;
}
