from conftest import H, fake_ai, make_job, make_profile

PLAN = {"title": "Docker and AWS in 2 weeks", "weeks": [
    {"week": 1, "goal": "Docker basics", "tasks": [
        {"skill": "docker", "title": "Install Docker and run hello-world", "cadence": "daily", "day": 1, "minutes": 30},
        {"skill": "Docker", "title": "Containerize a Flask app", "cadence": "weekly", "day": None, "minutes": 90},
        {"skill": "Kubernetes", "title": "Not requested", "cadence": "daily", "day": 2, "minutes": 30}]},
    {"week": 2, "goal": "AWS basics", "tasks": [
        {"skill": "AWS", "title": "Create a free-tier account", "cadence": "daily", "day": 1, "minutes": 30}]}]}


def setup(client):
    pid = make_profile(client)
    return pid, make_job(client, pid)


def test_ai_plan_progress_and_next_topic(client, monkeypatch):
    pid, jid = setup(client)
    fake_ai(monkeypatch, PLAN)
    r = client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 2, "hours_per_week": 5}, headers=H())
    assert r.status_code == 201
    d = r.json
    assert d["plan"]["generated_by"] == "ai"
    assert [t["skill"] for t in d["plan"]["tasks"]] == ["Docker", "Docker", "AWS"]  # unknown skill dropped, names canonical
    assert d["progress"] == {"total": 3, "completed": 0, "in_progress": 0, "percent": 0}
    assert d["next_topic"]["skill"] == "Docker"
    assert set(d["resources"]) == {"Docker", "AWS"} and any(x["source"] == "curated" for x in d["resources"]["Docker"])

    tid = d["plan"]["tasks"][1]["id"]
    d = client.patch(f"/api/profiles/{pid}/learning/tasks/{tid}", json={"status": "in_progress"}, headers=H()).json
    assert d["next_topic"]["task_id"] == tid and "started" in d["next_topic"]["reason"]
    for t in d["plan"]["tasks"]:
        d = client.patch(f"/api/profiles/{pid}/learning/tasks/{t['id']}", json={"status": "completed"}, headers=H()).json
    assert d["progress"]["percent"] == 100 and d["next_topic"] is None
    assert client.patch(f"/api/profiles/{pid}/learning/tasks/{tid}", json={"status": "bogus"}, headers=H()).status_code == 400


def test_template_fallback(client, monkeypatch):
    pid, jid = setup(client)
    fake_ai(monkeypatch, "bad", "bad")
    d = client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 2}, headers=H()).json
    assert d["plan"]["generated_by"] == "template" and d["progress"]["total"] == 10  # 2 skills x 5 tasks
    assert {t["skill"] for t in d["plan"]["tasks"]} == {"Docker", "AWS"}


def test_new_plan_replaces_active_one(client, monkeypatch):
    pid, jid = setup(client)
    fake_ai(monkeypatch, "bad", "bad", "bad", "bad")
    client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 1}, headers=H())
    client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 1}, headers=H())
    assert client.get(f"/api/profiles/{pid}/learning", headers=H()).json["progress"]["total"] == 10


def test_validation(client):
    pid, jid = setup(client)
    assert client.post(f"/api/profiles/{pid}/learning/plan", json={}, headers=H()).status_code == 400
    assert client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 20}, headers=H()).status_code == 400
    full = make_job(client, pid, title="Easy", required_skills=["Python"], preferred_skills=[])
    assert client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": full}, headers=H()).status_code == 422


def test_custom_resources(client, monkeypatch):
    pid, jid = setup(client)
    fake_ai(monkeypatch, PLAN)
    client.post(f"/api/profiles/{pid}/learning/plan", json={"job_id": jid, "weeks": 2}, headers=H())
    bad = client.post(f"/api/profiles/{pid}/learning/resources", json={"skill": "Docker", "title": "x", "url": "javascript:alert(1)"}, headers=H())
    assert bad.status_code == 422
    ok = client.post(f"/api/profiles/{pid}/learning/resources", json={"skill": "Docker", "title": "My notes", "url": "https://example.com/docker"}, headers=H())
    mine = [r for r in ok.json["resources"]["Docker"] if r["source"] == "user"]
    assert len(mine) == 1
    after = client.delete(f"/api/profiles/{pid}/learning/resources/{mine[0]['id']}", headers=H()).json
    assert not [r for r in after["resources"]["Docker"] if r["source"] == "user"]
