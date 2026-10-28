"""Helpers shared by route modules."""
from core import ApiError, owner_id
from models import Job
from services import NotFound, get_owned


def load(pid):
    oid = owner_id()
    return oid, get_owned(oid, pid)


def child(model, profile, cid):
    obj = model.query.filter_by(id=cid, profile_id=profile.id).first()
    if obj is None:
        raise NotFound(f"{model.__name__} not found.")
    return obj


def int_field(body, key, lo, hi, default):
    v = body.get(key, default)
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ApiError(f"{key} must be a whole number from {lo} to {hi}.", 400)
    return v


def optional_job(profile, body):
    jid = body.get("job_id")
    if jid is None:
        return None
    if isinstance(jid, bool) or not isinstance(jid, int):
        raise ApiError("job_id must be a number.", 400)
    return child(Job, profile, jid)


def required_job(profile, body):
    job = optional_job(profile, body)
    if job is None:
        raise ApiError("Choose a saved job or target role first.", 400)
    return job


def have_skills(profile):
    """Skill names the candidate can be matched on: listed skills plus project technologies."""
    return [s.name for s in profile.skills] + [t for p in profile.projects for t in (p.tech or [])]


def candidate_summary(profile):
    """Compact, non-identifying facts about the candidate for prompts."""
    return {
        "skills": [s.name for s in profile.skills][:40],
        "projects": [{"title": p.title, "tech": (p.tech or [])[:8]} for p in profile.projects][:8],
        "experience": [{"role": e.role, "organization": e.organization} for e in profile.experiences][:6],
        "education": [{"degree": e.degree, "institution": e.institution} for e in profile.education][:3],
    }
