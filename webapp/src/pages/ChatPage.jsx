import { useState } from "react";
import { Link } from "react-router-dom";

export default function ChatPage() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState([]);

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

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>AI chat</h1>
        <Link className="back-link" to="/jobs">
          Back to all roles
        </Link>
      </header>

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
