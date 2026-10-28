from conftest import GOOD, H, fake_ai, make_job, make_profile

PROFILE = dict(GOOD, experience=[], projects=[{"title": "Portfolio", "tech": ["React", "Flask"], "description": "Personal site"}])
RECS = {"recommendations": [{"action": "Learn Docker and containerize your portfolio.", "why": "Docker is required and missing.", "impact": "high"}]}


def test_score_is_computed_by_code(client, monkeypatch):
    pid = make_profile(client, PROFILE)
    jid = make_job(client, pid)
    fake_ai(monkeypatch, RECS)
    r = client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H())
    assert r.status_code == 201
    rep = r.json["report"]
    # skills: Python listed only (0.6), React proven (1), Docker missing -> req .533; preferred Flask proven, AWS missing -> .5
    # skills=52, experience 0/6 months=0, projects 1 of 2 = 50  ->  0.6*52 + 0.2*0 + 0.2*50 = 41
    assert rep["score"] == 41 and rep["components"] == {"skills": 52, "experience": 0, "projects": 50}
    assert rep["missing_required"] == ["Docker"] and rep["missing_preferred"] == ["AWS"]
    assert rep["unverified_skills"] == ["Python"]
    assert any(s["name"] == "React" and s["verified"] for s in rep["strong_skills"])
    assert rep["experience_gaps"] and rep["project_gaps"]
    assert rep["recommendations_source"] == "ai" and rep["recommendations"][0]["impact"] == "high"


def test_falls_back_to_rules_when_ai_fails(client, monkeypatch):
    pid = make_profile(client, PROFILE)
    jid = make_job(client, pid)
    fake_ai(monkeypatch, "garbage", "garbage")
    rep = client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H()).json["report"]
    assert rep["recommendations_source"] == "rules" and "Docker" in rep["recommendations"][0]["action"]


def test_experience_counts_dated_months(client, monkeypatch):
    pid = make_profile(client)  # Jun-Aug 2025 = 3 months
    jid = make_job(client, pid, experience_level="intern")
    fake_ai(monkeypatch, RECS)
    rep = client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H()).json["report"]
    assert rep["experience_months"] == 3 and rep["components"]["experience"] == 100


def test_history_and_validation(client, monkeypatch):
    pid = make_profile(client)
    jid = make_job(client, pid)
    assert client.post(f"/api/profiles/{pid}/readiness", json={}, headers=H()).status_code == 400
    assert client.post(f"/api/profiles/{pid}/readiness", json={"job_id": 999}, headers=H()).status_code == 404
    fake_ai(monkeypatch, RECS, RECS)
    for _ in range(2):
        client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H())
    assert len(client.get(f"/api/profiles/{pid}/readiness?job_id={jid}", headers=H()).json["reports"]) == 2
