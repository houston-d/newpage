import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";

import HealthStatusPage from "./HealthStatusPage";
import { getHealthStatus } from "../services/api";

vi.mock("../services/api", () => ({
  getHealthStatus: vi.fn(),
}));

function renderHealthStatusPage() {
  return render(
    <MemoryRouter>
      <HealthStatusPage />
    </MemoryRouter>,
  );
}

describe("HealthStatusPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the health page header and back link", () => {
    getHealthStatus.mockResolvedValue({
      httpStatus: 200,
      status: 200,
      message: "OK",
    });

    renderHealthStatusPage();

    expect(screen.getByRole("heading", { name: "Health status", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to all roles" }).getAttribute("href")).toBe("/jobs");
  });

  it("shows loading state before displaying a healthy response", async () => {
    let resolveHealthRequest;
    getHealthStatus.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveHealthRequest = resolve;
        }),
    );

    renderHealthStatusPage();

    expect(screen.getByText("Checking service health...")).toBeTruthy();

    resolveHealthRequest({
      httpStatus: 200,
      status: 200,
      message: "Everything is running.",
    });

    expect(await screen.findByText("Healthy")).toBeTruthy();
    expect(screen.getByText("Everything is running.")).toBeTruthy();
    expect(screen.getByText("HTTP 200 · API status 200")).toBeTruthy();
  });

  it("shows API errors", async () => {
    getHealthStatus.mockRejectedValue(new Error("Service is unavailable"));

    renderHealthStatusPage();

    expect(await screen.findByText("Unable to load health status.")).toBeTruthy();
  });

  it("shows a fallback error message for non-Error rejections", async () => {
    getHealthStatus.mockRejectedValue("bad response");

    renderHealthStatusPage();

    expect(await screen.findByText("Unable to load health status.")).toBeTruthy();
  });
});
