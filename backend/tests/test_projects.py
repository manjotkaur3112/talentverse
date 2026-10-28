from conftest import H, fake_ai, make_job, make_profile


def idea(level, title):
    return {"level": level, "title": title, "problem_statement": "Students cannot track applications.",
            "features": ["Add job", "Track status"], "tech_stack": ["React", "Docker"],
            "milestones": [{"title": "Design schema", "description": ""}, {"title": "Build API", "description": ""}],
            "datasets": [{"name": "Sample job posts", "description": "Search Kaggle for job postings"}],
            "evaluation_metrics": ["Task completion rate"], "readme_outline": ["Overview", "Setup"],
            "github_description": "Track job applications.", "skills_demonstrated": ["Docker"]}


IDEAS = {"ideas": [idea("advanced", "C"), idea("beginner", "A"), idea("intermediate", "B")]}


def test_ideas_are_previews_then_saved_on_choice(client, monkeypatch):
    pid = make_profile(client)
    jid = make_job(client, pid)
    fake_ai(monkeypatch, IDEAS)
    r = client.post(f"/api/profiles/{pid}/project-ideas", json={"job_id": jid}, headers=H())
    assert [i["level"] for i in r.json["ideas"]] == ["beginner", "intermediate", "advanced"]
    assert client.get(f"/api/profiles/{pid}/portfolio", headers=H()).json["projects"] == []  # nothing saved yet
    saved = client.post(f"/api/profiles/{pid}/portfolio", json={"idea": r.json["ideas"][0], "job_id": jid}, headers=H())
    assert saved.status_code == 201 and len(saved.json["project"]["milestones"]) == 2


def test_ideas_validation(client, monkeypatch):
    pid = make_profile(client)
    assert client.post(f"/api/profiles/{pid}/project-ideas", json={}, headers=H()).status_code == 400
    fake_ai(monkeypatch, {"ideas": [idea("beginner", "A")] * 3}, {"ideas": [idea("beginner", "A")] * 3})
    assert client.post(f"/api/profiles/{pid}/project-ideas", json={"goal": "ML Engineer"}, headers=H()).status_code == 502


def test_completion_needs_proof_and_updates_profile(client):
    pid = make_profile(client)
    proj = client.post(f"/api/profiles/{pid}/portfolio", json={"idea": idea("beginner", "Job Tracker")}, headers=H()).json["project"]
    url = f"/api/profiles/{pid}/portfolio/{proj['id']}"
    assert client.patch(url, json={"status": "completed"}, headers=H()).status_code == 422
    assert client.patch(url, json={"repo_url": "ftp://x"}, headers=H()).status_code == 422
    m = client.patch(f"{url}/milestones/{proj['milestones'][0]['id']}", json={"done": True}, headers=H()).json["project"]
    assert m["status"] == "in_progress" and m["milestones"][0]["done"] is True
    done = client.patch(url, json={"status": "completed", "repo_url": "https://github.com/me/tracker",
                                   "demo_url": "https://tracker.example.com"}, headers=H()).json
    assert done["project"]["status"] == "completed" and done["added_to_profile"] is True
    prof = client.get(f"/api/profiles/{pid}", headers=H()).json["profile"]
    assert "Job Tracker" in [p["title"] for p in prof["projects"]]
    client.patch(url, json={"status": "in_progress"}, headers=H())
    again = client.patch(url, json={"status": "completed"}, headers=H()).json
    assert again["added_to_profile"] is False
    assert client.delete(url, headers=H()).status_code == 200
