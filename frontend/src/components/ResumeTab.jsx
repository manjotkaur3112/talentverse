import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import { Chips, ErrorNote, JobSelect, NeedJob, ScoreRing, copyText, useRun } from "./ui";

function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function Result({ o, notify }) {
  return (
    <div className="stack">
      <div className="notice notice-info">
        <span>Everything below is built from what is already in your profile. Skills, tools and numbers you never wrote are blocked automatically.
          {o.dropped_suggestions > 0 && ` ${o.dropped_suggestions} AI suggestion${o.dropped_suggestions === 1 ? " was" : "s were"} blocked because they added facts you did not write.`}
          {o.summary_rejected && " The AI's summary was replaced because it added claims your profile doesn't support."}
        </span>
      </div>

      <div className="result">
        <ScoreRing value={o.keyword_score} label="Keyword match" />
        <div className="result-body">
          <h4>Keyword match for {o.job_title}</h4>
          <p className="muted small-text">Share of the job's required and nice-to-have keywords that appear in your profile.</p>
          <h5>Keywords you already show</h5><Chips items={o.present_keywords} tone="have" />
          <h5>Missing keywords</h5><Chips items={o.missing_keywords} tone="gap" />
          {o.missing_keywords.length > 0 && <p className="muted small-text">Only add a keyword if you really have that skill. If you don't, treat it as something to learn.</p>}
        </div>
      </div>

      {o.unsupported_claims.length > 0 && (
        <section className="panel">
          <h3>Claims your profile doesn't back up</h3>
          <ul className="plain">{o.unsupported_claims.map((c, i) => (
            <li key={i} className="issue"><strong>{c.claim}</strong><br /><span className="muted">{c.issue} {c.suggestion}</span></li>
          ))}</ul>
        </section>
      )}

      {o.unclear_items.length > 0 && (
        <section className="panel">
          <h3>Unclear or weak statements</h3>
          <ul className="plain">{o.unclear_items.map((u, i) => (
            <li key={i} className="issue"><q>{u.text}</q><br /><span className="muted"><strong>Issue:</strong> {u.issue} <strong>Fix:</strong> {u.suggestion}</span></li>
          ))}</ul>
        </section>
      )}

      <section className="panel">
        <h3>Stronger wording</h3>
        {o.bullet_fixes.length === 0 ? <p className="empty">No safe rewrites to suggest.</p> : o.bullet_fixes.map((b) => (
          <div key={b.id} className="diff">
            <p className="before"><span className="tag">Before</span> {b.original}</p>
            <p className="after"><span className="tag tag-ok">After</span> {b.improved}</p>
            <p className="muted small-text">{b.reason} <button className="link" onClick={() => copyText(b.improved, notify)}>Copy</button></p>
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Tailored resume draft</h3>
          <div className="actions tight">
            <button className="btn small" onClick={() => copyText(o.draft, notify)}>Copy</button>
            <button className="btn small" onClick={() => download("tailored-resume.md", o.draft)}>Download .md</button>
          </div>
        </div>
        <p className="muted small-text">Check every line before you send it. The draft only reorders and rewords your saved facts.</p>
        <pre className="draft">{o.draft}</pre>
      </section>
    </div>
  );
}

export default function ResumeTab({ profileId, jobs, go, notify }) {
  const [jobId, setJobId] = useState(jobs[0]?.id ?? null);
  const [history, setHistory] = useState([]);
  const [shown, setShown] = useState(null);
  const r = useRun();

  useEffect(() => {
    api.listOptimizations(profileId).then((x) => {
      setHistory(x.optimizations);
      setShown(x.optimizations.find((o) => o.job_id === jobId) || null);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId]);

  const pick = (id) => { setJobId(id); setShown(history.find((o) => o.job_id === id) || null); };
  const run = () => r.run(async () => {
    const res = await api.optimize(profileId, jobId);
    setShown(res.optimization);
    setHistory((h) => [res.optimization, ...h]);
  });

  if (!jobs.length) return <section className="panel"><h3>ATS resume optimizer</h3><NeedJob go={go} /></section>;
  return (
    <div className="stack">
      <section className="panel">
        <h3>ATS resume optimizer</h3>
        <p className="muted">Compare your profile with a job, find missing keywords, tighten your wording and get a tailored draft. It never adds skills or experience you don't have.</p>
        <JobSelect jobs={jobs} value={jobId} onChange={pick} />
        <ErrorNote message={r.error} onRetry={r.retry} />
        <div className="actions">
          <button className="btn primary" disabled={!jobId || r.busy} onClick={run}>{r.busy ? "Analyzing…" : "Analyze and tailor my resume"}</button>
          {r.busy && <span className="muted small-text">This can take 10 to 30 seconds.</span>}
          {shown && !r.busy && <span className="muted small-text">Showing the result from {fmtDateTime(shown.created_at)}.</span>}
        </div>
      </section>
      {shown && <Result o={shown} notify={notify} />}
    </div>
  );
}
