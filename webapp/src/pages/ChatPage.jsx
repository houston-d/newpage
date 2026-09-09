import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

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

  useEffect(() => {
    if (cvText) {
      console.log(cvText);
    }
  }, [cvText]);

  const sendMessage = (event) => {
    event.preventDefault();

    const trimmedMessage = draft.trim();
    if (!trimmedMessage) {
      return;
    }

    setMessages((previousMessages) => [
      ...previousMessages,
      { role: "user", text: trimmedMessage },
      { role: "assistant", text: "TODO" },
    ]);
    setDraft("");
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
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Type your message"
            type="text"
            value={draft}
          />
          <button className="chat-send-button" type="submit">
            Send
          </button>
        </form>
      </section>
    </main>
  );
}
