from conftest import H, JOB, OTHER, fake_ai, make_job, make_profile

JD_POSTING = {"title": "Data Analyst Intern", "company": "Acme", "location": "Pune", "work_mode": "hybrid",
              "experience_level": "intern", "required_skills": ["SQL", "Python"], "preferred_skills": ["Tableau"],
              "deadline": None, "notes": None}
JD = "We need a data analyst intern with SQL and Python skills. Nice to have: Tableau. " * 2


def test_extract_from_jd_and_role(client, monkeypatch):
    pid = make_profile(client)
    fake_ai(monkeypatch, JD_POSTING)
    r = client.post(f"/api/profiles/{pid}/jobs/extract", json={"jd_text": JD}, headers=H())
    assert r.status_code == 200 and r.json["job"]["source"] == "jd" and r.json["job"]["required_skills"] == ["SQL", "Python"]
    fake_ai(monkeypatch, dict(JD_POSTING, title="ML Engineer"))
    r = client.post(f"/api/profiles/{pid}/jobs/extract", json={"role_title": "ML Engineer"}, headers=H())
    assert r.json["job"]["source"] == "role_title"


def test_extract_rejects_bad_input(client, monkeypatch):
    pid = make_profile(client)
    assert client.post(f"/api/profiles/{pid}/jobs/extract", json={"jd_text": "short"}, headers=H()).status_code == 422
    fake_ai(monkeypatch, dict(JD_POSTING, required_skills=[], preferred_skills=[]), dict(JD_POSTING, required_skills=[], preferred_skills=[]))
    assert client.post(f"/api/profiles/{pid}/jobs/extract", json={"jd_text": JD}, headers=H()).status_code == 502


def test_create_list_match_filter(client):
    pid = make_profile(client)
    a = make_job(client, pid)
    make_job(client, pid, title="Backend Dev", company="Zed", location="Delhi", work_mode="onsite",
             required_skills=["Go"], preferred_skills=[], experience_level="mid", deadline=None)
    rows = client.get(f"/api/profiles/{pid}/jobs", headers=H()).json["jobs"]
    assert [r["title"] for r in rows] == ["Full Stack Intern", "Backend Dev"]  # sorted by match
    first = rows[0]["match"]
    assert first["missing_required"] == ["Docker"] and first["missing_preferred"] == ["AWS"]
    assert "2 of 3 required" in first["explanation"]
    q = lambda s: client.get(f"/api/profiles/{pid}/jobs?{s}", headers=H()).json["jobs"]
    assert len(q("work_mode=onsite")) == 1 and len(q("location=delhi")) == 1
    assert len(q("experience_level=entry")) == 1 and len(q("q=acme")) == 1 and len(q("status=applied")) == 0
    assert q("sort=deadline")[0]["id"] == a


def test_status_history_and_edit(client):
    pid = make_profile(client)
    jid = make_job(client, pid)
    r = client.patch(f"/api/profiles/{pid}/jobs/{jid}", json={"status": "applied", "notes": "Applied via site"}, headers=H())
    j = r.json["job"]
    assert j["status"] == "applied" and [h["status"] for h in j["status_history"]] == ["saved", "applied"]
    assert j["notes"] == "Applied via site" and j["title"] == "Full Stack Intern"
    assert client.patch(f"/api/profiles/{pid}/jobs/{jid}", json={"status": "ghosted"}, headers=H()).status_code == 422
    assert client.patch(f"/api/profiles/{pid}/jobs/{jid}", json={"deadline": "2026-13-45"}, headers=H()).status_code == 422


def test_validation_and_isolation(client):
    pid = make_profile(client)
    r = client.post(f"/api/profiles/{pid}/jobs", json={"job": {"title": "X", "required_skills": []}}, headers=H())
    assert r.status_code == 422
    jid = make_job(client, pid)
    assert client.get(f"/api/profiles/{pid}/jobs/{jid}", headers=H(OTHER)).status_code == 404
    assert client.delete(f"/api/profiles/{pid}/jobs/{jid}", headers=H()).status_code == 200
    assert client.get(f"/api/profiles/{pid}/jobs/{jid}", headers=H()).status_code == 404
