# Repository settings

The GitHub settings the project relies on, recorded so they can be audited and restored. Change a setting and this
page in the same pull request (or right after, for settings that only exist in the UI).

## General

- Merges: **squash only** (merge commits and rebase merging off). Squash commit title: the pull request title;
  message: the commit messages.
- Branches are deleted after merging. Auto-merge is allowed. "Update branch" is suggested.
- Discussions on (categories: Announcements, Q&A, Ideas, Proposals, Show and tell). Wiki off: docs live in `docs/`.

## Branches and tags

- `main` (branch protection):
  - Changes only through pull requests, for everyone, administrators included. No force pushes, no deletion.
  - Required checks, branch up to date before merging: `tests`, `lint`, `runtime`, `install`, `render`, `pr-policy`,
    `dependency-review`, `secrets` and `workflows`. The `platforms` jobs (Windows, macOS, Python 3.10 and 3.13) and
    `docs` (which only runs when docs change) run on every pull request but are not required yet.
  - Conversations must be resolved. Stale approvals are dismissed when new commits are pushed.
- `v*` tags (ruleset "Release tags"): only repository administrators can create, move or delete release tags.
- `cla-signatures`: holds the CLA signatures (`signatures/cla.json`), written by the CLA workflow.

## Security

- Private vulnerability reporting: on.
- Dependabot alerts and Dependabot security updates: on. Version updates: [.github/dependabot.yml](https://github.com/Okohedeki/scroll-studio/blob/main/.github/dependabot.yml).
- Secret scanning and push protection: on.
- Code scanning: CodeQL default setup (Python, JavaScript/TypeScript, GitHub Actions; extended query suite), plus
  OpenSSF Scorecard results.

## Actions

- Workflows from fork pull requests need approval for first-time contributors.
- The default `GITHUB_TOKEN` is read-only; each workflow asks for the permissions it needs.
- Actions must be pinned to full commit SHAs ("Require actions to be pinned to a full-length commit SHA" is on);
  Dependabot updates them.
