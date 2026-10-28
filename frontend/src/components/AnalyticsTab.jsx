import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import { Chips, ErrorNote, LineChart, shortDate, useRun } from "./ui";

const TREND_LABEL = { technical: "Technical", hr: "HR", behavioral: "Behavioral" };

function Tile({ label, value, sub }) {
  return <div className="tile"><strong>{value}</strong><span>{label}</span>{sub && <em>{sub}</em>}</div>;
}

function Bars({ rows, max }) {
  const top = max || Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="plain bars">
      {rows.map((r) => (
        <li key={r.label}><span className="bars-label">{r.label}</span>
          <div className="bar"><div className="bar-fill" style={{ width: `${(100 * r.value) / top}%` }} /></div>
          <strong>{r.value}</strong></li>
      ))}
    </ul>
  );
}

export default function AnalyticsTab({ profileId, go }) {
  const [a, setA] = useState(null);
  const r = useRun();
  useEffect(() => { r.run(async () => setA(await api.analytics(profileId))); /* eslint-disable-next-line */ }, [profileId]);

  if (!a) return r.error ? <ErrorNote message={r.error} onRetry={r.retry} /> : <p className="muted">Loading your progress…</p>;
  const s = a.summary;
  const nothing = !a.readiness_history.length && !s.tasks_total && !s.projects_total && !a.interviews.attempts.length;

  return (
    <div className="stack">
      <section className="panel">
        <h3>Your progress</h3>
        <p className="muted">Every number comes from your saved records. Nothing is estimated or made up.</p>
        <div className="tiles">
          <Tile label="Latest readiness" value={s.latest_readiness ?? "n/a"} />
          <Tile label="Skills learned" value={s.skills_learned} sub="all plan tasks done" />
          <Tile label="Tasks done" value={`${s.tasks_completed}/${s.tasks_total}`} />
          <Tile label="Projects done" value={`${s.projects_completed}/${s.projects_total}`} />
          <Tile label="Milestones" value={`${s.milestones_done}/${s.milestones_total}`} />
          <Tile label="Practice sessions" value={s.interview_sessions} />
        </div>
        {nothing && <p className="empty">No activity yet. Calculate a readiness score, start a study plan or practise an interview, and your progress shows up here.</p>}
      </section>

      <section className="panel">
        <h3>Readiness score over time</h3>
        {a.readiness_history.length === 0 ? <p className="empty">No readiness scores yet. Calculate one in the Readiness tab.</p> : (
          <>
            <LineChart points={a.readiness_history.map((p) => ({ x: shortDate(p.date), y: p.score }))} label="Readiness score history" />
            <p className="muted small-text">{a.readiness_history.length} score{a.readiness_history.length === 1 ? "" : "s"} saved. Latest was for {a.readiness_history[a.readiness_history.length - 1].job_title}.</p>
          </>
        )}
      </section>

      <section className="panel">
        <h3>Learning</h3>
        {s.tasks_total === 0 ? <p className="empty">No study plan yet.</p> : (
          <>
            <p>{a.learning.percent}% of all planned tasks are completed.</p>
            {a.learning.completed_by_week.length > 0 && (<><h5>Tasks completed per week</h5>
              <Bars rows={a.learning.completed_by_week.map((w) => ({ label: `Week of ${shortDate(w.week)}`, value: w.count }))} /></>)}
            <h5>Skills you have finished learning</h5>
            <Chips items={a.learning.skills_learned.map((x) => x.skill)} tone="have" empty="None yet. Finish every task for a skill and it appears here." />
          </>
        )}
      </section>

      <section className="panel">
        <h3>Projects</h3>
        {a.projects.completed.length === 0 ? <p className="empty">No completed projects yet.</p> : (
          <ul className="plain">{a.projects.completed.map((p, i) => (
            <li key={i}><strong>{p.title}</strong> <span className="muted small-text">{p.level}, finished {fmtDateTime(p.completed_at)}</span>
              {p.demo_url && <> · <a href={p.demo_url} target="_blank" rel="noopener noreferrer">demo</a></>}
              {p.repo_url && <> · <a href={p.repo_url} target="_blank" rel="noopener noreferrer">code</a></>}</li>
          ))}</ul>
        )}
      </section>

      <section className="panel">
        <h3>Interview practice</h3>
        {a.interviews.attempts.length === 0 ? <p className="empty">No scored practice sessions yet.</p> : (
          <>
            {Object.entries(a.interviews.trend).map(([mode, t]) => (
              <p key={mode}><strong>{TREND_LABEL[mode]}</strong>: {t.attempts} attempt{t.attempts === 1 ? "" : "s"}, latest {t.latest}/100
                {t.attempts > 1 && <> ({t.change >= 0 ? "+" : ""}{t.change} since the first)</>}</p>
            ))}
            <LineChart points={a.interviews.attempts.map((x) => ({ x: shortDate(x.date), y: x.avg_score }))} label="Interview average scores" />
            {a.interviews.common_missing_concepts.length > 0 && (<><h5>Concepts you often miss</h5>
              <Chips items={a.interviews.common_missing_concepts.map((c) => `${c.concept} (${c.count})`)} tone="soft" /></>)}
          </>
        )}
      </section>

      <section className="panel">
        <h3>Applications</h3>
        {s.jobs_tracked === 0 ? <p className="empty">No jobs tracked yet.</p> : (
          <>
            <Bars rows={Object.entries(a.applications.funnel).map(([k, v]) => ({ label: k, value: v }))} />
            {a.applications.upcoming_deadlines.length > 0 && (<><h5>Upcoming deadlines</h5>
              <ul className="plain">{a.applications.upcoming_deadlines.map((d) => (
                <li key={d.id}>{d.deadline}: {d.title}{d.company ? `, ${d.company}` : ""} <span className="muted small-text">({d.status})</span></li>))}</ul></>)}
          </>
        )}
      </section>

      <section className="panel">
        <h3>Skills that need more practice</h3>
        {a.practice_needed.length === 0 ? <p className="empty">Nothing flagged yet. Gaps appear after a readiness score, a study plan or interview practice.</p> : (
          <ul className="plain">{a.practice_needed.map((p) => (
            <li key={p.skill} className="issue"><strong>{p.skill}</strong><br /><span className="muted">{p.reasons.join(" · ")}</span></li>
          ))}</ul>
        )}
        <div className="actions"><button className="btn small" onClick={() => go("learning")}>Open study tracker</button></div>
      </section>
    </div>
  );
}
