import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ChatPage from "./ChatPage";

const { getDocumentMock, globalWorkerOptionsMock } = vi.hoisted(() => ({
  getDocumentMock: vi.fn(),
  globalWorkerOptionsMock: { workerSrc: "" },
}));

vi.mock("pdfjs-dist", () => ({
  getDocument: getDocumentMock,
  GlobalWorkerOptions: globalWorkerOptionsMock,
}));

vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({
  default: "mock-worker-url",
}));

function renderChatPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  );
}

describe("ChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it("extracts text from uploaded PDF and logs it once saved", async () => {
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const pdfTextContent = {
      items: [{ str: "Alice" }, { str: "Example" }, { str: "Engineer" }],
    };
    getDocumentMock.mockReturnValue({
      promise: Promise.resolve({
        numPages: 1,
        getPage: vi.fn().mockResolvedValue({
          getTextContent: vi.fn().mockResolvedValue(pdfTextContent),
        }),
      }),
    });

    renderChatPage();
    const pdfFile = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
    vi.spyOn(pdfFile, "arrayBuffer").mockResolvedValue(new ArrayBuffer(32));

    fireEvent.change(screen.getByLabelText("Upload CV PDF"), {
      target: { files: [pdfFile] },
    });

    expect(await screen.findByText("CV text extracted and saved.")).toBeTruthy();
    expect(getDocumentMock).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.any(ArrayBuffer),
      }),
    );
    expect(consoleLogSpy).toHaveBeenCalledWith("Alice Example Engineer");
  });

  it("shows a validation error for non-PDF uploads", async () => {
    renderChatPage();
    const textFile = new File(["hello"], "notes.txt", { type: "text/plain" });

    fireEvent.change(screen.getByLabelText("Upload CV PDF"), {
      target: { files: [textFile] },
    });

    expect(await screen.findByText("Please upload a PDF file.")).toBeTruthy();
  });
});
