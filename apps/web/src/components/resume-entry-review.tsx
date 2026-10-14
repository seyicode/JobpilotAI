"use client";
import { type Experience, formatDateRange } from "@/lib/library";
import { moveItem, type ResumeBullet, type ResumeEntry, unusedHighlights } from "@/lib/tailored";

const CHANGED_LABEL = { none: null, ai: "Reworded by AI", user: "Edited by you" } as const;

type Props = {
  entry: ResumeEntry;
  source: Experience | undefined;
  editable: boolean;
  onChange: (entry: ResumeEntry | null) => void;
};

/** One resume entry: the verified library source on the left, the tailored version on the right. */
export function ResumeEntryReview({ entry, source, editable, onChange }: Props) {
  const facts = [entry.organization, entry.location, formatDateRange(entry)].filter(Boolean).join(" · ");
  const setBullets = (bullets: ResumeBullet[]) => onChange({ ...entry, bullets });
  const setText = (i: number, text: string) => setBullets(entry.bullets.map((b, j) => j === i ? { ...b, text } : b));
  const unused = unusedHighlights(entry, source);
  const small = "rounded border border-slate-300 px-2 py-0.5 text-xs disabled:opacity-40";

  return <article className="grid gap-4 rounded-xl border border-slate-200 bg-white p-5 lg:grid-cols-2">
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">From your verified library</p>
      <h4 className="mt-1 font-semibold">{entry.title}</h4>
      {facts && <p className="text-sm text-slate-600">{facts}</p>}
      {entry.reason && <p className="mt-2 text-xs text-teal-800">Why it&apos;s here: {entry.reason}</p>}
      <ul className="mt-3 space-y-2">{(source?.highlights ?? entry.bullets.map(b => b.source_text)).map((h, i) => {
        const used = entry.bullets.find(b => b.source_text === h);
        return <li key={i} className="text-sm">
          <span className={used ? "text-slate-800" : "text-slate-400 line-through"} title={used ? undefined : "Not used on this resume"}>{h}</span>
          {used?.reason && <span className="block text-xs text-slate-500">{used.reason}</span>}
        </li>;
      })}</ul>
      {!source && <p className="mt-2 text-sm text-red-700">This entry is no longer verified in your library.</p>}
    </div>

    <div className="min-w-0 border-t border-slate-100 pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">On your tailored resume</p>
        {editable && <button type="button" onClick={() => onChange(null)} className="text-xs text-slate-500 hover:text-red-700">Remove entry</button>}
      </div>
      <h4 className="mt-1 font-semibold">{entry.title}</h4>
      {facts && <p className="text-sm text-slate-600">{facts}</p>}
      <p className="text-xs text-slate-500">Title, organisation and dates always match your library.</p>
      <ul className="mt-3 space-y-3">{entry.bullets.map((b, i) => <li key={b.source_text}>
        {editable
          ? <textarea aria-label={`Bullet ${i + 1}`} value={b.text} maxLength={500} onChange={e => setText(i, e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" rows={2} />
          : <p className="text-sm">• {b.text}</p>}
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {CHANGED_LABEL[b.changed_by] && b.text !== b.source_text && <span className="rounded bg-violet-100 px-1.5 text-xs font-medium text-violet-800">{CHANGED_LABEL[b.changed_by]}</span>}
          {editable && <>
            <button type="button" className={small} disabled={i === 0} onClick={() => setBullets(moveItem(entry.bullets, i, -1))} aria-label="Move up">↑</button>
            <button type="button" className={small} disabled={i === entry.bullets.length - 1} onClick={() => setBullets(moveItem(entry.bullets, i, 1))} aria-label="Move down">↓</button>
            {b.text !== b.source_text && <button type="button" className={small} onClick={() => setText(i, b.source_text)}>Use original</button>}
            <button type="button" className={small} onClick={() => setBullets(entry.bullets.filter((_, j) => j !== i))}>Remove</button>
          </>}
        </div>
      </li>)}</ul>
      {editable && unused.length > 0 && <label className="mt-3 block text-sm">Add a bullet from this entry
        <select className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5" value=""
          onChange={e => e.target.value && setBullets([...entry.bullets, { text: e.target.value, source_text: e.target.value, changed_by: "none", reason: "Added by you." }])}>
          <option value="">Choose…</option>{unused.map(h => <option key={h} value={h}>{h}</option>)}
        </select>
      </label>}
    </div>
  </article>;
}
