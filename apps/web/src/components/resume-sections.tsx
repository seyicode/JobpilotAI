import type { ResumeDetail } from "@/lib/resumes";

export function ResumeSections({ resume }: { resume: ResumeDetail }) {
  return <div className="space-y-4">
    <p className="text-sm text-slate-600">We found {resume.sections.length} section{resume.sections.length === 1 ? "" : "s"}. Check that nothing is missing before you rely on it.</p>
    {resume.sections.map((section, index) => <section key={`${section.key}-${index}`} className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-teal-700">{section.heading}</h3>
      <p className="mt-2 whitespace-pre-line text-slate-700">{section.content}</p>
    </section>)}
  </div>;
}
