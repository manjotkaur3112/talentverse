import { useCallback, useRef, useState } from "react";

export function useRun() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const last = useRef(null);
  const run = useCallback(async (fn) => {
    last.current = fn;
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e.message || "Something went wrong.");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  const retry = useCallback(() => (last.current ? run(last.current) : undefined), [run]);
  return { busy, error, setError, run, retry };
}

export function ErrorNote({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="notice notice-error" role="alert">
      <span>{message}</span>
      {onRetry && <button type="button" className="btn small" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function ScoreRing({ value, size = 120, label }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="ring" style={{ "--pct": v, "--size": `${size}px` }} role="img" aria-label={`${label || "Score"} ${v} out of 100`}>
      <span style={{ fontSize: size * 0.3 }}>{v}</span>
    </div>
  );
}

export function Chips({ items, tone = "plain", empty = "None" }) {
  if (!items?.length) return <p className="empty">{empty}</p>;
  return (
    <ul className="chips">
      {items.map((s, i) => <li key={`${s}-${i}`} className={`chip chip-${tone}`}>{s}</li>)}
    </ul>
  );
}

export function Bar({ label, value, note }) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="bar-row">
      <div className="bar-head"><span>{label}</span><strong>{v}</strong></div>
      <div className="bar"><div className="bar-fill" style={{ width: `${v}%` }} /></div>
      {note && <p className="muted small-text">{note}</p>}
    </div>
  );
}

export function JobSelect({ jobs, value, onChange, allowNone, label = "Target job or role" }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{allowNone ? "No saved job" : "Choose a saved job or role"}</option>
        {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}{j.company ? `, ${j.company}` : ""}</option>)}
      </select>
    </label>
  );
}

export function NeedJob({ go }) {
  return (
    <div className="empty-state">
      <p>Save a job description or a target role first. Every tool here works against a role.</p>
      <button className="btn primary" onClick={() => go("jobs")}>Add a job or role</button>
    </div>
  );
}

export function LineChart({ points, height = 150, label }) {
  if (!points?.length) return null;
  const W = 520, padL = 30, padB = 22, padT = 8, padR = 10;
  const innerW = W - padL - padR, innerH = height - padT - padB;
  const xs = (i) => padL + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const ys = (v) => padT + innerH - (Math.max(0, Math.min(100, v)) / 100) * innerH;
  const path = points.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p.y).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="chart" role="img" aria-label={label}>
      {[0, 50, 100].map((g) => (
        <g key={g}>
          <line x1={padL} x2={W - padR} y1={ys(g)} y2={ys(g)} className="chart-grid" />
          <text x={padL - 6} y={ys(g) + 4} textAnchor="end" className="chart-text">{g}</text>
        </g>
      ))}
      <path d={path} className="chart-line" fill="none" />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={xs(i)} cy={ys(p.y)} r="4" className="chart-dot"><title>{`${p.x}: ${p.y}`}</title></circle>
        </g>
      ))}
      <text x={padL} y={height - 5} className="chart-text">{points[0].x}</text>
      {points.length > 1 && <text x={W - padR} y={height - 5} textAnchor="end" className="chart-text">{points[points.length - 1].x}</text>}
    </svg>
  );
}

export async function copyText(text, notify) {
  try {
    await navigator.clipboard.writeText(text);
    notify({ kind: "ok", text: "Copied to clipboard." });
  } catch {
    notify({ kind: "error", text: "Couldn't copy. Select the text and copy it manually." });
  }
}

export const shortDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "");
export const splitList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
