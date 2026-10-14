import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MatchView, ScoreBadge } from "../src/components/match-view";
import { RequirementsView } from "../src/components/requirements-view";
import { emptyRequirements, formatSalary, jobLabel, type MatchResult, validateNewJob } from "../src/lib/jobs";

const render = (el: React.ReactElement) => renderToStaticMarkup(el);
const longText = "x".repeat(60);

describe("validateNewJob", () => {
  it("requires a real description and an http(s) URL", () => {
    expect(validateNewJob({ description: "short", source_url: "", title: "", company: "" })).toMatch(/at least 50/);
    expect(validateNewJob({ description: longText, source_url: "ftp://x", title: "", company: "" })).toMatch(/http/);
    expect(validateNewJob({ description: longText, source_url: " https://example.com/j ", title: "", company: "" })).toBeNull();
  });
});

describe("formatting", () => {
  it("formats salary ranges and single values", () => {
    expect(formatSalary({ min: 80000, max: 95000, currency: "GBP", period: "year" })).toBe("80,000–95,000 GBP per year");
    expect(formatSalary({ min: 45, max: 45, currency: "USD", period: "hour" })).toBe("45 USD per hour");
    expect(formatSalary({ min: null, max: 60000, currency: null, period: null })).toBe("60,000");
    expect(formatSalary(emptyRequirements().salary)).toBeNull();
  });
  it("labels jobs without a title", () => {
    expect(jobLabel({ title: null, company: "Acme" })).toBe("Untitled job · Acme");
  });
});

describe("RequirementsView", () => {
  it("shows missing details as Unknown rather than none", () => {
    const html = render(React.createElement(RequirementsView, { requirements: { ...emptyRequirements(), seniority: "senior", required_skills: ["Python"] } }));
    expect(html).toContain("Senior");
    expect(html).toContain("Python");
    expect(html.match(/Unknown/g)).toHaveLength(7);
  });
});

const match: MatchResult = {
  eligible: true, score: 73, coverage: 65, summary: "73% match, based on 65% of the scoring factors.",
  filters: [{ filter: "work_arrangement", status: "unknown", reason: "The posting does not say remote, hybrid, or on-site." }],
  preference_checks: [{ filter: "min_salary", status: "pass", reason: "Top of range meets your minimum." }],
  components: [
    { key: "required_skills", label: "Required skills", weight: 35, status: "scored", value: 0.5, points: 17.5, detail: "1 of 2 backed by your verified library." },
    { key: "seniority", label: "Seniority", weight: 10, status: "unknown", value: null, points: null, detail: "The posting does not state a level." },
  ],
  evidence: [{ requirement: "Python", kind: "required_skill", source: "experience", source_label: "Engineer at Example Corp", quote: "Built APIs in Python" }],
  gaps: [{ requirement: "Kubernetes", kind: "required_skill", hint: "“Kubernetes” is a draft skill in your library. Verify it if it's accurate." }],
};

describe("MatchView", () => {
  it("explains the score, unknown factors, evidence and gaps", () => {
    const html = render(React.createElement(MatchView, { match }));
    expect(html).toContain("73%");
    expect(html).toContain("17.5 / 35 pts");
    expect(html).toContain("Unknown, not scored");
    expect(html).toContain('aria-label="Seniority: unknown"');
    expect(html).toContain("Built APIs in Python");
    expect(html).toContain("draft skill");
    expect(html).toContain("Scores are estimates, not guarantees.");
  });
  it("hides the number when filtered out", () => {
    const html = render(React.createElement(MatchView, { match: { ...match, eligible: false } }));
    expect(html).toContain("Filtered out");
    expect(html).not.toContain(">73%<");
  });
});

describe("ScoreBadge", () => {
  it("covers each state", () => {
    expect(render(React.createElement(ScoreBadge, { score: null, eligible: true }))).toContain("Not scored");
    expect(render(React.createElement(ScoreBadge, { score: 81, eligible: true }))).toContain("81%");
  });
});
