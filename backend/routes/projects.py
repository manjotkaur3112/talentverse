"""Smart project and portfolio builder."""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify

import ai
from core import ApiError, check_rate_limit, clean_url, json_body, one_of, parse
from matcher import compute_match
from models import PortfolioProject, Project, ProjectMilestone, db
from prompts import IDEAS_SYSTEM_PROMPT, wrap
from routes.common import candidate_summary, child, have_skills, load, optional_job
from schemas import ProjectIdea, ProjectIdeas

bp = Blueprint("projects", __name__)
STATUSES = ("not_started", "in_progress", "completed")


@bp.post("/api/profiles/<int:pid>/project-ideas")
def project_ideas(pid):
    """Preview only: three ideas (beginner, intermediate, advanced). Nothing is saved until the user picks one."""
    oid, profile = load(pid)
    body = json_body()
    job = optional_job(profile, body)
    goal = (body.get("goal") or "").strip()
    if not job and not goal:
        raise ApiError("Describe your career goal or choose a saved job.", 400)
    if len(goal) > 300:
        raise ApiError("Goal is too long (max 300 characters).", 422)

    ctx = {"candidate": candidate_summary(profile), "goal": goal or None}
    if job:
        res = compute_match(have_skills(profile), job.required_skills or [], job.preferred_skills or [])
        ctx["target_job"] = {"title": job.title, "required_skills": job.required_skills or [],
                             "preferred_skills": job.preferred_skills or [],
                             "skills_candidate_is_missing": (res["missing_required"] + res["missing_preferred"]) if res else []}
    check_rate_limit(oid)
    ideas = ai.structured_call(ProjectIdeas, IDEAS_SYSTEM_PROMPT, wrap(json.dumps(ctx, ensure_ascii=False), "context"))
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    return jsonify({"ideas": sorted((i.model_dump() for i in ideas.ideas), key=lambda i: order[i["level"]])})


@bp.post("/api/profiles/<int:pid>/portfolio")
def save_project(pid):
    _, profile = load(pid)
    body = json_body()
    idea = parse(ProjectIdea, body.get("idea") or {})
    job = optional_job(profile, body)
    if len(profile.portfolio) >= 30:
        raise ApiError("Portfolio limit reached. Delete a project first.", 400)
    data = idea.model_dump()
    milestones = data.pop("milestones")
    proj = PortfolioProject(profile_id=profile.id, job_id=job.id if job else None, level=idea.level,
                            title=idea.title, idea=data)
    for i, m in enumerate(milestones):
        proj.milestones.append(ProjectMilestone(position=i, title=m["title"][:200], description=m.get("description") or ""))
    db.session.add(proj)
    db.session.commit()
    return jsonify({"project": proj.to_dict(), "message": f"Added \"{proj.title}\" to your projects."}), 201


@bp.get("/api/profiles/<int:pid>/portfolio")
def list_projects(pid):
    _, profile = load(pid)
    return jsonify({"projects": [p.to_dict() for p in profile.portfolio]})


@bp.patch("/api/profiles/<int:pid>/portfolio/<int:jid>")
def update_project(pid, jid):
    _, profile = load(pid)
    proj = child(PortfolioProject, profile, jid)
    body = json_body()
    if "repo_url" in body:
        proj.repo_url = clean_url(body["repo_url"], "repo_url")
    if "demo_url" in body:
        proj.demo_url = clean_url(body["demo_url"], "demo_url")

    added = False
    if "status" in body:
        status = one_of(body["status"], STATUSES, "status")
        if status == "completed" and proj.status != "completed":
            if not (proj.repo_url or proj.demo_url):
                raise ApiError("Add a GitHub repo or live demo link before marking a project completed.", 422)
            proj.completed_at = datetime.now(timezone.utc)
            idea = proj.idea or {}
            if not any(p.title.lower() == proj.title.lower() for p in profile.projects):
                profile.projects.append(Project(title=proj.title[:120], tech=(idea.get("tech_stack") or [])[:15],
                                                description=(idea.get("github_description") or "")[:2000]))
                added = True
        elif status != "completed":
            proj.completed_at = None
        proj.status = status
    db.session.commit()
    out = {"project": proj.to_dict(), "added_to_profile": added}
    if added:
        out["message"] = "Completed. This project was also added to your profile, which strengthens your skill evidence."
    return jsonify(out)


@bp.patch("/api/profiles/<int:pid>/portfolio/<int:jid>/milestones/<int:mid>")
def update_milestone(pid, jid, mid):
    _, profile = load(pid)
    proj = child(PortfolioProject, profile, jid)
    m = ProjectMilestone.query.filter_by(id=mid, project_id=proj.id).first()
    if m is None:
        raise ApiError("Milestone not found.", 404)
    done = json_body().get("done")
    if not isinstance(done, bool):
        raise ApiError("done must be true or false.", 400)
    m.done = done
    m.done_at = datetime.now(timezone.utc) if done else None
    if done and proj.status == "not_started":
        proj.status = "in_progress"
    db.session.commit()
    return jsonify({"project": proj.to_dict()})


@bp.delete("/api/profiles/<int:pid>/portfolio/<int:jid>")
def delete_project(pid, jid):
    _, profile = load(pid)
    db.session.delete(child(PortfolioProject, profile, jid))
    db.session.commit()
    return jsonify({"deleted": True})
