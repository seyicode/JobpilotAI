import type { Metadata } from "next";
import Link from "next/link";
import { ResumeManager } from "@/components/resume-manager";
export const metadata: Metadata = { title: "Resumes · JobPilot AI" };
export default function ResumesPage() {
  return <main className="mx-auto max-w-5xl px-6 py-16">
    <Link href="/" className="text-sm font-semibold tracking-widest text-teal-700">← JOBPILOT AI</Link>
    <h1 className="mt-4 text-4xl font-bold tracking-tight">Your resumes</h1>
    <p className="mt-4 max-w-2xl text-lg text-slate-600">Upload a resume and we&apos;ll split it into sections. Text is extracted on our server without AI, and the original file isn&apos;t kept.</p>
    <ResumeManager />
  </main>;
}
