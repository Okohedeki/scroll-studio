import { useEffect, useState } from "react";
import { api } from "./api";
import { Home } from "./components/Home";
import { ProjectView } from "./components/ProjectView";
import { Doctor } from "./components/Doctor";

export interface Info { scene_types: Record<string, string>; block_types: string[]; themes: Record<string, any>; presets3d: string[]; projects_dir: string }

function useHash(): [string, (h: string) => void] {
  const [h, setH] = useState(location.hash.slice(1));
  useEffect(() => { const f = () => setH(location.hash.slice(1)); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return [h, (v) => { location.hash = v; }];
}

export default function App() {
  const [route, go] = useHash();
  const [info, setInfo] = useState<Info | null>(null);
  const [schema, setSchema] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [error, setError] = useState("");
  const refresh = () => api.projects().then(setProjects).catch((e) => setError(String(e)));
  useEffect(() => {
    Promise.all([api.info(), api.schema()]).then(([i, s]) => { setInfo(i); setSchema(s); }).catch((e) => setError(String(e)));
    refresh();
  }, []);

  const [view, arg] = route.split("/");
  const current = view === "p" ? projects.find((p) => p.name === arg) : null;

  return (
    <div className="app">
      <aside className="side">
        <a className="brand" href="#"><span className="mark" />Scroll Studio</a>
        <nav>
          <a className={!view ? "on" : ""} href="#">Projects</a>
          <a className={view === "doctor" ? "on" : ""} href="#doctor">Toolchain</a>
        </nav>
        <div className="side-label">Your projects</div>
        <div className="side-list">
          {projects.filter((p) => p.kind === "project").map((p) => <a key={p.name} className={arg === p.name ? "on" : ""} href={`#p/${p.name}`}>{p.title}</a>)}
          {!projects.some((p) => p.kind === "project") && <div className="muted small pad">None yet: start from an example.</div>}
        </div>
        <div className="side-label">Examples</div>
        <div className="side-list">
          {projects.filter((p) => p.kind === "example").map((p) => <a key={p.name} className={arg === p.name ? "on" : ""} href={`#p/${p.name}`}>{p.title}</a>)}
        </div>
      </aside>
      <main className="main">
        {error && <div className="banner bad">Can't reach the Studio server: {error}</div>}
        {!info || !schema ? <div className="pad muted">Loading…</div>
          : view === "doctor" ? <Doctor />
          : view === "p" && current ? <ProjectView key={current.name} project={current} info={info} schema={schema} onChanged={refresh} />
          : <Home projects={projects} info={info} onCreated={(name) => { refresh().then(() => go(`p/${name}`)); }} />}
      </main>
    </div>
  );
}
