<!--
Title: type(area): what changed, e.g. "fix(runtime): end reveals on transform none". See CONTRIBUTING.md#pull-requests.
Every pull request needs an accepted issue; core changes need a design-approved one (CONTRIBUTING.md#rules-per-area).
-->

Closes #

## What and why

<!-- What this changes and why. Pictures or a short recording for anything visual (desktop and phone). -->

## Checklist

- [ ] Linked to an issue labelled `status: accepted` (`status: design-approved` for a core change).
- [ ] An engine feature or fix, not a one-off page; no hosted APIs or keys ([ground rules](../CONTRIBUTING.md#ground-rules)).
- [ ] Tests added or updated; `python -m pytest -q` passes.
- [ ] A changelog fragment in `changes/` for anything a user would notice ([changes/README.md](../changes/README.md)).
- [ ] Docs updated; new dependencies declared (`pyproject.toml`, `package.json`, `engine/models.yaml`, `docs/INSTALL.md`).
- [ ] Third-party material (code, images, models, text) named with its source and licence.
- [ ] Nothing from one machine: no drive-letter paths, home folders, usernames or folder layouts.

**If it touches a core area** ([extra checks](../CONTRIBUTING.md#rules-per-area)):

- [ ] Runtime: `npm run build:runtime` run and the bundle committed; checked on desktop and phone, with reduced motion.
- [ ] Spec, CLI or MCP: descriptions written for people; snapshots and generated reference updated.
- [ ] Compiler or themes: layout snapshots unchanged, or re-recorded with every change explained here.
- [ ] Anything an existing spec, site, command or tool does changes: labelled `breaking-change`, with a migration note.
- [ ] Models, downloads or servers: threat model updated if needed; checksums for downloads; servers on `127.0.0.1`.
