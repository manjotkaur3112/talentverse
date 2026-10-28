from conftest import H, OTHER, fake_ai, make_job, make_profile

QS = {"questions": [
    {"question": "Explain how your Portfolio project uses React state.", "focus": "React", "difficulty": "easy"},
    {"question": "How would you design a REST API for tasks?", "focus": "REST API", "difficulty": "medium"},
    {"question": "What is the difference between a process and a thread?", "focus": None, "difficulty": "hard"}]}
FB = {"relevance": 8, "clarity": 7, "completeness": 6, "strengths": ["Clear example"], "improvements": ["Mention hooks"],
      "missing_concepts": ["useEffect"], "sample_structure": ["Situation: [your real situation]", "Task:", "Action:", "Result:"]}


def test_session_answer_and_scores(client, monkeypatch):
    pid = make_profile(client)
    fake_ai(monkeypatch, QS)
    r = client.post(f"/api/profiles/{pid}/interviews", json={"mode": "technical", "target_role": "Frontend Intern", "count": 3}, headers=H())
    assert r.status_code == 201
    s = r.json["session"]
    assert s["mode"] == "technical" and len(s["questions"]) == 3 and s["avg_score"] is None
    qid = s["questions"][0]["id"]

    fake_ai(monkeypatch, FB)
    a = client.post(f"/api/profiles/{pid}/interviews/{s['id']}/questions/{qid}/answer",
                    json={"answer": "I keep the list in useState and update it with setState."}, headers=H())
    assert a.status_code == 200
    q = a.json["question"]
    assert q["score"] == 70 and q["feedback"]["overall"] == 70 and q["feedback"]["missing_concepts"] == ["useEffect"]
    assert a.json["session"]["avg_score"] == 70 and a.json["session"]["answered_count"] == 1
    listing = client.get(f"/api/profiles/{pid}/interviews", headers=H()).json["sessions"]
    assert listing[0]["avg_score"] == 70 and "questions" not in listing[0]


def test_validation(client, monkeypatch):
    pid = make_profile(client)
    assert client.post(f"/api/profiles/{pid}/interviews", json={"mode": "chat"}, headers=H()).status_code == 400
    assert client.post(f"/api/profiles/{pid}/interviews", json={"mode": "hr"}, headers=H()).status_code == 400  # no role
    fake_ai(monkeypatch, QS)
    jid = make_job(client, pid)
    sid = client.post(f"/api/profiles/{pid}/interviews", json={"mode": "hr", "job_id": jid}, headers=H()).json["session"]
    qid = sid["questions"][0]["id"]
    url = f"/api/profiles/{pid}/interviews/{sid['id']}/questions/{qid}/answer"
    assert client.post(url, json={"answer": "idk"}, headers=H()).status_code == 422
    assert client.post(url, json={"answer": "x" * 3001}, headers=H()).status_code == 422
    assert client.post(url, json={"answer": "A real answer " * 4}, headers=H(OTHER)).status_code == 404


def test_bad_feedback_is_rejected(client, monkeypatch):
    pid = make_profile(client)
    fake_ai(monkeypatch, QS)
    s = client.post(f"/api/profiles/{pid}/interviews", json={"mode": "hr", "target_role": "Intern"}, headers=H()).json["session"]
    fake_ai(monkeypatch, dict(FB, relevance=15), dict(FB, relevance=15))
    r = client.post(f"/api/profiles/{pid}/interviews/{s['id']}/questions/{s['questions'][0]['id']}/answer",
                    json={"answer": "A long enough answer here."}, headers=H())
    assert r.status_code == 502
    again = client.get(f"/api/profiles/{pid}/interviews/{s['id']}", headers=H()).json["session"]
    assert again["answered_count"] == 0
