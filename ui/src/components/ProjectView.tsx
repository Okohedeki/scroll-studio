import { useEffect, useMemo, useRef, useState } from "react";
import { api, follow } from "../api";
import type { Info } from "../App";
import { Fields, Fieldset, type Ctx } from "./SchemaForm";

const DEFS: Record<string, string> = {
  film: "FilmScene", artwork: "ArtworkScene", scene3d: "Scene3DScene", sequence: "SequenceScene", parallax: "ParallaxScene", type: "TypeScene",
  intro: "IntroBlock", features: "FeaturesBlock", stats: "StatsBlock", timeline: "TimelineBlock", quote: "QuoteBlock", cta: "CtaBlock", gallery: "GalleryBlock",
};
const SCENES = ["film", "artwork", "scene3d", "sequence", "parallax", "type"];

function starter(type: string, n: number): any {
  const id = `${type}-${n}`;
  switch (type) {
    case "film": return { id, type, video: "inputs/film.mp4", steps: [{ title: "Your headline <em>here.</em>", at: [0.05, 0.3] }] };
    case "artwork": return { id, type, image: { generate: "A detailed oil portrait of a lighthouse keeper, soft window light" },
      hud: { kind: "progress" }, steps: [{ intro: true, title: "Watch it <em>come together.</em>" }, { title: "Proportion" }, { title: "Line" }, { title: "Value" }, { title: "Underpainting" }, { title: "Colour" }] };
    case "scene3d": return { id, type, levels: [{ preset: "galaxy" }, { preset: "star-system" }, { preset: "planet" }],
      hud: { kind: "scale", scales: ["100,000 ly", "40 AU", "12,700 km"] }, steps: [{ intro: true, title: "Fall <em>inward.</em>" }, { title: "The galaxy" }, { title: "One star" }, { title: "Home" }] };
    case "sequence": return { id, type, model: "inputs/model.glb", steps: [{ intro: true, title: "Meet the <em>product.</em>" }, { title: "Every part" }, { title: "Back together" }] };
    case "parallax": return { id, type, steps: [{ intro: true, title: "A place worth <em>the trip.</em>" },
      { title: "Morning", image: { generate: "A sunlit terrace above the sea at morning, photoreal" } }, { title: "Evening", image: { generate: "The same terrace at dusk with lanterns, photoreal" } }] };
    case "type": return { id, type, mode: "reveal", text: "Say the one thing that <em>matters</em>, and let the page take its time." };
    case "intro": return { type, title: "One line about <em>what you do.</em>", body: "A short paragraph." };
    case "features": return { type, items: [{ title: "First" }, { title: "Second" }, { title: "Third" }] };
    case "stats": return { type, items: [{ value: "12", label: "Something countable" }, { value: "98", unit: "%", label: "Something measured" }] };
    case "timeline": return { type, items: [{ when: "Step 1", title: "Start" }, { when: "Step 2", title: "Finish" }] };
    case "quote": return { type, text: "A line worth quoting.", who: "Someone" };
    case "cta": return { type, title: "Ready when <em>you are.</em>", button: { label: "Get in touch", href: "#" } };
    default: return { type, items: [] };
  }
}

export function ProjectView({ project, info, schema, onChanged }: { project: any; info: Info; schema: any; onChanged: () => void }) {
  const name = project.name;
  const [tab, setTab] = useState("edit");
  const [data, setData] = useState<any>(null);
  const [yamlText, setYamlText] = useState("");
  const [modified, setModified] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [errors, setErrors] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [sel, setSel] = useState(-1);
  const [inputs, setInputs] = useState<any[]>([]);
  const [job, setJob] = useState<any>(null);
  const [draft, setDraft] = useState(false);
  const [previewStamp, setPreviewStamp] = useState(Date.now());

  const load = () => api.spec(name).then((s) => { setData(s.data); setYamlText(s.yaml); setModified(s.modified); setDirty(false); setErrors([]); });
  useEffect(() => { load(); api.inputs(name).then(setInputs); }, [name]);
  // Pick up edits made outside the UI (Claude via MCP, a text editor) when there are no unsaved changes here.
  useEffect(() => {
    const t = setInterval(() => { if (!dirty) api.spec(name).then((s) => { if (s.modified !== modified) { setData(s.data); setYamlText(s.yaml); setModified(s.modified); } }); }, 2500);
    return () => clearInterval(t);
  }, [dirty, modified, name]);

  const ctx: Ctx = useMemo(() => ({ root: schema, inputs }), [schema, inputs]);
  const update = (next: any) => { setData(next); setDirty(true); };

  async function save(): Promise<boolean> {
    setSaving(true);
    const r = tab === "yaml" ? await api.saveSpec(name, { yaml: yamlText }) : await api.saveSpec(name, { data });
    setSaving(false);
    if (!r.ok) { setErrors(r.errors); return false; }
    await load();
    onChanged();
    return true;
  }

  async function run(kind: "build" | "snapshot" | "record", opts: any = {}) {
    if (dirty && !(await save())) return;
    const start = kind === "build" ? api.build(name, { draft, ...opts }) : kind === "snapshot" ? api.snapshot(name, opts.at) : api.record(name, opts);
    const j = await start;
    setJob(j);
    const final = await follow(j.id, setJob);
    if (kind === "build" && final.status === "done") { setPreviewStamp(Date.now()); onChanged(); }
    return final;
  }

  if (!data) return <div className="pad muted">Loading…</div>;
  const sections: any[] = data.sections || [];
  const s = sel >= 0 ? sections[sel] : null;
  const scenes = sections.filter((x) => SCENES.includes(x.type));
  const setSections = (next: any[]) => update({ ...data, sections: next });

  return (
    <div className="project">
      <datalist id="inputs-list">{inputs.map((i) => <option key={i.path} value={i.path} />)}</datalist>
      <datalist id="presets-list">{info.presets3d.map((p) => <option key={p} value={p} />)}</datalist>
      <datalist id="hdri-list">{["studio", "interior", "city", "courtyard", "forest", "night", "sunrise", "sunset"].map((p) => <option key={p} value={p} />)}</datalist>
      <header className="proj-head">
        <div>
          <div className="muted small">{project.kind === "example" ? "Example" : "Project"} · {name}</div>
          <h1>{data.name}</h1>
        </div>
        <div className="actions">
          {dirty && <span className="muted small">Unsaved changes</span>}
          <button className="ghost" disabled={!dirty || saving} onClick={save}>{saving ? "Saving…" : "Save"}</button>
          <label className="check small"><input type="checkbox" checked={draft} onChange={(e) => setDraft(e.target.checked)} /> Draft quality</label>
          <button className="primary" disabled={job?.status === "running" || job?.status === "queued"} onClick={() => run("build")}>Build site</button>
        </div>
      </header>
      {errors.length > 0 && <div className="banner bad">{errors.map((e, i) => <div key={i}><code>{e.loc}</code> {e.msg}</div>)}</div>}
      <JobBar job={job} onClose={() => setJob(null)} />

      <nav className="tabs">
        {[["edit", "Sections"], ["site", "Site & theme"], ["inputs", `Inputs (${inputs.length})`], ["yaml", "YAML"], ["preview", "Preview"], ["review", "Review"], ["export", "Export"]].map(([k, l]) =>
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
      </nav>

      {tab === "edit" && (
        <div className="editor">
          <div className="sec-list">
            {sections.map((x, i) => (
              <div key={i} className={"sec" + (sel === i ? " on" : "")} onClick={() => setSel(i)}>
                <span className={"tag" + (SCENES.includes(x.type) ? " scene" : "")}>{x.type}</span>
                <span className="sec-t">{x.id || (x.title || x.text || "").replace(/<[^>]+>/g, "").slice(0, 40)}</span>
                <span className="sec-tools" onClick={(e) => e.stopPropagation()}>
                  <button disabled={i === 0} onClick={() => { const n = [...sections]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; setSections(n); setSel(i - 1); }}>↑</button>
                  <button disabled={i === sections.length - 1} onClick={() => { const n = [...sections]; [n[i + 1], n[i]] = [n[i], n[i + 1]]; setSections(n); setSel(i + 1); }}>↓</button>
                  <button onClick={() => { setSections(sections.filter((_, j) => j !== i)); setSel(-1); }}>✕</button>
                </span>
              </div>
            ))}
            <AddSection info={info} onAdd={(t) => { setSections([...sections, starter(t, sections.length + 1)]); setSel(sections.length); }} />
          </div>
          <div className="sec-form">
            {s ? (
              <>
                <div className="sf-head">
                  <span className={"tag" + (SCENES.includes(s.type) ? " scene" : "")}>{s.type}</span>
                  <span className="muted small">{info.scene_types[s.type] || "Content block"}</span>
                  {SCENES.includes(s.type) && s.id && <button className="ghost small" onClick={() => run("build", { section: s.id })}>Build this scene</button>}
                </div>
                <Fields schema={schema.$defs[DEFS[s.type]]} value={s} ctx={ctx} skip={["type"]}
                  onChange={(v) => { const n = [...sections]; n[sel] = { ...v, type: s.type }; setSections(n); }} />
              </>
            ) : <div className="muted pad">Select a section to edit it, or add one. Scenes are the scroll-driven visuals; blocks are the static content between them.</div>}
          </div>
        </div>
      )}

      {tab === "site" && (
        <div className="narrow">
          <ThemePicker info={info} value={data.theme || {}} onChange={(t) => update({ ...data, theme: t })} />
          <Fields schema={schema} value={data} ctx={ctx} skip={["sections", "theme"]} onChange={update} />
          <Fieldset name="theme overrides" schema={schema.$defs.Theme} value={data.theme || {}} ctx={ctx} onChange={(t) => update({ ...data, theme: t })} />
        </div>
      )}

      {tab === "inputs" && <Inputs name={name} inputs={inputs} onUploaded={() => api.inputs(name).then(setInputs)} />}

      {tab === "yaml" && (
        <div className="narrow">
          <p className="muted small">The whole site in one file. Claude can edit this too; changes made elsewhere appear here automatically.</p>
          <textarea className="mono yaml" spellCheck={false} value={yamlText} onChange={(e) => { setYamlText(e.target.value); setDirty(true); }} />
        </div>
      )}

      {tab === "preview" && <Preview name={name} built={project.built} scenes={scenes} stamp={previewStamp} />}
      {tab === "review" && <Review name={name} job={job} run={(at) => run("snapshot", { at })} />}
      {tab === "export" && <Export name={name} scenes={scenes} run={(opts) => run("record", opts)} />}
    </div>
  );
}

function AddSection({ info, onAdd }: { info: Info; onAdd: (t: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="add">
      <button className="ghost small" onClick={() => setOpen(!open)}>+ Add section</button>
      {open && (
        <div className="add-menu">
          <div className="side-label">Scenes</div>
          {SCENES.map((t) => <button key={t} onClick={() => { onAdd(t); setOpen(false); }}><b>{t}</b><span>{info.scene_types[t]}</span></button>)}
          <div className="side-label">Blocks</div>
          <div className="row wrap">{info.block_types.map((t) => <button key={t} className="chip" onClick={() => { onAdd(t); setOpen(false); }}>{t}</button>)}</div>
        </div>
      )}
    </div>
  );
}

function ThemePicker({ info, value, onChange }: { info: Info; value: any; onChange: (v: any) => void }) {
  return (
    <div className="themes">
      {Object.entries(info.themes).map(([k, t]: any) => (
        <button key={k} className={"theme" + ((value.preset || "night") === k ? " on" : "")} onClick={() => onChange({ ...value, preset: k })}
          style={{ background: t.colors.bg, color: t.colors.ink, fontFamily: t.fonts.display }}>
          <span className="th-name">{k}</span>
          <span className="th-sample">Aa <em style={{ color: t.colors.accent, fontStyle: t.em_italic ? "italic" : "normal" }}>accent</em></span>
          <span className="th-dots">{["bg2", "accent", "accent2"].map((c) => <i key={c} style={{ background: t.colors[c] }} />)}</span>
        </button>
      ))}
    </div>
  );
}

function Inputs({ name, inputs, onUploaded }: { name: string; inputs: any[]; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const pick = useRef<HTMLInputElement>(null);
  const send = async (files: FileList | null) => { if (!files?.length) return; setBusy(true); await api.upload(name, files); setBusy(false); onUploaded(); };
  return (
    <div className="narrow">
      <div className={"drop" + (over ? " over" : "")} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); send(e.dataTransfer.files); }} onClick={() => pick.current?.click()}>
        <input ref={pick} type="file" multiple hidden onChange={(e) => send(e.target.files)} />
        {busy ? "Uploading…" : "Drop images, videos, 3D models (glb, obj, fbx, stl) or Blender files here, or click to choose"}
      </div>
      <div className="inputs">
        {inputs.map((i) => (
          <div key={i.path} className="input">
            {/\.(jpe?g|png|webp)$/i.test(i.path) ? <img src={i.url} alt="" /> : /\.(mp4|webm)$/i.test(i.path) ? <video src={i.url} muted /> : <div className="file-ico">{i.path.split(".").pop()}</div>}
            <code className="small">{i.path}</code><span className="muted small">{(i.size / 1e6).toFixed(1)} MB</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Preview({ name, built, scenes, stamp }: { name: string; built: boolean; scenes: any[]; stamp: number }) {
  const [device, setDevice] = useState("desktop");
  const [scene, setScene] = useState("");
  const [p, setP] = useState(0);
  const [src, setSrc] = useState(`/preview/${name}/index.html?t=${stamp}`);
  useEffect(() => { setSrc(`/preview/${name}/index.html?t=${stamp}`); }, [stamp, name]);
  useEffect(() => {
    if (!scene) return;
    const t = setTimeout(() => setSrc(`/preview/${name}/index.html?p=${p}&s=${scene}&t=${stamp}`), 250);
    return () => clearTimeout(t);
  }, [p, scene]);
  if (!built && stamp === 0) return <div className="pad muted">Not built yet. Press Build site.</div>;
  return (
    <div className="preview">
      <div className="row wrap pv-tools">
        <div className="seg">{["desktop", "phone"].map((d) => <button key={d} className={device === d ? "on" : ""} onClick={() => setDevice(d)}>{d}</button>)}</div>
        <select value={scene} onChange={(e) => setScene(e.target.value)}><option value="">Free scroll</option>{scenes.map((s) => <option key={s.id} value={s.id}>Scrub: {s.id} ({s.type})</option>)}</select>
        {scene && <input className="grow" type="range" min={0} max={1} step={0.01} value={p} onChange={(e) => setP(Number(e.target.value))} />}
        {scene && <span className="mono small">{p.toFixed(2)}</span>}
        <a className="ghost small btnlike" href={`/preview/${name}/index.html`} target="_blank" rel="noreferrer">Open in a new tab ↗</a>
      </div>
      <div className={"frame " + device}><iframe title="preview" src={src} /></div>
    </div>
  );
}

function Review({ name, job, run }: { name: string; job: any; run: (at: string[]) => Promise<any> }) {
  const [res, setRes] = useState<any>(null);
  return (
    <div className="narrow wide">
      <div className="row"><button className="primary" onClick={async () => { const j = await run([]); if (j?.status === "done") setRes(j.result); }}>Take snapshots</button>
        <span className="muted small">Screenshots of every scene at 15%, 50% and 85% of its scroll, in headless Chrome.</span></div>
      <div className="shots">{(res?.images || []).map((u: string) => <a key={u} href={u} target="_blank" rel="noreferrer"><img src={u} alt="" /></a>)}</div>
    </div>
  );
}

function Export({ name, scenes, run }: { name: string; scenes: any[]; run: (o: any) => Promise<any> }) {
  const [section, setSection] = useState("");
  const [seconds, setSeconds] = useState(12);
  const [list, setList] = useState<any[]>([]);
  const refresh = () => api.recordings(name).then(setList);
  useEffect(() => { refresh(); }, [name]);
  return (
    <div className="narrow wide">
      <h3>Record a scroll-through</h3>
      <p className="muted small">An MP4 of the page scrolling smoothly, for a README, a launch post or Reddit.</p>
      <div className="row wrap">
        <select value={section} onChange={(e) => setSection(e.target.value)}><option value="">Whole page</option>{scenes.map((s) => <option key={s.id} value={s.id}>{s.id} ({s.type})</option>)}</select>
        <label className="row small">Seconds <input type="number" min={4} max={60} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} style={{ width: 70 }} /></label>
        <button className="primary" onClick={async () => { await run({ section: section || undefined, seconds }); refresh(); }}>Record MP4</button>
      </div>
      <div className="recs">{list.map((r) => <div key={r.name} className="rec"><video src={r.url} controls muted /><a href={r.url} download>{r.name}</a></div>)}</div>
      <h3>Publish</h3>
      <p className="muted small">The built site is plain static files in <code>dist/</code>. Upload that folder to any static host (GitHub Pages, Netlify, Cloudflare Pages, S3).</p>
    </div>
  );
}

function JobBar({ job, onClose }: { job: any; onClose: () => void }) {
  const [open, setOpen] = useState(false);
  if (!job) return null;
  const pct = Math.round((job.progress || 0) * 100);
  return (
    <div className={"jobbar " + job.status}>
      <div className="jb-row">
        <b>{job.label}</b>
        <span className="muted small">{job.status === "running" ? `${pct}% ${job.message || ""}` : job.status}</span>
        <div className="jb-bar"><i style={{ width: `${job.status === "done" ? 100 : pct}%` }} /></div>
        <button className="ghost small" onClick={() => setOpen(!open)}>{open ? "Hide log" : "Log"}</button>
        {(job.status === "done" || job.status === "failed") && <button className="ghost small" onClick={onClose}>✕</button>}
      </div>
      {job.error && <div className="bad small pre">{job.error}</div>}
      {open && <pre className="log">{(job.log || []).join("\n")}</pre>}
    </div>
  );
}
