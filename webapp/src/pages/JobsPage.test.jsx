import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import JobsPage from "./JobsPage";
import { getJobs, queryJobBoardSummary } from "../services/api";

vi.mock("../services/api", () => ({
  getJobs: vi.fn(),
  queryJobBoardSummary: vi.fn(),
}));

function renderJobsPage() {
  return render(
    <MemoryRouter>
      <JobsPage />
    </MemoryRouter>,
  );
}

describe("JobsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders the page header and health link", () => {
    getJobs.mockResolvedValue([]);

    renderJobsPage();

    expect(screen.getByRole("heading", { name: "Open roles", level: 1 })).toBeTruthy();
    expect(screen.getByRole("separator")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View backend health" }).getAttribute("href")).toBe("/health");
    expect(screen.getByRole("link", { name: "Open AI chat" }).getAttribute("href")).toBe("/chat");
  });

  it("shows loading state before rendering jobs", async () => {
    let resolveJobsRequest;
    getJobs.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveJobsRequest = resolve;
        }),
    );

    renderJobsPage();

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

    renderJobsPage();

    expect(await screen.findByText("No jobs are currently available.")).toBeTruthy();
  });

  it("shows safe fallback messages for API and non-Error failures", async () => {
    getJobs.mockRejectedValueOnce(new Error("Jobs endpoint unavailable"));
    const { unmount } = renderJobsPage();
    expect(await screen.findByText("Unable to load jobs.")).toBeTruthy();
    unmount();

    getJobs.mockRejectedValueOnce("bad payload");
    renderJobsPage();
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

    renderJobsPage();

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

    renderJobsPage();
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(await screen.findByText("failed to generate summary")).toBeTruthy();
  });

  it("restores cached jobs summary after remount", async () => {
    getJobs.mockResolvedValue([]);
    window.localStorage.setItem("ai-summary:jobs-page", "Cached jobs summary.");

    const { unmount } = renderJobsPage();
    expect(await screen.findByText("Cached jobs summary.")).toBeTruthy();
    unmount();

    renderJobsPage();
    expect(await screen.findByText("Cached jobs summary.")).toBeTruthy();
  });

  it("truncates long job descriptions in the list preview", async () => {
    getJobs.mockResolvedValue([
      {
        id: "senior-engineer",
        company: "NewPage",
        location: "London",
        title: "Senior Engineer",
        salary: "£110k",
        jd: "A".repeat(400),
      },
    ]);

    renderJobsPage();

    expect(await screen.findByText("Senior Engineer")).toBeTruthy();
    expect(screen.getByText(`${"A".repeat(300)}...`)).toBeTruthy();
  });

  it("renders a salary placeholder for empty salary values", async () => {
    getJobs.mockResolvedValue([
      {
        id: "senior-engineer",
        company: "NewPage",
        location: "London",
        title: "Senior Engineer",
        salary: "",
        jd: "Build APIs and services.",
      },
    ]);

    renderJobsPage();

    const salaryElement = (await screen.findByText("Senior Engineer"))
      .closest(".job-card")
      .querySelector(".salary");

    expect(salaryElement).toBeTruthy();
    expect(salaryElement.textContent).toBe("\u00A0");
  });
});
