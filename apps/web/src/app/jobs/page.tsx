import type { Metadata } from "next";
import Link from "next/link";
import { JobsManager } from "@/components/jobs-manager";
export const metadata: Metadata = { title: "Jobs · JobPilot AI" };
export default function JobsPage() {
  return <main className="mx-auto max-w-6xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Jobs</h1>
    <p className="mt-4 max-w-3xl text-lg text-slate-600">Paste a job description to see what it asks for and how it matches your <Link href="/library" className="text-teal-700 underline">verified experience</Link> and <Link href="/preferences" className="text-teal-700 underline">preferences</Link>. Scores are estimates. JobPilot never applies for you.</p>
    <JobsManager />
  </main>;
}
