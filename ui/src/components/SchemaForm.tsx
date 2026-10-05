/**
 * Renders a form for any part of the site spec from its JSON Schema (generated from engine/spec.py),
 * so new spec fields appear in the UI without UI changes.
 */
import { useState } from "react";

type S = any;
export interface Ctx { root: S; inputs: { path: string; url: string }[] }

const deref = (s: S, ctx: Ctx): S => (s?.$ref ? ctx.root.$defs[s.$ref.split("/").pop()] : s);
const label = (k: string) => k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/** Collapse Optional[X] (anyOf [X, null]) to X; keep real unions. */
function unwrap(s: S, ctx: Ctx): { s: S; nullable: boolean } {
  s = deref(s, ctx);
  if (s?.anyOf) {
    const opts = s.anyOf.filter((o: S) => o.type !== "null");
    const nullable = opts.length < s.anyOf.length;
    if (opts.length === 1) return { s: { ...deref(opts[0], ctx), description: s.description, default: s.default, title: s.title }, nullable };
    return { s: { ...s, anyOf: opts }, nullable };
  }
  return { s, nullable: false };
}

function isImageRef(s: S, ctx: Ctx) {
  return s?.anyOf?.length === 2 && s.anyOf.some((o: S) => o.type === "string") && s.anyOf.some((o: S) => deref(o, ctx)?.title === "ImageInput");
}

export function Field({ name, schema, value, onChange, ctx }: { name: string; schema: S; value: any; onChange: (v: any) => void; ctx: Ctx }) {
  const { s } = unwrap(schema, ctx);
  const help = s?.description;
  const head = <div className="f-head"><span className="f-label">{label(name)}</span>{help && <span className="f-help">{help}</span>}</div>;

  if (isImageRef(s, ctx)) return <div className="f">{head}<ImageField value={value} onChange={onChange} ctx={ctx} /></div>;

  if (s?.enum || s?.const !== undefined) {
    const opts = s.enum || [s.const];
    return <label className="f">{head}<select value={value ?? s.default ?? ""} onChange={(e) => onChange(e.target.value)}>{opts.map((o: string) => <option key={o}>{o}</option>)}</select></label>;
  }
  if (s?.anyOf) {   // e.g. focus: "auto" | [[x, y]]
    const text = typeof value === "string" || value === undefined ? (value ?? s.default ?? "") : JSON.stringify(value);
    return <label className="f">{head}<input value={text} onChange={(e) => { try { onChange(JSON.parse(e.target.value)); } catch { onChange(e.target.value); } }} /></label>;
  }
  if (s?.type === "boolean") return <label className="f f-row"><input type="checkbox" checked={!!(value ?? s.default)} onChange={(e) => onChange(e.target.checked)} />{head}</label>;
  if (s?.type === "number" || s?.type === "integer")
    return <label className="f">{head}<input type="number" step={s.type === "integer" ? 1 : "any"} value={value ?? s.default ?? ""} onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} /></label>;
  if (s?.type === "string") {
    const long = /title|body|text|description|fact|prompt|generate/.test(name);
    const pickable = /^(file|model|video|image)$/.test(name);
    const listId = pickable ? "inputs-list" : name === "preset" ? "presets-list" : name === "hdri" ? "hdri-list" : undefined;
    return (
      <label className="f">{head}
        {long ? <textarea rows={name === "text" || name === "generate" ? 4 : 2} value={value ?? ""} placeholder={s.default ?? ""} onChange={(e) => onChange(e.target.value || undefined)} />
          : <input value={value ?? ""} placeholder={s.default ?? ""} list={listId} onChange={(e) => onChange(e.target.value || undefined)} />}
      </label>
    );
  }
  if (s?.type === "array" && s.prefixItems) {   // tuples: size, at, bloom
    const v = value ?? s.default ?? s.prefixItems.map(() => 0);
    return <div className="f">{head}<div className="tuple">{s.prefixItems.map((_: S, i: number) =>
      <input key={i} type="number" step="any" value={v[i] ?? ""} onChange={(e) => { const n = [...v]; n[i] = Number(e.target.value); onChange(n); }} />)}</div></div>;
  }
  if (s?.type === "array") {
    const item = unwrap(s.items, ctx).s;
    if (item?.type === "string" || item?.enum)
      return <label className="f">{head}<input value={(value ?? s.default ?? []).join(", ")} onChange={(e) => onChange(e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} /></label>;
    if (item?.properties) return <div className="f">{head}<ObjectList items={value ?? []} schema={item} onChange={onChange} ctx={ctx} /></div>;
    return <JsonField head={head} value={value ?? s.default ?? []} onChange={onChange} />;
  }
  if (s?.properties) return <Fieldset name={name} schema={s} value={value ?? {}} onChange={onChange} ctx={ctx} />;
  return <JsonField head={head} value={value ?? s?.default ?? {}} onChange={onChange} />;
}

function JsonField({ head, value, onChange }: { head: any; value: any; onChange: (v: any) => void }) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [bad, setBad] = useState(false);
  return <label className="f">{head}<textarea className={"mono" + (bad ? " bad" : "")} rows={Math.min(14, text.split("\n").length + 1)} value={text}
    onChange={(e) => { setText(e.target.value); try { onChange(JSON.parse(e.target.value)); setBad(false); } catch { setBad(true); } }} /></label>;
}

function ImageField({ value, onChange, ctx }: { value: any; onChange: (v: any) => void; ctx: Ctx }) {
  const obj = typeof value === "string" ? { file: value } : value ?? {};
  const mode = obj.generate !== undefined && !obj.file ? "generate" : "file";
  const set = (k: string, v: any) => onChange({ ...obj, [k]: v || undefined });
  const preview = ctx.inputs.find((i) => i.path === obj.file)?.url;
  return (
    <div className="imagefield">
      <div className="seg">
        <button className={mode === "file" ? "on" : ""} onClick={(e) => { e.preventDefault(); onChange({ file: obj.file || "", credit: obj.credit }); }}>File</button>
        <button className={mode === "generate" ? "on" : ""} onClick={(e) => { e.preventDefault(); onChange({ generate: obj.generate || "", size: obj.size, seed: obj.seed }); }}>Generate</button>
      </div>
      {mode === "file" ? (
        <div className="row">
          {preview && <img className="thumb" src={preview} alt="" />}
          <input list="inputs-list" placeholder="inputs/photo.jpg or https://…" value={obj.file ?? ""} onChange={(e) => set("file", e.target.value)} />
        </div>
      ) : (
        <textarea rows={3} placeholder="Describe the photo; it is generated locally with Z-Image Turbo" value={obj.generate ?? ""} onChange={(e) => set("generate", e.target.value)} />
      )}
      <input placeholder="Credit (optional)" value={obj.credit ?? ""} onChange={(e) => set("credit", e.target.value)} />
    </div>
  );
}

export function Fieldset({ name, schema, value, onChange, ctx, open = false }: { name: string; schema: S; value: any; onChange: (v: any) => void; ctx: Ctx; open?: boolean }) {
  const [isOpen, setOpen] = useState(open);
  return (
    <div className="fieldset">
      <button className="fs-head" onClick={(e) => { e.preventDefault(); setOpen(!isOpen); }}>{isOpen ? "▾" : "▸"} {label(name)}</button>
      {isOpen && <Fields schema={schema} value={value} onChange={onChange} ctx={ctx} />}
    </div>
  );
}

export function Fields({ schema, value, onChange, ctx, skip = [] }: { schema: S; value: any; onChange: (v: any) => void; ctx: Ctx; skip?: string[] }) {
  const props = schema.properties || {};
  return <div className="fields">{Object.keys(props).filter((k) => !skip.includes(k) && !props[k].const).map((k) =>
    <Field key={k} name={k} schema={props[k]} value={value?.[k]} ctx={ctx}
      onChange={(v) => { const next = { ...value }; if (v === undefined || v === "") delete next[k]; else next[k] = v; onChange(next); }} />)}</div>;
}

function ObjectList({ items, schema, onChange, ctx }: { items: any[]; schema: S; onChange: (v: any[]) => void; ctx: Ctx }) {
  const [open, setOpen] = useState<number | null>(null);
  const summary = (it: any) => String(it.title ?? it.label ?? it.preset ?? it.value ?? it.when ?? it.t ?? "item").replace(/<[^>]+>/g, "");
  const move = (i: number, d: number) => { const n = [...items]; const [x] = n.splice(i, 1); n.splice(i + d, 0, x); onChange(n); };
  return (
    <div className="olist">
      {items.map((it, i) => (
        <div key={i} className={"oitem" + (open === i ? " open" : "")}>
          <div className="oi-head" onClick={() => setOpen(open === i ? null : i)}>
            <span className="oi-n">{i + 1}</span><span className="oi-t">{summary(it)}</span>
            <span className="oi-tools" onClick={(e) => e.stopPropagation()}>
              <button disabled={i === 0} onClick={() => move(i, -1)} title="Move up">↑</button>
              <button disabled={i === items.length - 1} onClick={() => move(i, 1)} title="Move down">↓</button>
              <button onClick={() => onChange(items.filter((_, j) => j !== i))} title="Remove">✕</button>
            </span>
          </div>
          {open === i && <Fields schema={schema} value={it} ctx={ctx} onChange={(v) => { const n = [...items]; n[i] = v; onChange(n); }} />}
        </div>
      ))}
      <button className="ghost small" onClick={(e) => { e.preventDefault(); onChange([...items, {}]); setOpen(items.length); }}>+ Add</button>
    </div>
  );
}
