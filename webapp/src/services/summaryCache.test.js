import { beforeEach, describe, expect, it } from "vitest";

import { clearCachedSummaries } from "./summaryCache";

describe("summaryCache", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("clears only summary cache entries", () => {
    window.localStorage.setItem("ai-summary:jobs-page", "Jobs summary");
    window.localStorage.setItem("ai-summary:job-detail:backend", "Backend summary");
    window.localStorage.setItem("unrelated-key", "keep me");

    clearCachedSummaries();

    expect(window.localStorage.getItem("ai-summary:jobs-page")).toBeNull();
    expect(window.localStorage.getItem("ai-summary:job-detail:backend")).toBeNull();
    expect(window.localStorage.getItem("unrelated-key")).toBe("keep me");
  });
});
