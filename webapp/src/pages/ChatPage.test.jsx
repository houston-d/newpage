import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ChatPage from "./ChatPage";

function renderChatPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  );
}

describe("ChatPage", () => {
  it("renders chat page header and back link", () => {
    renderChatPage();

    expect(screen.getByRole("heading", { name: "AI chat", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to all roles" }).getAttribute("href")).toBe("/jobs");
  });

  it('adds a "TODO" AI reply for every sent message', () => {
    renderChatPage();
    const input = screen.getByRole("textbox", { name: "Message" });

    fireEvent.change(input, { target: { value: "Hello there" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("You:")).toBeTruthy();
    expect(screen.getByText("Hello there")).toBeTruthy();
    expect(screen.getByText("AI:")).toBeTruthy();
    expect(screen.getByText("TODO")).toBeTruthy();
    expect(input.value).toBe("");
  });
});
