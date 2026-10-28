import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import { Bar, Chips, ErrorNote, JobSelect, LineChart, shortDate, useRun } from "./ui";

const MODES = [["technical", "Technical"], ["hr", "HR"], ["behavioral", "Behavioral"]];

function Feedback({ fb, mode }) {
  return (
    <div className="feedback">
      <div className="fb-scores">
        <Bar label="Relevance" value={fb.relevance * 10} />
        <Bar label="Clarity" value={fb.clarity * 10} />
        <Bar label="Completeness" value={fb.completeness * 10} />
      </div>
      <p><strong>Overall: {fb.overall}/100</strong></p>
      {fb.strengths.length > 0 && <><h5>What worked</h5><ul>{fb.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul></>}
      {fb.improvements.length > 0 && <><h5>How to improve</h5><ul>{fb.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul></>}
      {fb.missing_concepts.length > 0 && <><h5>Concepts you missed</h5><Chips items={fb.missing_concepts} tone="soft" /></>}
      {fb.sample_structure.length > 0 && (
        <><h5>{mode === "behavioral" ? "Answer with the STAR method" : "A strong answer structure"}</h5>
          <ol>{fb.sample_structure.map((s, i) => <li key={i}>{s}</li>)}</ol></>
      )}
    </div>
  );
}

function Question({ q, n, mode, profileId, sessionId, onUpdated }) {
  const [text, setText] = useState(q.answer || "");
  const [editing, setEditing] = useState(!q.answer);
  const r = useRun();
  const submit = () => r.run(async () => {
    const res = await api.answerQuestion(profileId, sessionId, q.id, text);
    setEditing(false);
    onUpdated(res);
  });
  return (
    <article className="qcard">
      <h4>{n}. {q.question}</h4>
      <p className="muted small-text">{[q.focus, q.difficulty].filter(Boolean).join(" · ")}</p>
      {editing ? (
        <>
          <label className="field"><span className="sr">Your answer</span>
            <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="Type your answer as you would say it in the interview" /></label>
          <ErrorNote message={r.error} onRetry={r.retry} />
          <div className="actions">
            <button className="btn primary small" disabled={r.busy} onClick={submit}>{r.busy ? "Evaluating…" : "Get feedback"}</button>
            {q.answer && <button className="btn ghost small" onClick={() => { setEditing(false); setText(q.answer); }}>Cancel</button>}
          </div>
        </>
      ) : (
        <>
          <p className="your-answer">{q.answer}</p>
          {q.feedback && <Feedback fb={q.feedback} mode={mode} />}
          <button className="link" onClick={() => setEditing(true)}>Answer again</button>
        </>
      )}
    </article>
  );
}

function Trend({ sessions }) {
  const done = sessions.filter((s) => s.avg_score != null).slice().reverse();
  if (done.length < 1) return null;
  return (
    <section className="panel">
      <h3>Your improvement</h3>
      {MODES.map(([k, label]) => {
        const pts = done.filter((s) => s.mode === k).map((s) => ({ x: shortDate(s.created_at), y: s.avg_score }));
        if (!pts.length) return null;
        const change = pts.length > 1 ? pts[pts.length - 1].y - pts[0].y : null;
        return (
          <div key={k} className="trend">
            <h5>{label}: {pts.length} attempt{pts.length === 1 ? "" : "s"}{change != null && `, ${change >= 0 ? "+" : ""}${change} since your first`}</h5>
            <LineChart points={pts} height={120} label={`${label} interview average scores`} />
          </div>
        );
      })}
    </section>
  );
}

export default function InterviewTab({ profileId, jobs }) {
  const [sessions, setSessions] = useState([]);
  const [open, setOpen] = useState(null);
  const [mode, setMode] = useState("technical");
  const [jobId, setJobId] = useState(null);
  const [role, setRole] = useState("");
  const [count, setCount] = useState(5);
  const start = useRun();
  const load = useRun();

  const refresh = () => api.listInterviews(profileId).then((r) => setSessions(r.sessions)).catch(() => {});
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [profileId]);

  const create = () => start.run(async () => {
    if (!jobId && !role.trim()) throw new Error("Choose a saved job or type the role you are preparing for.");
    const res = await api.createInterview(profileId, { mode, job_id: jobId, target_role: role, count: Number(count) });
    setOpen(res.session);
    refresh();
  });
  const openSession = (id) => load.run(async () => setOpen((await api.getInterview(profileId, id)).session));
  const removeSession = async (id) => {
    if (!window.confirm("Delete this practice session?")) return;
    await api.deleteInterview(profileId, id);
    if (open?.id === id) setOpen(null);
    refresh();
  };
  const updated = (res) => {
    setOpen((s) => ({ ...s, avg_score: res.session.avg_score, answered_count: res.session.answered_count,
      questions: s.questions.map((q) => (q.id === res.question.id ? res.question : q)) }));
    refresh();
  };

  return (
    <div className="stack">
      <section className="panel">
        <h3>Mock interview coach</h3>
        <p className="muted">Questions come from your resume and the role. Answer in text and get feedback on relevance, clarity and missing concepts.</p>
        <div className="tabs" role="group" aria-label="Interview mode">
          {MODES.map(([k, label]) => <button key={k} className={mode === k ? "tab on" : "tab"} aria-pressed={mode === k} onClick={() => setMode(k)}>{label}</button>)}
        </div>
        <JobSelect jobs={jobs} value={jobId} onChange={setJobId} allowNone label="Practice for a saved job" />
        {!jobId && (
          <label className="field"><span className="field-label">Or type a role</span>
            <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="For example: Backend Intern" /></label>
        )}
        <label className="field"><span className="field-label">Number of questions</span>
          <select value={count} onChange={(e) => setCount(e.target.value)}>{[3, 4, 5, 6, 8].map((n) => <option key={n}>{n}</option>)}</select></label>
        <ErrorNote message={start.error} onRetry={start.retry} />
        <div className="actions">
          <button className="btn primary" disabled={start.busy} onClick={create}>{start.busy ? "Writing questions…" : "Start a practice session"}</button>
          {start.busy && <span className="muted small-text">This usually takes 5 to 20 seconds.</span>}
        </div>
      </section>

      {open && (
        <section className="panel">
          <div className="panel-head">
            <h3>{MODES.find((m) => m[0] === open.mode)?.[1]} practice: {open.target_role}</h3>
            <span className="tag">{open.answered_count}/{open.questions.length} answered{open.avg_score != null && `, average ${open.avg_score}`}</span>
          </div>
          {open.questions.map((q, i) => (
            <Question key={q.id} q={q} n={i + 1} mode={open.mode} profileId={profileId} sessionId={open.id} onUpdated={updated} />
          ))}
        </section>
      )}

      <Trend sessions={sessions} />

      {sessions.length > 0 && (
        <section className="panel">
          <h3>Previous attempts</h3>
          <ErrorNote message={load.error} />
          <ul className="list">
            {sessions.map((s) => (
              <li key={s.id} className="list-line">
                <button className="list-row four" onClick={() => openSession(s.id)}>
                  <span className="list-name">{s.mode} · {s.target_role}</span>
                  <span className="muted">{s.answered_count}/{s.question_count} answered</span>
                  <strong>{s.avg_score != null ? `${s.avg_score}/100` : "not scored"}</strong>
                  <span className="muted small-text">{fmtDateTime(s.created_at)}</span>
                </button>
                <button className="link" onClick={() => removeSession(s.id)}>Delete</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
