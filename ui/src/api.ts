export type Json = any;

async function req(method: string, url: string, body?: unknown): Promise<Json> {
  const r = await fetch(url, {
    method,
    headers: body instanceof FormData || body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok && r.status !== 422) throw new Error(data.detail || `${r.status} ${r.statusText}`);
  return data;
}

export const api = {
  info: () => req("GET", "/api/info"),
  schema: () => req("GET", "/api/schema"),
  doctor: () => req("GET", "/api/doctor"),
  projects: () => req("GET", "/api/projects"),
  create: (name: string, example?: string) => req("POST", "/api/projects", { name, example }),
  spec: (name: string) => req("GET", `/api/projects/${name}/spec`),
  saveSpec: (name: string, payload: { data?: Json; yaml?: string }) => req("PUT", `/api/projects/${name}/spec`, payload),
  inputs: (name: string) => req("GET", `/api/projects/${name}/inputs`),
  upload: (name: string, files: FileList | File[]) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    return req("POST", `/api/projects/${name}/inputs`, fd);
  },
  build: (name: string, opts: { section?: string; force?: boolean; draft?: boolean }) => req("POST", `/api/projects/${name}/build`, opts),
  snapshot: (name: string, at: string[] = []) => req("POST", `/api/projects/${name}/snapshot`, { at }),
  record: (name: string, opts: { section?: string; seconds?: number }) => req("POST", `/api/projects/${name}/record`, opts),
  recordings: (name: string) => req("GET", `/api/projects/${name}/recordings`),
  jobs: (project?: string) => req("GET", `/api/jobs${project ? `?project=${project}` : ""}`),
  job: (id: string) => req("GET", `/api/jobs/${id}`),
};

/** Poll a job until it finishes; calls back with every update. */
export async function follow(id: string, on: (j: Json) => void): Promise<Json> {
  for (;;) {
    const j = await api.job(id);
    on(j);
    if (j.status === "done" || j.status === "failed") return j;
    await new Promise((r) => setTimeout(r, 700));
  }
}
