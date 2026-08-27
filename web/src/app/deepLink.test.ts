import { describe, expect, it } from "vitest";

import { buildDeepLink, readDeepLink } from "./deepLink";

describe("deepLink", () => {
  it("reads a selected case and an allowed section", () => {
    expect(readDeepLink("#case=case%2F1&section=decision")).toEqual({
      caseId: "case/1",
      section: "decision",
    });
  });

  it("falls back to overview for unknown or malformed sections", () => {
    expect(readDeepLink("#case=case-1&section=admin-token")).toEqual({
      caseId: "case-1",
      section: "overview",
    });
    expect(readDeepLink("#section=%00").section).toBe("overview");
  });

  it("builds a stable, encoded hash without credentials or free-form text", () => {
    expect(buildDeepLink({ caseId: "case/1", section: "decision" })).toBe(
      "#case=case%2F1&section=decision",
    );
    expect(buildDeepLink({ caseId: "", section: "overview" })).toBe("");
  });
});
