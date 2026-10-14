import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ResumeSections } from "../src/components/resume-sections";
import { formatBytes, validateResumeFile } from "../src/lib/resumes";

describe("validateResumeFile", () => {
  it("accepts supported types regardless of case", () => {
    expect(validateResumeFile({ name: "CV.PDF", size: 100 })).toBeNull();
    expect(validateResumeFile({ name: "cv.docx", size: 100 })).toBeNull();
    expect(validateResumeFile({ name: "cv.txt", size: 100 })).toBeNull();
  });
  it("rejects unsupported, empty, and oversized files", () => {
    expect(validateResumeFile({ name: "cv.doc", size: 100 })).toMatch(/PDF, DOCX, or TXT/);
    expect(validateResumeFile({ name: "cv.pdf", size: 0 })).toMatch(/empty/);
    expect(validateResumeFile({ name: "cv.pdf", size: 5 * 1024 * 1024 + 1 })).toMatch(/5 MB/);
  });
});

describe("formatBytes", () => {
  it("uses readable units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});

describe("ResumeSections", () => {
  it("renders each parsed section", () => {
    const html = renderToStaticMarkup(React.createElement(ResumeSections, { resume: {
      id: "1", filename: "cv.txt", file_type: "txt", size_bytes: 10, created_at: "2026-01-01T00:00:00Z", text: "",
      sections: [{ key: "header", heading: "Header", content: "Alex Example" }, { key: "skills", heading: "Skills", content: "Python" }],
    } }));
    expect(html).toContain("2 sections");
    expect(html.match(/<section/g)).toHaveLength(2);
    expect(html).toContain("Python");
  });
});
