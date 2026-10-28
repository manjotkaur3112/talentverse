from conftest import GOOD, H, fake_ai, make_job, make_profile


def run(client, monkeypatch, draft):
    pid = make_profile(client)
    jid = make_job(client, pid)  # needs Python, React, Docker; nice to have Flask, AWS
    fake_ai(monkeypatch, draft)
    r = client.post(f"/api/profiles/{pid}/optimize", json={"job_id": jid}, headers=H())
    assert r.status_code == 201, r.json
    return r.json["optimization"]


def test_valid_rewrites_are_kept(client, monkeypatch):
    o = run(client, monkeypatch, {
        "tailored_summary": "Student with Python and React skills, building web apps.",
        "bullet_fixes": [{"id": "exp0-0", "improved": "Developed a REST API with Flask for internal tools", "reason": "Stronger verb"}],
        "unclear_items": [{"id": "summary", "issue": "Vague", "suggestion": "Name your strongest project"}]})
    assert o["bullet_fixes"][0]["original"] == "Built a REST API with Flask for internal tools"
    assert "Developed a REST API" in o["draft"] and o["dropped_suggestions"] == 0
    assert o["unclear_items"][0]["text"] == GOOD["summary"]
    assert o["tailored_summary"].startswith("Student with Python")


def test_ai_cannot_invent_numbers_skills_or_ids(client, monkeypatch):
    o = run(client, monkeypatch, {
        "tailored_summary": "Docker expert with 3 years of experience.",
        "bullet_fixes": [
            {"id": "exp0-0", "improved": "Built a REST API with Flask, cutting latency by 40%", "reason": "x"},
            {"id": "exp0-1", "improved": "Created React dashboards deployed with Docker", "reason": "x"},
            {"id": "nope", "improved": "Something else entirely", "reason": "x"}],
        "unclear_items": []})
    assert o["bullet_fixes"] == [] and o["dropped_suggestions"] == 3
    assert o["summary_rejected"] is True and "Docker" not in o["tailored_summary"]
    assert "40%" not in o["draft"] and "Docker" not in o["draft"]


def test_keywords_and_unsupported_claims(client, monkeypatch):
    o = run(client, monkeypatch, {"tailored_summary": None, "bullet_fixes": [], "unclear_items": []})
    assert o["missing_keywords"] == ["Docker", "AWS"] and set(o["present_keywords"]) == {"Python", "React", "Flask"}
    assert o["keyword_score"] == 60
    assert any(c["claim"].startswith("Python") for c in o["unsupported_claims"])
    assert "Relevant to this role: Python, React" in o["draft"]


def test_needs_something_to_improve(client):
    pid = make_profile(client, {"full_name": "A B", "skills": [{"name": "Go"}]})
    jid = make_job(client, pid)
    assert client.post(f"/api/profiles/{pid}/optimize", json={"job_id": jid}, headers=H()).status_code == 422
