import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import App from "./App";

vi.mock("./pages/JobsPage", () => ({
  default: () => <p>Jobs page</p>,
}));

vi.mock("./pages/HealthStatusPage", () => ({
  default: () => <p>Health page</p>,
}));

vi.mock("./pages/NotFoundPage", () => ({
  default: () => <p>Not found page</p>,
}));

vi.mock("./pages/JobDetailPage", () => ({
  default: ({ jobId }) => <p>Job detail: {jobId}</p>,
}));

describe("App", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("renders jobs page for /jobs", () => {
    window.history.pushState({}, "", "/jobs");
    render(<App />);
    expect(screen.getByText("Jobs page")).toBeTruthy();
  });

  it("renders health page for /health", () => {
    window.history.pushState({}, "", "/health");
    render(<App />);
    expect(screen.getByText("Health page")).toBeTruthy();
  });

  it("renders job details for encoded job id", () => {
    window.history.pushState({}, "", "/jobs/backend%2Fengineer");
    render(<App />);
    expect(screen.getByText("Job detail: backend/engineer")).toBeTruthy();
  });

  it("falls back to not found for malformed job id encoding", () => {
    window.history.pushState({}, "", "/jobs/%E0%A4%A");
    render(<App />);
    expect(screen.getByText("Not found page")).toBeTruthy();
  });
});
