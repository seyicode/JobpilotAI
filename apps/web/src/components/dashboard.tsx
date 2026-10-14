import Link from "next/link";
const steps: { title: string; detail: string; href?: string }[] = [
  { title: "Your experience", detail: "Upload a resume, then review and verify your skills and accomplishments in your library.", href: "/library" },
  { title: "Your preferences", detail: "Set the roles, locations, and salary you want, and choose which ones must match.", href: "/preferences" },
  { title: "Your opportunities", detail: "Paste job descriptions to see their requirements and an explainable match score.", href: "/jobs" },
  { title: "Job tracker", detail: "See newly discovered jobs, saved opportunities and the status of every application.", href: "/tracker" },
  { title: "Job sources", detail: "Follow companies on Greenhouse, Lever or Ashby to discover new jobs automatically.", href: "/sources" },
  { title: "Your applications", detail: "Open a job and choose Tailor resume to review, approve and download a resume. You apply manually.", href: "/jobs" },
];
export function Dashboard() {
  return <main className="mx-auto max-w-5xl px-6 py-16">
    <p className="text-sm font-semibold tracking-widest text-teal-700">JOBPILOT AI</p>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Your next chapter starts here.</h1>
    <p className="mt-4 max-w-2xl text-lg text-slate-600">Discover opportunities, understand your fit, and prepare an application you can stand behind. You stay in control and apply manually.</p>
    <section aria-labelledby="dashboard-heading" className="mt-12">
      <h2 id="dashboard-heading" className="text-2xl font-semibold">Your dashboard</h2>
      <p className="mt-2 text-slate-600">Start with your experience. More features are coming next.</p>
      <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{steps.map(step => <article key={step.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <span className={`text-xs font-semibold uppercase tracking-wide ${step.href ? "text-teal-700" : "text-slate-500"}`}>{step.href ? "Available" : "Coming soon"}</span>
        <h3 className="mt-3 text-lg font-semibold">{step.href ? <Link href={step.href} className="hover:text-teal-700">{step.title} →</Link> : step.title}</h3><p className="mt-2 text-slate-600">{step.detail}</p>
      </article>)}</div>
    </section>
  </main>;
}
