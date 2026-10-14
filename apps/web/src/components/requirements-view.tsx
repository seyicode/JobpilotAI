import { arrangementLabel, employmentLabel, formatSalary, type JobRequirements, seniorityLabel } from "@/lib/jobs";

const Unknown = () => <span className="text-slate-400">Unknown</span>;

function Skills({ skills }: { skills: string[] }) {
  if (skills.length === 0) return <Unknown />;
  return <ul className="flex flex-wrap gap-1.5">{skills.map(s => <li key={s} className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-sm">{s}</li>)}</ul>;
}

export function RequirementsView({ requirements: r }: { requirements: JobRequirements }) {
  const rows: [string, React.ReactNode][] = [
    ["Required skills", <Skills key="r" skills={r.required_skills} />],
    ["Preferred skills", <Skills key="p" skills={r.preferred_skills} />],
    ["Seniority", seniorityLabel(r.seniority) ?? <Unknown />],
    ["Work arrangement", arrangementLabel(r.work_arrangement) ?? <Unknown />],
    ["Location", r.location ?? <Unknown />],
    ["Employment type", employmentLabel(r.employment_type) ?? <Unknown />],
    ["Salary", formatSalary(r.salary) ?? <Unknown />],
    ["Minimum experience", r.years_experience_min !== null ? `${r.years_experience_min}+ years` : <Unknown />],
    ["Qualifications", r.qualifications.length ? <ul className="list-disc pl-5">{r.qualifications.map(q => <li key={q}>{q}</li>)}</ul> : <Unknown />],
  ];
  return <dl className="divide-y divide-slate-100">{rows.map(([term, value]) => <div key={term} className="grid gap-1 py-2 sm:grid-cols-[11rem_1fr]">
    <dt className="text-sm font-medium text-slate-600">{term}</dt><dd className="text-slate-800">{value}</dd>
  </div>)}</dl>;
}
