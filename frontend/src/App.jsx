import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Intake from "./components/Intake";
import Preview from "./components/Preview";
import ProfileView from "./components/ProfileView";
import ProfilesList from "./components/ProfilesList";
import Stepper from "./components/Stepper";
import Toasts from "./components/Toasts";

export default function App() {
  const [view, setView] = useState("build"); // build | profiles | profile
  const [stage, setStage] = useState("input"); // input | extracting | review | saved
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [banner, setBanner] = useState(null);
  const [toasts, setToasts] = useState([]);

  // Wake a sleeping free-tier backend as early as possible.
  useEffect(() => { api.health().catch(() => {}); }, []);

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const notify = useCallback((t) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, ...t }]);
    setTimeout(() => dismiss(id), 7000);
  }, [dismiss]);

  async function runExtract(input) {
    setError(null);
    setStage("extracting");
    try {
      const res = input.file ? await api.extractFile(input.file) : await api.extractText(input.text);
      setDraft(res.profile);
      setStage("review");
    } catch (e) {
      setStage("input");
      setError({ message: e.message, retry: () => runExtract(input) });
    }
  }

  function startOver() {
    setDraft(null);
    setError(null);
    setBanner(null);
    setOpenId(null);
    setStage("input");
    setView("build");
  }

  function onSaved(res) {
    setOpenId(res.profile.id);
    setBanner(res.message);
    setStage("saved");
    notify({ kind: "ok", text: res.message });
  }

  return (
    <div className="shell">
      <header className="top">
        <button className="brand" onClick={startOver} aria-label="TalentVerse home">TalentVerse</button>
        <nav aria-label="Main">
          <button className={view === "build" ? "nav on" : "nav"} onClick={() => setView("build")}>Build a profile</button>
          <button className={view !== "build" ? "nav on" : "nav"} onClick={() => setView("profiles")}>My profiles</button>
        </nav>
      </header>

      {view === "build" && (
        <main>
          {stage === "input" && (
            <div className="hero">
              <h1>Your resume, turned into data you can measure against any job.</h1>
            </div>
          )}
          <Stepper stage={stage} />
          {(stage === "input" || stage === "extracting") && (
            <Intake busy={stage === "extracting"} error={error} onSubmit={runExtract} />
          )}
          {stage === "review" && draft && (
            <Preview draft={draft} onCancel={startOver} onSaved={onSaved} notify={notify} />
          )}
          {stage === "saved" && openId && (
            <ProfileView id={openId} banner={banner} onStartOver={startOver} onDeleted={startOver} notify={notify} />
          )}
        </main>
      )}

      {view === "profiles" && (
        <main>
          <ProfilesList
            notify={notify}
            onBuild={startOver}
            onOpen={(id) => { setOpenId(id); setBanner(null); setView("profile"); }}
          />
        </main>
      )}

      {view === "profile" && openId && (
        <main>
          <button className="link back" onClick={() => setView("profiles")}>Back to your profiles</button>
          <ProfileView id={openId} onDeleted={() => setView("profiles")} notify={notify} />
        </main>
      )}

      <footer className="foot">
        <span>Resume text is processed by an AI service to extract fields. Only the profile you confirm is stored.</span>
      </footer>
      <Toasts toasts={toasts} dismiss={dismiss} />
    </div>
  );
}
