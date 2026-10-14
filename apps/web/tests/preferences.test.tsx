import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MustMatch } from "../src/components/preferences-form";
import { parseSalary, parseTerms, toggle, withoutUpdatedAt } from "../src/lib/preferences";

describe("parseTerms", () => {
  it("splits on commas and new lines, trimming and deduping case-insensitively", () => {
    expect(parseTerms(" Backend  Engineer, ,SRE\nsre", ["Platform"])).toEqual(["Platform", "Backend Engineer", "SRE"]);
    expect(parseTerms("platform", ["Platform"])).toEqual(["Platform"]);
  });
});

describe("parseSalary", () => {
  it("accepts whole numbers with separators and treats blank as no minimum", () => {
    expect(parseSalary("85,000")).toBe(85000);
    expect(parseSalary(" ")).toBeNull();
    expect(parseSalary("85k")).toBeUndefined();
    expect(parseSalary("-5")).toBeUndefined();
  });
});

describe("helpers", () => {
  it("toggles list membership", () => {
    expect(toggle(["remote"], "hybrid")).toEqual(["remote", "hybrid"]);
    expect(toggle(["remote", "hybrid"], "remote")).toEqual(["hybrid"]);
  });
  it("drops updated_at before saving", () => {
    const saved = { updated_at: "2026-01-01", target_titles: [] } as unknown as Parameters<typeof withoutUpdatedAt>[0];
    expect(withoutUpdatedAt(saved)).not.toHaveProperty("updated_at");
  });
});

describe("MustMatch", () => {
  it("renders a labelled checkbox", () => {
    const html = renderToStaticMarkup(React.createElement(MustMatch, { checked: true, onChange() {} }));
    expect(html).toContain("Must match");
    expect(html).toContain('checked=""');
  });
});
