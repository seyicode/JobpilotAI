import type { Metadata } from "next";
import Link from "next/link";
import { SourcesManager } from "@/components/sources-manager";
export const metadata: Metadata = { title: "Job sources · JobPilot AI" };
export default function SourcesPage() {
  return <main className="mx-auto max-w-4xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Job sources</h1>
    <p className="mt-4 text-lg text-slate-600">Follow companies that publish jobs on Greenhouse, Lever or Ashby. New postings that fit your <Link href="/preferences" className="text-teal-700 underline">preferences</Link> appear in your <Link href="/tracker" className="text-teal-700 underline">tracker</Link>.</p>
    <SourcesManager />
  </main>;
}
