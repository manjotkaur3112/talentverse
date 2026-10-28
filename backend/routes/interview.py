"""Mock interview coach: generate questions, score text answers, keep every attempt."""
import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify

import ai
from core import ApiError, check_rate_limit, json_body, one_of
from models import InterviewQuestion, InterviewSession, db
from prompts import FEEDBACK_SYSTEM_PROMPT, QUESTIONS_SYSTEM_PROMPT, wrap
from routes.common import candidate_summary, child, int_field, load, optional_job
from schemas import AnswerFeedback, QuestionSet

bp = Blueprint("interview", __name__)
MODES = ("technical", "hr", "behavioral")


@bp.post("/api/profiles/<int:pid>/interviews")
def create_session(pid):
    oid, profile = load(pid)
    body = json_body()
    mode = one_of(body.get("mode"), MODES, "mode")
    count = int_field(body, "count", 3, 8, 5)
    job = optional_job(profile, body)
    role = job.title if job else (body.get("target_role") or "").strip()
    if not role:
        raise ApiError("Choose a saved job or type the role you are preparing for.", 400)
    if len(role) > 120:
        raise ApiError("Role is too long (max 120 characters).", 422)
    if len(profile.interviews) >= 60:
        raise ApiError("Interview history limit reached. Delete older sessions first.", 400)

    setup = {"mode": mode, "role": role, "question_count": count}
    if job:
        setup.update(required_skills=job.required_skills or [], preferred_skills=job.preferred_skills or [],
                     level=job.experience_level)
    check_rate_limit(oid)
    qs = ai.structured_call(QuestionSet, QUESTIONS_SYSTEM_PROMPT,
                            wrap(json.dumps(setup), "setup") + "\n" + wrap(json.dumps(candidate_summary(profile), ensure_ascii=False), "candidate"))

    session = InterviewSession(profile_id=profile.id, job_id=job.id if job else None, mode=mode, target_role=role)
    for i, q in enumerate(qs.questions[:count]):
        session.questions.append(InterviewQuestion(position=i, question=q.question, focus=q.focus, difficulty=q.difficulty))
    db.session.add(session)
    db.session.commit()
    return jsonify({"session": session.to_dict()}), 201


@bp.get("/api/profiles/<int:pid>/interviews")
def list_sessions(pid):
    _, profile = load(pid)
    return jsonify({"sessions": [s.to_dict(with_questions=False) for s in profile.interviews]})


@bp.get("/api/profiles/<int:pid>/interviews/<int:sid>")
def get_session(pid, sid):
    _, profile = load(pid)
    return jsonify({"session": child(InterviewSession, profile, sid).to_dict()})


@bp.post("/api/profiles/<int:pid>/interviews/<int:sid>/questions/<int:qid>/answer")
def answer(pid, sid, qid):
    oid, profile = load(pid)
    session = child(InterviewSession, profile, sid)
    q = InterviewQuestion.query.filter_by(id=qid, session_id=session.id).first()
    if q is None:
        raise ApiError("Question not found.", 404)

    text = (json_body().get("answer") or "").strip()
    if len(text) < 10:
        raise ApiError("Write a bit more. Your answer is too short to evaluate.", 422)
    if len(text) > 3000:
        raise ApiError("Your answer is too long (max 3000 characters).", 422)

    check_rate_limit(oid)
    setup = {"mode": session.mode, "role": session.target_role}
    fb = ai.structured_call(AnswerFeedback, FEEDBACK_SYSTEM_PROMPT,
                            "\n".join([wrap(json.dumps(setup), "setup"), wrap(q.question, "question"), wrap(text, "answer")]))
    q.answer = text
    q.feedback = {**fb.model_dump(), "overall": fb.overall()}
    q.score = fb.overall()
    q.answered_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"question": q.to_dict(), "session": session.to_dict(with_questions=False)})


@bp.delete("/api/profiles/<int:pid>/interviews/<int:sid>")
def delete_session(pid, sid):
    _, profile = load(pid)
    db.session.delete(child(InterviewSession, profile, sid))
    db.session.commit()
    return jsonify({"deleted": True})
