import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";

export default function ProfilesList({ onOpen, notify, onBuild }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setError(null);
    api.listProfiles().then((r) => setRows(r.profiles)).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  async function wipe() {
    if (!window.confirm("Delete ALL your profiles and job comparisons? This can't be undone.")) return;
    try {
      const r = await api.deleteAll();
      notify({ kind: "ok", text: `Deleted ${r.deleted} profile${r.deleted === 1 ? "" : "s"}.` });
      load();
    } catch (e) {
      notify({ kind: "error", text: e.message });
    }
  }

  if (error) {
    return (
      <div className="notice notice-error" role="alert">
        <span>{error}</span>
        <button className="btn small" onClick={load}>Retry</button>
      </div>
    );
  }
  if (!rows) return <p className="muted">Loading your profiles…</p>;

  return (
    <section className="panel">
      <h2>Your profiles</h2>
      {rows.length === 0 ? (
        <div className="empty-state">
          <p>You haven't saved a profile yet.</p>
          <button className="btn primary" onClick={onBuild}>Build your first profile</button>
        </div>
      ) : (
        <>
          <ul className="list">
            {rows.map((r) => (
              <li key={r.id}>
                <button className="list-row" onClick={() => onOpen(r.id)}>
                  <span className="list-name">{r.full_name || `Profile #${r.id}`}</span>
                  <span className="muted">{r.skill_count} skills, {r.experience_count} roles</span>
                  <span className="muted small-text">Updated {fmtDateTime(r.updated_at)}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="actions">
            <button className="btn small danger" onClick={wipe}>Delete all my data</button>
            <span className="muted small-text">Profiles are tied to this browser and can't be seen from other devices.</span>
          </div>
        </>
      )}
    </section>
  );
}
