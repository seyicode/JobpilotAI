import type { Metadata } from "next";
import Link from "next/link";
import { ResumeReview } from "@/components/resume-review";
export const metadata: Metadata = { title: "Tailored resume · JobPilot AI" };
export default async function ResumePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <main className="mx-auto max-w-6xl px-6 py-16">
    <Link href="/jobs" className="text-sm font-semibold tracking-widest text-teal-700">← JOBS</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Tailored resume</h1>
    <p className="mt-4 max-w-3xl text-lg text-slate-600">Compare each line with the verified entry it came from, edit the wording, then approve to download. Titles, employers and dates always come from your library, and only verified skills can be listed.</p>
    <ResumeReview jobId={id} />
  </main>;
}
