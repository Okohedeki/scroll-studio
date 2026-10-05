import { useEffect, useState } from "react";
import { api } from "../api";

export function Doctor() {
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => { api.doctor().then(setRows); }, []);
  return (
    <div className="page">
      <header className="page-head">
        <h1>Toolchain</h1>
        <p className="muted">What each scene type needs, and whether this machine has it. Install steps are in docs/INSTALL.md.</p>
      </header>
      {!rows ? <div className="muted">Checking…</div> : (
        <table className="table">
          <thead><tr><th></th><th>Check</th><th>Detail</th><th>Needed by</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.name}><td>{r.ok ? <span className="ok">●</span> : <span className="bad">●</span>}</td><td>{r.name}</td><td className="mono small">{String(r.detail)}</td><td className="muted">{r.needed_by}</td></tr>)}</tbody>
        </table>
      )}
    </div>
  );
}
