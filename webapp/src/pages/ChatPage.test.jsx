import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ChatPage from "./ChatPage";

const { getDocumentMock, globalWorkerOptionsMock, chatWithCvMock } = vi.hoisted(() => ({
  getDocumentMock: vi.fn(),
  globalWorkerOptionsMock: { workerSrc: "" },
  chatWithCvMock: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  getDocument: getDocumentMock,
  GlobalWorkerOptions: globalWorkerOptionsMock,
}));

vi.mock("pdfjs-dist/build/pdf.worker.min.mjs?url", () => ({
  default: "mock-worker-url",
}));

vi.mock("../services/api", () => ({
  chatWithCv: chatWithCvMock,
}));

function renderChatPage() {
  return render(
    <MemoryRouter>
      <ChatPage />
    </MemoryRouter>,
  );
}

function setupPdfExtractionMock(extractedWords = ["Alice", "Example", "Engineer"]) {
  const pdfTextContent = {
    items: extractedWords.map((word) => ({ str: word })),
  };

  getDocumentMock.mockReturnValue({
    promise: Promise.resolve({
      numPages: 1,
      getPage: vi.fn().mockResolvedValue({
        getTextContent: vi.fn().mockResolvedValue(pdfTextContent),
      }),
    }),
  });
}

async function uploadValidPdf() {
  const pdfFile = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
  vi.spyOn(pdfFile, "arrayBuffer").mockResolvedValue(new ArrayBuffer(32));

  fireEvent.change(screen.getByLabelText("Upload CV PDF"), {
    target: { files: [pdfFile] },
  });

  await screen.findByText("CV text extracted and saved.");
}

function uploadPdfWithoutWaitingForSuccess() {
  const pdfFile = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
  vi.spyOn(pdfFile, "arrayBuffer").mockResolvedValue(new ArrayBuffer(32));

  fireEvent.change(screen.getByLabelText("Upload CV PDF"), {
    target: { files: [pdfFile] },
  });
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("ChatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, "log").mockImplementation(() => {});
    chatWithCvMock.mockResolvedValue("TODO");
  });

  it("renders chat page header and back link", () => {
    renderChatPage();

    expect(screen.getByRole("heading", { name: "AI chat", level: 1 })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to all roles" }).getAttribute("href")).toBe("/jobs");
  });

  it("keeps chat disabled until a valid CV is uploaded", async () => {
    renderChatPage();

    const input = screen.getByRole("textbox", { name: "Message" });
    const sendButton = screen.getByRole("button", { name: "Send" });
    expect(input.hasAttribute("disabled")).toBe(true);
    expect(sendButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Upload a valid CV PDF to enable chat.")).toBeTruthy();

    setupPdfExtractionMock();
    await uploadValidPdf();
    expect(input.hasAttribute("disabled")).toBe(false);
    expect(sendButton.hasAttribute("disabled")).toBe(false);
  });

  it('adds a "TODO" AI reply for every sent message', async () => {
    setupPdfExtractionMock();
    renderChatPage();
    await uploadValidPdf();
    const input = screen.getByRole("textbox", { name: "Message" });

    fireEvent.change(input, { target: { value: "Hello there" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByText("You:")).toBeTruthy();
    expect(screen.getByText("Hello there")).toBeTruthy();
    expect(await screen.findByText("AI:")).toBeTruthy();
    expect(await screen.findByText("TODO")).toBeTruthy();
    expect(input.value).toBe("");
    expect(chatWithCvMock).toHaveBeenCalledWith({
      cv: "Alice Example Engineer",
      messageHistory: [{ role: "user", content: "Hello there" }],
    });
  });

  it("shows a thinking message while waiting for chat reply", async () => {
    const deferred = createDeferred();
    chatWithCvMock.mockReturnValueOnce(deferred.promise);
    setupPdfExtractionMock();
    renderChatPage();
    await uploadValidPdf();

    fireEvent.change(screen.getByRole("textbox", { name: "Message" }), {
      target: { value: "Find me backend roles" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Thinking...")).toBeTruthy();
    deferred.resolve("You are a strong fit for backend roles.");
    expect(await screen.findByText("You are a strong fit for backend roles.")).toBeTruthy();
  });

  it("extracts text from uploaded PDF and logs it once saved", async () => {
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    setupPdfExtractionMock();

    renderChatPage();
    await uploadValidPdf();
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

  it("shows an error and keeps chat disabled when PDF has no text", async () => {
    setupPdfExtractionMock([]);
    renderChatPage();
    uploadPdfWithoutWaitingForSuccess();

    expect(await screen.findByText("No selectable text found in PDF.")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Message" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Send" }).hasAttribute("disabled")).toBe(true);
  });
});
