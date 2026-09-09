import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import JobDetailPage from "./JobDetailPage";
import { getJobById } from "../services/api";

vi.mock("../services/api", () => ({
  getJobById: vi.fn(),
}));

describe("JobDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    render(<JobDetailPage jobId="backend-engineer" />);

    expect(screen.getByRole("heading", { name: "Job details", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to all roles" }).getAttribute("href")).toBe("/jobs");
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

    render(<JobDetailPage jobId="backend-engineer" />);

    expect(screen.getByText("Loading job...")).toBeTruthy();
    expect(await screen.findByText("Backend Engineer")).toBeTruthy();
    expect(screen.getByText("Build APIs.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Apply" })).toBeTruthy();
    expect(getJobById).toHaveBeenCalledWith(
      "backend-engineer",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a safe fallback message for API errors", async () => {
    getJobById.mockRejectedValue(new Error("Job not found"));

    render(<JobDetailPage jobId="missing-job" />);

    expect(await screen.findByText("Unable to load job.")).toBeTruthy();
  });

  it("shows fallback error message for non-Error rejections", async () => {
    getJobById.mockRejectedValue("bad request");

    render(<JobDetailPage jobId="bad-job" />);

    expect(await screen.findByText("Unable to load job.")).toBeTruthy();
  });
});
