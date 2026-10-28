"""Anti-fabrication guards for the ATS optimizer. The AI may reword, never invent."""
import re

from matcher import norm
from scoring import all_text, evidence_map, evidence_texts, mentions, relevant_projects

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?%?")


def numbers_in(text: str) -> set[str]:
    return set(NUM_RE.findall(text or ""))


def invented_numbers(new_text: str, allowed_text: str) -> bool:
    return not numbers_in(new_text) <= numbers_in(allowed_text)


def unsupported_keywords(new_text: str, original: str, job_skills, supported: set) -> list[str]:
    """Job keywords that appear in new_text although the candidate has no evidence for them."""
    bad = []
    for s in job_skills:
        if norm(s) in supported:
            continue
        if mentions(new_text, s) and not mentions(original, s):
            bad.append(s)
    return bad


def resume_items(profile) -> dict:
    """id -> text for every existing sentence the AI may suggest rewording."""
    items = {}
    if profile.summary:
        items["summary"] = profile.summary
    for i, e in enumerate(profile.experiences):
        for j, h in enumerate(e.highlights or []):
            items[f"exp{i}-{j}"] = h
    for i, p in enumerate(profile.projects):
        if p.description:
            items[f"proj{i}"] = p.description
    return items


def keyword_report(profile, required, preferred):
    """Which job keywords the profile covers anywhere (listed, project tech or mentioned in text)."""
    ev = evidence_map(profile)
    blob = all_text(profile)
    present, missing = [], []
    for s in list(dict.fromkeys([*required, *preferred])):
        (present if (norm(s) in ev or mentions(blob, s)) else missing).append(s)
    total = len(present) + len(missing)
    return present, missing, (round(100 * len(present) / total) if total else 0)


def month_label(v):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if not v:
        return None
    y, m = v.split("-")
    return f"{months[int(m) - 1]} {y}"


def build_draft(profile, job_skills, summary, fixes: dict) -> str:
    """Tailored resume as markdown, assembled from saved data only. `fixes` maps item id -> improved text."""
    job_norm = {norm(s) for s in job_skills}
    lines = [f"# {profile.full_name or 'Your Name'}"]
    if profile.email:
        lines.append(profile.email)
    if summary:
        lines += ["", "## Summary", summary]

    names = [s.name for s in profile.skills]
    first = [n for n in names if norm(n) in job_norm]
    rest = [n for n in names if norm(n) not in job_norm]
    if names:
        lines += ["", "## Skills"]
        if first:
            lines.append("Relevant to this role: " + ", ".join(first))
        if rest:
            lines.append("Other: " + ", ".join(rest))

    if profile.experiences:
        lines += ["", "## Experience"]
        for i, e in enumerate(profile.experiences):
            dates = ""
            if e.start_date:
                dates = f" ({month_label(e.start_date)} - {month_label(e.end_date) if e.end_date else 'Present'})"
            lines.append(f"### {e.role}{', ' + e.organization if e.organization else ''}{dates}")
            for j, h in enumerate(e.highlights or []):
                lines.append("- " + fixes.get(f"exp{i}-{j}", h))

    if profile.projects:
        rel = {p.id for p in relevant_projects(profile, job_skills)}
        ordered = sorted(enumerate(profile.projects), key=lambda ip: (ip[1].id not in rel, ip[0]))
        lines += ["", "## Projects"]
        for i, p in ordered:
            tech = f" ({', '.join(p.tech)})" if p.tech else ""
            lines.append(f"### {p.title}{tech}")
            if p.description:
                lines.append(fixes.get(f"proj{i}", p.description))

    if profile.education:
        lines += ["", "## Education"]
        for e in profile.education:
            lines.append("- " + ", ".join(x for x in [e.degree, e.institution, str(e.year) if e.year else None] if x))
    return "\n".join(lines)
