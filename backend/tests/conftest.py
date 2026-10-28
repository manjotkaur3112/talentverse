import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai  # noqa: E402
from app import create_app  # noqa: E402

OWNER = "owner-aaaaaaaaaaaaaaaa"
OTHER = "owner-bbbbbbbbbbbbbbbb"

GOOD = {
    "full_name": "Manjot Kaur", "email": "manjot@gmail.com", "summary": "Student interested in web development.",
    "skills": [{"name": "Python", "category": "language", "proficiency": None},
               {"name": "React", "category": "framework", "proficiency": "advanced"}],
    "experience": [{"role": "Web Intern", "organization": "Nimbus Labs", "start_date": "2025-06", "end_date": "2025-08",
                    "highlights": ["Built a REST API with Flask for internal tools", "Created React dashboards"]}],
    "education": [{"degree": "B.Tech CSE", "institution": "Lovely Professional University", "year": 2028}],
    "projects": [{"title": "Portfolio", "tech": ["React", "Flask"], "description": "Personal site"}],
    "missing_fields": [],
}


@pytest.fixture()
def client(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/t.db",
                      "RATE_LIMIT_PER_HOUR": 1000, "GLOBAL_LIMIT_PER_HOUR": 1000})
    return app.test_client()


def H(owner=OWNER):
    return {"X-Owner-Id": owner}


def fake_ai(monkeypatch, *replies):
    """Queue canned model replies. dicts are JSON-encoded, strings are returned as-is."""
    queue = list(replies)
    calls = []

    def fake(system, user, json_mode=True):
        calls.append((system, user))
        r = queue.pop(0)
        return r if isinstance(r, str) else json.dumps(r)

    monkeypatch.setattr(ai, "_call_model", fake)
    return calls


def make_profile(client, data=GOOD, owner=OWNER):
    r = client.post("/api/profiles", json={"profile": data}, headers=H(owner))
    assert r.status_code == 201, r.json
    return r.json["profile"]["id"]


JOB = {"title": "Full Stack Intern", "company": "Acme", "location": "Remote India", "work_mode": "remote",
       "experience_level": "entry", "required_skills": ["Python", "React", "Docker"],
       "preferred_skills": ["Flask", "AWS"], "deadline": "2099-12-31"}


def make_job(client, pid, owner=OWNER, **over):
    r = client.post(f"/api/profiles/{pid}/jobs", json={"job": {**JOB, **over}}, headers=H(owner))
    assert r.status_code == 201, r.json
    return r.json["job"]["id"]
