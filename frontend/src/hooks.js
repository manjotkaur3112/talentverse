import { useEffect, useState } from "react";

// Seconds elapsed while `active` is true.
export function useElapsed(active) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!active) { setS(0); return; }
    const t = setInterval(() => setS((v) => v + 1), 1000);
    return () => clearInterval(t);
  }, [active]);
  return s;
}

export function waitLabel(base, seconds) {
  if (seconds < 1) return base;
  return seconds >= 15 ? `${base} ${seconds}s (the server may be waking up)` : `${base} ${seconds}s`;
}
