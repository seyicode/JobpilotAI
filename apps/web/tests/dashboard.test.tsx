import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Dashboard } from "../src/components/dashboard";
describe("dashboard smoke test", () => {
  it("renders the workspace and manual application principle", () => {
    const html = renderToStaticMarkup(React.createElement(Dashboard));
    expect(html).toContain("Your dashboard");
    expect(html).toContain("apply manually");
    expect(html.match(/<article/g)).toHaveLength(6);
  });
});
