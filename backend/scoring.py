"""Deterministic career metrics. Code computes the numbers; the AI only explains them."""
import re
from datetime import date

from matcher import ALIASES, norm

LEVEL_MONTHS = {"intern": 0, "entry": 6, "mid": 36, "senior": 60}
LEVEL_PROJECTS = {"intern": 1, "entry": 2, "mid": 3, "senior": 4}
WEIGHTS = {"skills": 0.6, "experience": 0.2, "projects": 0.2}


# ---------- text and skill evidence ----------
def mentions(text: str, skill: str) -> bool:
    """True if `skill` (or a known alias of it) appears as a whole term in `text`."""
    if not text:
        return False
    t = text.lower()
    k = norm(skill)
    names = {skill.strip().lower(), k} | {a for a, c in ALIASES.items() if c == k}
    return any(re.search(r"(?<![a-z0-9+#.])" + re.escape(n) + r"(?![a-z0-9+#])", t) for n in names if n)


def evidence_texts(profile) -> list[str]:
    texts = []
    for e in profile.experiences:
        texts += [e.role or "", e.organization or ""] + list(e.highlights or [])
    for p in profile.projects:
        texts += [p.title or "", p.description or ""]
    return [t for t in texts if t]


def evidence_map(profile) -> dict:
    """norm skill -> {name, listed, verified}. Verified = shown in a project or experience text."""
    ev = {}

    def add(name, listed=False, verified=False):
        e = ev.setdefault(norm(name), {"name": name, "listed": False, "verified": False})
        e["listed"] |= listed
        e["verified"] |= verified

    texts = evidence_texts(profile)
    for s in profile.skills:
        add(s.name, listed=True, verified=any(mentions(t, s.name) for t in texts))
    for p in profile.projects:
        for tech in (p.tech or []):
            add(tech, verified=True)
    return ev


def all_text(profile) -> str:
    parts = [profile.full_name or "", profile.summary or ""] + evidence_texts(profile)
    for e in profile.education:
        parts += [e.degree or "", e.institution or "", str(e.year or "")]
    for e in profile.experiences:
        parts += [e.start_date or "", e.end_date or ""]
    return " ".join(parts)


# ---------- experience ----------
def experience_months(profile, today=None):
    """Months of dated experience (overlaps merged) and the number of undated roles."""
    today = today or date.today()
    now = today.year * 12 + today.month - 1
    spans, undated = [], 0
    for e in profile.experiences:
        if not e.start_date:
            undated += 1
            continue
        sy, sm = (int(x) for x in e.start_date.split("-"))
        start = sy * 12 + sm - 1
        if e.end_date:
            ey, em = (int(x) for x in e.end_date.split("-"))
            end = ey * 12 + em - 1
        else:
            end = now
        if end >= start:
            spans.append((start, end + 1))
    spans.sort()
    total, cur_s, cur_e = 0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total, undated


def _dedupe(items):
    seen, out = set(), []
    for s in items:
        k = norm(s)
        if k and k not in seen:
            seen.add(k)
            out.append(s)
    return out


def relevant_projects(profile, skills):
    out = []
    for p in profile.projects:
        blob = " ".join([p.title or "", p.description or ""] + list(p.tech or []))
        if any(mentions(blob, s) for s in skills):
            out.append(p)
    return out


# ---------- readiness ----------
def compute_readiness(profile, required, preferred, level, today=None) -> dict:
    required, preferred = _dedupe(required), _dedupe(preferred)
    level = level if level in LEVEL_MONTHS else "entry"
    ev = evidence_map(profile)

    def cover(skills):
        credit, strong, missing, unverified = 0.0, [], [], []
        for s in skills:
            e = ev.get(norm(s))
            if e is None:
                missing.append(s)
            elif e["verified"]:
                credit += 1.0
                strong.append({"name": s, "verified": True})
            else:
                credit += 0.6  # listed, but nothing in the profile shows it
                strong.append({"name": s, "verified": False})
                unverified.append(s)
        return credit, strong, missing, unverified

    rc, rs, rm, ru = cover(required)
    pc, ps, pm, pu = cover(preferred)
    if required and preferred:
        skills_score = 0.7 * rc / len(required) + 0.3 * pc / len(preferred)
    elif required:
        skills_score = rc / len(required)
    elif preferred:
        skills_score = pc / len(preferred)
    else:
        skills_score = 0.0
    skills_score = round(skills_score * 100)

    months, undated = experience_months(profile, today)
    rel = relevant_projects(profile, required + preferred)
    target_m, target_p = LEVEL_MONTHS[level], LEVEL_PROJECTS[level]
    if target_m == 0:
        exp_score = 100 if (months > 0 or rel) else 30
    else:
        exp_score = min(100, round(100 * months / target_m))
    proj_score = min(100, round(100 * len(rel) / target_p))

    overall = round(WEIGHTS["skills"] * skills_score + WEIGHTS["experience"] * exp_score
                    + WEIGHTS["projects"] * proj_score)

    exp_gaps, proj_gaps = [], []
    if target_m and months < target_m:
        exp_gaps.append(f"This level usually expects about {target_m} months of experience. "
                        f"Your dated experience adds up to {months} month{'s' if months != 1 else ''}.")
    if target_m == 0 and months == 0 and not rel:
        exp_gaps.append("No work experience or relevant project found yet. One solid project would help a lot.")
    if undated:
        exp_gaps.append(f"{undated} role{'s have' if undated != 1 else ' has'} no dates, so "
                        f"{'they were' if undated != 1 else 'it was'} not counted.")
    if len(rel) < target_p:
        proj_gaps.append(f"{len(rel)} of your projects use this role's skills. About {target_p} are expected.")
    unverified = ru + pu
    if unverified:
        proj_gaps.append("Listed without proof in any project or experience: " + ", ".join(unverified) + ".")

    return {
        "score": overall,
        "components": {"skills": skills_score, "experience": exp_score, "projects": proj_score},
        "weights": WEIGHTS,
        "level": level,
        "strong_skills": rs + ps,
        "missing_required": rm,
        "missing_preferred": pm,
        "unverified_skills": unverified,
        "experience_months": months,
        "relevant_projects": len(rel),
        "experience_gaps": exp_gaps,
        "project_gaps": proj_gaps,
    }


def rule_recommendations(r: dict) -> list[dict]:
    """Fallback advice when the AI is unavailable. Built only from the measured gaps."""
    recs = []
    for s in r["missing_required"][:3]:
        recs.append({"action": f"Learn {s} and use it in a small project.",
                     "why": f"{s} is required for this role and is not in your profile.", "impact": "high"})
    for s in r["unverified_skills"][:2]:
        recs.append({"action": f"Add a project or experience bullet that shows {s}.",
                     "why": f"You list {s}, but nothing in your profile proves it yet.", "impact": "medium"})
    if r["relevant_projects"] < LEVEL_PROJECTS.get(r["level"], 2):
        recs.append({"action": "Build one more project using this role's core skills and publish it on GitHub.",
                     "why": "Relevant projects are 20% of the readiness score.", "impact": "high"})
    if r["experience_gaps"]:
        recs.append({"action": "Look for an internship, freelance task or open-source contribution and add dates to it.",
                     "why": "Experience is 20% of the readiness score.", "impact": "medium"})
    for s in r["missing_preferred"][:1]:
        recs.append({"action": f"Pick up {s} after the required skills.", "why": "It is a nice-to-have for this role.", "impact": "low"})
    return recs[:5] or [{"action": "Keep building and documenting projects.", "why": "Your profile already covers this role well.", "impact": "low"}]


# ---------- learning tracker ----------
def plan_progress(tasks) -> dict:
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "completed")
    return {"total": total, "completed": done,
            "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
            "percent": round(100 * done / total) if total else 0}


def next_topic(tasks):
    """Next skill to study: continue anything in progress, otherwise the earliest unfinished task."""
    open_tasks = [t for t in tasks if t.status != "completed"]
    if not open_tasks:
        return None
    started = [t for t in open_tasks if t.status == "in_progress"]
    pick = (started or open_tasks)[0]  # tasks are ordered by position (week, then day)
    remaining = sum(1 for t in open_tasks if t.skill == pick.skill)
    return {"skill": pick.skill, "task_id": pick.id, "task_title": pick.title, "week": pick.week_number,
            "remaining_for_skill": remaining,
            "reason": ("You already started this one." if pick.status == "in_progress"
                       else "It is the earliest unfinished task in your plan.")}
