import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";

const CATS = ["language", "framework", "tool", "soft", "other"];
const LEVELS = ["", "beginner", "intermediate", "advanced"];
const DATE_RE = /^\d{4}-(0[1-9]|1[0-2])$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function toEditor(p) {
  return {
    full_name: p.full_name || "",
    email: p.email || "",
    summary: p.summary || "",
    skills: p.skills.map((s) => ({ ...s, proficiency: s.proficiency || "" })),
    experience: p.experience.map((e) => ({
      role: e.role, organization: e.organization || "", start_date: e.start_date || "", end_date: e.end_date || "",
      highlights_text: (e.highlights || []).join("\n"),
    })),
    education: p.education.map((e) => ({ degree: e.degree, institution: e.institution || "", year: e.year ?? "" })),
    projects: p.projects.map((x) => ({ title: x.title, tech_text: (x.tech || []).join(", "), description: x.description || "" })),
  };
}

const orNull = (v) => (String(v).trim() === "" ? null : String(v).trim());
const blank = (o, keys) => keys.every((k) => String(o[k] ?? "").trim() === "");

function toPayload(ed) {
  const errors = [];
  const skills = ed.skills.filter((s) => s.name.trim()).map((s) => ({ name: s.name.trim(), category: s.category, proficiency: orNull(s.proficiency) }));

  const experience = [];
  ed.experience.forEach((e, i) => {
    if (blank(e, ["role", "organization", "start_date", "end_date", "highlights_text"])) return;
    if (!e.role.trim()) errors.push(`Experience ${i + 1}: add a role.`);
    if (e.start_date && !DATE_RE.test(e.start_date)) errors.push(`Experience ${i + 1}: start date must look like 2024-06.`);
    if (e.end_date && !DATE_RE.test(e.end_date)) errors.push(`Experience ${i + 1}: end date must look like 2024-06.`);
    if (e.start_date && e.end_date && e.start_date > e.end_date) errors.push(`Experience ${i + 1}: start date is after the end date.`);
    experience.push({
      role: e.role.trim(), organization: orNull(e.organization), start_date: orNull(e.start_date), end_date: orNull(e.end_date),
      highlights: e.highlights_text.split("\n").map((h) => h.trim()).filter(Boolean),
    });
  });

  const education = [];
  ed.education.forEach((e, i) => {
    if (blank(e, ["degree", "institution", "year"])) return;
    if (!e.degree.trim()) errors.push(`Education ${i + 1}: add a degree.`);
    const year = e.year === "" ? null : Number(e.year);
    if (year !== null && (!Number.isInteger(year) || year < 1950 || year > 2100)) errors.push(`Education ${i + 1}: year must be between 1950 and 2100.`);
    education.push({ degree: e.degree.trim(), institution: orNull(e.institution), year });
  });

  const projects = [];
  ed.projects.forEach((x, i) => {
    if (blank(x, ["title", "tech_text", "description"])) return;
    if (!x.title.trim()) errors.push(`Project ${i + 1}: add a title.`);
    projects.push({ title: x.title.trim(), tech: x.tech_text.split(",").map((t) => t.trim()).filter(Boolean), description: x.description.trim() });
  });

  const email = orNull(ed.email);
  if (email && !EMAIL_RE.test(email)) errors.push("Email doesn't look valid.");

  return { errors, payload: { full_name: orNull(ed.full_name), email, summary: orNull(ed.summary), skills, experience, education, projects } };
}

function Field({ label, value, onChange, missing, ...rest }) {
  const isMissing = missing && String(value).trim() === "";
  return (
    <label className={`field ${isMissing ? "is-missing" : ""}`}>
      <span className="field-label">
        {label}
        {isMissing && <span className="flag">Not found. Add it if you want it saved.</span>}
      </span>
      <input value={value} onChange={(e) => onChange(e.target.value)} {...rest} />
    </label>
  );
}

export default function Preview({ draft, onCancel, onSaved, notify }) {
  const [ed, setEd] = useState(() => toEditor(draft));
  const [targets, setTargets] = useState([]);
  const [target, setTarget] = useState("new");
  const [mode, setMode] = useState("merge");
  const [saving, setSaving] = useState(false);
  const [problems, setProblems] = useState([]);

  useEffect(() => {
    api.listProfiles().then((r) => setTargets(r.profiles)).catch(() => {});
  }, []);

  const missing = useMemo(() => draft.missing_fields || [], [draft]);
  const set = (k, v) => setEd((p) => ({ ...p, [k]: v }));
  const setItem = (list, i, patch) => setEd((p) => ({ ...p, [list]: p[list].map((x, j) => (j === i ? { ...x, ...patch } : x)) }));
  const remove = (list, i) => setEd((p) => ({ ...p, [list]: p[list].filter((_, j) => j !== i) }));
  const add = (list, item) => setEd((p) => ({ ...p, [list]: [...p[list], item] }));

  async function confirm() {
    const { errors, payload } = toPayload(ed);
    setProblems(errors);
    if (errors.length) return;
    setSaving(true);
    try {
      const body = { profile: payload };
      if (target !== "new") { body.profile_id = Number(target); body.mode = mode; }
      const res = await api.saveProfile(body);
      onSaved(res);
    } catch (e) {
      const detail = (e.details || []).map((d) => `${d.field}: ${d.message}`);
      setProblems([e.message, ...detail]);
      notify({ kind: "error", text: "Couldn't save your profile.", actionLabel: "Retry", onAction: confirm });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="review">
      <div className="panel status">
        <h2>Check what we found</h2>
        <p className="muted">
          Nothing is saved yet. Fix anything that looks wrong, fill in what's missing, then confirm.
        </p>
        <p className="ok-line"><span className="dot ok" /> The extracted data passed validation.</p>
        {missing.length > 0 && (
          <p className="warn-line">
            <span className="dot warn" /> Not found in your resume: {missing.map((m) => m.replace(/_/g, " ")).join(", ")}.
          </p>
        )}
      </div>

      <div className="panel">
        <h3>About you</h3>
        <div className="grid2">
          <Field label="Full name" value={ed.full_name} onChange={(v) => set("full_name", v)} missing />
          <Field label="Email" type="email" value={ed.email} onChange={(v) => set("email", v)} missing />
        </div>
        <label className={`field ${ed.summary.trim() === "" ? "is-missing" : ""}`}>
          <span className="field-label">Summary {ed.summary.trim() === "" && <span className="flag">Not found. Add it if you want it saved.</span>}</span>
          <textarea rows={3} value={ed.summary} onChange={(e) => set("summary", e.target.value)} />
        </label>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Skills</h3><button className="btn small ghost" onClick={() => add("skills", { name: "", category: "other", proficiency: "" })}>Add skill</button></div>
        {ed.skills.length === 0 && <p className="empty">No skills found. Add the ones you want matched against jobs.</p>}
        {ed.skills.map((s, i) => (
          <div className="row skill-row" key={i}>
            <input aria-label="Skill name" value={s.name} onChange={(e) => setItem("skills", i, { name: e.target.value })} placeholder="Skill" />
            <select aria-label="Category" value={s.category} onChange={(e) => setItem("skills", i, { category: e.target.value })}>
              {CATS.map((c) => <option key={c}>{c}</option>)}
            </select>
            <select aria-label="Proficiency" value={s.proficiency} onChange={(e) => setItem("skills", i, { proficiency: e.target.value })}>
              {LEVELS.map((l) => <option key={l} value={l}>{l || "level not stated"}</option>)}
            </select>
            <button className="btn small ghost" onClick={() => remove("skills", i)} aria-label={`Remove skill ${s.name}`}>Remove</button>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Experience</h3><button className="btn small ghost" onClick={() => add("experience", { role: "", organization: "", start_date: "", end_date: "", highlights_text: "" })}>Add experience</button></div>
        {ed.experience.length === 0 && <p className="empty">No work experience found.</p>}
        {ed.experience.map((e, i) => (
          <fieldset className="block" key={i}>
            <div className="grid2">
              <Field label="Role" value={e.role} onChange={(v) => setItem("experience", i, { role: v })} />
              <Field label="Organization" value={e.organization} onChange={(v) => setItem("experience", i, { organization: v })} />
              <Field label="Start (YYYY-MM)" value={e.start_date} onChange={(v) => setItem("experience", i, { start_date: v })} missing placeholder="2024-06" />
              <Field label="End (YYYY-MM, blank if current)" value={e.end_date} onChange={(v) => setItem("experience", i, { end_date: v })} placeholder="2024-09" />
            </div>
            <label className="field">
              <span className="field-label">Highlights (one per line)</span>
              <textarea rows={3} value={e.highlights_text} onChange={(ev) => setItem("experience", i, { highlights_text: ev.target.value })} />
            </label>
            <button className="btn small ghost" onClick={() => remove("experience", i)}>Remove this experience</button>
          </fieldset>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Education</h3><button className="btn small ghost" onClick={() => add("education", { degree: "", institution: "", year: "" })}>Add education</button></div>
        {ed.education.length === 0 && <p className="empty">No education found.</p>}
        {ed.education.map((e, i) => (
          <div className="row edu-row" key={i}>
            <input aria-label="Degree" value={e.degree} onChange={(ev) => setItem("education", i, { degree: ev.target.value })} placeholder="Degree" />
            <input aria-label="Institution" value={e.institution} onChange={(ev) => setItem("education", i, { institution: ev.target.value })} placeholder="Institution" />
            <input aria-label="Year" inputMode="numeric" value={e.year} onChange={(ev) => setItem("education", i, { year: ev.target.value })} placeholder="Year" />
            <button className="btn small ghost" onClick={() => remove("education", i)}>Remove</button>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Projects</h3><button className="btn small ghost" onClick={() => add("projects", { title: "", tech_text: "", description: "" })}>Add project</button></div>
        {ed.projects.length === 0 && <p className="empty">No projects found.</p>}
        {ed.projects.map((x, i) => (
          <fieldset className="block" key={i}>
            <div className="grid2">
              <Field label="Title" value={x.title} onChange={(v) => setItem("projects", i, { title: v })} />
              <Field label="Technologies (comma separated)" value={x.tech_text} onChange={(v) => setItem("projects", i, { tech_text: v })} />
            </div>
            <label className="field">
              <span className="field-label">Description</span>
              <textarea rows={2} value={x.description} onChange={(ev) => setItem("projects", i, { description: ev.target.value })} />
            </label>
            <button className="btn small ghost" onClick={() => remove("projects", i)}>Remove this project</button>
          </fieldset>
        ))}
      </div>

      <div className="panel confirm">
        <h3>Save</h3>
        <label className="field">
          <span className="field-label">Where should this go?</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="new">Create a new profile</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>Update {t.full_name || `profile #${t.id}`} (last changed {fmtDateTime(t.updated_at)})</option>
            ))}
          </select>
        </label>
        {target !== "new" && (
          <div className="choice" role="radiogroup" aria-label="Update mode">
            <label><input type="radio" name="mode" checked={mode === "merge"} onChange={() => setMode("merge")} /> Merge: keep existing data and add new items</label>
            <label><input type="radio" name="mode" checked={mode === "replace"} onChange={() => setMode("replace")} /> Replace: overwrite the profile with what's above</label>
          </div>
        )}

        {problems.length > 0 && (
          <div className="notice notice-error" role="alert">
            <ul>{problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
          </div>
        )}

        <div className="actions">
          <button className="btn primary" onClick={confirm} disabled={saving}>{saving ? "Saving…" : "Confirm and save"}</button>
          <button className="btn ghost" onClick={onCancel} disabled={saving}>Discard and start over</button>
        </div>
      </div>
    </div>
  );
}
