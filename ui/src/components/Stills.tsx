import { useEffect, useState } from "react";
import { api, follow } from "../api";

/** Product stills (outputs.stills): each shot's lead candidate large, its shortlist beside it, every other candidate
 * below, best first. Compare pins two side by side; more / different / pick write back to stills/stills.json. */

const SHOT: Record<string, string> = { packshot: "Pack shot", lifestyle: "Lifestyle", detail: "Detail" };

type Cand = { id: string; shot: string; direction: string; seed: number; backend: string; url: string; harmonised: boolean;
  notes: string[]; scores: { fidelity: number; framing: number; contrast: number; score: number } };

export default function Stills({ name, onJob }: { name: string; onJob: (j: any) => void }) {
  const [st, setSt] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [focus, setFocus] = useState<Record<string, string>>({});
  const [compare, setCompare] = useState<string[]>([]);

  const load = () => api.stills(name).then(setSt).catch((e) => setError(String(e.message || e)));
  useEffect(() => { load(); }, [name]);

  async function act(body: { more?: string; different?: boolean; pick?: string }) {
    setError(""); setBusy(true);
    try {
      const r = await api.makeStills(name, body);
      if (r.state) setSt(r.state);
      else if (r.id) { onJob(r); const f = await follow(r.id, onJob); if (f.status === "failed") setError(f.error || "The job failed: see its log."); await load(); }
    } catch (e: any) { setError(String(e.message || e)); }
    setBusy(false);
  }

  if (!st) return <div className="pad muted">{error || "Loading…"}</div>;
  if (!st.enabled) return <div className="narrow"><p className="muted">{st.why}</p></div>;
  const dirs: Record<string, any> = Object.fromEntries(st.directions.map((d: any) => [d.id, d]));
  const byId: Record<string, Cand> = Object.fromEntries(st.candidates.map((c: Cand) => [c.id, c]));
  const toggle = (id: string) => setCompare((c) => c.includes(id) ? c.filter((x) => x !== id) : [...c, id].slice(-2));

  const card = (c: Cand, big = false) => {
    const d = dirs[c.direction] || {};
    return (
      <div className={"st-cap" + (big ? " big" : "")}>
        <div className="st-shot">{SHOT[c.shot] || c.shot}{st.picked[c.shot] === c.id && <span> · picked</span>}</div>
        <div className="st-name">{d.name}</div>
        <div className="st-meta mono">
          <span className="st-sw">{(d.palette || []).map((h: string) => <i key={h} style={{ background: h }} />)}</span>
          {c.id} · {c.scores.score.toFixed(2)} · {c.backend}{c.harmonised ? " · blended" : ""}
        </div>
      </div>
    );
  };

  return (
    <div className="stills">
      <div className="st-bar">
        <span className="muted small">{st.candidates.length} candidates · {st.directions.length} directions</span>
        <span className="grow" />
        {compare.length > 0 && <button className="ghost small" onClick={() => setCompare([])}>Clear compare ({compare.length})</button>}
        <button className="ghost" disabled={busy} onClick={() => act({ different: true })}>Something different</button>
        <button className="primary" disabled={busy} onClick={() => act({})}>{st.candidates.length ? "Fill in" : "Make the first set"}</button>
      </div>
      {error && <div className="banner bad">{error}</div>}

      {compare.length === 2 && (
        <section className="st-compare" aria-label="Compare">
          {compare.map((id) => byId[id] && (
            <figure key={id}><img src={byId[id].url} alt={`${SHOT[byId[id].shot]}, ${dirs[byId[id].direction]?.name || ""}`} />{card(byId[id])}</figure>))}
        </section>
      )}

      {st.candidates.length === 0 && <div className="st-empty muted">No candidates yet. Make the first set: art directions, then candidates for every shot, scored and shortlisted.</div>}

      {st.shots.map((shot: string) => {
        const pool: Cand[] = st.candidates.filter((c: Cand) => c.shot === shot).sort((a: Cand, b: Cand) => b.scores.score - a.scores.score);
        if (!pool.length) return null;
        const short: string[] = (st.shortlist[shot] || []).filter((i: string) => byId[i]);
        const leadId = focus[shot] || st.picked[shot] || short[0] || pool[0].id;
        const lead = byId[leadId];
        const rest = pool.filter((c) => !short.includes(c.id));
        return (
          <section key={shot} className="st-shotrow" aria-label={SHOT[shot] || shot}>
            <figure className="st-hero">
              <img src={lead.url} alt={`${SHOT[shot] || shot}, ${dirs[lead.direction]?.name || ""}`} />
              {card(lead, true)}
              <div className="st-actions">
                <button className="small" disabled={busy} onClick={() => act({ more: lead.id })}>More like this</button>
                <button className={"small" + (compare.includes(lead.id) ? " on" : "")} onClick={() => toggle(lead.id)}>Compare</button>
                <button className="small primary" disabled={busy || st.picked[shot] === lead.id} onClick={() => act({ pick: lead.id })}>
                  {st.picked[shot] === lead.id ? "Picked" : "Pick"}</button>
              </div>
              {lead.notes?.length > 0 && <div className="st-notes small muted">{lead.notes.join(" · ")}</div>}
            </figure>
            <div className="st-side">
              <div className="st-label">Shortlist · {short.length}</div>
              {short.map((id) => {
                const c = byId[id];
                return (
                  <button key={id} className={"st-thumb" + (id === leadId ? " on" : "")} onClick={() => setFocus({ ...focus, [shot]: id })}
                    aria-label={`${dirs[c.direction]?.name || id}, score ${c.scores.score.toFixed(2)}`}>
                    <img src={c.url} alt="" />
                    <span>
                      <span className="st-tname">{dirs[c.direction]?.name}</span>
                      {(["fidelity", "framing", "contrast"] as const).map((k) => (
                        <span key={k} className="st-score mono"><span>{k}</span><i><b style={{ width: `${Math.max(2, c.scores[k] * 100)}%` }} /></i>{c.scores[k].toFixed(2)}</span>))}
                    </span>
                  </button>);
              })}
              {rest.length > 0 && <div className="st-label">Every other · {rest.length}</div>}
              <div className="st-grid">
                {rest.map((c) => (
                  <button key={c.id} className={"st-mini" + (c.scores.fidelity <= 0 ? " fail" : "") + (c.id === leadId ? " on" : "")}
                    onClick={() => setFocus({ ...focus, [shot]: c.id })} aria-label={`${dirs[c.direction]?.name || c.id}, score ${c.scores.score.toFixed(2)}`}>
                    <img src={c.url} alt="" loading="lazy" />
                  </button>))}
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}
