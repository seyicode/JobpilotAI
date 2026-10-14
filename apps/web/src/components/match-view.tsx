import type { FilterResult, MatchResult } from "@/lib/jobs";

const STATUS_STYLE = {
  pass: "bg-teal-100 text-teal-800", fail: "bg-red-100 text-red-800", unknown: "bg-slate-100 text-slate-600",
} as const;
const STATUS_LABEL = { pass: "Pass", fail: "Fail", unknown: "Unknown" } as const;

function Checks({ title, checks }: { title: string; checks: FilterResult[] }) {
  if (checks.length === 0) return null;
  return <div>
    <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h4>
    <ul className="mt-2 space-y-1">{checks.map(c => <li key={c.filter} className="flex items-start gap-2 text-sm">
      <span className={`mt-0.5 shrink-0 rounded px-1.5 text-xs font-semibold ${STATUS_STYLE[c.status]}`}>{STATUS_LABEL[c.status]}</span>
      <span className="text-slate-700">{c.reason}</span>
    </li>)}</ul>
  </div>;
}

export function ScoreBadge({ score, eligible }: { score: number | null; eligible: boolean }) {
  if (!eligible) return <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800">Filtered out</span>;
  if (score === null) return <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">Not scored</span>;
  const tone = score >= 70 ? "bg-teal-100 text-teal-800" : score >= 40 ? "bg-amber-100 text-amber-900" : "bg-slate-200 text-slate-700";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{score}%</span>;
}

export function MatchView({ match }: { match: MatchResult }) {
  return <div className="space-y-6">
    <div className="flex flex-wrap items-baseline gap-3">
      <span className="text-4xl font-bold tabular-nums">{match.eligible && match.score !== null ? `${match.score}%` : "—"}</span>
      <ScoreBadge score={match.score} eligible={match.eligible} />
      <span className="text-sm text-slate-600">Based on {match.coverage}% of the scoring factors</span>
    </div>
    <p className="text-slate-700">{match.summary}</p>

    <Checks title="Must-match filters" checks={match.filters} />

    <div>
      <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Score breakdown</h4>
      <ul className="mt-2 space-y-3">{match.components.map(c => <li key={c.key}>
        <div className="flex flex-wrap justify-between gap-2 text-sm">
          <span className="font-medium">{c.label}</span>
          <span className="tabular-nums text-slate-600">{c.status === "unknown" ? "Unknown, not scored" : `${c.points} / ${c.weight} pts`}</span>
        </div>
        <div className={`mt-1 h-2 overflow-hidden rounded-full ${c.status === "unknown" ? "border border-dashed border-slate-300" : "bg-slate-200"}`}
          role="img" aria-label={c.status === "unknown" ? `${c.label}: unknown` : `${c.label}: ${Math.round((c.value ?? 0) * 100)}%`}>
          {c.status === "scored" && <div className="h-full rounded-full bg-teal-600" style={{ width: `${Math.round((c.value ?? 0) * 100)}%` }} />}
        </div>
        <p className="mt-1 text-xs text-slate-500">{c.detail}</p>
      </li>)}</ul>
    </div>

    <Checks title="Other preferences (ranking only)" checks={match.preference_checks} />

    <div className="grid gap-6 md:grid-cols-2">
      <div>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Evidence from your verified library</h4>
        {match.evidence.length === 0 ? <p className="mt-2 text-sm text-slate-600">No verified evidence yet.</p>
          : <ul className="mt-2 space-y-2">{match.evidence.map((e, i) => <li key={i} className="text-sm">
              <span className="font-medium">{e.requirement}</span>
              <span className="text-slate-600">: {e.source_label}</span>
              {e.quote && <blockquote className="mt-1 border-l-2 border-teal-600 pl-2 text-slate-600">{e.quote}</blockquote>}
            </li>)}</ul>}
      </div>
      <div>
        <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Gaps</h4>
        {match.gaps.length === 0 ? <p className="mt-2 text-sm text-slate-600">No gaps found.</p>
          : <ul className="mt-2 space-y-2">{match.gaps.map((g, i) => <li key={i} className="text-sm">
              <span className="font-medium">{g.requirement}</span>
              <span className="text-slate-500"> ({g.kind.replace("_", " ")})</span>
              {g.hint && <p className="text-amber-800">{g.hint}</p>}
            </li>)}</ul>}
      </div>
    </div>
    <p className="text-xs text-slate-500">Scores are estimates, not guarantees. Only verified library entries count as evidence.</p>
  </div>;
}
