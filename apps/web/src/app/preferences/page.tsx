import type { Metadata } from "next";
import Link from "next/link";
import { PreferencesForm } from "@/components/preferences-form";
export const metadata: Metadata = { title: "Job preferences · JobPilot AI" };
export default function PreferencesPage() {
  return <main className="mx-auto max-w-3xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Job preferences</h1>
    <p className="mt-4 text-lg text-slate-600">Tell JobPilot what you&apos;re looking for. Tick <strong>Must match</strong> to filter out jobs that clearly conflict; everything else only affects how matches are ranked. Jobs missing a detail are never filtered out for it.</p>
    <PreferencesForm />
  </main>;
}
