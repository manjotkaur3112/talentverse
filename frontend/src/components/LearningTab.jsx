import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNote, JobSelect, useRun } from "./ui";

const STATUS = [["pending", "To do"], ["in_progress", "In progress"], ["completed", "Done"]];

function Resources({ data, profileId, apply, notify }) {
  const skills = Object.keys(data.resources);
  const [skill, setSkill] = useState(skills[0] || "");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const r = useRun();

  const add = () => r.run(async () => {
    if (!skill || !title.trim() || !url.trim()) throw new Error("Choose a skill and add a title and a link.");
    apply(await api.addResource(profileId, { skill, title, url }));
    setTitle(""); setUrl("");
    notify({ kind: "ok", text: "Resource saved." });
  });
  const remove = (id) => r.run(async () => apply(await api.deleteResource(profileId, id)));

  return (
    <section className="panel">
      <h3>Free learning resources</h3>
      <p className="muted small-text">Official docs and free search links for each skill in your plan. Add your own below.</p>
      {skills.map((s) => (
        <div key={s} className="skill-group">
          <h5>{s}</h5>
          <ul className="plain">
            {data.resources[s].map((x) => (
              <li key={x.id}>
                <a href={x.url} target="_blank" rel="noopener noreferrer">{x.title}</a>{" "}
                <span className="muted small-text">{x.source === "user" ? "yours" : x.source === "search" ? "search" : "official"}</span>
                {x.source === "user" && <> <button className="link" onClick={() => remove(x.id)}>Remove</button></>}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <h5>Add your own resource</h5>
      <div className="row res-row">
        <select aria-label="Skill" value={skill} onChange={(e) => setSkill(e.target.value)}>{skills.map((s) => <option key={s}>{s}</option>)}</select>
        <input aria-label="Title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <input aria-label="Link" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="btn small" onClick={add}>Save</button>
      </div>
      <ErrorNote message={r.error} />
    </section>
  );
}

export default function LearningTab({ profileId, jobs, notify }) {
  const [data, setData] = useState(null);
  const [jobId, setJobId] = useState(jobs[0]?.id ?? null);
  const [weeks, setWeeks] = useState(4);
  const [hours, setHours] = useState(6);
  const load = useRun();
  const gen = useRun();
  const upd = useRun();

  useEffect(() => { load.run(async () => setData(await api.getLearning(profileId))); /* eslint-disable-next-line */ }, [profileId]);

  const generate = () => gen.run(async () => {
    if (!jobId) throw new Error("Choose the job you want to prepare for.");
    setData(await api.createPlan(profileId, { job_id: jobId, weeks: Number(weeks), hours_per_week: Number(hours) }));
    notify({ kind: "ok", text: "Study plan created." });
  });
  const setStatus = (tid, status) => upd.run(async () => setData(await api.updateTask(profileId, tid, status)));

  const plan = data?.plan;
  const byWeek = {};
  (plan?.tasks || []).forEach((t) => { (byWeek[t.week_number] ||= []).push(t); });
  const nt = data?.next_topic;

  return (
    <div className="stack">
      <section className="panel">
        <h3>{plan ? "Make a new study plan" : "Build your study plan"}</h3>
        <p className="muted">We turn the skills you're missing for a job into daily and weekly tasks. A new plan replaces the current one.</p>
        <JobSelect jobs={jobs} value={jobId} onChange={setJobId} label="Prepare for" />
        <div className="grid2">
          <label className="field"><span className="field-label">Weeks</span>
            <select value={weeks} onChange={(e) => setWeeks(e.target.value)}>{[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n}>{n}</option>)}</select></label>
          <label className="field"><span className="field-label">Hours per week</span>
            <input type="number" min="1" max="40" value={hours} onChange={(e) => setHours(e.target.value)} /></label>
        </div>
        <ErrorNote message={gen.error || load.error} onRetry={gen.error ? gen.retry : load.retry} />
        <div className="actions">
          <button className="btn primary" disabled={gen.busy || !jobs.length} onClick={generate}>{gen.busy ? "Planning…" : "Generate plan"}</button>
          {!jobs.length && <span className="muted small-text">Save a job first so the plan targets real gaps.</span>}
          {gen.busy && <span className="muted small-text">This usually takes 10 to 30 seconds.</span>}
        </div>
      </section>

      {plan && (
        <>
          <section className="panel">
            <div className="panel-head"><h3>{plan.title}</h3>
              {plan.generated_by === "template" && <span className="tag">Template plan, AI was unavailable</span>}</div>
            <div className="bar-row">
              <div className="bar-head"><span>Progress</span><strong>{data.progress.percent}%</strong></div>
              <div className="bar"><div className="bar-fill" style={{ width: `${data.progress.percent}%` }} /></div>
              <p className="muted small-text">{data.progress.completed} of {data.progress.total} tasks done, {data.progress.in_progress} in progress.</p>
            </div>
            {nt ? (
              <div className="next">
                <span className="tag tag-ok">Next topic</span>
                <h4>{nt.skill}: {nt.task_title}</h4>
                <p className="muted small-text">{nt.reason} {nt.remaining_for_skill} task{nt.remaining_for_skill === 1 ? "" : "s"} left for this skill.</p>
                {nt.task_id && <button className="btn small" onClick={() => setStatus(nt.task_id, "in_progress")}>Start this task</button>}
              </div>
            ) : <p className="ok-line"><span className="dot ok" /> Every task is done. Re-run the readiness score to see the change.</p>}
            <ErrorNote message={upd.error} onRetry={upd.retry} />
          </section>

          {Object.entries(byWeek).map(([w, tasks]) => (
            <section className="panel" key={w}>
              <h3>Week {w}</h3>
              <ul className="plain tasks">
                {tasks.map((t) => (
                  <li key={t.id} className={`task task-${t.status}`}>
                    <div>
                      <strong>{t.title}</strong>
                      <p className="muted small-text">{t.skill} · {t.cadence === "daily" ? `Daily practice${t.day_number ? `, day ${t.day_number}` : ""}` : "Weekly task"} · {t.minutes} min</p>
                      {t.description && <p className="small-text">{t.description}</p>}
                    </div>
                    <div className="seg" role="group" aria-label={`Status for ${t.title}`}>
                      {STATUS.map(([k, label]) => (
                        <button key={k} className={t.status === k ? "seg-on" : ""} aria-pressed={t.status === k} onClick={() => setStatus(t.id, k)}>{label}</button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <Resources data={data} profileId={profileId} apply={setData} notify={notify} />
        </>
      )}
    </div>
  );
}
