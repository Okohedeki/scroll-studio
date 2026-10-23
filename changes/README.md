# Changelog fragments

Every pull request a user would notice adds one small file here instead of editing `CHANGELOG.md`. At release time
the files are gathered into a new section of the changelog and deleted, so pull requests never conflict over it.

## Name

`<issue>.<kind>.md`, for example `13.added.md` for issue #13. Two fragments for the same issue: `13.added.md` and
`13.fixed.md`. A change with no issue (rare, maintainers only): `+short-name.<kind>.md`.

| Kind | For |
|---|---|
| `breaking` | Something an existing spec, built site, command or tool does differently. Include the migration: what to change in `site.yaml`. |
| `added` | A new scene, spec field, style, command, option or tool |
| `changed` | Existing behaviour that works differently (and is not breaking) |
| `deprecated` | Still works, warns, and will be removed in a named version |
| `removed` | Gone (only in a major release, after a deprecation) |
| `fixed` | A bug fix |
| `security` | A security fix, without exploit details |

## Text

A sentence or two, written for someone who builds sites with Scroll Studio: what they can do now, or what works
differently, in plain words. Name spec fields and commands in backticks. Markdown is fine; no heading, no bullet.

```markdown
Inside flights take `light:` keys over the scroll (exposure, ambient, lamp, rim, lamp colour), eased between keys,
so the light can change as the page goes.
```

`feat`, `fix` and `perf` pull requests need a fragment; the check says so if one is missing. Docs, tests, CI and
refactors don't, and a maintainer can label anything else `skip-changelog`.
