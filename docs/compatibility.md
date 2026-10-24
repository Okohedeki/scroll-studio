# Compatibility and deprecation

What you can rely on between Scroll Studio releases, and how things change when they have to.

## Versions

Scroll Studio follows [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`.

- **Patch** (1.4.1): fixes only. A site that built before builds the same page, except where the old page was wrong.
- **Minor** (1.5.0): new features. Everything that worked keeps working; deprecated things warn.
- **Major** (2.0.0): may remove what was deprecated. Each removal is listed in the migration guide.

## What the promise covers

| Surface | What stays the same within a major version |
|---|---|
| **The spec** (`site.yaml`, `engine/spec.py`) | Every valid spec stays valid and builds the same page: same sections, words, order and layout. New fields are optional, with defaults that keep today's result. |
| **The built page** (the runtime in `engine/compile/static/runtime/`) | A built site keeps working as a static folder with no server. Its scroll behaviour, timing and accessibility do not change without a spec field asking for it. |
| **The CLI** (`studio ...`) | Commands, options and exit codes keep working. Output meant for people (tables, progress) may change; anything documented as machine-readable (`--json`) does not. |
| **The MCP tools** | Tool names and their inputs keep working; new inputs are optional. |
| **The style contract** ([engine/styles/README.md](https://github.com/Okohedeki/scroll-studio/blob/main/engine/styles/README.md)) | A project style written to the contract keeps rendering. |
| **Theme presets and styles** | Keep their names and character. Colours may be adjusted to meet the contrast rules. |

Not covered: internal Python modules and functions (anything not reached through the spec, CLI or MCP), the cache
layout under `.build/`, the Studio app's internal API, and model choices (a better model may replace a worse one; the
spec field that selects it keeps working).

## How something changes

1. **Deprecate.** The old field, option or tool keeps working and warns, whenever a spec is validated or the command
   runs, naming the replacement and the version it will be removed in. The docs and the generated reference mark it
   deprecated.
2. **Wait.** At least one minor release with the warning; longer for anything common.
3. **Remove**, only in a major release, with an entry in the migration guide showing the exact rewrite of the spec.

A pull request that changes any surface above is labelled `breaking-change` and carries a migration note in its
changelog fragment, whether it deprecates something or (in a major release) removes it.

## How the promise is checked

- **Layout snapshots** of every example (`tests/test_layout_snapshots.py`): what each spec compiles to. A change shows
  up as a diff that is reviewed like code.
- **An old-spec corpus**: the examples from every release tag must still validate and compile.
- **Schema, CLI and MCP snapshots**: a change to the public surface shows up as a reviewed diff.
- **Conformance tests** for every theme preset and style.

## How to deprecate a field

Mark it where it is declared in `engine/spec.py`. Nothing else changes: it still validates and builds.

```python
from engine.spec import deprecated, deprecated_all

# a whole field
tagline: Optional[str] = Field(None, description="...", json_schema_extra=deprecated("2.0.0", "`description`"))

# one value of a field (several: wrap the marks in deprecated_all)
layout: Literal["flow", "stack", "pile"] = Field("flow", json_schema_extra=deprecated("2.0.0", "`stack`", value="pile"))
```

`deprecated(removed_in, replacement=None, note="")` takes the major version that removes it, what to write instead
(in backticks) and, if needed, a note. `engine.spec.deprecations(spec)` returns a `Deprecation` for every use in a
spec (its `path`, the `section` it is in, `removed_in`, `replacement` and a `text` sentence). `studio build` prints each
as a warning, the `set_spec` MCP tool and the Studio app's spec save return them as `deprecations`, and the generated
reference marks the field. The mark is in the JSON Schema (`deprecated: true`, `x-deprecated`), so the schema snapshot
changes: update it in the same pull request, with the migration note in the changelog fragment.
