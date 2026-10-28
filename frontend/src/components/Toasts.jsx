export default function Toasts({ toasts, dismiss }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind || "info"}`}>
          <span>{t.text}</span>
          {t.actionLabel && (
            <button className="link" onClick={() => { t.onAction?.(); dismiss(t.id); }}>
              {t.actionLabel}
            </button>
          )}
          <button className="link" aria-label="Dismiss" onClick={() => dismiss(t.id)}>Close</button>
        </div>
      ))}
    </div>
  );
}
