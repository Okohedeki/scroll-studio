"""stills/board.html: every shot's shortlist at a glance. The best candidate is the hero; the rest of the shortlist sits
beside it; every other candidate follows, small and ordered by score. Amber marks the shortlist (and a pick), red a
failed critic. Static HTML with relative image paths: open the file, nothing is served."""
from __future__ import annotations

import html
import json

from ..project import Project

CSS = """
:root{--canvas:#0d0e10;--surface:rgba(255,255,255,.04);--t1:#f1efe9;--t2:#a9a69e;--t3:#6d6a64;
--a1:#f2b56b;--a2:#ff6b5e;--mono:ui-monospace,"JetBrains Mono","IBM Plex Mono",Consolas,monospace;
--sans:Inter,"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
*{box-sizing:border-box}html,body{margin:0;background:var(--canvas);color:var(--t1);font:14px/1.45 var(--sans)}
header{padding:40px 40px 8px}header h1{margin:0;font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--t2);font-weight:500}
header p{margin:6px 0 0;color:var(--t3);font:12px var(--mono)}
section{padding:32px 40px 48px}
.top{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:28px;align-items:start}
.hero{position:relative;margin:0;display:flex;justify-content:center}
.hero img{display:block;max-width:100%;width:auto;height:auto;max-height:72vh;border-radius:6px;
transition:opacity .35s ease}
.hero figcaption{position:absolute;left:16px;top:16px;max-width:min(560px,calc(100% - 32px));padding:12px 14px;border-radius:6px;
background:rgba(10,10,12,.62);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
h2{margin:0 0 2px;font-size:30px;line-height:1.1;font-weight:600;letter-spacing:-.01em}
.shot{color:var(--a1);font:600 11px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.meta{color:var(--t2);font:12px var(--mono)}
.side h3,.rest h3{margin:0 0 10px;color:var(--t3);font:500 11px var(--mono);letter-spacing:.12em;text-transform:uppercase}
.strip{display:grid;gap:10px}
button.c{all:unset;cursor:pointer;display:grid;grid-template-columns:96px 1fr;gap:10px;align-items:center;padding:6px;
border-radius:6px;transition:background .2s ease}
button.c:hover,button.c[aria-pressed=true]{background:var(--surface)}
button.c:focus-visible{outline:2px solid var(--a1);outline-offset:2px}
button.c img{width:96px;height:96px;object-fit:cover;border-radius:4px;display:block}
.name{font-size:13px;color:var(--t1)}
.sw{display:inline-flex;gap:3px;vertical-align:middle;margin-right:6px}.sw i{width:10px;height:10px;border-radius:2px;display:block}
.bars{display:grid;grid-template-columns:auto 1fr auto;gap:2px 6px;align-items:center;margin-top:4px;font:11px var(--mono);color:var(--t3)}
.bar{height:3px;background:rgba(255,255,255,.08);border-radius:2px;overflow:hidden}.bar b{display:block;height:100%;background:var(--t2)}
.short .bar b{background:var(--a1)}.fail .bar b{background:var(--a2)}
.num{font-variant-numeric:tabular-nums;text-align:right}
.rest{margin-top:26px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:6px}
.grid button.c{display:block;padding:0}.grid button.c img{width:100%;height:auto;aspect-ratio:1}
.grid button.c.fail img{outline:2px solid var(--a2);outline-offset:-2px;opacity:.55}
.picked{color:var(--a1)}
.empty{padding:80px 40px;color:var(--t3);font:13px var(--mono)}
@media (max-width:860px){header,section{padding-left:16px;padding-right:16px}.top{grid-template-columns:1fr}h2{font-size:24px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

JS = """
document.querySelectorAll('section').forEach(s=>{
  const hero=s.querySelector('.hero img'),cap=s.querySelector('.hero figcaption');
  s.querySelectorAll('button.c').forEach(b=>b.addEventListener('click',()=>{
    s.querySelectorAll('button.c').forEach(x=>x.setAttribute('aria-pressed','false'));
    b.setAttribute('aria-pressed','true');hero.style.opacity=0;
    setTimeout(()=>{hero.src=b.dataset.src;hero.alt=b.dataset.alt;cap.innerHTML=b.dataset.cap;hero.style.opacity=1},180);
  }));
});
"""

SHOTS = {"packshot": "Pack shot", "lifestyle": "Lifestyle", "detail": "Detail"}


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _bars(sc: dict) -> str:
    rows = "".join(f"<span>{k}</span><span class=bar><b style='width:{max(2, round(sc[k] * 100))}%'></b></span>"
                   f"<span class=num>{sc[k]:.2f}</span>" for k in ("fidelity", "framing", "contrast"))
    return f"<div class=bars>{rows}</div>"


def _caption(c: dict, d: dict, picked: bool) -> str:
    sw = "".join(f"<i style='background:{_e(x)}'></i>" for x in d.get("palette", []))
    pick = " <span class=picked>picked</span>" if picked else ""
    return (f"<div class=shot>{_e(SHOTS.get(c['shot'], c['shot']))}{pick}</div><h2>{_e(d.get('name', ''))}</h2>"
            f"<div class=meta><span class=sw>{sw}</span>{_e(c['id'])} · score {c['scores']['score']:.2f} · "
            f"{_e(c['backend'])}{' · blended' if c.get('harmonised') else ''}</div>")


def _button(c: dict, d: dict, cls: str, picked: bool, full: bool) -> str:
    alt = f"{SHOTS.get(c['shot'], c['shot'])}, {d.get('name', '')}"
    data = f"data-src='{_e(c['image'])}' data-alt='{_e(alt)}' data-cap=\"{_e(_caption(c, d, picked))}\""
    body = (f"<span><span class=name>{_e(d.get('name', ''))}</span>{_bars(c['scores'])}</span>" if full else "")
    return (f"<button class='c {cls}' aria-pressed=false aria-label='{_e(alt)}, score {c['scores']['score']:.2f}' "
            f"{data}><img loading=lazy src='{_e(c['image'])}' alt=''>{body}</button>")


def render(state: dict, title: str) -> str:
    dirs = {d["id"]: d for d in state.get("directions", [])}
    shots = list(dict.fromkeys(c["shot"] for c in state.get("candidates", [])))
    parts = []
    for shot in shots:
        pool = sorted((c for c in state["candidates"] if c["shot"] == shot), key=lambda c: -c["scores"]["score"])
        short = state.get("shortlist", {}).get(shot, [])
        picked = state.get("picked", {}).get(shot)
        by_id = {c["id"]: c for c in pool}
        lead_id = picked if picked in by_id else (short[0] if short else pool[0]["id"])
        lead = by_id[lead_id]
        side = [by_id[i] for i in short if i in by_id]
        rest = [c for c in pool if c["id"] not in short]
        side_html = "".join(_button(c, dirs.get(c["direction"], {}), "short", c["id"] == picked, True) for c in side)
        rest_html = "".join(_button(c, dirs.get(c["direction"], {}), "fail" if c["scores"]["fidelity"] <= 0 else "",
                                    c["id"] == picked, False) for c in rest)
        d = dirs.get(lead["direction"], {})
        parts.append(
            f"<section aria-labelledby='h-{_e(shot)}'><div class=top><figure class=hero>"
            f"<img src='{_e(lead['image'])}' alt='{_e(SHOTS.get(shot, shot))}, {_e(d.get('name', ''))}'>"
            f"<figcaption id='h-{_e(shot)}'>{_caption(lead, d, lead_id == picked)}</figcaption></figure>"
            f"<div class=side><h3>Shortlist · {len(side)}</h3><div class=strip>{side_html}</div></div></div>"
            + (f"<div class=rest><h3>Every other candidate · {len(rest)}, best first</h3><div class=grid>{rest_html}</div></div>"
               if rest else "") + "</section>")
    body = "".join(parts) or "<p class=empty>No candidates yet: run studio stills on this project.</p>"
    n, nd = len(state.get("candidates", [])), len(dirs)
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{_e(title)} · stills</title><style>{CSS}</style></head><body><header><h1>"
            f"{_e(title)} · product stills</h1><p>{n} candidates · {nd} directions · records in stills.json</p></header>"
            f"<main>{body}</main><script>{JS}</script></body></html>")


def write(project: Project, state: dict) -> None:
    from .run import folder
    folder(project).mkdir(parents=True, exist_ok=True)
    try:
        title = project.load_project().name
    except Exception:
        title = project.name
    (folder(project) / "board.html").write_text(render(state, title), encoding="utf-8")
    (folder(project) / "board.json").write_text(json.dumps({"shortlist": state.get("shortlist", {}),
                                                            "picked": state.get("picked", {})}, indent=2), encoding="utf-8")
