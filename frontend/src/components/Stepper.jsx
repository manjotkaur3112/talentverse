const STEPS = [
  { key: "input", label: "Upload resume" },
  { key: "extracting", label: "Extract and validate" },
  { key: "review", label: "Review and confirm" },
  { key: "saved", label: "Saved" },
];

export default function Stepper({ stage }) {
  const current = STEPS.findIndex((s) => s.key === stage);
  return (
    <ol className="rail" aria-label="Progress">
      {STEPS.map((s, i) => {
        const state = i < current || stage === "saved" ? "done" : i === current ? "now" : "next";
        return (
          <li key={s.key} className={`rail-step rail-${state}`} aria-current={state === "now" ? "step" : undefined}>
            <span className="rail-node" aria-hidden="true">{state === "done" ? "✓" : ""}</span>
            <span className="rail-label">{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
