export const CATEGORY_LABELS = {
  language: "Languages",
  framework: "Frameworks",
  tool: "Tools",
  soft: "Soft skills",
  other: "Other",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtMonth(v) {
  if (!v) return null;
  const [y, m] = v.split("-");
  return `${MONTHS[Number(m) - 1] || ""} ${y}`.trim();
}

export function fmtDateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function maskEmail(email) {
  if (!email) return "";
  const [name, domain] = email.split("@");
  return `${name.slice(0, 1)}${"•".repeat(Math.max(3, name.length - 1))}@${domain}`;
}
