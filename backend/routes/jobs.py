"""Job tracker: save pasted job descriptions or target roles, match them, track applications."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

import ai
import extractor
from core import ApiError, check_rate_limit, json_body, parse
from matcher import compute_match, explain
from models import Job, db, iso
from prompts import JD_SYSTEM_PROMPT, ROLE_SYSTEM_PROMPT, wrap
from routes.common import child, have_skills, load
from schemas import JobIn, JobPosting

bp = Blueprint("jobs", __name__)
STATUSES = ["saved", "applied", "shortlisted", "interview", "offer", "rejected"]


def job_json(job, profile):
    d = job.to_dict()
    res = compute_match(have_skills(profile), job.required_skills or [], job.preferred_skills or [])
    d["match"] = None if res is None else {
        "score": res["score"], "matched": res["matched"],
        "missing_required": res["missing_required"], "missing_preferred": res["missing_preferred"],
        "explanation": explain(res),
    }
    return d


def _history(status):
    return {"status": status, "at": iso(datetime.now(timezone.utc))}


@bp.post("/api/profiles/<int:pid>/jobs/extract")
def extract_job(pid):
    """Preview only: turn a pasted job description (or a role title) into editable fields."""
    oid, _ = load(pid)
    body = json_body()
    role = (body.get("role_title") or "").strip()
    if role:
        if not 2 <= len(role) <= 120:
            raise ApiError("Role title must be 2 to 120 characters.", 422)
        system, user, source = ROLE_SYSTEM_PROMPT, wrap(role, "role_title"), "role_title"
    else:
        text = extractor.clean_text(body.get("jd_text", ""), "job description")
        system, user, source = JD_SYSTEM_PROMPT, wrap(text, "job_description"), "jd"
    check_rate_limit(oid)
    posting = ai.structured_call(JobPosting, system, user)
    out = posting.model_dump()
    out["source"] = source
    if source == "jd":
        out["jd_text"] = text
    return jsonify({"job": out, "status": "validated"})


@bp.post("/api/profiles/<int:pid>/jobs")
def create_job(pid):
    oid, profile = load(pid)
    if len(profile.jobs) >= 50:
        raise ApiError("You can track up to 50 jobs. Delete some first.", 400)
    data = parse(JobIn, json_body().get("job") or {})
    job = Job(profile_id=profile.id, title=data.title, company=data.company, location=data.location,
              work_mode=data.work_mode, experience_level=data.experience_level,
              required_skills=data.required_skills, preferred_skills=data.preferred_skills,
              jd_text=data.jd_text, source=data.source, status=data.status, deadline=data.deadline,
              notes=data.notes, status_history=[_history(data.status)])
    db.session.add(job)
    db.session.commit()
    return jsonify({"job": job_json(job, profile), "message": f"Saved \"{job.title}\" to your tracker."}), 201


@bp.get("/api/profiles/<int:pid>/jobs")
def list_jobs(pid):
    _, profile = load(pid)
    q = request.args
    rows = [job_json(j, profile) for j in profile.jobs]

    def has(field, needle):
        return needle.lower() in (field or "").lower()

    if q.get("status") in STATUSES:
        rows = [r for r in rows if r["status"] == q["status"]]
    if q.get("work_mode"):
        rows = [r for r in rows if r["work_mode"] == q["work_mode"]]
    if q.get("experience_level"):
        rows = [r for r in rows if r["experience_level"] == q["experience_level"]]
    if q.get("location"):
        rows = [r for r in rows if has(r["location"], q["location"])]
    if q.get("q"):
        rows = [r for r in rows if has(r["title"], q["q"]) or has(r["company"], q["q"])]

    sort = q.get("sort", "match")
    if sort == "deadline":
        rows.sort(key=lambda r: (r["deadline"] is None, r["deadline"] or ""))
    elif sort == "newest":
        rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    else:
        rows.sort(key=lambda r: -(r["match"]["score"] if r["match"] else -1))
    return jsonify({"jobs": rows})


@bp.get("/api/profiles/<int:pid>/jobs/<int:jid>")
def get_job(pid, jid):
    _, profile = load(pid)
    return jsonify({"job": job_json(child(Job, profile, jid), profile)})


@bp.patch("/api/profiles/<int:pid>/jobs/<int:jid>")
def patch_job(pid, jid):
    _, profile = load(pid)
    job = child(Job, profile, jid)
    body = json_body()
    editable = ["title", "company", "location", "work_mode", "experience_level", "required_skills",
                "preferred_skills", "deadline", "notes", "status"]
    merged = {k: getattr(job, k) for k in editable}
    merged["jd_text"], merged["source"] = job.jd_text, job.source
    merged.update({k: body[k] for k in editable if k in body})
    data = parse(JobIn, merged)

    old_status = job.status
    for k in editable:
        setattr(job, k, getattr(data, k))
    if data.status != old_status:
        job.status_history = list(job.status_history or []) + [_history(data.status)]
    db.session.commit()
    return jsonify({"job": job_json(job, profile)})


@bp.delete("/api/profiles/<int:pid>/jobs/<int:jid>")
def delete_job(pid, jid):
    _, profile = load(pid)
    db.session.delete(child(Job, profile, jid))
    db.session.commit()
    return jsonify({"deleted": True})
