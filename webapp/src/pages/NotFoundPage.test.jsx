import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import NotFoundPage from "./NotFoundPage";

describe("NotFoundPage", () => {
  it("renders a not found message and jobs link", () => {
    render(<NotFoundPage />);

    expect(screen.getByRole("heading", { name: "Page not found", level: 1 })).toBeTruthy();
    expect(screen.getByText("Go to the jobs page to see available roles.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open /jobs" }).getAttribute("href")).toBe("/jobs");
  });
});
