# TalentVerse: AI Career & Skills Intelligence

CSB312 CA3 Mini Project 2 (Option 9, TalentVerse).

A resume goes in. The AI extracts a structured skills and experience profile, the server validates it,
you review and confirm it, and it is saved to a database. That saved profile then powers a career workspace
with eight tools. Every score, percentage and chart is computed from saved database records.

## Workflow

```
Upload PDF/TXT or paste text
  -> POST /api/extract   (text extraction -> LLM with JSON schema in prompt -> Pydantic validation, 1 retry)
  -> Preview screen      (user edits, missing fields highlighted)
  -> POST /api/profiles  (re-validate -> create or merge/replace -> DB commit)
  -> Frontend shows the saved record from the database
```

## Career workspace (open a profile, then use the tabs)

| Tab | What it does | AI does | Code does |
|---|---|---|---|
| Jobs | Paste a job description or a role title. Match score, filters (role, location, level, work mode), statuses (saved, applied, shortlisted, interview, offer, rejected), deadlines, notes | Extracts requirements into a schema | Match score, explanation, status history |
| Readiness | Score out of 100 for a role, strong and missing skills, experience and project gaps, recommendations | Writes recommendations from measured facts (rule-based fallback if AI fails) | The whole score: 60% skills, 20% experience, 20% projects. Skills with proof in a project count fully, skills only listed count 60% |
| Resume | Missing keywords, unsupported claims, stronger wording, tailored draft | Suggests rewordings | Guards block invented numbers, skills and unknown ids. Draft is assembled from saved data |
| Learning | Study plan with daily and weekly tasks, status, progress %, next topic, free resources | Writes the plan (template fallback) | Progress, next topic, curated or search links (the AI never writes URLs) |
| Interview | Technical, HR and behavioral practice, text answers, feedback, STAR structure, saved attempts | Questions and feedback | Overall score, trends |
| Projects | 3 ideas per goal (beginner to advanced), milestones, datasets, metrics, README outline, repo and demo links | Designs ideas (preview only until you add one) | Completion rules: needs a repo or demo link |
| Progress | Readiness history, tasks and milestones, projects, interview trend, funnel, skills needing practice | Nothing | Everything, from saved records |
| Mentor | Chat grounded in your saved data | Answers | Builds the context (email is never sent) |

Existing deployments: new tables are created automatically on start. The old `jd_matches` table is no longer used.

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite, plain CSS |
| Backend | Python Flask, Flask-SQLAlchemy, Pydantic v2, pypdf, gunicorn |
| Database | SQLite locally, PostgreSQL when deployed (via `DATABASE_URL`) |
| AI | Gemini (default) or Claude, selected with `AI_PROVIDER` |

## Run locally

Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then put your GEMINI_API_KEY in .env
python app.py                     # http://localhost:5000
pytest -q                         # 38 tests, no API key needed (AI is mocked)
```

Frontend (new terminal):
```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

If you see "The AI service failed", run `python check_ai.py` in `backend/`. It tests your key and model
and prints the real error.

Try `samples/resume_good.txt`, `samples/resume_missing_fields.txt` and `samples/job_description.txt`.
Suggested demo order: save a profile, add a job, Readiness, Resume, Learning, Interview, Projects, Progress, Mentor.

Get a free Gemini key at https://aistudio.google.com/apikey. To use Claude instead, set
`AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.

## Deploy (required for submission)

1. Push this folder to GitHub.
2. Backend on Render: New > Blueprint, pick the repo (it reads `render.yaml`, creates the API and a free
   Postgres database). Set `GEMINI_API_KEY` and `FRONTEND_ORIGIN` (your Vercel URL, no trailing slash).
3. Frontend on Vercel: import the repo, set Root Directory to `frontend`, add the env var
   `VITE_API_URL` = your Render URL (no trailing slash), deploy.
4. If you change `FRONTEND_ORIGIN` later, redeploy the backend. Submit the Vercel URL.

Render's free tier sleeps when idle, so the first request can take about a minute. Open the site before
your demo or viva to wake it.

## Report and viva cheat sheet

**Schema** (`backend/schemas.py`): `ResumeProfile` with `full_name`, `email`, `summary`, `skills[]`,
`experience[]`, `education[]`, `projects[]`, `missing_fields[]`. Dates are `YYYY-MM`, proficiency is only set
if the resume states it, unknown values are `null`.

**Prompt** (`backend/prompts.py`): schema is written into the system prompt, rules forbid guessing, resume
text is wrapped in `<resume>` tags and treated as untrusted data (prompt-injection safeguard).

**Validation**: Pydantic checks types, enums, date format, date order and email. If the LLM output fails, the
errors are fed back and it retries once, then a clear error is shown. The save endpoint validates again
because the browser is not trusted either. `missing_fields` is also computed in code, not only by the LLM.

**Database** (`backend/models.py`): `profiles`, `skills`, `experiences`, `education`, `projects`, plus the workspace
tables `jobs`, `readiness_reports`, `resume_optimizations`, `learning_plans`, `learning_tasks`, `resources`,
`interview_sessions`, `interview_questions`, `portfolio_projects`, `project_milestones`, `chat_messages`.
All hang off `profile_id` with cascade delete.
- Create: confirmed preview with "Create a new profile".
- Update: choose an existing profile, then Merge (dedupes skills and entries, nulls never erase data) or Replace.

**Error handling**: empty or tiny input, wrong file type, unreadable PDF, file over 5 MB, invalid AI output,
AI service down, rate limit, network failure (toast and Retry button), invalid fields on save (field-level messages).

**Safeguards**: nothing is saved until Confirm; API keys stay on the server; resume text is never stored or
logged; each browser gets an anonymous owner id and can only see its own profiles; email is masked by default;
delete one profile or all data; upload size cap; per-user and global rate limits on AI endpoints.

**Why "code computes, AI explains"**: scores and progress must be reproducible and defensible. The readiness score,
match score, progress, next topic and analytics are plain code over database rows. The AI extracts, writes plans
and questions, and explains. If the AI fails, readiness and plans fall back to rule-based output.

**Anti-fabrication guards** (`backend/guards.py`): an AI rewrite is dropped if it adds a number not in the original,
mentions a job skill the candidate has no evidence for, or refers to text that does not exist. The tailored summary is
replaced with a safe one if it breaks the same rules.

**Test cases** (`backend/tests/`, 38 tests, one file per feature):
1. Success: extract, confirm, save, read back.
2. Missing field: no email, education or projects are flagged and not invented.
3. Errors: tiny input, wrong file type, bad PDF, invalid AI output (twice and recovered), invalid save payload.

**Limitations**: no login (browser-based owner id only), skill matching is exact after a small alias table
(no semantic matching), scanned image PDFs are not OCR'd, in-memory rate limiter is per server process,
free-tier cold starts.

**Future work**: user accounts, OCR, DOCX upload, embedding-based skill matching, voice answers in the mock
interview, a live job API, email reminders for deadlines.
