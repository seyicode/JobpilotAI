import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SourceCard } from "../src/components/source-card";
import { TrackerRowCard } from "../src/components/tracker-row";
import { boardFromInput, describeRun, type Source, type SourceRun } from "../src/lib/sources";
import { defaultFilters, filterQuery, rowSalary, statusLabel, type TrackerRow } from "../src/lib/tracker";

const row: TrackerRow = {
  id: "j1", title: "Backend Engineer", company: "Acme", application_status: "discovered", match_score: 82, match_coverage: 75,
  eligible: true, location: "London", work_arrangement: "hybrid", salary_min: 80000, salary_max: 95000, salary_currency: "GBP",
  salary_period: "year", found_at: "2026-10-14T09:00:00Z", posted_at: null, last_seen_at: null, closed: true, is_new: true,
  source_provider: "greenhouse", source_url: "https://boards.greenhouse.io/acme/jobs/1", resume_status: "approved", status_changed_at: null,
};

describe("tracker helpers", () => {
  it("builds a query with only the filters that are set", () => {
    expect(filterQuery(defaultFilters())).toBe("view=new&sort=score&order=desc");
    const q = filterQuery({ ...defaultFilters(), view: "all", min_salary: "90,000", salary_currency: "gbp", company: " Acme ", include_unknown_salary: false });
    expect(q).toBe("view=all&company=Acme&min_salary=90000&salary_currency=GBP&include_unknown_salary=false&sort=score&order=desc");
  });
  it("formats salary and status", () => {
    expect(rowSalary(row)).toBe("80,000–95,000 GBP / year");
    expect(rowSalary({ ...row, salary_min: null, salary_max: null })).toBeNull();
    expect(statusLabel("ready_to_apply")).toBe("Ready to apply");
  });
});

describe("TrackerRowCard", () => {
  it("shows score, badges, status control and links", () => {
    const html = renderToStaticMarkup(React.createElement(TrackerRowCard, { row, busy: false, onStatus() {}, onOpen() {} }));
    for (const text of ["82%", "New", "No longer listed", "Resume approved", "Acme · London · Hybrid · 80,000–95,000 GBP / year",
      "via Greenhouse", "score based on 75% of factors", 'href="/jobs?job=j1"', 'href="/jobs/j1/resume"', 'rel="noopener noreferrer nofollow"']) {
      expect(html).toContain(text);
    }
    expect(html.match(/<option/g)).toHaveLength(8);
    expect(html).not.toMatch(/auto.?apply/i);
  });
});

describe("sources helpers", () => {
  it("accepts board names or board links", () => {
    expect(boardFromInput(" acme ")).toBe("acme");
    expect(boardFromInput("https://boards.greenhouse.io/acme/jobs/123")).toBe("acme");
    expect(boardFromInput("https://jobs.lever.co/acme-labs?team=eng")).toBe("acme-labs");
    expect(boardFromInput("https://jobs.ashbyhq.com/acme")).toBe("acme");
    expect(boardFromInput("https://evil.example/acme")).toBe("https://evil.example/acme");
  });
  it("describes runs", () => {
    const base: SourceRun = { id: "r", trigger: "manual", status: "success", started_at: "", finished_at: "", attempts: 1, http_status: 200,
      fetched: 12, new_jobs: 3, seen_again: 9, filtered_out: 4, archived: 1, closed: 2, error_code: null, error_message: null };
    expect(describeRun(base)).toBe("12 listed · 3 new · 4 skipped by your preferences · 1 archived (must-match) · 2 no longer listed");
    expect(describeRun({ ...base, status: "failed", error_message: "No job board was found with that name." })).toBe("No job board was found with that name.");
  });
});

describe("SourceCard", () => {
  const source: Source = { id: "s", provider: "lever", board: "acme", company_name: "Acme", enabled: false, interval_minutes: 360,
    status: "failing", consecutive_failures: 3, last_run_at: null, last_success_at: null, next_run_at: null,
    last_error_code: "not_found", last_error_message: "No job board was found with that name.", created_at: "" };
  it("shows health, pause state and the last error", () => {
    const html = renderToStaticMarkup(React.createElement(SourceCard, { source, runs: null, busy: false, confirmingDelete: false,
      onRun() {}, onToggle() {}, onInterval() {}, onDelete() {}, onCancelDelete() {}, onShowRuns() {} }));
    for (const text of ["Failing", "Paused", "Lever · acme", "No job board was found with that name.", ">Resume<", "Show recent checks"]) {
      expect(html).toContain(text);
    }
  });
});
