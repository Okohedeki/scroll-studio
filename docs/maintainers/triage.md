# Triage

How issues and pull requests are handled, for maintainers and triagers. Labels are defined in
[.github/labels.yml](https://github.com/Okohedeki/scroll-studio/blob/main/.github/labels.yml); change them there, never
in the GitHub UI.

## Response targets

| What | First response | Then |
|---|---|---|
| Security report (private advisory) | 2 days | Fix plan within 7 days ([SECURITY.md](https://github.com/Okohedeki/scroll-studio/blob/main/SECURITY.md)) |
| `priority: p0` issue | Same day | Fix or workaround in a patch release |
| New issue | 3 days: triaged | |
| Pull request | 3 days: first comment | Full review within 7 days of the checks passing |
| `status: needs-info` | — | Closed 21 days after the question if nobody answers (the stale workflow does this) |

These are targets for a volunteer project, not guarantees. If a target is missed, say so on the issue.

## Triaging an issue

Every new issue arrives with `status: needs-triage` (the issue forms add it). For each:

1. **Is it in the right place?** Questions go to Discussions (convert the issue). Security problems: hide the issue
   and ask the reporter to use a private advisory. Duplicates: label `duplicate`, link the original, close.
2. **Is it complete?** A bug needs the spec (or the part that matters), the command, what happened and what was
   expected, and `studio doctor` output for GPU stages. If not, ask specifically and label `status: needs-info`.
3. **Label it**: one `type:`, one or more `area:`, and a `priority:`:
   - `p0`: broken for everyone, data loss, or security; drop everything.
   - `p1`: a real bug or planned work for the next release.
   - `p2`: planned, not urgent.
   - `p3`: nice to have.
4. **Decide.** Remove `status: needs-triage` and either:
   - **accept**: `status: accepted`. For a core change (see
     [CONTRIBUTING.md](https://github.com/Okohedeki/scroll-studio/blob/main/CONTRIBUTING.md#rules-per-area)), only
     once the design is written down: then `status: design-approved` as well. Put it in a milestone if it's planned.
   - **decline**: `wontfix` with the reason (usually a ground rule: one-off pages, hosted APIs, or not an engine
     feature), and close. Be kind and specific.
   - **needs design**: ask for a design section or an RFC ([docs/rfcs/](../rfcs/README.md)) and leave it open.
5. **Invite help** where it fits: `good first issue` (small, clearly described, with pointers to the files) or
   `help wanted`.

## Triaging a pull request

The checks do most of it. The `pr-policy` check fails until the pull request links an accepted issue (a core pull
request needs a design-approved one). The labeler adds `area:`, `tier: core` and `size:` labels.

1. **No linked issue?** The check explains what to do. If the change is welcome, open or find the issue, accept it, and
   re-run the check. If it isn't, say why and close it, thanking the contributor.
2. **Core pull request** (`tier: core`): make sure the area's extra checks ran and the design matches what was
   approved. Behaviour changes need a migration note and the `breaking-change` label.
3. **Snapshots changed?** Label `snapshots-updated` and read the diff like code: every change must be explained.
4. **CLA**: the bot asks first-time contributors to sign. Nothing is merged before that.
5. **Review** for the ground rules and consistency rules, then the code. Request changes with concrete suggestions;
   maintainers can push small fixes to the contributor's branch.
6. **Merge** with squash once everything is green. The pull request title becomes the commit message, so make sure it
   follows the [title format](https://github.com/Okohedeki/scroll-studio/blob/main/CONTRIBUTING.md#pull-requests).

## Dependabot pull requests

They are exempt from the issue rule. Python and Actions updates merge when green. npm updates to the runtime's
libraries change the built bundle, so the `runtime` check fails until it is rebuilt: check out the branch, run
`npm ci && npm run build:runtime`, look at the scenes the library drives (`studio snapshot` on an example that uses
it), commit the bundle and push. Major versions are never proposed automatically; they are planned upgrades with
their own issue.

## Saying no

Most declined work breaks a ground rule. Link it, say what would make the idea fit (often: make it an engine feature
every site can use), and thank the person. Close politely; never leave someone waiting without an answer.
