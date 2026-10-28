import json
from io import BytesIO

from conftest import GOOD, H, OTHER, OWNER, fake_ai, make_profile

import ai
from app import create_app

RESUME = ("Manjot Kaur. B.Tech CSE, Lovely Professional University, 2027. "
          "Skills: Python, React, SQL. Project: Portfolio site built with React and Flask.")


def test_health_and_root(client):
    assert client.get("/api/health").json == {"status": "ok"}
    assert client.get("/").json["service"] == "TalentVerse API"


def test_requires_owner_header(client):
    assert client.get("/api/profiles").status_code == 401


def test_extract_then_save_then_read(client, monkeypatch):
    fake_ai(monkeypatch, GOOD)
    r = client.post("/api/extract", json={"text": RESUME}, headers=H())
    assert r.status_code == 200 and r.json["status"] == "validated"
    saved = client.post("/api/profiles", json={"profile": r.json["profile"]}, headers=H())
    assert saved.status_code == 201 and saved.json["created"] is True
    got = client.get(f"/api/profiles/{saved.json['profile']['id']}", headers=H())
    assert {s["name"] for s in got.json["profile"]["skills"]} == {"Python", "React"}


def test_missing_fields_flagged(client, monkeypatch):
    fake_ai(monkeypatch, dict(GOOD, email=None, education=[], projects=[]))
    p = client.post("/api/extract", json={"text": RESUME}, headers=H()).json["profile"]
    assert p["email"] is None and {"email", "education", "projects"} <= set(p["missing_fields"])


def test_input_errors(client):
    assert client.post("/api/extract", json={"text": "hi"}, headers=H()).status_code == 422
    r = client.post("/api/extract", data={"file": (BytesIO(b"x" * 100), "cv.exe")}, headers=H(), content_type="multipart/form-data")
    assert r.status_code == 400
    r = client.post("/api/extract", data={"file": (BytesIO(b"not a pdf"), "cv.pdf")}, headers=H(), content_type="multipart/form-data")
    assert r.status_code == 422


def test_invalid_ai_output(client, monkeypatch):
    calls = fake_ai(monkeypatch, "nope", "still nope")
    assert client.post("/api/extract", json={"text": RESUME}, headers=H()).status_code == 502
    assert len(calls) == 2
    fake_ai(monkeypatch, dict(GOOD, email="not-an-email"), GOOD)
    assert client.post("/api/extract", json={"text": RESUME}, headers=H()).json["profile"]["email"] == "manjot@gmail.com"


def test_save_validation(client):
    bad = dict(GOOD, experience=[{"role": "Intern", "start_date": "2024-13", "highlights": []}])
    r = client.post("/api/profiles", json={"profile": bad}, headers=H())
    assert r.status_code == 422 and r.json["details"]
    assert client.post("/api/profiles", json={"profile": {}}, headers=H()).status_code == 422


def test_merge_and_replace(client):
    pid = make_profile(client)
    more = {"skills": [{"name": "python", "proficiency": "advanced"}, {"name": "SQL"}]}
    p = client.post("/api/profiles", json={"profile": more, "profile_id": pid}, headers=H()).json["profile"]
    assert sorted(s["name"] for s in p["skills"]) == ["Python", "React", "SQL"]
    assert p["full_name"] == "Manjot Kaur"
    p = client.post("/api/profiles", json={"profile": {"full_name": "M K", "skills": [{"name": "Go"}]},
                                           "profile_id": pid, "mode": "replace"}, headers=H()).json["profile"]
    assert [s["name"] for s in p["skills"]] == ["Go"] and p["projects"] == []


def test_owner_isolation_and_delete_all(client):
    pid = make_profile(client)
    assert client.get(f"/api/profiles/{pid}", headers=H(OTHER)).status_code == 404
    assert client.delete(f"/api/profiles/{pid}", headers=H(OTHER)).status_code == 404
    assert client.delete("/api/me", headers=H()).json["deleted"] == 1


def test_rate_limit(tmp_path, monkeypatch):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/r.db", "RATE_LIMIT_PER_HOUR": 1})
    c = app.test_client()
    monkeypatch.setattr(ai, "_call_model", lambda s, u, json_mode=True: json.dumps(GOOD))
    assert c.post("/api/extract", json={"text": RESUME}, headers=H()).status_code == 200
    assert c.post("/api/extract", json={"text": RESUME}, headers=H()).status_code == 429
