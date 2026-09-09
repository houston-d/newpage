import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import JobDetailPage from "./JobDetailPage";
import { analyseJobSummary, getJobById } from "../services/api";

vi.mock("../services/api", () => ({
  getJobById: vi.fn(),
  analyseJobSummary: vi.fn(),
}));

function renderJobDetailPage(jobId) {
  return render(
    <MemoryRouter>
      <JobDetailPage jobId={jobId} />
    </MemoryRouter>,
  );
}

describe("JobDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders the page header and jobs link", () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "Build APIs.",
    });

    renderJobDetailPage("backend-engineer");

    expect(screen.getByRole("heading", { name: "Job details", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to all roles" }).getAttribute("href")).toBe("/jobs");
    expect(screen.getByRole("link", { name: "Open AI chat" }).getAttribute("href")).toBe("/chat");
  });

  it("loads the requested job and renders details", async () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "Build APIs.",
    });

    renderJobDetailPage("backend-engineer");

    expect(screen.getByText("Loading job...")).toBeTruthy();
    expect(await screen.findByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText("Build APIs.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Apply" })).toBeTruthy();
    expect(getJobById).toHaveBeenCalledWith(
      "backend-engineer",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("renders markdown-style bold text in the description", async () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "**About the Role**\nBuild APIs.",
    });

    renderJobDetailPage("backend-engineer");

    expect(await screen.findByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText("About the Role", { selector: "strong" })).toBeTruthy();
    expect(screen.getByText("Build APIs.")).toBeTruthy();
  });

  it("shows AI summary accordion and generates job summary", async () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "Build APIs.",
    });
    let resolveSummaryRequest;
    analyseJobSummary.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSummaryRequest = resolve;
        }),
    );

    renderJobDetailPage("backend-engineer");

    expect(await screen.findByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText("AI summary")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(screen.getByText("Generating summary...")).toBeTruthy();
    expect(analyseJobSummary).toHaveBeenCalledWith("Build APIs.");

    resolveSummaryRequest("Strong backend-focused role.");
    expect(await screen.findByText("Strong backend-focused role.")).toBeTruthy();
    expect(window.localStorage.getItem("ai-summary:job-detail:backend-engineer")).toBe(
      "Strong backend-focused role.",
    );
  });

  it('shows "failed to generate summary" when generation fails', async () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "Build APIs.",
    });
    analyseJobSummary.mockRejectedValue(new Error("Model unavailable"));

    renderJobDetailPage("backend-engineer");

    expect(await screen.findByText("Backend Engineer")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));

    expect(await screen.findByText("failed to generate summary")).toBeTruthy();
  });

  it("restores cached summary for the current job and keeps cache per job id", async () => {
    getJobById.mockResolvedValue({
      id: "backend-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Backend Engineer",
      salary: "£95k",
      jd: "Build APIs.",
    });
    window.localStorage.setItem("ai-summary:job-detail:backend-engineer", "Cached backend summary.");
    window.localStorage.setItem("ai-summary:job-detail:data-engineer", "Different job summary.");

    const { rerender } = renderJobDetailPage("backend-engineer");
    expect(await screen.findByText("Cached backend summary.")).toBeTruthy();

    getJobById.mockResolvedValue({
      id: "data-engineer",
      company: "NewPage",
      location: "Remote",
      title: "Data Engineer",
      salary: "£90k",
      jd: "Build data pipelines.",
    });
    rerender(
      <MemoryRouter>
        <JobDetailPage jobId="data-engineer" />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Different job summary.")).toBeTruthy();
  });

  it("shows a safe fallback message for API errors", async () => {
    getJobById.mockRejectedValue(new Error("Job not found"));

    renderJobDetailPage("missing-job");

    expect(await screen.findByText("Unable to load job.")).toBeTruthy();
  });

  it("shows fallback error message for non-Error rejections", async () => {
    getJobById.mockRejectedValue("bad request");

    renderJobDetailPage("bad-job");

    expect(await screen.findByText("Unable to load job.")).toBeTruthy();
  });
});
