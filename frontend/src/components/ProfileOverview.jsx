import { useState } from "react";
import { CATEGORY_LABELS, fmtMonth, maskEmail } from "../util";

export default function ProfileOverview({ profile }) {
  const [showEmail, setShowEmail] = useState(false);
  const byCat = {};
  profile.skills.forEach((s) => { (byCat[s.category] ||= []).push(s); });

  return (
    <section className="panel">
      {profile.email && (
        <p className="email-line">
          {showEmail ? profile.email : maskEmail(profile.email)}{" "}
          <button className="link" onClick={() => setShowEmail((v) => !v)}>{showEmail ? "Hide email" : "Show email"}</button>
        </p>
      )}
      {profile.summary && <p>{profile.summary}</p>}

      <h3>Skills</h3>
      {profile.skills.length === 0 && <p className="empty">No skills saved.</p>}
      {Object.entries(byCat).map(([cat, list]) => (
        <div key={cat} className="skill-group">
          <h5>{CATEGORY_LABELS[cat] || cat}</h5>
          <ul className="chips">
            {list.map((s) => <li key={s.name} className="chip chip-have">{s.name}{s.proficiency ? <em> {s.proficiency}</em> : null}</li>)}
          </ul>
        </div>
      ))}

      {profile.experience.length > 0 && <h3>Experience</h3>}
      {profile.experience.map((e, i) => (
        <article key={i} className="entry">
          <h4>{e.role}{e.organization ? `, ${e.organization}` : ""}</h4>
          <p className="muted small-text">
            {e.start_date ? `${fmtMonth(e.start_date)} to ${e.end_date ? fmtMonth(e.end_date) : "present"}` : "Dates not stated"}
          </p>
          {e.highlights.length > 0 && <ul>{e.highlights.map((h, j) => <li key={j}>{h}</li>)}</ul>}
        </article>
      ))}

      {profile.education.length > 0 && <h3>Education</h3>}
      {profile.education.map((e, i) => (
        <article key={i} className="entry">
          <h4>{e.degree}</h4>
          <p className="muted small-text">{[e.institution, e.year].filter(Boolean).join(", ")}</p>
        </article>
      ))}

      {profile.projects.length > 0 && <h3>Projects</h3>}
      {profile.projects.map((p, i) => (
        <article key={i} className="entry">
          <h4>{p.title}</h4>
          {p.description && <p>{p.description}</p>}
          {p.tech.length > 0 && <ul className="chips">{p.tech.map((t) => <li key={t} className="chip chip-plain">{t}</li>)}</ul>}
        </article>
      ))}
    </section>
  );
}
