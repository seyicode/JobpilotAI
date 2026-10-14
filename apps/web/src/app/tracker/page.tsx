import type { Metadata } from "next";
import Link from "next/link";
import { TrackerDashboard } from "@/components/tracker-dashboard";
export const metadata: Metadata = { title: "Job tracker · JobPilot AI" };
export default function TrackerPage() {
  return <main className="mx-auto max-w-6xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Job tracker</h1>
    <p className="mt-4 max-w-3xl text-lg text-slate-600">New jobs from the companies you <Link href="/sources" className="text-teal-700 underline">follow</Link>, jobs you&apos;ve saved, and where each application stands. You apply yourself, then update the status here.</p>
    <TrackerDashboard />
  </main>;
}
