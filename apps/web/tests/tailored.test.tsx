import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ResumeEntryReview } from "../src/components/resume-entry-review";
import type { Experience } from "../src/lib/library";
import {
  addEntry, entryFromLibrary, exportUrl, moveItem, type ResumeContent, type ResumeEntry, unusedHighlights, updateEntry, versionLabel,
} from "../src/lib/tailored";

const source: Experience = {
  id: "e1", kind: "job", title: "Engineer", organization: "Example Corp", location: null, start_date: "2021-03", end_date: null,
  is_current: true, highlights: ["Built Python APIs", "Ran the offsite", "Wrote runbooks"], verified: true,
  source_resume_id: null, created_at: "", updated_at: "",
};
const entry: ResumeEntry = {
  ...entryFromLibrary(source), reason: "Relevant: mentions Python (required).",
  bullets: [
    { text: "Delivered Python APIs", source_text: "Built Python APIs", changed_by: "ai", reason: "Mentions Python (required)." },
    { text: "Wrote runbooks", source_text: "Wrote runbooks", changed_by: "none", reason: "Kept for context." },
  ],
};
const content: ResumeContent = {
  header: { name: "Alex", headline: null, email: null, phone: null, location: null, links: [] },
  summary: null, skills: [], sections: [{ kind: "job", heading: "Experience", entries: [entry] }],
};

describe("helpers", () => {
  it("labels versions", () => {
    const base = { id: "v", job_id: "j", based_on_version: null, warning_count: 0, note: null, created_at: "", updated_at: "", approved_at: null };
    expect(versionLabel({ ...base, version: 3, status: "draft", generation_method: "ai", edited: true })).toBe("v3 · Draft · AI-reworded · edited");
    expect(versionLabel({ ...base, version: 1, status: "approved", generation_method: "deterministic", edited: false })).toBe("v1 · Approved · Selected");
  });
  it("moves items within bounds", () => {
    expect(moveItem([1, 2, 3], 0, 1)).toEqual([2, 1, 3]);
    expect(moveItem([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
  });
  it("finds unused highlights and builds entries from the library", () => {
    expect(unusedHighlights(entry, source)).toEqual(["Ran the offsite"]);
    expect(entryFromLibrary(source).bullets.map(b => b.text)).toEqual(source.highlights);
  });
  it("adds, updates and removes entries, dropping empty sections", () => {
    const project = entryFromLibrary({ ...source, id: "p1", kind: "project", title: "Tool" });
    const added = addEntry(content, project);
    expect(added.sections.map(s => s.heading)).toEqual(["Experience", "Projects"]);
    const removed = updateEntry(added, "p1", () => null);
    expect(removed.sections.map(s => s.heading)).toEqual(["Experience"]);
    const renamed = updateEntry(content, "e1", e => ({ ...e, bullets: [] }));
    expect(renamed.sections[0].entries[0].bullets).toEqual([]);
  });
  it("builds export URLs", () => {
    expect(exportUrl("abc", "pdf")).toMatch(/\/tailored-resumes\/abc\/export\?format=pdf$/);
  });
});

describe("ResumeEntryReview", () => {
  const render = (editable: boolean) =>
    renderToStaticMarkup(React.createElement(ResumeEntryReview, { entry, source, editable, onChange() {} }));

  it("shows the verified source beside the tailored text", () => {
    const html = render(false);
    expect(html).toContain("From your verified library");
    expect(html).toContain("Built Python APIs");
    expect(html).toContain("Delivered Python APIs");
    expect(html).toContain("Reworded by AI");
    expect(html).toContain("Why it&#x27;s here: Relevant: mentions Python (required).");
    expect(html).toContain('title="Not used on this resume"');
    expect(html).not.toContain("<textarea");
  });
  it("offers editing controls on drafts", () => {
    const html = render(true);
    expect(html).toContain("<textarea");
    expect(html).toContain("Use original");
    expect(html).toContain("Add a bullet from this entry");
    expect(html).toContain("Ran the offsite</option>");
  });
  it("warns when the source is no longer verified", () => {
    const html = renderToStaticMarkup(React.createElement(ResumeEntryReview, { entry, source: undefined, editable: false, onChange() {} }));
    expect(html).toContain("no longer verified");
  });
});
