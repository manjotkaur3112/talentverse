"""Career progress analytics (real saved records only) and the mentor chatbot."""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify

import ai
from core import ApiError, check_rate_limit, json_body
from matcher import norm
from models import ChatMessage, db
from prompts import MENTOR_SYSTEM_PROMPT, wrap
from routes.common import candidate_summary, load
from routes.jobs import STATUSES as JOB_STATUSES, job_json
from routes.learning import learning_json
from scoring import evidence_map, experience_months

bp = Blueprint("insights", __name__)


def _day(dt):
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).date()


def _week_start(d):
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------- analytics
def build_analytics(profile):
    reports = sorted(profile.readiness_reports, key=lambda r: r.created_at or datetime.min)
    readiness = [{"date": r.created_at.isoformat() if r.created_at else None, "score": r.score, "job_title": r.job_title}
                 for r in reports]

    # learning
    tasks = [t for p in profile.plans for t in p.tasks]
    done_by_week = Counter()
    for t in tasks:
        if t.status == "completed" and t.completed_at:
            done_by_week[_week_start(_day(t.completed_at)).isoformat()] += 1
    by_skill = defaultdict(list)
    for p in profile.plans:
        for t in p.tasks:
            by_skill[(p.id, t.skill)].append(t)
    skills_learned, pending_by_skill = {}, Counter()
    for (_, skill), ts in by_skill.items():
        if all(t.status == "completed" for t in ts):
            last = max((t.completed_at for t in ts if t.completed_at), default=None)
            skills_learned[skill] = last.isoformat() if last else None
        else:
            pending_by_skill[skill] += sum(1 for t in ts if t.status != "completed")

    # projects
    projects = profile.portfolio
    ms_total = sum(len(p.milestones) for p in projects)
    ms_done = sum(1 for p in projects for m in p.milestones if m.done)
    completed_projects = [{"title": p.title, "level": p.level, "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                           "repo_url": p.repo_url, "demo_url": p.demo_url} for p in projects if p.status == "completed"]

    # interviews
    sessions = sorted([s for s in profile.interviews if s.avg_score() is not None], key=lambda s: s.created_at)
    attempts = [{"date": s.created_at.isoformat(), "mode": s.mode, "avg_score": s.avg_score(),
                 "answered": sum(1 for q in s.questions if q.score is not None)} for s in sessions]
    trend = {}
    for mode in ("technical", "hr", "behavioral"):
        ms = [a["avg_score"] for a in attempts if a["mode"] == mode]
        if ms:
            trend[mode] = {"attempts": len(ms), "first": ms[0], "latest": ms[-1], "change": ms[-1] - ms[0]}
    focus_scores, concepts = defaultdict(list), Counter()
    for s in profile.interviews:
        for q in s.questions:
            if q.score is None:
                continue
            if q.focus:
                focus_scores[q.focus].append(q.score)
            for c in (q.feedback or {}).get("missing_concepts", []):
                concepts[c] += 1
    weak_focus = sorted(({"skill": k, "avg": round(sum(v) / len(v)), "attempts": len(v)}
                         for k, v in focus_scores.items() if sum(v) / len(v) < 60), key=lambda x: x["avg"])

    # applications
    funnel = {s: 0 for s in JOB_STATUSES}
    for j in profile.jobs:
        funnel[j.status] = funnel.get(j.status, 0) + 1
    today = date.today().isoformat()
    upcoming = sorted(({"id": j.id, "title": j.title, "company": j.company, "deadline": j.deadline, "status": j.status}
                       for j in profile.jobs if j.deadline and j.deadline >= today and j.status in ("saved", "applied")),
                      key=lambda x: x["deadline"])[:5]

    # skills needing practice: merge every signal that points at the same skill
    needs = {}

    def need(skill, reason):
        e = needs.setdefault(norm(skill), {"skill": skill, "reasons": []})
        if reason not in e["reasons"]:
            e["reasons"].append(reason)

    if reports:
        latest = reports[-1]
        d = latest.details or {}
        for s in d.get("missing_required", []):
            need(s, f"Required for {latest.job_title} and not in your profile")
        for s in d.get("unverified_skills", []):
            need(s, "Listed, but no project or experience shows it")
    for skill, n in pending_by_skill.items():
        need(skill, f"{n} learning task{'s' if n != 1 else ''} left")
    for w in weak_focus:
        need(w["skill"], f"Interview answers average {w['avg']}/100")
    practice = sorted(needs.values(), key=lambda e: -len(e["reasons"]))[:10]

    total_tasks = len(tasks)
    done_tasks = sum(1 for t in tasks if t.status == "completed")
    return {
        "summary": {
            "skills_listed": len(profile.skills), "skills_learned": len(skills_learned),
            "tasks_completed": done_tasks, "tasks_total": total_tasks,
            "projects_completed": len(completed_projects), "projects_total": len(projects),
            "milestones_done": ms_done, "milestones_total": ms_total,
            "interview_sessions": len(attempts), "jobs_tracked": len(profile.jobs),
            "latest_readiness": readiness[-1]["score"] if readiness else None,
        },
        "readiness_history": readiness,
        "learning": {"percent": round(100 * done_tasks / total_tasks) if total_tasks else 0,
                     "completed_by_week": [{"week": k, "count": v} for k, v in sorted(done_by_week.items())],
                     "skills_learned": [{"skill": k, "completed_at": v} for k, v in skills_learned.items()]},
        "projects": {"completed": completed_projects},
        "interviews": {"attempts": attempts, "trend": trend, "weak_focus": weak_focus,
                       "common_missing_concepts": [{"concept": c, "count": n} for c, n in concepts.most_common(8)]},
        "applications": {"funnel": funnel, "upcoming_deadlines": upcoming},
        "practice_needed": practice,
    }


@bp.get("/api/profiles/<int:pid>/analytics")
def analytics(pid):
    _, profile = load(pid)
    return jsonify(build_analytics(profile))


# ---------------------------------------------------------------- mentor chatbot
def build_context(profile) -> str:
    ev = evidence_map(profile)
    months, _ = experience_months(profile)
    ctx = {
        "candidate": {"name": profile.full_name, "summary": profile.summary, **candidate_summary(profile),
                      "skills_with_proof": [e["name"] for e in ev.values() if e["verified"]],
                      "skills_listed_without_proof": [e["name"] for e in ev.values() if e["listed"] and not e["verified"]],
                      "dated_experience_months": months},
        "saved_jobs": [],
    }
    for j in profile.jobs[:8]:
        d = job_json(j, profile)
        ctx["saved_jobs"].append({"title": d["title"], "company": d["company"], "status": d["status"], "level": d["experience_level"],
                                  "deadline": d["deadline"],
                                  "match_score": d["match"]["score"] if d["match"] else None,
                                  "missing_required": d["match"]["missing_required"] if d["match"] else [],
                                  "missing_preferred": d["match"]["missing_preferred"] if d["match"] else []})
    if profile.readiness_reports:
        r = profile.readiness_reports[0]
        d = r.details or {}
        ctx["latest_readiness"] = {"role": r.job_title, "score": r.score, "components": d.get("components"),
                                   "experience_gaps": d.get("experience_gaps"), "project_gaps": d.get("project_gaps"),
                                   "top_recommendations": [x["action"] for x in (d.get("recommendations") or [])[:3]]}
    lj = learning_json(profile)
    if lj["plan"]:
        ctx["learning"] = {"plan": lj["plan"]["title"], "progress": lj["progress"], "next_topic": lj["next_topic"],
                           "skills_in_plan": list(lj["resources"].keys())}
    ctx["portfolio"] = [{"title": p.title, "level": p.level, "status": p.status} for p in profile.portfolio[:8]]
    a = build_analytics(profile)
    ctx["interview_practice"] = {"sessions": a["interviews"]["attempts"][-5:], "weak_areas": a["interviews"]["weak_focus"][:4],
                                 "common_missing_concepts": a["interviews"]["common_missing_concepts"][:4]}
    return json.dumps(ctx, ensure_ascii=False)[:9000]


@bp.get("/api/profiles/<int:pid>/chat")
def get_chat(pid):
    _, profile = load(pid)
    return jsonify({"messages": [m.to_dict() for m in profile.chat[-50:]]})


@bp.post("/api/profiles/<int:pid>/chat")
def post_chat(pid):
    oid, profile = load(pid)
    msg = (json_body().get("message") or "").strip()
    if not msg:
        raise ApiError("Type a question first.", 422)
    if len(msg) > 1000:
        raise ApiError("Question is too long (max 1000 characters).", 422)

    history = [{"role": m.role, "text": m.content[:800]} for m in profile.chat[-8:]]
    prompt = "\n".join([wrap(build_context(profile), "context"), wrap(json.dumps(history, ensure_ascii=False), "history"),
                        wrap(msg, "question")])
    check_rate_limit(oid)
    reply = ai.generate_text(MENTOR_SYSTEM_PROMPT, prompt)[:4000]

    user_row = ChatMessage(profile_id=profile.id, role="user", content=msg)
    bot_row = ChatMessage(profile_id=profile.id, role="assistant", content=reply)
    db.session.add_all([user_row, bot_row])
    db.session.flush()
    for old in profile.chat[:-60]:  # keep the latest 60 messages
        db.session.delete(old)
    db.session.commit()
    return jsonify({"messages": [user_row.to_dict(), bot_row.to_dict()]}), 201


@bp.delete("/api/profiles/<int:pid>/chat")
def clear_chat(pid):
    _, profile = load(pid)
    for m in list(profile.chat):
        db.session.delete(m)
    db.session.commit()
    return jsonify({"deleted": True})
