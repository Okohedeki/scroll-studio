// The pull request policy (CONTRIBUTING.md#pull-requests, #rules-per-area), shared by three workflows:
//   pr-policy.yml          the required `pr-policy` check: title, linked accepted issue, changelog fragment
//   pr-labels.yml          area, tier and size labels
//   pr-policy-recheck.yml  re-runs the check when a linked issue is accepted
// The workflows load this file from the base branch, so a pull request cannot change the rules it is checked by.
// tests/test_pr_policy.py covers the pure functions.

const REPO_URL = "https://github.com/Okohedeki/scroll-studio";

const TYPES = ["feat", "fix", "perf", "docs", "test", "refactor", "style", "build", "ci", "chore", "revert"];
const SCOPES = ["runtime", "spec", "compiler", "scenes", "styles", "themes", "models", "cli", "mcp", "ui", "docs",
  "examples", "tests", "ci", "deps", "release"];
const NEEDS_FRAGMENT = ["feat", "fix", "perf"];
const FRAGMENT_KINDS = ["breaking", "added", "changed", "deprecated", "removed", "fixed", "security"];
const ACCEPTED = "status: accepted";
const DESIGN_APPROVED = "status: design-approved";
const EXEMPT_AUTHORS = ["dependabot[bot]", "github-actions[bot]"];

// Paths that make a pull request `tier: core`. The bundle in engine/compile/static/runtime is handled separately in
// isCore(): rebuilding it for a style-only change does not make a pull request core.
const CORE = [
  "engine/spec.py", "engine/compile/**", "engine/themes.yaml", "engine/styles/README.md",
  "engine/cli.py", "engine/mcp_server.py", "engine/backends/**", "engine/models.yaml", "engine/server/**",
  "engine/serve.py", ".github/**", "pyproject.toml", "package.json", "package-lock.json", "towncrier.toml",
  "LICENSE", "NOTICE.md", "CLA.md", "AGENTS.md",
];
const BUNDLE = "engine/compile/static/runtime/**";

// Area labels from paths; a file can be in several areas.
const AREAS = {
  "area: runtime": ["runtime/**", BUNDLE],
  "area: spec": ["engine/spec.py"],
  "area: compiler": ["engine/compile/*.py", "engine/compile/templates/**"],
  "area: themes": ["engine/themes.yaml", "engine/compile/themes.py"],
  "area: styles": ["engine/styles/**", "runtime/src/styles/**", "docs/styles/**", "docs/styles.md"],
  "area: scenes": ["engine/scenes/**"],
  "area: models": ["engine/backends/**", "engine/models.yaml"],
  "area: cli": ["engine/cli.py"],
  "area: mcp": ["engine/mcp_server.py"],
  "area: ui": ["ui/**", "engine/server/**"],
  "area: ci": [".github/**"],
  "area: docs": ["docs/**", "*.md", "mkdocs.yml"],
  "area: examples": ["examples/**"],
  "area: tests": ["tests/**"],
  "area: packaging": ["pyproject.toml", "package.json", "package-lock.json", "*/package.json", "towncrier.toml"],
  "area: legal": ["LICENSE", "NOTICE.md", "CLA.md", "AGENTS.md"],
};
// Generated files don't count toward the size label.
const GENERATED = [BUNDLE, "package-lock.json", "tests/snapshots/**", "ui/dist/**"];
const SIZES = [[10, "size: xs"], [100, "size: s"], [400, "size: m"], [1000, "size: l"], [Infinity, "size: xl"]];

function globToRegExp(glob) {
  let re = "";
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === "*" && glob[i + 1] === "*") { re += ".*"; i++; if (glob[i + 1] === "/") i++; }
    else if (c === "*") re += "[^/]*";
    else re += c.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
  }
  return new RegExp(`^${re}$`);
}
const matches = (file, globs) => globs.some((g) => globToRegExp(g).test(file));

function isCore(files) {
  if (files.some((f) => matches(f, CORE) && !matches(f, [BUNDLE]))) return true;
  const runtimeSrc = files.filter((f) => f.startsWith("runtime/"));
  if (runtimeSrc.some((f) => !f.startsWith("runtime/src/styles/"))) return true;
  // the bundle alone, or the bundle with source changes only in runtime/src/styles/
  return files.some((f) => matches(f, [BUNDLE])) && runtimeSrc.length === 0;
}

function areas(files) {
  return Object.keys(AREAS).filter((label) => files.some((f) => matches(f, AREAS[label])));
}

function sizeLabel(changes) {
  const lines = changes.filter((c) => !matches(c.filename, GENERATED)).reduce((n, c) => n + c.changes, 0);
  return SIZES.find(([limit]) => lines < limit)[1];
}

function parseTitle(title) {
  const m = /^([a-z]+)(?:\(([a-z-]+)\))?(!)?: (.+)$/.exec(title.trim());
  return m ? { type: m[1], scope: m[2] || null, breaking: Boolean(m[3]), subject: m[4] } : null;
}

function titleProblems(title) {
  const t = parseTitle(title);
  const example = "fix(runtime): end reveals on transform none";
  if (!t) return [`The title must look like \`type(area): what changed\`, e.g. \`${example}\`.`];
  const out = [];
  if (!TYPES.includes(t.type)) out.push(`\`${t.type}\` is not a type; use one of ${TYPES.map((x) => `\`${x}\``).join(", ")}.`);
  if (t.scope && !SCOPES.includes(t.scope)) out.push(`\`${t.scope}\` is not an area; use one of ${SCOPES.map((x) => `\`${x}\``).join(", ")}, or none.`);
  if (!/^[a-z0-9`]/.test(t.subject)) out.push("Start the description after the colon in lower case.");
  if (/\.$/.test(t.subject)) out.push("Leave the full stop off the end of the title.");
  return out;
}

const FRAGMENT_RE = new RegExp(`^changes/(\\d+|\\+[a-z0-9-]+)\\.(${FRAGMENT_KINDS.join("|")})(\\.\\d+)?\\.md$`);

function fragmentProblems(title, changes, labels) {
  const fragments = changes.filter((c) => c.filename.startsWith("changes/") && c.filename !== "changes/README.md"
    && c.status !== "removed");
  const out = fragments.filter((c) => !FRAGMENT_RE.test(c.filename))
    .map((c) => `\`${c.filename}\` is not a fragment name: use \`changes/<issue>.<kind>.md\` with a kind from ${FRAGMENT_KINDS.join(", ")} (changes/README.md).`);
  const t = parseTitle(title);
  if (!t || labels.includes("skip-changelog")) return out;
  if (NEEDS_FRAGMENT.includes(t.type) && fragments.length === 0) {
    out.push(`A \`${t.type}\` pull request needs a changelog fragment: add \`changes/<issue>.<kind>.md\` with a sentence for users (changes/README.md). A maintainer can label it \`skip-changelog\` if users won't notice.`);
  }
  if (t.breaking && !fragments.some((c) => /\.breaking(\.\d+)?\.md$/.test(c.filename))) {
    out.push("The title marks a breaking change (`!`): add a `changes/<issue>.breaking.md` fragment with the migration (what to change in `site.yaml`).");
  }
  return out;
}

const LINK_RE = /(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|part of|refs?|towards)\s*:?\s+(?:[\w.-]+\/[\w.-]+)?#(\d+)/gi;

function linkedNumbers(body) {
  return [...new Set([...(body || "").matchAll(LINK_RE)].map((m) => Number(m[1])))];
}

// issues: [{number, state, labels: [names], isPullRequest}]
function issueProblems(issues, core) {
  const real = issues.filter((i) => !i.isPullRequest);
  const need = core ? DESIGN_APPROVED : ACCEPTED;
  const how = `Link the issue in the description (\`Closes #123\`, or \`Part of #123\` when it takes several pull requests).`;
  if (real.length === 0) {
    return [`No linked issue. Every pull request needs an issue a maintainer has accepted (CONTRIBUTING.md#before-you-start). ${how}`];
  }
  const ok = real.some((i) => i.state === "open" && (core ? i.labels.includes(DESIGN_APPROVED)
    : i.labels.includes(ACCEPTED) || i.labels.includes(DESIGN_APPROVED)));
  if (ok) return [];
  const list = real.map((i) => `#${i.number} (${i.state}${i.labels.length ? `; ${i.labels.join(", ")}` : ""})`).join(", ");
  const why = core
    ? "This pull request touches a core area, so its issue needs an agreed design (`status: design-approved`) first (CONTRIBUTING.md#rules-per-area)."
    : "Its issue needs to be accepted by a maintainer (`status: accepted`) first.";
  return [`Linked: ${list}. ${why} This check re-runs when the issue is labelled \`${need}\`.`];
}

async function listFiles(github, owner, repo, number) {
  return github.paginate(github.rest.pulls.listFiles, { owner, repo, pull_number: number, per_page: 100 });
}

async function linkedIssues(github, owner, repo, pr) {
  const numbers = new Set(linkedNumbers(pr.body));
  try {
    const q = `query($owner:String!,$repo:String!,$n:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$n){
      closingIssuesReferences(first:20){nodes{number repository{nameWithOwner}}}}}}`;
    const r = await github.graphql(q, { owner, repo, n: pr.number });
    for (const i of r.repository.pullRequest.closingIssuesReferences.nodes) {
      if (i.repository.nameWithOwner.toLowerCase() === `${owner}/${repo}`.toLowerCase()) numbers.add(i.number);
    }
  } catch (e) { /* the body is enough when GraphQL is unavailable */ }
  const out = [];
  for (const n of numbers) {
    try {
      const { data } = await github.rest.issues.get({ owner, repo, issue_number: n });
      out.push({ number: n, state: data.state, labels: data.labels.map((l) => (typeof l === "string" ? l : l.name)),
        isPullRequest: Boolean(data.pull_request) });
    } catch (e) { out.push({ number: n, state: "missing", labels: [], isPullRequest: false }); }
  }
  return out;
}

// The `pr-policy` check.
async function check({ github, context, core }) {
  const pr = context.payload.pull_request;
  const { owner, repo } = context.repo;
  const labels = pr.labels.map((l) => l.name);
  const summary = core.summary.addHeading("Pull request policy", 2);
  if (EXEMPT_AUTHORS.includes(pr.user.login) || labels.includes("release")) {
    await summary.addRaw(`Exempt: opened by ${pr.user.login}${labels.includes("release") ? " (release)" : ""}.`).write();
    return;
  }
  const changes = await listFiles(github, owner, repo, pr.number);
  const files = changes.map((c) => c.filename);
  const coreTier = isCore(files);
  const issues = await linkedIssues(github, owner, repo, pr);
  const problems = [
    ...titleProblems(pr.title),
    ...issueProblems(issues, coreTier),
    ...fragmentProblems(pr.title, changes, labels),
  ];
  summary.addTable([
    [{ data: "Rule", header: true }, { data: "Result", header: true }],
    ["Tier", coreTier ? "core (needs a design-approved issue)" : "standard"],
    ["Linked issues", issues.length ? issues.map((i) => `#${i.number}`).join(", ") : "none"],
    ["Title", titleProblems(pr.title).length ? "needs fixing" : "ok"],
  ]);
  if (problems.length) {
    summary.addHeading("What to fix", 3).addList(problems);
    await summary.addRaw(`\nSee ${REPO_URL}/blob/main/CONTRIBUTING.md#pull-requests`).write();
    core.setFailed(problems.join("\n"));
  } else {
    await summary.addRaw("All rules pass.").write();
  }
}

// Area, tier and size labels (pull_request_target; never runs the pull request's code).
async function label({ github, context, core }) {
  const pr = context.payload.pull_request;
  const { owner, repo } = context.repo;
  const changes = await listFiles(github, owner, repo, pr.number);
  const files = changes.map((c) => c.filename);
  const have = pr.labels.map((l) => l.name);
  const want = [...areas(files), sizeLabel(changes)];
  if (isCore(files)) want.push("tier: core");
  const remove = have.filter((l) => (l.startsWith("size: ") || l === "tier: core") && !want.includes(l));
  const add = want.filter((l) => !have.includes(l));
  for (const name of remove) await github.rest.issues.removeLabel({ owner, repo, issue_number: pr.number, name });
  if (add.length) await github.rest.issues.addLabels({ owner, repo, issue_number: pr.number, labels: add });
  core.info(`added: ${add.join(", ") || "none"}; removed: ${remove.join(", ") || "none"}`);
}

// When an issue is accepted, re-run the policy check of every open pull request that links it.
async function recheck({ github, context, core }) {
  const { owner, repo } = context.repo;
  const issue = context.payload.issue.number;
  const prs = await github.paginate(github.rest.pulls.list, { owner, repo, state: "open", per_page: 100 });
  for (const pr of prs) {
    const linked = (await linkedIssues(github, owner, repo, pr)).map((i) => i.number);
    if (!linked.includes(issue)) continue;
    const { data } = await github.rest.actions.listWorkflowRuns({ owner, repo, workflow_id: "pr-policy.yml",
      head_sha: pr.head.sha, per_page: 1 });
    if (!data.workflow_runs.length) continue;
    await github.rest.actions.reRunWorkflow({ owner, repo, run_id: data.workflow_runs[0].id });
    core.info(`re-ran the policy check of #${pr.number}`);
  }
}

module.exports = {
  TYPES, SCOPES, FRAGMENT_KINDS, AREAS, CORE,
  isCore, areas, sizeLabel, parseTitle, titleProblems, fragmentProblems, linkedNumbers, issueProblems,
  check, label, recheck,
};
