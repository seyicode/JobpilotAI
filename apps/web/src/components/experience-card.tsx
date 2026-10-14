import { type Experience, formatDateRange } from "@/lib/library";

export function StatusBadge({ verified }: { verified: boolean }) {
  return verified
    ? <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs font-semibold text-teal-800">Verified</span>
    : <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Draft</span>;
}

type Actions = { onVerify: () => void; onEdit: () => void; onDelete: () => void; confirmingDelete: boolean; onCancelDelete: () => void; busy: boolean };

export function ExperienceCard({ experience: e, actions }: { experience: Experience; actions: Actions }) {
  const meta = [e.organization, e.location, formatDateRange(e)].filter(Boolean).join(" · ");
  const button = "rounded-lg border border-slate-300 px-3 py-1 text-sm hover:border-slate-400 disabled:opacity-50";
  return <article className={`rounded-xl border bg-white p-5 ${e.verified ? "border-slate-200" : "border-amber-300"}`}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <div className="flex items-center gap-2"><h4 className="text-lg font-semibold">{e.title}</h4><StatusBadge verified={e.verified} /></div>
        {meta && <p className="text-sm text-slate-600">{meta}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {!e.verified && <button onClick={actions.onVerify} disabled={actions.busy} className="rounded-lg bg-teal-700 px-3 py-1 text-sm font-medium text-white disabled:opacity-50">Verify</button>}
        <button onClick={actions.onEdit} disabled={actions.busy} className={button}>Edit</button>
        {actions.confirmingDelete
          ? <><button onClick={actions.onDelete} disabled={actions.busy} className="rounded-lg bg-red-700 px-3 py-1 text-sm font-medium text-white">Confirm delete</button>
              <button onClick={actions.onCancelDelete} className={button}>Cancel</button></>
          : <button onClick={actions.onDelete} disabled={actions.busy} className={`${button} hover:text-red-700`}>Delete</button>}
      </div>
    </div>
    {e.highlights.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-slate-700">{e.highlights.map((h, i) => <li key={i}>{h}</li>)}</ul>}
  </article>;
}
