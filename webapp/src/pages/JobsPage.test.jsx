import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import JobsPage from "./JobsPage";
import { getJobs, queryJobBoardSummary } from "../services/api";

vi.mock("../services/api", () => ({
  getJobs: vi.fn(),
  queryJobBoardSummary: vi.fn(),
}));

describe("JobsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders the page header and health link", () => {
    getJobs.mockResolvedValue([]);

    render(<JobsPage />);

    expect(screen.getByRole("heading", { name: "Open roles", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "View backend health" }).getAttribute("href")).toBe("/health");
  });

  it("shows loading state before rendering jobs", async () => {
    let resolveJobsRequest;
    getJobs.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveJobsRequest = resolve;
        }),
    );

    render(<JobsPage />);

    expect(screen.getByText("Loading jobs...")).toBeTruthy();

    resolveJobsRequest([
      {
        id: "senior dev/uk",
        company: "NewPage",
        location: "London",
        title: "Senior Developer",
        salary: "£100k",
        jd: "Build platform features.",
      },
    ]);

    expect(await screen.findByText("Senior Developer")).toBeTruthy();
    expect(screen.getByText("Build platform features.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View role" }).getAttribute("href")).toBe("/jobs/senior%20dev%2Fuk");
    expect(getJobs).toHaveBeenCalledWith(expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it("shows empty state when no jobs are available", async () => {
    getJobs.mockResolvedValue([]);

    render(<JobsPage />);

    expect(await screen.findByText("No jobs are currently available.")).toBeTruthy();
  });

  it("shows safe fallback messages for API and non-Error failures", async () => {
    getJobs.mockRejectedValueOnce(new Error("Jobs endpoint unavailable"));
    const { unmount } = render(<JobsPage />);
    expect(await screen.findByText("Unable to load jobs.")).toBeTruthy();
    unmount();

    getJobs.mockRejectedValueOnce("bad payload");
    render(<JobsPage />);
    expect(await screen.findByText("Unable to load jobs.")).toBeTruthy();
  });

  it("shows summary accordion and generates AI summary", async () => {
    let resolveSummaryRequest;
    getJobs.mockResolvedValue([]);
    queryJobBoardSummary.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSummaryRequest = resolve;
        }),
    );

    render(<JobsPage />);

    expect(screen.getByText("AI summary")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(screen.getByText("Generating summary...")).toBeTruthy();
    expect(queryJobBoardSummary).toHaveBeenCalledTimes(1);

    resolveSummaryRequest("Summary of open roles.");
    expect(await screen.findByText("Summary of open roles.")).toBeTruthy();
    expect(window.localStorage.getItem("ai-summary:jobs-page")).toBe("Summary of open roles.");
  });

  it('shows "failed to generate summary" when generation fails', async () => {
    getJobs.mockResolvedValue([]);
    queryJobBoardSummary.mockRejectedValue(new Error("Model unavailable"));

    render(<JobsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(await screen.findByText("failed to generate summary")).toBeTruthy();
  });

  it("restores cached jobs summary after remount", async () => {
    getJobs.mockResolvedValue([]);
    window.localStorage.setItem("ai-summary:jobs-page", "Cached jobs summary.");

    const { unmount } = render(<JobsPage />);
    expect(await screen.findByText("Cached jobs summary.")).toBeTruthy();
    unmount();

    render(<JobsPage />);
    expect(await screen.findByText("Cached jobs summary.")).toBeTruthy();
  });
});
