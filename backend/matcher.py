"""Deterministic job match scoring. The LLM extracts; plain code computes the score."""
from typing import Optional

ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python", "golang": "go",
    "reactjs": "react", "react.js": "react", "nodejs": "node.js", "node": "node.js",
    "expressjs": "express", "express.js": "express", "vuejs": "vue", "vue.js": "vue",
    "postgres": "postgresql", "mongo": "mongodb", "k8s": "kubernetes",
    "ml": "machine learning", "ai/ml": "machine learning", "html5": "html", "css3": "css",
    "rest": "rest api", "rest apis": "rest api", "restful apis": "rest api",
}


def norm(skill: str) -> str:
    s = " ".join(skill.strip().lower().split())
    return ALIASES.get(s, s)


def _split(wanted: list[str], have: set[str]):
    matched, missing, seen = [], [], set()
    for skill in wanted:
        k = norm(skill)
        if k in seen:
            continue
        seen.add(k)
        (matched if k in have else missing).append(skill)
    return matched, missing


def compute_match(profile_skills: list[str], required: list[str], preferred: list[str]) -> Optional[dict]:
    """Score = 70% required coverage + 30% preferred coverage (or 100% of whichever exists)."""
    have = {norm(s) for s in profile_skills}
    req_ok, req_missing = _split(required, have)
    pref_ok, pref_missing = _split(preferred, have)
    n_req, n_pref = len(req_ok) + len(req_missing), len(pref_ok) + len(pref_missing)

    if n_req == 0 and n_pref == 0:
        return None
    if n_req and n_pref:
        score = 0.7 * len(req_ok) / n_req + 0.3 * len(pref_ok) / n_pref
    elif n_req:
        score = len(req_ok) / n_req
    else:
        score = len(pref_ok) / n_pref
    return {
        "score": round(score * 100),
        "matched": req_ok + pref_ok,
        "missing_required": req_missing,
        "missing_preferred": pref_missing,
        "required_total": n_req,
        "preferred_total": n_pref,
    }


def explain(result: dict) -> str:
    """Plain-English reason for a match score (built from the numbers, not generated)."""
    n_req, n_pref = result["required_total"], result["preferred_total"]
    parts = []
    if n_req:
        text = f"You cover {n_req - len(result['missing_required'])} of {n_req} required skills"
        if result["missing_required"]:
            text += f" (missing {', '.join(result['missing_required'][:5])})"
        parts.append(text)
    if n_pref:
        parts.append(f"{n_pref - len(result['missing_preferred'])} of {n_pref} nice-to-have skills")
    return ". ".join(parts) + "." if parts else "No skills to compare."
