import { useRef, useState } from "react";
import { useElapsed, waitLabel } from "../hooks";

const MAX_BYTES = 5 * 1024 * 1024;

export default function Intake({ busy, error, onSubmit }) {
  const [mode, setMode] = useState("file");
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [localError, setLocalError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const elapsed = useElapsed(busy);

  function pick(f) {
    setLocalError(null);
    if (!f) return;
    const ok = /\.(pdf|txt)$/i.test(f.name);
    if (!ok) return setLocalError("Choose a PDF or TXT file.");
    if (f.size > MAX_BYTES) return setLocalError("That file is over 5 MB. Choose a smaller one.");
    setFile(f);
  }

  function submit(e) {
    e.preventDefault();
    setLocalError(null);
    if (mode === "file") {
      if (!file) return setLocalError("Choose a resume file first.");
      onSubmit({ file });
    } else {
      if (text.trim().length < 50) return setLocalError("Paste your resume text. It looks too short.");
      onSubmit({ text });
    }
  }

  const shown = localError || error?.message;

  return (
    <form className="panel intake" onSubmit={submit}>
      <h2>Start with your resume</h2>
      <p className="muted">
        We read it, pull out your skills and experience, and show you the result before anything is saved.
      </p>

      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "file"} className={mode === "file" ? "tab on" : "tab"} onClick={() => setMode("file")}>
          Upload a file
        </button>
        <button type="button" role="tab" aria-selected={mode === "text"} className={mode === "text" ? "tab on" : "tab"} onClick={() => setMode("text")}>
          Paste text
        </button>
      </div>

      {mode === "file" ? (
        <div
          className={`drop ${dragging ? "drop-on" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
        >
          <input ref={inputRef} id="resume-file" type="file" accept=".pdf,.txt,application/pdf,text/plain" hidden onChange={(e) => pick(e.target.files?.[0])} />
          {file ? (
            <p><strong>{file.name}</strong> <span className="muted">({Math.round(file.size / 1024)} KB)</span></p>
          ) : (
            <p>Drop a PDF or TXT here</p>
          )}
          <button type="button" className="btn ghost" onClick={() => inputRef.current?.click()}>
            {file ? "Choose a different file" : "Browse files"}
          </button>
        </div>
      ) : (
        <label className="field">
          <span className="field-label">Resume text</span>
          <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full text of your resume" />
        </label>
      )}

      {shown && (
        <div className="notice notice-error" role="alert">
          <span>{shown}</span>
          {!localError && error?.retry && (
            <button type="button" className="btn small" onClick={error.retry}>Retry</button>
          )}
        </div>
      )}

      <div className="actions">
        <button className="btn primary" disabled={busy}>
          {busy ? waitLabel("Reading your resume…", elapsed) : "Extract my profile"}
        </button>
        <span className="muted small-text">Resume text is sent to the AI service for extraction and is never stored.</span>
      </div>
    </form>
  );
}
