"""Learning tracker: AI study plan, task status, progress, next topic, free resources."""
import json

from flask import Blueprint, jsonify

import ai
from core import ApiError, check_rate_limit, clean_url, json_body, one_of
from matcher import compute_match, norm
from models import LearningPlan, LearningTask, Resource, db
from prompts import PLAN_SYSTEM_PROMPT, wrap
from resources import resources_for
from routes.common import child, have_skills, int_field, load, optional_job
from schemas import PlanDraft
from scoring import next_topic, plan_progress
from datetime import datetime, timezone

bp = Blueprint("learning", __name__)
STATUSES = ("pending", "in_progress", "completed")


def template_plan(skills, weeks, hours):
    """Rule-based plan used when the AI is unavailable."""
    per_week = {w: [] for w in range(1, weeks + 1)}
    for i, s in enumerate(skills):
        per_week[i % weeks + 1].append(s)
    for w in range(1, weeks + 1):  # spare weeks revisit earlier skills
        if not per_week[w]:
            per_week[w].append(skills[(w - 1) % len(skills)])
    out = []
    for w, ws in per_week.items():
        tasks = []
        for s in ws:
            tasks.append(dict(skill=s, title=f"Learn the fundamentals of {s}", description="Work through an official tutorial.",
                              cadence="weekly", day=None, minutes=90))
            for d in (1, 3, 5):
                tasks.append(dict(skill=s, title=f"Practice {s}: one small exercise", description="", cadence="daily", day=d, minutes=30))
            tasks.append(dict(skill=s, title=f"Build a mini demo using {s}", description="Keep it small and push it to GitHub.",
                              cadence="weekly", day=None, minutes=60))
        out.append({"week": w, "goal": "Focus on " + ", ".join(ws), "tasks": tasks})
    return {"title": "Study plan: " + ", ".join(skills[:3]), "weeks": out}


def _validated_ai_plan(draft: PlanDraft, skills, weeks):
    """Keep only tasks for the requested skills and weeks. Return None if coverage is incomplete."""
    canon = {norm(s): s for s in skills}
    out, covered = [], set()
    for w in sorted(draft.weeks, key=lambda x: x.week):
        if w.week > weeks:
            continue
        tasks = []
        for t in w.tasks:
            k = norm(t.skill)
            if k in canon:
                d = t.model_dump()
                d["skill"] = canon[k]
                if d["cadence"] == "weekly":
                    d["day"] = None
                tasks.append(d)
                covered.add(k)
        if tasks:
            out.append({"week": w.week, "goal": w.goal, "tasks": tasks})
    if covered != set(canon):
        return None
    return {"title": draft.title, "weeks": out}


def learning_json(profile):
    plan = next((p for p in profile.plans if p.is_active), None)
    skills = list(dict.fromkeys(t.skill for t in plan.tasks)) if plan else []
    res = {}
    for r in profile.resources:
        res.setdefault(r.skill, []).append(r.to_dict())
    return {
        "plan": plan.to_dict() if plan else None,
        "progress": plan_progress(plan.tasks) if plan else None,
        "next_topic": next_topic(plan.tasks) if plan else None,
        "resources": {s: res.get(s, []) for s in skills},
    }


@bp.post("/api/profiles/<int:pid>/learning/plan")
def create_plan(pid):
    oid, profile = load(pid)
    body = json_body()
    weeks = int_field(body, "weeks", 1, 8, 4)
    hours = int_field(body, "hours_per_week", 1, 40, 6)
    job = optional_job(profile, body)

    skills = body.get("skills")
    if skills is not None:
        if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
            raise ApiError("skills must be a list of names.", 400)
        skills = [s.strip()[:120] for s in skills if s.strip()]
    elif job:
        res = compute_match(have_skills(profile), job.required_skills or [], job.preferred_skills or [])
        skills = (res["missing_required"] + res["missing_preferred"]) if res else []
    else:
        raise ApiError("Choose a saved job to build a plan for, or list the skills to learn.", 400)
    skills = list({norm(s): s for s in skills}.values())[:6]
    if not skills:
        raise ApiError("No skill gaps found for this job, so there is nothing to study. Try another job.", 422)

    check_rate_limit(oid)
    request_ctx = {"skills": skills, "weeks": weeks, "hours_per_week": hours,
                   "target_role": job.title if job else None}
    plan_data, generated_by = None, "ai"
    try:
        draft = ai.structured_call(PlanDraft, PLAN_SYSTEM_PROMPT, wrap(json.dumps(request_ctx), "request"))
        plan_data = _validated_ai_plan(draft, skills, weeks)
    except ai.AIError:
        plan_data = None
    if plan_data is None:
        plan_data, generated_by = template_plan(skills, weeks, hours), "template"

    for old in profile.plans:
        old.is_active = False
    plan = LearningPlan(profile_id=profile.id, job_id=job.id if job else None, title=plan_data["title"][:120],
                        weeks=weeks, hours_per_week=hours, generated_by=generated_by, is_active=True)
    pos = 0
    for w in plan_data["weeks"]:
        for t in sorted(w["tasks"], key=lambda t: (t["day"] or 0)):
            plan.tasks.append(LearningTask(position=pos, skill=t["skill"], title=t["title"][:200],
                                           description=t.get("description") or "", cadence=t["cadence"],
                                           week_number=w["week"], day_number=t["day"], minutes=t["minutes"]))
            pos += 1
    db.session.add(plan)

    have = {r.skill.lower() for r in profile.resources}
    for s in skills:
        if s.lower() not in have:  # saved once per skill, reused by later plans
            for r in resources_for(s):
                db.session.add(Resource(profile_id=profile.id, skill=s, title=r["title"], url=r["url"], source=r["source"]))
    db.session.commit()
    db.session.refresh(profile)
    return jsonify(learning_json(profile)), 201


@bp.get("/api/profiles/<int:pid>/learning")
def get_learning(pid):
    _, profile = load(pid)
    return jsonify(learning_json(profile))


@bp.patch("/api/profiles/<int:pid>/learning/tasks/<int:tid>")
def update_task(pid, tid):
    _, profile = load(pid)
    task = LearningTask.query.join(LearningPlan).filter(LearningTask.id == tid, LearningPlan.profile_id == profile.id).first()
    if task is None:
        raise ApiError("Task not found.", 404)
    status = one_of(json_body().get("status"), STATUSES, "status")
    task.status = status
    task.completed_at = datetime.now(timezone.utc) if status == "completed" else None
    db.session.commit()
    return jsonify(learning_json(profile))


@bp.post("/api/profiles/<int:pid>/learning/resources")
def add_resource(pid):
    _, profile = load(pid)
    body = json_body()
    skill, title = (body.get("skill") or "").strip(), (body.get("title") or "").strip()
    if not skill or not title or len(skill) > 120 or len(title) > 200:
        raise ApiError("Add a skill and a title for the resource.", 422)
    url = clean_url(body.get("url"), "url")
    if not url:
        raise ApiError("Add a link for the resource.", 422)
    if len(profile.resources) >= 300:
        raise ApiError("Resource limit reached.", 400)
    db.session.add(Resource(profile_id=profile.id, skill=skill, title=title, url=url, source="user"))
    db.session.commit()
    db.session.refresh(profile)
    return jsonify(learning_json(profile)), 201


@bp.delete("/api/profiles/<int:pid>/learning/resources/<int:rid>")
def delete_resource(pid, rid):
    _, profile = load(pid)
    db.session.delete(child(Resource, profile, rid))
    db.session.commit()
    db.session.refresh(profile)
    return jsonify(learning_json(profile))
