import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import { Chips, ErrorNote, ScoreRing, splitList, useRun } from "./ui";

const STATUSES = ["saved", "applied", "shortlisted", "interview", "offer", "rejected"];
const MODES = ["", "remote", "hybrid", "onsite"];
const LEVELS = ["", "intern", "entry", "mid", "senior"];

function toDraft(job) {
  return {
    ...job,
    company: job.company || "", location: job.location || "", work_mode: job.work_mode || "",
    experience_level: job.experience_level || "", deadline: job.deadline || "", notes: job.notes || "",
    required_text: (job.required_skills || []).join(", "), preferred_text: (job.preferred_skills || []).join(", "),
  };
}

function fromDraft(d) {
  const nn = (v) => (String(v).trim() === "" ? null : String(v).trim());
  return {
    title: d.title.trim(), company: nn(d.company), location: nn(d.location), work_mode: nn(d.work_mode),
    experience_level: nn(d.experience_level), deadline: nn(d.deadline), notes: nn(d.notes),
    required_skills: splitList(d.required_text), preferred_skills: splitList(d.preferred_text),
    source: d.source, jd_text: d.jd_text || null,
  };
}

function Adder({ profileId, onSaved, notify }) {
  const [mode, setMode] = useState("jd");
  const [text, setText] = useState("");
  const [role, setRole] = useState("");
  const [draft, setDraft] = useState(null);
  const x = useRun();
  const s = useRun();
  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const extract = () => x.run(async () => {
    if (mode === "jd" && text.trim().length < 50) throw new Error("Paste the full job description. It looks too short.");
    if (mode === "role" && role.trim().length < 2) throw new Error("Type a role title, for example Data Analyst.");
    const res = await api.extractJob(profileId, mode === "jd" ? { jd_text: text } : { role_title: role });
    setDraft(toDraft(res.job));
  });

  const save = () => s.run(async () => {
    const payload = fromDraft(draft);
    if (!payload.title) throw new Error("Add a job title.");
    if (!payload.required_skills.length && !payload.preferred_skills.length) throw new Error("Add at least one skill.");
    const res = await api.createJob(profileId, payload);
    notify({ kind: "ok", text: res.message });
    setDraft(null); setText(""); setRole("");
    onSaved();
  });

  if (draft) {
    return (
      <section className="panel">
        <h3>Check the details</h3>
        <p className="muted">
          {draft.source === "role_title"
            ? "These are typical requirements for the role, written by AI. Edit them to match real postings."
            : "Fix anything the AI got wrong. Nothing is saved until you confirm."}
        </p>
        <div className="grid2">
          <label className="field"><span className="field-label">Title</span><input value={draft.title} onChange={(e) => set("title", e.target.value)} /></label>
          <label className="field"><span className="field-label">Company</span><input value={draft.company} onChange={(e) => set("company", e.target.value)} /></label>
          <label className="field"><span className="field-label">Location</span><input value={draft.location} onChange={(e) => set("location", e.target.value)} /></label>
          <label className="field"><span className="field-label">Application deadline</span><input type="date" value={draft.deadline} onChange={(e) => set("deadline", e.target.value)} /></label>
          <label className="field"><span className="field-label">Work mode</span>
            <select value={draft.work_mode} onChange={(e) => set("work_mode", e.target.value)}>{MODES.map((m) => <option key={m} value={m}>{m || "not stated"}</option>)}</select></label>
          <label className="field"><span className="field-label">Experience level</span>
            <select value={draft.experience_level} onChange={(e) => set("experience_level", e.target.value)}>{LEVELS.map((m) => <option key={m} value={m}>{m || "not stated"}</option>)}</select></label>
        </div>
        <label className="field"><span className="field-label">Required skills (comma separated)</span><input value={draft.required_text} onChange={(e) => set("required_text", e.target.value)} /></label>
        <label className="field"><span className="field-label">Nice-to-have skills (comma separated)</span><input value={draft.preferred_text} onChange={(e) => set("preferred_text", e.target.value)} /></label>
        <label className="field"><span className="field-label">Notes</span><textarea rows={2} value={draft.notes} onChange={(e) => set("notes", e.target.value)} /></label>
        <ErrorNote message={s.error} onRetry={s.retry} />
        <div className="actions">
          <button className="btn primary" disabled={s.busy} onClick={save}>{s.busy ? "Saving…" : "Confirm and save"}</button>
          <button className="btn ghost" onClick={() => setDraft(null)}>Discard</button>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <h3>Add a job or target role</h3>
      <div className="tabs">
        <button className={mode === "jd" ? "tab on" : "tab"} onClick={() => setMode("jd")}>Paste a job description</button>
        <button className={mode === "role" ? "tab on" : "tab"} onClick={() => setMode("role")}>Just a role title</button>
      </div>
      {mode === "jd" ? (
        <label className="field"><span className="field-label">Job description</span>
          <textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full job description" /></label>
      ) : (
        <label className="field"><span className="field-label">Role title</span>
          <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="For example: Data Analyst, ML Engineer, Frontend Intern" /></label>
      )}
      <ErrorNote message={x.error} onRetry={x.retry} />
      <div className="actions">
        <button className="btn primary" disabled={x.busy} onClick={extract}>{x.busy ? "Reading…" : "Extract requirements"}</button>
        {x.busy && <span className="muted small-text">This usually takes 5 to 20 seconds.</span>}
      </div>
    </section>
  );
}

function JobCard({ job, profileId, reload, notify }) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState(job.notes || "");
  const [deadline, setDeadline] = useState(job.deadline || "");
  const r = useRun();
  const m = job.match;

  const patch = (body, msg) => r.run(async () => { await api.patchJob(profileId, job.id, body); if (msg) notify({ kind: "ok", text: msg }); reload(); });
  const remove = () => {
    if (window.confirm(`Delete "${job.title}"? Its readiness reports stay in your history.`)) {
      r.run(async () => { await api.deleteJob(profileId, job.id); reload(); });
    }
  };
  const tags = [job.location, job.work_mode, job.experience_level, job.deadline && `Deadline ${job.deadline}`].filter(Boolean);
  const missingReq = new Set((m?.missing_required || []).map((s) => s.toLowerCase()));
  const missingPref = new Set((m?.missing_preferred || []).map((s) => s.toLowerCase()));

  return (
    <article className="job">
      <div className="job-top">
        {m && <ScoreRing value={m.score} size={64} label="Match score" />}
        <div className="job-main">
          <h4>{job.title}{job.company ? `, ${job.company}` : ""}</h4>
          {tags.length > 0 && <p className="muted small-text">{tags.join(" · ")}</p>}
          {m && <p className="small-text">{m.explanation}</p>}
        </div>
        <label className="status-pick">
          <span className="sr">Application status</span>
          <select value={job.status} onChange={(e) => patch({ status: e.target.value })}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
        </label>
      </div>
      <button className="link" onClick={() => setOpen((o) => !o)}>{open ? "Hide details" : "Show details"}</button>
      {open && (
        <div className="job-detail">
          <h5>Required skills</h5>
          <ul className="chips">{job.required_skills.map((s) => <li key={s} className={`chip ${missingReq.has(s.toLowerCase()) ? "chip-gap" : "chip-have"}`}>{s}</li>)}</ul>
          {job.preferred_skills.length > 0 && <><h5>Nice to have</h5>
            <ul className="chips">{job.preferred_skills.map((s) => <li key={s} className={`chip ${missingPref.has(s.toLowerCase()) ? "chip-soft" : "chip-have"}`}>{s}</li>)}</ul></>}
          <div className="grid2">
            <label className="field"><span className="field-label">Deadline</span><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
            <label className="field"><span className="field-label">Notes</span><textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          </div>
          <ErrorNote message={r.error} onRetry={r.retry} />
          <div className="actions">
            <button className="btn small" onClick={() => patch({ notes: notes || null, deadline: deadline || null }, "Job updated.")}>Save notes and deadline</button>
            <button className="btn small danger" onClick={remove}>Delete job</button>
          </div>
          <h5>Status history</h5>
          <ul className="plain">{(job.status_history || []).map((h, i) => <li key={i} className="small-text">{h.status}, {fmtDateTime(h.at)}</li>)}</ul>
        </div>
      )}
    </article>
  );
}

export default function JobsTab({ profileId, jobs, reloadJobs, notify }) {
  const [filters, setFilters] = useState({ q: "", location: "", work_mode: "", experience_level: "", status: "", sort: "match" });
  const [rows, setRows] = useState(jobs);
  const l = useRun();
  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    let live = true;
    l.run(async () => { const r = await api.listJobs(profileId, filters); if (live) setRows(r.jobs); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, filters, jobs]);

  const refresh = () => reloadJobs();
  const counts = STATUSES.map((s) => [s, jobs.filter((j) => j.status === s).length]);

  return (
    <div className="stack">
      <Adder profileId={profileId} onSaved={refresh} notify={notify} />
      <section className="panel">
        <h3>Your jobs and applications</h3>
        {jobs.length > 0 && <ul className="chips">{counts.map(([s, n]) => <li key={s} className="chip chip-plain">{s}: {n}</li>)}</ul>}
        {jobs.length === 0 ? <p className="empty">No jobs saved yet. Add one above to see your match score.</p> : (
          <>
            <div className="filters">
              <input aria-label="Search title or company" placeholder="Search role or company" value={filters.q} onChange={(e) => set("q", e.target.value)} />
              <input aria-label="Location" placeholder="Location" value={filters.location} onChange={(e) => set("location", e.target.value)} />
              <select aria-label="Work mode" value={filters.work_mode} onChange={(e) => set("work_mode", e.target.value)}>{MODES.map((m) => <option key={m} value={m}>{m || "any work mode"}</option>)}</select>
              <select aria-label="Experience level" value={filters.experience_level} onChange={(e) => set("experience_level", e.target.value)}>{LEVELS.map((m) => <option key={m} value={m}>{m || "any level"}</option>)}</select>
              <select aria-label="Status" value={filters.status} onChange={(e) => set("status", e.target.value)}><option value="">any status</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select>
              <select aria-label="Sort" value={filters.sort} onChange={(e) => set("sort", e.target.value)}>
                <option value="match">best match first</option><option value="deadline">nearest deadline</option><option value="newest">newest</option></select>
            </div>
            <ErrorNote message={l.error} onRetry={l.retry} />
            {rows.length === 0 ? <p className="empty">No jobs match these filters.</p> : rows.map((j) => (
              <JobCard key={j.id} job={j} profileId={profileId} reload={refresh} notify={notify} />
            ))}
          </>
        )}
      </section>
    </div>
  );
}
