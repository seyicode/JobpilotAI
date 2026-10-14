import type { Metadata } from "next";
import Link from "next/link";
import { LibraryManager } from "@/components/library-manager";
import { ProfileForm } from "@/components/profile-form";
export const metadata: Metadata = { title: "Experience library · JobPilot AI" };
export default function LibraryPage() {
  return <main className="mx-auto max-w-5xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Your experience library</h1>
    <p className="mt-4 max-w-2xl text-lg text-slate-600">Everything JobPilot knows about your background. Only verified entries will be used to tailor resumes, so nothing is claimed that you haven&apos;t confirmed. <Link href="/resumes" className="font-semibold text-teal-700 underline">Import from a resume</Link></p>
    <div className="mt-8"><ProfileForm /></div>
    <LibraryManager />
  </main>;
}
