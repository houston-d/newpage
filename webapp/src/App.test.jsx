import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

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
  const renderAtRoute = (route) =>
    render(
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>,
    );

  it("renders jobs page for /jobs", () => {
    renderAtRoute("/jobs");
    expect(screen.getByText("Jobs page")).toBeTruthy();
  });

  it("renders health page for /health", () => {
    renderAtRoute("/health");
    expect(screen.getByText("Health page")).toBeTruthy();
  });

  it("renders job details for encoded job id", () => {
    renderAtRoute("/jobs/backend%2Fengineer");
    expect(screen.getByText("Job detail: backend/engineer")).toBeTruthy();
  });

  it("falls back to not found for malformed job id encoding", () => {
    renderAtRoute("/jobs/%E0%A4%A");
    expect(screen.getByText("Not found page")).toBeTruthy();
  });
});
