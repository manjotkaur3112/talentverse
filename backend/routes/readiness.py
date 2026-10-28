"""Career readiness score and ATS resume optimizer."""
import json

from flask import Blueprint, jsonify, request

import ai
from core import ApiError, check_rate_limit, json_body
from guards import (build_draft, invented_numbers, keyword_report, resume_items, unsupported_keywords)
from models import ReadinessReport, ResumeOptimization, db
from prompts import OPTIMIZE_SYSTEM_PROMPT, RECOMMEND_SYSTEM_PROMPT, wrap
from routes.common import candidate_summary, load, required_job
from schemas import OptimizationDraft, Recommendations
from scoring import all_text, compute_readiness, evidence_map, rule_recommendations

bp = Blueprint("readiness", __name__)


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------- readiness
@bp.post("/api/profiles/<int:pid>/readiness")
def create_report(pid):
    oid, profile = load(pid)
    job = required_job(profile, json_body())
    facts = compute_readiness(profile, job.required_skills or [], job.preferred_skills or [], job.experience_level)

    ai_facts = {
        "role": job.title, "level": facts["level"], "score": facts["score"],
        "components": facts["components"], "weights": facts["weights"],
        "strong_skills": facts["strong_skills"], "missing_required": facts["missing_required"],
        "missing_preferred": facts["missing_preferred"], "listed_without_proof": facts["unverified_skills"],
        "experience_months": facts["experience_months"], "relevant_projects": facts["relevant_projects"],
        "experience_gaps": facts["experience_gaps"], "project_gaps": facts["project_gaps"],
        "candidate": candidate_summary(profile),
    }
    check_rate_limit(oid)
    try:
        recs = ai.structured_call(Recommendations, RECOMMEND_SYSTEM_PROMPT, wrap(_dumps(ai_facts), "facts"))
        facts["recommendations"] = [r.model_dump() for r in recs.recommendations]
        facts["recommendations_source"] = "ai"
    except ai.AIError:
        facts["recommendations"] = rule_recommendations(facts)
        facts["recommendations_source"] = "rules"

    score = facts.pop("score")
    report = ReadinessReport(profile_id=profile.id, job_id=job.id, job_title=job.title, score=score, details=facts)
    db.session.add(report)
    db.session.commit()
    return jsonify({"report": report.to_dict()}), 201


@bp.get("/api/profiles/<int:pid>/readiness")
def list_reports(pid):
    _, profile = load(pid)
    rows = profile.readiness_reports
    jid = request.args.get("job_id", type=int)
    if jid:
        rows = [r for r in rows if r.job_id == jid]
    return jsonify({"reports": [r.to_dict() for r in rows[:50]]})


# ---------------------------------------------------------------- optimizer
@bp.post("/api/profiles/<int:pid>/optimize")
def optimize(pid):
    oid, profile = load(pid)
    job = required_job(profile, json_body())
    required, preferred = job.required_skills or [], job.preferred_skills or []
    job_skills = list(dict.fromkeys([*required, *preferred]))

    present, missing, kw_score = keyword_report(profile, required, preferred)
    items = resume_items(profile)
    if not items:
        raise ApiError("Your profile has no summary, bullet points or project descriptions to improve yet.", 422)

    job_ctx = {"title": job.title, "required_skills": required, "preferred_skills": preferred,
               "description_excerpt": (job.jd_text or "")[:3000]}
    facts = {"skills": [s.name for s in profile.skills], "summary": profile.summary,
             **{k: v for k, v in candidate_summary(profile).items() if k != "skills"}}
    user = "\n".join([
        wrap(_dumps(job_ctx), "job"),
        wrap(_dumps([{"id": k, "text": v} for k, v in items.items()]), "resume_items"),
        wrap(_dumps(facts), "candidate_facts"),
    ])
    check_rate_limit(oid)
    draft = ai.structured_call(OptimizationDraft, OPTIMIZE_SYSTEM_PROMPT, user)

    supported = set(evidence_map(profile))
    allowed_text = all_text(profile)

    # --- guards: the AI may reword, never invent
    fixes, kept, dropped = {}, [], 0
    for f in draft.bullet_fixes:
        orig = items.get(f.id)
        if orig is None or f.improved.strip() == orig.strip():
            dropped += orig is None
            continue
        if (invented_numbers(f.improved, orig)
                or unsupported_keywords(f.improved, orig, job_skills, supported)):
            dropped += 1
            continue
        fixes[f.id] = f.improved
        kept.append({"id": f.id, "original": orig, "improved": f.improved, "reason": f.reason})

    unclear = []
    for u in draft.unclear_items:
        if u.id in items:
            unclear.append({"id": u.id, "text": items[u.id], "issue": u.issue, "suggestion": u.suggestion})

    summary, summary_rejected = draft.tailored_summary, False
    if summary and (invented_numbers(summary, allowed_text)
                    or unsupported_keywords(summary, "", job_skills, supported)):
        summary, summary_rejected = None, True
    if not summary:
        summary = fixes.get("summary") or profile.summary
    if not summary:
        top = [e["name"] for e in supported_names(profile)][:5]
        summary = f"Candidate with skills in {', '.join(top)}." if top else None

    # --- deterministic: claims the profile does not back up
    claims = []
    levels = {s.name.lower(): s.proficiency for s in profile.skills}
    for e in evidence_map(profile).values():
        if e["listed"] and not e["verified"]:
            lvl = levels.get(e["name"].lower())
            claims.append({
                "claim": f"{e['name']}" + (f" ({lvl})" if lvl else ""),
                "issue": "Listed, but no project or experience bullet shows it.",
                "suggestion": f"Add a project or bullet that uses {e['name']}, or remove it if you cannot back it up.",
            })

    result = {
        "present_keywords": present, "missing_keywords": missing, "bullet_fixes": kept,
        "unclear_items": unclear, "unsupported_claims": claims, "tailored_summary": summary,
        "summary_rejected": summary_rejected, "dropped_suggestions": dropped,
    }
    draft_md = build_draft(profile, job_skills, summary, fixes)
    row = ResumeOptimization(profile_id=profile.id, job_id=job.id, job_title=job.title,
                             keyword_score=kw_score, result=result, draft=draft_md)
    db.session.add(row)
    db.session.commit()
    return jsonify({"optimization": row.to_dict()}), 201


def supported_names(profile):
    return [e for e in evidence_map(profile).values() if e["verified"]]


@bp.get("/api/profiles/<int:pid>/optimizations")
def list_optimizations(pid):
    _, profile = load(pid)
    return jsonify({"optimizations": [o.to_dict() for o in profile.optimizations[:10]]})
