import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ExperienceCard } from "../src/components/experience-card";
import { errorMessage } from "../src/lib/api";
import { type Experience, emptyForm, formatDateRange, groupByKind, toForm, toPayload } from "../src/lib/library";
import { describeImport } from "../src/lib/resumes";

const job: Experience = {
  id: "1", kind: "job", title: "Software Engineer", organization: "Example Corp", location: null,
  start_date: "2021-03", end_date: null, is_current: true, highlights: ["Built a billing service"],
  verified: false, source_resume_id: null, created_at: "", updated_at: "",
};

describe("formatDateRange", () => {
  it("formats months, years, and current roles", () => {
    expect(formatDateRange(job)).toBe("Mar 2021 – Present");
    expect(formatDateRange({ start_date: "2019", end_date: "2020-12", is_current: false })).toBe("2019 – Dec 2020");
    expect(formatDateRange({ start_date: null, end_date: "2018", is_current: false })).toBe("2018");
    expect(formatDateRange({ start_date: "2019", end_date: null, is_current: false })).toBe("2019 – ?");
  });
});

describe("form conversion", () => {
  it("round-trips an experience and cleans input", () => {
    const form = { ...toForm(job), organization: "  ", highlights: "• First\n\n - Second ", end_date: "2024" };
    expect(toPayload(form)).toEqual({
      kind: "job", title: "Software Engineer", organization: null, location: null,
      start_date: "2021-03", end_date: null, is_current: true, highlights: ["First", "Second"],
    });
    expect(toPayload(emptyForm()).highlights).toEqual([]);
  });
});

describe("groupByKind", () => {
  it("orders groups and drops empty ones", () => {
    const groups = groupByKind([{ ...job, kind: "education" }, job]);
    expect(groups.map(g => g.value)).toEqual(["job", "education"]);
  });
});

describe("errorMessage", () => {
  it("reads string and validation-list details", () => {
    expect(errorMessage({ detail: "Nope." }, 409)).toBe("Nope.");
    expect(errorMessage({ detail: [{ msg: "Value error, Bad date." }] }, 422)).toBe("Bad date.");
    expect(errorMessage(null, 500)).toBe("Request failed (500).");
  });
});

describe("describeImport", () => {
  it("summarises created and skipped items", () => {
    expect(describeImport({ experiences_created: 1, skills_created: 3, skipped: 0 })).toBe("Added 1 draft entry and 3 draft skills.");
    expect(describeImport({ experiences_created: 0, skills_created: 0, skipped: 2 })).toBe("Added 0 draft entries and 0 draft skills; 2 already in your library.");
  });
});

describe("ExperienceCard", () => {
  const actions = { onVerify() {}, onEdit() {}, onDelete() {}, onCancelDelete() {}, confirmingDelete: false, busy: false };
  it("shows draft status with a verify action", () => {
    const html = renderToStaticMarkup(React.createElement(ExperienceCard, { experience: job, actions }));
    expect(html).toContain("Draft");
    expect(html).toContain(">Verify<");
    expect(html).toContain("Example Corp · Mar 2021 – Present");
  });
  it("hides verify once verified", () => {
    const html = renderToStaticMarkup(React.createElement(ExperienceCard, { experience: { ...job, verified: true }, actions }));
    expect(html).toContain("Verified");
    expect(html).not.toContain(">Verify<");
  });
});
