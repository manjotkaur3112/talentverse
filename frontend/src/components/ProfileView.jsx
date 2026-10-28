import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateTime } from "../util";
import AnalyticsTab from "./AnalyticsTab";
import InterviewTab from "./InterviewTab";
import JobsTab from "./JobsTab";
import LearningTab from "./LearningTab";
import MentorTab from "./MentorTab";
import ProfileOverview from "./ProfileOverview";
import ProjectsTab from "./ProjectsTab";
import ReadinessTab from "./ReadinessTab";
import ResumeTab from "./ResumeTab";

const TABS = [
  ["profile", "Profile"], ["jobs", "Jobs"], ["readiness", "Readiness"], ["resume", "Resume"],
  ["learning", "Learning"], ["interview", "Interview"], ["projects", "Projects"], ["progress", "Progress"], ["mentor", "Mentor"],
];

export default function ProfileView({ id, banner, onDeleted, onStartOver, notify }) {
  const [profile, setProfile] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [tab, setTab] = useState("profile");
  const [error, setError] = useState(null);

  const reloadJobs = useCallback(() => api.listJobs(id, { sort: "match" }).then((r) => setJobs(r.jobs)).catch(() => {}), [id]);

  useEffect(() => {
    let live = true;
    setError(null);
    setTab("profile");
    api.getProfile(id).then((r) => live && setProfile(r.profile)).catch((e) => live && setError(e.message));
    reloadJobs();
    return () => { live = false; };
  }, [id, reloadJobs]);

  async function remove() {
    if (!window.confirm("Delete this profile and everything saved with it (jobs, scores, plans, interviews, projects, chat)? This can't be undone.")) return;
    try {
      await api.deleteProfile(id);
      notify({ kind: "ok", text: "Profile deleted." });
      onDeleted();
    } catch (e) {
      notify({ kind: "error", text: e.message });
    }
  }

  if (error) return <div className="notice notice-error" role="alert">{error}</div>;
  if (!profile) return <p className="muted">Loading profile…</p>;

  const ctx = { profileId: profile.id, jobs, reloadJobs, notify, go: setTab };

  return (
    <div className="profile">
      {banner && (
        <div className="notice notice-ok" role="status">
          <span><strong>{banner}</strong> Record #{profile.id}, saved {fmtDateTime(profile.updated_at)}.</span>
          {onStartOver && <button className="btn small" onClick={onStartOver}>Add another resume</button>}
        </div>
      )}

      <div className="panel-head headline">
        <h2>{profile.full_name || `Profile #${profile.id}`}</h2>
        <button className="btn small danger" onClick={remove}>Delete profile</button>
      </div>

      <nav className="subtabs" aria-label="Career tools">
        {TABS.map(([k, label]) => (
          <button key={k} className={tab === k ? "subtab on" : "subtab"} aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{label}</button>
        ))}
      </nav>

      {tab === "profile" && <ProfileOverview profile={profile} />}
      {tab === "jobs" && <JobsTab {...ctx} />}
      {tab === "readiness" && <ReadinessTab {...ctx} />}
      {tab === "resume" && <ResumeTab {...ctx} />}
      {tab === "learning" && <LearningTab {...ctx} />}
      {tab === "interview" && <InterviewTab {...ctx} />}
      {tab === "projects" && <ProjectsTab {...ctx} />}
      {tab === "progress" && <AnalyticsTab {...ctx} />}
      {tab === "mentor" && <MentorTab {...ctx} />}
    </div>
  );
}
