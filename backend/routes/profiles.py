"""Resume extraction and profile create / update / delete."""
from flask import Blueprint, jsonify, request

import ai
import extractor
from core import ApiError, check_rate_limit, json_body, owner_id, parse
from models import Profile, db
from prompts import RESUME_SYSTEM_PROMPT, wrap
from schemas import ResumeProfile
from services import get_owned, save_profile

bp = Blueprint("profiles", __name__)


@bp.post("/api/extract")
def extract():
    """Extract + validate only. Nothing is written to the database here."""
    oid = owner_id()
    if "file" in request.files:
        f = request.files["file"]
        name = (f.filename or "").lower()
        data = f.read()
        if name.endswith(".pdf"):
            text = extractor.read_pdf(data)
        elif name.endswith(".txt"):
            text = data.decode("utf-8", errors="ignore")
        else:
            raise ApiError("Only PDF or TXT files are supported.", 400)
    else:
        text = json_body().get("text", "")

    text = extractor.clean_text(text, "resume")
    check_rate_limit(oid)
    profile = ai.structured_call(ResumeProfile, RESUME_SYSTEM_PROMPT, wrap(text, "resume"))
    profile = profile.with_computed_missing()
    if profile.is_empty():
        raise ApiError("No profile information could be found in this text.", 422)
    return jsonify({"profile": profile.model_dump(), "status": "validated"})


@bp.post("/api/profiles")
def create_or_update_profile():
    """Confirmed save. Re-validates the payload: never trust the client or the LLM."""
    oid = owner_id()
    body = json_body()
    data = parse(ResumeProfile, body.get("profile") or {})
    if data.is_empty():
        raise ApiError("There is nothing to save. The profile is empty.", 422)

    profile_id = body.get("profile_id")
    if profile_id is not None and (isinstance(profile_id, bool) or not isinstance(profile_id, int)):
        raise ApiError("profile_id must be an integer.", 400)
    mode = "replace" if body.get("mode") == "replace" else "merge"

    profile, created = save_profile(oid, data, profile_id, mode)
    msg = (f"Saved as new profile #{profile.id}." if created
           else f"Profile #{profile.id} updated ({'replaced' if mode == 'replace' else 'merged'}).")
    return jsonify({"profile": profile.to_dict(), "created": created, "message": msg}), (201 if created else 200)


@bp.get("/api/profiles")
def list_profiles():
    oid = owner_id()
    rows = Profile.query.filter_by(owner_id=oid).order_by(Profile.updated_at.desc()).all()
    return jsonify({"profiles": [p.to_summary() for p in rows]})


@bp.get("/api/profiles/<int:profile_id>")
def get_profile(profile_id):
    return jsonify({"profile": get_owned(owner_id(), profile_id).to_dict()})


@bp.delete("/api/profiles/<int:profile_id>")
def delete_profile(profile_id):
    db.session.delete(get_owned(owner_id(), profile_id))
    db.session.commit()
    return jsonify({"deleted": True})


@bp.delete("/api/me")
def delete_all_my_data():
    oid = owner_id()
    count = 0
    for p in Profile.query.filter_by(owner_id=oid).all():
        db.session.delete(p)
        count += 1
    db.session.commit()
    return jsonify({"deleted": count})
