"""Database design: one profile owns skills, experience, education, projects and job matches."""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


def iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite drops tzinfo
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class Profile(db.Model):
    __tablename__ = "profiles"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.String(64), nullable=False, index=True)
    full_name = db.Column(db.String(120))
    email = db.Column(db.String(254))
    summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    skills = db.relationship("Skill", backref="profile", cascade="all, delete-orphan", order_by="Skill.id")
    experiences = db.relationship("Experience", backref="profile", cascade="all, delete-orphan", order_by="Experience.id")
    education = db.relationship("Education", backref="profile", cascade="all, delete-orphan", order_by="Education.id")
    projects = db.relationship("Project", backref="profile", cascade="all, delete-orphan", order_by="Project.id")
    jobs = db.relationship("Job", backref="profile", cascade="all, delete-orphan", order_by="Job.id.desc()")
    readiness_reports = db.relationship("ReadinessReport", backref="profile", cascade="all, delete-orphan", order_by="ReadinessReport.id.desc()")
    optimizations = db.relationship("ResumeOptimization", backref="profile", cascade="all, delete-orphan", order_by="ResumeOptimization.id.desc()")
    plans = db.relationship("LearningPlan", backref="profile", cascade="all, delete-orphan", order_by="LearningPlan.id.desc()")
    resources = db.relationship("Resource", backref="profile", cascade="all, delete-orphan", order_by="Resource.id")
    interviews = db.relationship("InterviewSession", backref="profile", cascade="all, delete-orphan", order_by="InterviewSession.id.desc()")
    portfolio = db.relationship("PortfolioProject", backref="profile", cascade="all, delete-orphan", order_by="PortfolioProject.id.desc()")
    chat = db.relationship("ChatMessage", backref="profile", cascade="all, delete-orphan", order_by="ChatMessage.id")

    def to_dict(self):
        out = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "summary": self.summary,
            "skills": [s.to_dict() for s in self.skills],
            "experience": [e.to_dict() for e in self.experiences],
            "education": [e.to_dict() for e in self.education],
            "projects": [p.to_dict() for p in self.projects],
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        return out

    def to_summary(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "skill_count": len(self.skills),
            "experience_count": len(self.experiences),
            "updated_at": iso(self.updated_at),
        }


class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(20), default="other")
    proficiency = db.Column(db.String(20))

    def to_dict(self):
        return {"name": self.name, "category": self.category, "proficiency": self.proficiency}


class Experience(db.Model):
    __tablename__ = "experiences"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    role = db.Column(db.String(120), nullable=False)
    organization = db.Column(db.String(120))
    start_date = db.Column(db.String(7))
    end_date = db.Column(db.String(7))
    highlights = db.Column(db.JSON, default=list)

    def to_dict(self):
        return {"role": self.role, "organization": self.organization, "start_date": self.start_date,
                "end_date": self.end_date, "highlights": self.highlights or []}


class Education(db.Model):
    __tablename__ = "education"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    degree = db.Column(db.String(120), nullable=False)
    institution = db.Column(db.String(120))
    year = db.Column(db.Integer)

    def to_dict(self):
        return {"degree": self.degree, "institution": self.institution, "year": self.year}


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    tech = db.Column(db.JSON, default=list)
    description = db.Column(db.Text, default="")

    def to_dict(self):
        return {"title": self.title, "tech": self.tech or [], "description": self.description or ""}


# ---------------------------------------------------------------------------
# Career workspace tables. Every table hangs off a profile and is deleted with it.
# ---------------------------------------------------------------------------
class Job(db.Model):
    """A saved job description or target role, with application tracking."""
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120))
    location = db.Column(db.String(120))
    work_mode = db.Column(db.String(10))          # remote | hybrid | onsite
    experience_level = db.Column(db.String(10))   # intern | entry | mid | senior
    required_skills = db.Column(db.JSON, default=list)
    preferred_skills = db.Column(db.JSON, default=list)
    jd_text = db.Column(db.Text)
    source = db.Column(db.String(12), default="jd")  # jd | role_title
    status = db.Column(db.String(12), default="saved", index=True)
    status_history = db.Column(db.JSON, default=list)
    deadline = db.Column(db.String(10))           # YYYY-MM-DD
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "company": self.company, "location": self.location,
            "work_mode": self.work_mode, "experience_level": self.experience_level,
            "required_skills": self.required_skills or [], "preferred_skills": self.preferred_skills or [],
            "source": self.source, "status": self.status, "status_history": self.status_history or [],
            "deadline": self.deadline, "notes": self.notes, "has_jd_text": bool(self.jd_text),
            "created_at": iso(self.created_at), "updated_at": iso(self.updated_at),
        }


class ReadinessReport(db.Model):
    __tablename__ = "readiness_reports"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"))
    job_title = db.Column(db.String(120))
    score = db.Column(db.Integer, nullable=False)
    details = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def to_dict(self):
        return {"id": self.id, "job_id": self.job_id, "job_title": self.job_title, "score": self.score,
                "created_at": iso(self.created_at), **(self.details or {})}


class ResumeOptimization(db.Model):
    __tablename__ = "resume_optimizations"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"))
    job_title = db.Column(db.String(120))
    keyword_score = db.Column(db.Integer, nullable=False)
    result = db.Column(db.JSON, default=dict)
    draft = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def to_dict(self):
        return {"id": self.id, "job_id": self.job_id, "job_title": self.job_title,
                "keyword_score": self.keyword_score, "draft": self.draft,
                "created_at": iso(self.created_at), **(self.result or {})}


class LearningPlan(db.Model):
    __tablename__ = "learning_plans"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"))
    title = db.Column(db.String(120), nullable=False)
    weeks = db.Column(db.Integer, default=4)
    hours_per_week = db.Column(db.Integer, default=6)
    generated_by = db.Column(db.String(10), default="ai")  # ai | template
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    tasks = db.relationship("LearningTask", backref="plan", cascade="all, delete-orphan", order_by="LearningTask.position")

    def to_dict(self):
        return {"id": self.id, "job_id": self.job_id, "title": self.title, "weeks": self.weeks,
                "hours_per_week": self.hours_per_week, "generated_by": self.generated_by,
                "is_active": self.is_active, "created_at": iso(self.created_at),
                "tasks": [t.to_dict() for t in self.tasks]}


class LearningTask(db.Model):
    __tablename__ = "learning_tasks"
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("learning_plans.id"), nullable=False, index=True)
    position = db.Column(db.Integer, default=0)
    skill = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    cadence = db.Column(db.String(8), default="weekly")  # daily | weekly
    week_number = db.Column(db.Integer, default=1)
    day_number = db.Column(db.Integer)
    minutes = db.Column(db.Integer, default=30)
    status = db.Column(db.String(12), default="pending")  # pending | in_progress | completed
    completed_at = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        return {"id": self.id, "skill": self.skill, "title": self.title, "description": self.description,
                "cadence": self.cadence, "week_number": self.week_number, "day_number": self.day_number,
                "minutes": self.minutes, "status": self.status, "completed_at": iso(self.completed_at)}


class Resource(db.Model):
    __tablename__ = "resources"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    skill = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(400), nullable=False)
    source = db.Column(db.String(10), default="curated")  # curated | search | user

    def to_dict(self):
        return {"id": self.id, "skill": self.skill, "title": self.title, "url": self.url, "source": self.source}


class InterviewSession(db.Model):
    __tablename__ = "interview_sessions"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"))
    mode = db.Column(db.String(12), nullable=False)  # technical | hr | behavioral
    target_role = db.Column(db.String(120))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    questions = db.relationship("InterviewQuestion", backref="session", cascade="all, delete-orphan", order_by="InterviewQuestion.position")

    def avg_score(self):
        scores = [q.score for q in self.questions if q.score is not None]
        return round(sum(scores) / len(scores)) if scores else None

    def to_dict(self, with_questions=True):
        out = {"id": self.id, "job_id": self.job_id, "mode": self.mode, "target_role": self.target_role,
               "created_at": iso(self.created_at), "question_count": len(self.questions),
               "answered_count": sum(1 for q in self.questions if q.score is not None),
               "avg_score": self.avg_score()}
        if with_questions:
            out["questions"] = [q.to_dict() for q in self.questions]
        return out


class InterviewQuestion(db.Model):
    __tablename__ = "interview_questions"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("interview_sessions.id"), nullable=False, index=True)
    position = db.Column(db.Integer, default=0)
    question = db.Column(db.Text, nullable=False)
    focus = db.Column(db.String(120))
    difficulty = db.Column(db.String(8))
    answer = db.Column(db.Text)
    feedback = db.Column(db.JSON)
    score = db.Column(db.Integer)
    answered_at = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        return {"id": self.id, "question": self.question, "focus": self.focus, "difficulty": self.difficulty,
                "answer": self.answer, "feedback": self.feedback, "score": self.score,
                "answered_at": iso(self.answered_at)}


class PortfolioProject(db.Model):
    __tablename__ = "portfolio_projects"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id", ondelete="SET NULL"))
    level = db.Column(db.String(12), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    idea = db.Column(db.JSON, default=dict)   # problem, features, stack, datasets, metrics, README outline, description
    status = db.Column(db.String(12), default="not_started")  # not_started | in_progress | completed
    repo_url = db.Column(db.String(300))
    demo_url = db.Column(db.String(300))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    milestones = db.relationship("ProjectMilestone", backref="project", cascade="all, delete-orphan", order_by="ProjectMilestone.position")

    def to_dict(self):
        return {"id": self.id, "job_id": self.job_id, "level": self.level, "title": self.title, "status": self.status,
                "repo_url": self.repo_url, "demo_url": self.demo_url, "completed_at": iso(self.completed_at),
                "created_at": iso(self.created_at), **(self.idea or {}),
                "milestones": [m.to_dict() for m in self.milestones]}


class ProjectMilestone(db.Model):
    __tablename__ = "project_milestones"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("portfolio_projects.id"), nullable=False, index=True)
    position = db.Column(db.Integer, default=0)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    done = db.Column(db.Boolean, default=False)
    done_at = db.Column(db.DateTime(timezone=True))

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description,
                "done": bool(self.done), "done_at": iso(self.done_at)}


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    def to_dict(self):
        return {"id": self.id, "role": self.role, "content": self.content, "created_at": iso(self.created_at)}
