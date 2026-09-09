import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import AiSummaryAccordion from "./AiSummaryAccordion";

describe("AiSummaryAccordion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("restores a cached summary by cache key", () => {
    window.localStorage.setItem("ai-summary:jobs-page", "Cached summary.");

    render(<AiSummaryAccordion cacheKey="jobs-page" generateSummary={vi.fn()} />);

    expect(screen.getByText("Cached summary.")).toBeTruthy();
  });

  it("generates and caches a summary", async () => {
    let resolveGenerate;
    const generateSummary = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGenerate = resolve;
        }),
    );

    render(<AiSummaryAccordion cacheKey="jobs-page" generateSummary={generateSummary} />);
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(screen.getByText("Generating summary...")).toBeTruthy();
    expect(generateSummary).toHaveBeenCalledTimes(1);

    resolveGenerate("Generated summary.");
    expect(await screen.findByText("Generated summary.")).toBeTruthy();
    expect(window.localStorage.getItem("ai-summary:jobs-page")).toBe("Generated summary.");
  });

  it('shows "failed to generate summary" when generation fails', async () => {
    const generateSummary = vi.fn().mockRejectedValue(new Error("Model unavailable"));

    render(<AiSummaryAccordion cacheKey="jobs-page" generateSummary={generateSummary} />);
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(await screen.findByText("failed to generate summary")).toBeTruthy();
  });

  it("loads the correct cached summary when cache key changes", async () => {
    const generateSummary = vi.fn();
    window.localStorage.setItem("ai-summary:job-detail:backend", "Backend summary.");
    window.localStorage.setItem("ai-summary:job-detail:data", "Data summary.");

    const { rerender } = render(
      <AiSummaryAccordion cacheKey="job-detail:backend" generateSummary={generateSummary} />,
    );
    expect(screen.getByText("Backend summary.")).toBeTruthy();

    rerender(<AiSummaryAccordion cacheKey="job-detail:data" generateSummary={generateSummary} />);
    expect(await screen.findByText("Data summary.")).toBeTruthy();
  });
});
