from conftest import H, fake_ai, make_job, make_profile
from test_interview import FB, QS
from test_learning import PLAN
from test_projects import idea
from test_readiness import RECS


def test_analytics_empty_state_has_no_fake_data(client):
    pid = make_profile(client)
    a = client.get(f"/api/profiles/{pid}/analytics", headers=H()).json
    assert a["readiness_history"] == [] and a["interviews"]["attempts"] == []
    assert a["learning"]["completed_by_week"] == [] and a["practice_needed"] == []
    assert a["summary"]["latest_readiness"] is None and a["summary"]["skills_listed"] == 2


def test_analytics_reflects_saved_records(client, monkeypatch):
    pid = make_profile(client)
    jid = make_job(client, pid)
    fake_ai(monkeypatch, RECS, PLAN, QS, FB, QS, dict(FB, relevance=3, clarity=3, completeness=3))
    client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H())
    plan = client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 2}, headers=H()).json["plan"]
    for t in plan["tasks"]:
        if t["skill"] == "AWS":
            client.patch(f"/api/profiles/{pid}/learning/tasks/{t['id']}", json={"status": "completed"}, headers=H())
    client.patch(f"/api/profiles/{pid}/jobs/{jid}", json={"status": "applied"}, headers=H())
    for fb_expected in (70, 30):
        s = client.post(f"/api/profiles/{pid}/interviews", json={"mode": "technical", "target_role": "Intern", "count": 3}, headers=H()).json["session"]
        client.post(f"/api/profiles/{pid}/interviews/{s['id']}/questions/{s['questions'][0]['id']}/answer",
                    json={"answer": "Some reasonably long answer text."}, headers=H())

    a = client.get(f"/api/profiles/{pid}/analytics", headers=H()).json
    assert len(a["readiness_history"]) == 1 and a["readiness_history"][0]["score"] == a["summary"]["latest_readiness"]
    assert a["learning"]["skills_learned"][0]["skill"] == "AWS" and a["summary"]["tasks_completed"] == 1
    assert a["learning"]["percent"] == 33 and len(a["learning"]["completed_by_week"]) == 1
    assert a["applications"]["funnel"]["applied"] == 1 and a["applications"]["upcoming_deadlines"][0]["id"] == jid
    assert a["interviews"]["trend"]["technical"] == {"attempts": 2, "first": 70, "latest": 30, "change": -40}
    assert a["interviews"]["weak_focus"] == [{"skill": "React", "avg": 50, "attempts": 2}]  # (70 + 30) / 2 is below 60
    skills = {p["skill"]: p["reasons"] for p in a["practice_needed"]}
    assert "Docker" in skills and any("learning task" in r for r in skills["Docker"])


def test_mentor_chat_uses_saved_context(client, monkeypatch):
    pid = make_profile(client)
    make_job(client, pid, title="ML Engineer", required_skills=["Python", "PyTorch"], preferred_skills=[])
    calls = fake_ai(monkeypatch, "Your ML Engineer match is low because PyTorch is missing. Next: learn PyTorch basics.")
    r = client.post(f"/api/profiles/{pid}/chat", json={"message": "Why is my ML Engineer match score low?"}, headers=H())
    assert r.status_code == 201 and [m["role"] for m in r.json["messages"]] == ["user", "assistant"]
    sent = calls[0][1]
    assert "ML Engineer" in sent and "PyTorch" in sent and "Why is my ML Engineer" in sent
    assert "manjot@gmail.com" not in sent  # email never goes to the model
    assert len(client.get(f"/api/profiles/{pid}/chat", headers=H()).json["messages"]) == 2
    assert client.post(f"/api/profiles/{pid}/chat", json={"message": " "}, headers=H()).status_code == 422
    assert client.delete(f"/api/profiles/{pid}/chat", headers=H()).status_code == 200
    assert client.get(f"/api/profiles/{pid}/chat", headers=H()).json["messages"] == []


def test_profile_delete_cascades_everything(client, monkeypatch):
    pid = make_profile(client)
    jid = make_job(client, pid)
    fake_ai(monkeypatch, RECS, "A reply.")
    client.post(f"/api/profiles/{pid}/readiness", json={"job_id": jid}, headers=H())
    client.post(f"/api/profiles/{pid}/chat", json={"message": "hi there"}, headers=H())
    client.post(f"/api/profiles/{pid}/portfolio", json={"idea": idea("beginner", "X")}, headers=H())
    assert client.delete(f"/api/profiles/{pid}", headers=H()).status_code == 200
    assert client.get(f"/api/profiles/{pid}/analytics", headers=H()).status_code == 404
