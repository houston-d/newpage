import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { chatWithCv } from "../services/api";

if (!GlobalWorkerOptions.workerSrc) {
  GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
}

async function extractPdfText(file) {
  const pdfFileBuffer = await file.arrayBuffer();
  const pdfDocument = await getDocument({
    data: pdfFileBuffer,
  }).promise;
  const extractedPages = [];

  for (let pageNumber = 1; pageNumber <= pdfDocument.numPages; pageNumber += 1) {
    const pdfPage = await pdfDocument.getPage(pageNumber);
    const pageTextContent = await pdfPage.getTextContent();
    const pageText = pageTextContent.items
      .map((item) => ("str" in item ? item.str : ""))
      .join(" ")
      .trim();

    if (pageText) {
      extractedPages.push(pageText);
    }
  }

  return extractedPages.join("\n\n");
}

export default function ChatPage() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState([]);
  const [cvText, setCvText] = useState("");
  const [isExtractingCv, setIsExtractingCv] = useState(false);
  const [cvErrorMessage, setCvErrorMessage] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [chatErrorMessage, setChatErrorMessage] = useState("");
  const hasCvText = cvText.trim().length > 0;
  const requiresCvUpload = !hasCvText && !isExtractingCv;
  const isChatEnabled = hasCvText && !isExtractingCv && !isSendingMessage;

  useEffect(() => {
    if (cvText) {
      console.log(cvText);
    }
  }, [cvText]);

  const sendMessage = async (event) => {
    event.preventDefault();
    if (!isChatEnabled) {
      return;
    }

    const trimmedMessage = draft.trim();
    if (!trimmedMessage) {
      return;
    }

    const updatedMessages = [...messages, { role: "user", text: trimmedMessage }];
    setMessages([...updatedMessages, { role: "assistant", text: "Thinking...", isThinking: true }]);
    setDraft("");

    setIsSendingMessage(true);
    setChatErrorMessage("");
    try {
      const assistantReply = await chatWithCv({
        cv: cvText,
        messageHistory: updatedMessages.map((message) => ({
          role: message.role,
          content: message.text,
        })),
      });
      setMessages((previousMessages) =>
        previousMessages.map((message, index) =>
          message.isThinking
            ? {
                ...message,
                isThinking: false,
                text: assistantReply,
              }
            : message,
        ),
      );
    } catch (error) {
      setMessages((previousMessages) => previousMessages.filter((message) => !message.isThinking));
      setChatErrorMessage(error instanceof Error ? error.message : "Failed to send chat message.");
    } finally {
      setIsSendingMessage(false);
    }
  };

  const uploadCv = async (event) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) {
      return;
    }

    const isPdfFile = selectedFile.type === "application/pdf" || selectedFile.name.toLowerCase().endsWith(".pdf");
    if (!isPdfFile) {
      setCvText("");
      setCvErrorMessage("Please upload a PDF file.");
      return;
    }

    setIsExtractingCv(true);
    setCvErrorMessage("");

    try {
      const extractedText = await extractPdfText(selectedFile);
      if (!extractedText.trim()) {
        setCvText("");
        setCvErrorMessage("No selectable text found in PDF.");
        return;
      }

      setCvText(extractedText);
    } catch (error) {
      setCvText("");
      setCvErrorMessage(
        error instanceof Error ? error.message : "Unable to extract text from PDF.",
      );
    } finally {
      setIsExtractingCv(false);
    }
  };

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>AI chat</h1>
        <Link className="back-link" to="/jobs">
          Back to all roles
        </Link>
      </header>

      <section className="cv-upload-box" aria-label="CV upload">
        <h2>Upload CV</h2>
        <input
          accept=".pdf,application/pdf"
          aria-label="Upload CV PDF"
          className="cv-upload-input"
          onChange={uploadCv}
          type="file"
        />
        {isExtractingCv ? <p className="state">Extracting CV text...</p> : null}
        {!isExtractingCv && cvText ? <p className="state">CV text extracted and saved.</p> : null}
        {cvErrorMessage ? <p className="state error">{cvErrorMessage}</p> : null}
      </section>

      <section className="chat-box" aria-label="AI chat conversation">
        {requiresCvUpload ? <p className="state">Upload a valid CV PDF to enable chat.</p> : null}
        {isSendingMessage ? <p className="state">AI is replying...</p> : null}
        {chatErrorMessage ? <p className="state error">{chatErrorMessage}</p> : null}
        <div className="chat-messages">
          {messages.length === 0 ? <p className="state">Start the conversation.</p> : null}
          {messages.map((message, index) => (
            <p className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
              <strong>{message.role === "assistant" ? "AI" : "You"}:</strong> {message.text}
            </p>
          ))}
        </div>

        <form className="chat-form" onSubmit={sendMessage}>
          <input
            className="chat-input"
            aria-label="Message"
            disabled={!isChatEnabled}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Type your message"
            type="text"
            value={draft}
          />
          <button className="chat-send-button" disabled={!isChatEnabled} type="submit">
            Send
          </button>
        </form>
      </section>
    </main>
  );
}
