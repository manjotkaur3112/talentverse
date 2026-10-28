import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ErrorNote, useRun } from "./ui";

const STARTERS = [
  "Which skill should I learn next?",
  "Why is my match score low for my saved jobs?",
  "Suggest a project using Python and NLP.",
  "Prepare me for an internship interview.",
];

export default function MentorTab({ profileId }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [pending, setPending] = useState(null);
  const r = useRun();
  const end = useRef(null);

  useEffect(() => { api.getChat(profileId).then((x) => setMessages(x.messages)).catch(() => {}); }, [profileId]);
  useEffect(() => { end.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [messages, pending]);

  const send = (msg) => r.run(async () => {
    const q = (msg ?? text).trim();
    if (!q) throw new Error("Type a question first.");
    setPending(q);
    setText("");
    try {
      const res = await api.sendChat(profileId, q);
      setMessages((m) => [...m, ...res.messages]);
    } catch (e) {
      setText(q);
      throw e;
    } finally {
      setPending(null);
    }
  });

  const clear = async () => {
    if (!window.confirm("Clear this conversation?")) return;
    await api.clearChat(profileId);
    setMessages([]);
  };

  return (
    <section className="panel chat">
      <div className="panel-head">
        <h3>Career mentor</h3>
        {messages.length > 0 && <button className="link" onClick={clear}>Clear chat</button>}
      </div>
      <p className="muted small-text">Answers use your saved profile, jobs, readiness score, study plan, projects and interview scores. If something is missing, the mentor says so.</p>

      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && !pending && (
          <div className="starters">
            {STARTERS.map((s) => <button key={s} className="chip chip-plain starter" onClick={() => send(s)}>{s}</button>)}
          </div>
        )}
        {messages.map((m) => <div key={m.id} className={`bubble bubble-${m.role}`}>{m.content}</div>)}
        {pending && <div className="bubble bubble-user">{pending}</div>}
        {pending && <div className="bubble bubble-assistant muted">Thinking…</div>}
        <div ref={end} />
      </div>

      <ErrorNote message={r.error} onRetry={r.retry} />
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input aria-label="Ask the mentor" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} placeholder="Ask about your skills, jobs, projects or interviews" />
        <button className="btn primary" disabled={r.busy}>{r.busy ? "Sending…" : "Send"}</button>
      </form>
    </section>
  );
}
