import { useEffect, useState } from "react";
import { api } from "../api";
import { Chips, ErrorNote, JobSelect, copyText, useRun } from "./ui";

const LEVEL_LABEL = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };
const STATUS_LABEL = { not_started: "Not started", in_progress: "In progress", completed: "Completed" };

function IdeaDetails({ p, notify }) {
  return (
    <div className="idea-body">
      <p>{p.problem_statement}</p>
      <h5>Features</h5><ul>{p.features.map((f, i) => <li key={i}>{f}</li>)}</ul>
      <h5>Tech stack</h5><Chips items={p.tech_stack} />
      <h5>Milestones</h5>
      <ol>{p.milestones.map((m, i) => <li key={i}><strong>{m.title}</strong>{m.description ? `: ${m.description}` : ""}</li>)}</ol>
      {p.datasets?.length > 0 && <><h5>Suggested datasets</h5><ul>{p.datasets.map((d, i) => <li key={i}><strong>{d.name}</strong>{d.description ? `: ${d.description}` : ""}</li>)}</ul></>}
      {p.evaluation_metrics?.length > 0 && <><h5>Evaluation metrics</h5><ul>{p.evaluation_metrics.map((m, i) => <li key={i}>{m}</li>)}</ul></>}
      {p.readme_outline?.length > 0 && <><h5>README outline</h5><ol>{p.readme_outline.map((m, i) => <li key={i}>{m}</li>)}</ol></>}
      {p.github_description && (
        <><h5>GitHub portfolio description</h5>
          <p className="quote">{p.github_description} <button className="link" onClick={() => copyText(p.github_description, notify)}>Copy</button></p></>
      )}
      {p.skills_demonstrated?.length > 0 && <><h5>Skills this shows</h5><Chips items={p.skills_demonstrated} tone="have" /></>}
    </div>
  );
}

function MyProject({ p, profileId, apply, remove, notify }) {
  const [repo, setRepo] = useState(p.repo_url || "");
  const [demo, setDemo] = useState(p.demo_url || "");
  const [open, setOpen] = useState(false);
  const r = useRun();
  const done = p.milestones.filter((m) => m.done).length;

  const patch = (body) => r.run(async () => {
    const res = await api.patchProject(profileId, p.id, body);
    apply(res.project);
    if (res.message) notify({ kind: "ok", text: res.message });
  });
  const toggle = (m) => r.run(async () => apply((await api.patchMilestone(profileId, p.id, m.id, !m.done)).project));

  return (
    <article className="idea">
      <div className="panel-head">
        <div><h4>{p.title}</h4><p className="muted small-text">{LEVEL_LABEL[p.level]} · {done}/{p.milestones.length} milestones</p></div>
        <select aria-label="Project status" value={p.status} onChange={(e) => patch({ status: e.target.value })}>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <div className="bar"><div className="bar-fill" style={{ width: `${p.milestones.length ? (100 * done) / p.milestones.length : 0}%` }} /></div>
      <ul className="plain checks">
        {p.milestones.map((m) => (
          <li key={m.id}><label><input type="checkbox" checked={m.done} onChange={() => toggle(m)} /> {m.title}</label></li>
        ))}
      </ul>
      <div className="grid2">
        <label className="field"><span className="field-label">GitHub repo link</span><input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="https://github.com/you/project" /></label>
        <label className="field"><span className="field-label">Live demo link</span><input value={demo} onChange={(e) => setDemo(e.target.value)} placeholder="https://your-demo.vercel.app" /></label>
      </div>
      <ErrorNote message={r.error} />
      <div className="actions">
        <button className="btn small" onClick={() => patch({ repo_url: repo, demo_url: demo })}>Save links</button>
        <button className="link" onClick={() => setOpen((o) => !o)}>{open ? "Hide project plan" : "Show project plan"}</button>
        <button className="link" onClick={() => remove(p.id)}>Delete</button>
      </div>
      {p.status === "completed" && <p className="ok-line"><span className="dot ok" /> Completed{p.demo_url ? <> · <a href={p.demo_url} target="_blank" rel="noopener noreferrer">live demo</a></> : null}</p>}
      {open && <IdeaDetails p={p} notify={notify} />}
    </article>
  );
}

export default function ProjectsTab({ profileId, jobs, notify }) {
  const [goal, setGoal] = useState("");
  const [jobId, setJobId] = useState(null);
  const [ideas, setIdeas] = useState([]);
  const [mine, setMine] = useState([]);
  const gen = useRun();
  const sv = useRun();

  useEffect(() => { api.listProjects(profileId).then((r) => setMine(r.projects)).catch(() => {}); }, [profileId]);

  const generate = () => gen.run(async () => {
    if (!jobId && goal.trim().length < 3) throw new Error("Describe your career goal or choose a saved job.");
    setIdeas((await api.projectIdeas(profileId, { goal, job_id: jobId })).ideas);
  });
  const add = (idea) => sv.run(async () => {
    const res = await api.saveProject(profileId, idea, jobId);
    setMine((m) => [res.project, ...m]);
    setIdeas((list) => list.filter((i) => i !== idea));
    notify({ kind: "ok", text: res.message });
  });
  const apply = (p) => setMine((m) => m.map((x) => (x.id === p.id ? p : x)));
  const remove = async (id) => {
    if (!window.confirm("Delete this project?")) return;
    await api.deleteProject(profileId, id);
    setMine((m) => m.filter((x) => x.id !== id));
  };

  return (
    <div className="stack">
      <section className="panel">
        <h3>Smart project and portfolio builder</h3>
        <p className="muted">Turn a career goal into three projects, from beginner to advanced, that prove the skills the role needs.</p>
        <JobSelect jobs={jobs} value={jobId} onChange={setJobId} allowNone label="Build for a saved job" />
        <label className="field"><span className="field-label">{jobId ? "Anything to add? (optional)" : "Or describe your career goal"}</span>
          <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="For example: become a machine learning engineer" /></label>
        <ErrorNote message={gen.error} onRetry={gen.retry} />
        <div className="actions">
          <button className="btn primary" disabled={gen.busy} onClick={generate}>{gen.busy ? "Designing projects…" : "Suggest projects"}</button>
          {gen.busy && <span className="muted small-text">This usually takes 10 to 30 seconds.</span>}
        </div>
      </section>

      {ideas.length > 0 && (
        <section className="panel">
          <h3>Pick the ones you want to build</h3>
          <ErrorNote message={sv.error} onRetry={sv.retry} />
          {ideas.map((p) => (
            <article key={p.title} className="idea">
              <div className="panel-head"><div><span className="tag">{LEVEL_LABEL[p.level]}</span><h4>{p.title}</h4></div>
                <button className="btn small primary" disabled={sv.busy} onClick={() => add(p)}>Add to my projects</button></div>
              <IdeaDetails p={p} notify={notify} />
            </article>
          ))}
        </section>
      )}

      <section className="panel">
        <h3>My projects</h3>
        {mine.length === 0 ? <p className="empty">Nothing here yet. Add a suggested project to start tracking it.</p>
          : mine.map((p) => <MyProject key={p.id} p={p} profileId={profileId} apply={apply} remove={remove} notify={notify} />)}
      </section>
    </div>
  );
}
