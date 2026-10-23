// The Contributor Licence Agreement check (CLA.md, CONTRIBUTING.md#licence-and-the-cla), run by cla.yml.
// Every author of a pull request's commits signs once by commenting the sentence below; signatures are kept in
// signatures/cla.json on the `cla-signatures` branch (the format the project has used since the first signature).
// Loaded from the default branch; never reads or runs the pull request's code. tests/test_cla.py covers the pure parts.

const SENTENCE = "I have read the CLA Document and I hereby sign the CLA";
const BRANCH = "cla-signatures";
const FILE = "signatures/cla.json";
const ALLOWLIST = ["Okohedeki"];
const MARKER = "<!-- scroll-studio-cla -->";
const CLA_URL = "https://github.com/Okohedeki/scroll-studio/blob/main/CLA.md";

const isBot = (login) => /\[bot\]$/.test(login);
const isSigning = (body) => (body || "").trim().replace(/\s+/g, " ").replace(/\.$/, "") === SENTENCE;

// commits: [{author: {login, id} | null, commit: {author: {name, email}}}]
function authors(commits) {
  const out = new Map();
  for (const c of commits) {
    if (c.author && c.author.login) {
      if (!isBot(c.author.login) && !ALLOWLIST.includes(c.author.login)) out.set(c.author.login, { login: c.author.login, id: c.author.id });
    } else {
      // a commit whose email isn't linked to a GitHub account can't be matched to a signature
      const name = c.commit.author.name;
      out.set(`unlinked:${name}`, { login: null, name });
    }
  }
  return [...out.values()];
}

function unsigned(people, signatures) {
  const ids = new Set(signatures.signedContributors.map((s) => s.id));
  return people.filter((p) => p.login === null || !ids.has(p.id));
}

function message(missing) {
  if (missing.length === 0) return `${MARKER}\nAll contributors have signed the CLA. Thank you.`;
  const named = missing.filter((p) => p.login).map((p) => `@${p.login}`);
  const unlinked = missing.filter((p) => !p.login).map((p) => p.name);
  let text = `${MARKER}\nThank you for contributing to Scroll Studio. Before this can be merged, please read the ` +
    `[Contributor Licence Agreement](${CLA_URL}) and sign it by commenting on this pull request with exactly:\n\n` +
    `> ${SENTENCE}\n\nYou only sign once, for all your contributions.`;
  if (named.length) text += `\n\nStill to sign: ${named.join(", ")}.`;
  if (unlinked.length) {
    text += `\n\nSome commits are by ${unlinked.join(", ")}, whose email is not linked to a GitHub account. Add the ` +
      "email to your GitHub account (or amend the commits with one that is), then push again.";
  }
  return text;
}

async function readSignatures(github, owner, repo) {
  const { data } = await github.rest.repos.getContent({ owner, repo, path: FILE, ref: BRANCH });
  return { sha: data.sha, signatures: JSON.parse(Buffer.from(data.content, "base64").toString("utf8")) };
}

// Ask on the pull request while someone hasn't signed; once everyone has, turn the request into a thank-you.
async function upsertComment(github, owner, repo, number, body, create) {
  const comments = await github.paginate(github.rest.issues.listComments, { owner, repo, issue_number: number, per_page: 100 });
  const mine = comments.find((c) => c.user.login === "github-actions[bot]" && (c.body || "").startsWith(MARKER));
  if (mine) {
    if (mine.body !== body) await github.rest.issues.updateComment({ owner, repo, comment_id: mine.id, body });
  } else if (create) {
    await github.rest.issues.createComment({ owner, repo, issue_number: number, body });
  }
}

async function run({ github, context, core }) {
  const { owner, repo } = context.repo;
  const number = context.payload.pull_request ? context.payload.pull_request.number : context.payload.issue.number;
  const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number: number });
  const commits = await github.paginate(github.rest.pulls.listCommits, { owner, repo, pull_number: number, per_page: 100 });
  const people = authors(commits);
  let { sha, signatures } = await readSignatures(github, owner, repo);

  if (context.eventName === "issue_comment" && isSigning(context.payload.comment.body)) {
    const who = context.payload.comment.user;
    if (people.some((p) => p.id === who.id) && !signatures.signedContributors.some((s) => s.id === who.id)) {
      signatures.signedContributors.push({ name: who.login, id: who.id, comment_id: context.payload.comment.id,
        created_at: context.payload.comment.created_at, repoId: context.payload.repository.id, pullRequestNo: number });
      await github.rest.repos.createOrUpdateFileContents({ owner, repo, path: FILE, branch: BRANCH, sha,
        message: `@${who.login} has signed the CLA in #${number}`,
        content: Buffer.from(JSON.stringify(signatures, null, 2) + "\n").toString("base64") });
      core.info(`recorded the signature of ${who.login}`);
    }
  }

  const missing = unsigned(people, signatures);
  await upsertComment(github, owner, repo, number, message(missing), missing.length > 0);
  if (context.eventName === "issue_comment") {
    // the check that branch protection sees belongs to the pull request's run: run it again with the new signature
    const { data } = await github.rest.actions.listWorkflowRuns({ owner, repo, workflow_id: "cla.yml",
      head_sha: pr.head.sha, event: "pull_request_target", per_page: 1 });
    if (data.workflow_runs.length) await github.rest.actions.reRunWorkflow({ owner, repo, run_id: data.workflow_runs[0].id });
    return;
  }
  if (missing.length) core.setFailed(`Not signed yet: ${missing.map((p) => p.login || p.name).join(", ")}`);
}

module.exports = { SENTENCE, isSigning, authors, unsigned, message, run };
