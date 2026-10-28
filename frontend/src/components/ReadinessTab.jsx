import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import { Bar, Chips, ErrorNote, JobSelect, NeedJob, ScoreRing, useRun } from "./ui";

const LEVEL_TEXT = { intern: "internship", entry: "entry-level", mid: "mid-level", senior: "senior" };

function Report({ r }) {
  const c = r.components;
  return (
    <div className="result">
      <ScoreRing value={r.score} label="Readiness score" />
      <div className="result-body">
        <h4>{r.job_title}: {r.score}/100</h4>
        <p className="muted small-text">Measured for {LEVEL_TEXT[r.level] || "entry-level"} expectations. Skills count 60%, experience 20%, projects 20%.</p>
        <Bar label="Skills" value={c.skills} note="Skills with proof in a project or experience count fully. Skills only listed count 60%." />
        <Bar label="Experience" value={c.experience} note={`${r.experience_months} month${r.experience_months === 1 ? "" : "s"} of dated experience.`} />
        <Bar label="Projects" value={c.projects} note={`${r.relevant_projects} project${r.relevant_projects === 1 ? "" : "s"} using this role's skills.`} />

        <h5>Strong skills</h5>
        <ul className="chips">
          {r.strong_skills.length === 0 && <li className="empty">None yet</li>}
          {r.strong_skills.map((s) => (
            <li key={s.name} className={`chip ${s.verified ? "chip-have" : "chip-soft"}`}>{s.name}{s.verified ? "" : " (listed, not proven)"}</li>
          ))}
        </ul>
        <h5>Required skills you're missing</h5><Chips items={r.missing_required} tone="gap" />
        <h5>Nice-to-have skills you're missing</h5><Chips items={r.missing_preferred} tone="soft" />

        {(r.experience_gaps.length > 0 || r.project_gaps.length > 0) && (
          <>
            <h5>Experience and project gaps</h5>
            <ul>{[...r.experience_gaps, ...r.project_gaps].map((g, i) => <li key={i}>{g}</li>)}</ul>
          </>
        )}

        <h5>How to improve this score {r.recommendations_source === "rules" && <span className="muted small-text">(rule-based, AI was unavailable)</span>}</h5>
        <ol className="recs">
          {r.recommendations.map((x, i) => (
            <li key={i}><span className={`impact impact-${x.impact}`}>{x.impact}</span> <strong>{x.action}</strong><br /><span className="muted">{x.why}</span></li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export default function ReadinessTab({ profileId, jobs, go, notify }) {
  const [jobId, setJobId] = useState(jobs[0]?.id ?? null);
  const [reports, setReports] = useState([]);
  const [shown, setShown] = useState(null);
  const r = useRun();

  useEffect(() => {
    if (!jobId) { setReports([]); setShown(null); return; }
    api.listReadiness(profileId, jobId).then((x) => { setReports(x.reports); setShown(x.reports[0] || null); }).catch(() => {});
  }, [profileId, jobId]);

  const calc = () => r.run(async () => {
    const res = await api.createReadiness(profileId, jobId);
    setShown(res.report);
    setReports((prev) => [res.report, ...prev]);
    notify({ kind: "ok", text: `Readiness saved: ${res.report.score}/100.` });
  });

  if (!jobs.length) return <section className="panel"><h3>Career readiness score</h3><NeedJob go={go} /></section>;
  return (
    <div className="stack">
      <section className="panel">
        <h3>Career readiness score</h3>
        <p className="muted">How ready your saved profile is for a role, scored out of 100 from your skills, experience and projects.</p>
        <JobSelect jobs={jobs} value={jobId} onChange={setJobId} />
        <ErrorNote message={r.error} onRetry={r.retry} />
        <div className="actions">
          <button className="btn primary" disabled={!jobId || r.busy} onClick={calc}>{r.busy ? "Calculating…" : "Calculate readiness"}</button>
          {r.busy && <span className="muted small-text">This usually takes 5 to 20 seconds.</span>}
        </div>
        {shown && <Report r={shown} />}
      </section>
      {reports.length > 1 && (
        <section className="panel">
          <h3>Earlier scores for this role</h3>
          <ul className="list">
            {reports.map((x) => (
              <li key={x.id}><button className="list-row two" onClick={() => setShown(x)}><strong>{x.score}/100</strong><span className="muted small-text">{fmtDateTime(x.created_at)}</span></button></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
