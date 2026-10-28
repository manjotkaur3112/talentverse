const BASE = (import.meta.env.VITE_API_URL || "http://localhost:5000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details || [];
  }
}

// Anonymous per-browser id. Profiles are only visible to the browser that created them.
export function ownerId() {
  try {
    let id = localStorage.getItem("tv_owner");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("tv_owner", id);
    }
    return id;
  } catch {
    return "session-" + Math.random().toString(36).slice(2).padEnd(20, "0");
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      ...options,
      headers: { "X-Owner-Id": ownerId(), ...(options.headers || {}) },
    });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again. The server may be waking up, which can take up to a minute.", 0);
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    throw new ApiError(data?.error || `Request failed (${res.status}).`, res.status, data?.details);
  }
  return data;
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request("/api/health"),
  extractText: (text) => request("/api/extract", json("POST", { text })),
  extractFile: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/api/extract", { method: "POST", body: fd });
  },
  saveProfile: (payload) => request("/api/profiles", json("POST", payload)),
  listProfiles: () => request("/api/profiles"),
  getProfile: (id) => request(`/api/profiles/${id}`),
  deleteProfile: (id) => request(`/api/profiles/${id}`, { method: "DELETE" }),
  deleteAll: () => request("/api/me", { method: "DELETE" }),
};

const P = (pid) => `/api/profiles/${pid}`;
const qs = (params = {}) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString();
  return s ? `?${s}` : "";
};

Object.assign(api, {
  // jobs and applications
  extractJob: (pid, body) => request(`${P(pid)}/jobs/extract`, json("POST", body)),
  createJob: (pid, job) => request(`${P(pid)}/jobs`, json("POST", { job })),
  listJobs: (pid, params) => request(`${P(pid)}/jobs${qs(params)}`),
  patchJob: (pid, jid, body) => request(`${P(pid)}/jobs/${jid}`, json("PATCH", body)),
  deleteJob: (pid, jid) => request(`${P(pid)}/jobs/${jid}`, { method: "DELETE" }),
  // readiness and resume optimizer
  createReadiness: (pid, job_id) => request(`${P(pid)}/readiness`, json("POST", { job_id })),
  listReadiness: (pid, job_id) => request(`${P(pid)}/readiness${qs({ job_id })}`),
  optimize: (pid, job_id) => request(`${P(pid)}/optimize`, json("POST", { job_id })),
  listOptimizations: (pid) => request(`${P(pid)}/optimizations`),
  // learning tracker
  getLearning: (pid) => request(`${P(pid)}/learning`),
  createPlan: (pid, body) => request(`${P(pid)}/learning/plan`, json("POST", body)),
  updateTask: (pid, tid, status) => request(`${P(pid)}/learning/tasks/${tid}`, json("PATCH", { status })),
  addResource: (pid, body) => request(`${P(pid)}/learning/resources`, json("POST", body)),
  deleteResource: (pid, rid) => request(`${P(pid)}/learning/resources/${rid}`, { method: "DELETE" }),
  // mock interviews
  createInterview: (pid, body) => request(`${P(pid)}/interviews`, json("POST", body)),
  listInterviews: (pid) => request(`${P(pid)}/interviews`),
  getInterview: (pid, sid) => request(`${P(pid)}/interviews/${sid}`),
  answerQuestion: (pid, sid, qid, answer) => request(`${P(pid)}/interviews/${sid}/questions/${qid}/answer`, json("POST", { answer })),
  deleteInterview: (pid, sid) => request(`${P(pid)}/interviews/${sid}`, { method: "DELETE" }),
  // portfolio projects
  projectIdeas: (pid, body) => request(`${P(pid)}/project-ideas`, json("POST", body)),
  saveProject: (pid, idea, job_id) => request(`${P(pid)}/portfolio`, json("POST", { idea, job_id })),
  listProjects: (pid) => request(`${P(pid)}/portfolio`),
  patchProject: (pid, id, body) => request(`${P(pid)}/portfolio/${id}`, json("PATCH", body)),
  patchMilestone: (pid, id, mid, done) => request(`${P(pid)}/portfolio/${id}/milestones/${mid}`, json("PATCH", { done })),
  deleteProject: (pid, id) => request(`${P(pid)}/portfolio/${id}`, { method: "DELETE" }),
  // analytics and mentor
  analytics: (pid) => request(`${P(pid)}/analytics`),
  getChat: (pid) => request(`${P(pid)}/chat`),
  sendChat: (pid, message) => request(`${P(pid)}/chat`, json("POST", { message })),
  clearChat: (pid) => request(`${P(pid)}/chat`, { method: "DELETE" }),
});
