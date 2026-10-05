import { useState } from "react";
import { api } from "../api";
import type { Info } from "../App";

export function Home({ projects, info, onCreated }: { projects: any[]; info: Info; onCreated: (name: string) => void }) {
  const [name, setName] = useState("");
  const [example, setExample] = useState("");
  const [err, setErr] = useState("");
  const examples = projects.filter((p) => p.kind === "example");
  const mine = projects.filter((p) => p.kind === "project");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { const p = await api.create(name, example || undefined); onCreated(p.name); }
    catch (x) { setErr(String(x)); }
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Build a scroll site</h1>
        <p className="muted">Give the engine a brief, images, a 3D model or nothing at all. It builds a static site where scrolling plays the visuals. Everything runs on this machine.</p>
      </header>

      <form className="card new" onSubmit={create}>
        <div className="row wrap">
          <label className="f grow"><div className="f-head"><span className="f-label">Project name</span></div>
            <input id="new-name" required placeholder="harbour-hotel" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="f grow"><div className="f-head"><span className="f-label">Start from</span></div>
            <select id="new-example" value={example} onChange={(e) => setExample(e.target.value)}>
              <option value="">Blank starter</option>
              {examples.map((x) => <option key={x.name} value={x.name}>{x.title} ({x.scenes.join(", ")})</option>)}
            </select></label>
          <button className="primary" type="submit">Create project</button>
        </div>
        {err && <div className="bad small">{err}</div>}
        <div className="muted small">Saved in {info.projects_dir}</div>
      </form>

      {mine.length > 0 && <><h2>Your projects</h2><Grid items={mine} /></>}
      <h2>Examples</h2>
      <Grid items={examples} />

      <h2>Scene types</h2>
      <div className="types">
        {Object.entries(info.scene_types).map(([k, v]) => <div key={k} className="type-card"><code>{k}</code><p>{v}</p></div>)}
      </div>
    </div>
  );
}

function Grid({ items }: { items: any[] }) {
  return (
    <div className="grid">
      {items.map((p) => (
        <a key={p.name} className="pcard" href={`#p/${p.name}`}>
          <div className="pc-media">{p.poster ? <img src={p.poster} alt="" /> : <div className="pc-empty">{p.built ? "Built" : "Not built yet"}</div>}</div>
          <div className="pc-body">
            <div className="pc-tags">{p.scenes.map((s: string, i: number) => <span key={i} className="tag">{s}</span>)}<span className="tag ghost">{p.theme}</span></div>
            <h3>{p.title}</h3>
            <p className="muted small">{p.description}</p>
          </div>
        </a>
      ))}
    </div>
  );
}
