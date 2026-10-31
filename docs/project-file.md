# The project file

A project can be written as `project.yaml` instead of `site.yaml`. The project file sets what every output shares
once, at the top, and puts each output under `outputs:`. A site is the first output; more follow
([design](https://github.com/Okohedeki/scroll-studio/issues/172)).

```yaml
# docs: no-validate (a project file, not a site.yaml)
name: Example Shop
description: Handmade ceramics.
brief: An autumn range of glazed planters.
brand: { preset: paper }          # a site's `theme`
imagery: { medium: photo }
outputs:
  site:
    sections:
      - type: intro
        title: Hello
```

| In `project.yaml` | In the site it builds |
| --- | --- |
| `name`, `description` | `name`, `description` |
| `brand` | `theme` |
| `product`, `imagery` | `product`, `imagery` |
| `outputs.site.*` | everything else |
| `brief` | (the project only) |

- **`site.yaml` keeps working.** A folder with only `site.yaml` builds as before. A folder with both uses
  `project.yaml`.
- **Convert one:** `studio migrate my-site` prints the change; `studio migrate my-site --write` writes `project.yaml`
  and keeps the old file as `site.yaml.bak`. The site it builds is checked to be the same first. Comments are not
  carried over.
- **One place per field.** A shared field may also sit inside `outputs.site` (as in a site.yaml); set in both places
  with different values, it is refused.
- **Editing tools** (the Studio app, the MCP tools, `studio copy`, `studio brand`, direction picks and the storyboard)
  edit a project file too. They lay the file out afresh, so comments in a `project.yaml` are not kept.
- **Schema:** `studio schema --project`.

## Models: which backend does each job

Every image, edit and text job goes through the model router. Local models come first; a provider is used only when
its key is set (see [install](INSTALL.md)). `studio models my-site` shows what can run and what each job would use.

```yaml
# docs: no-validate (a project file)
models:
  prefer: local            # or provider
  fallback: true           # when the preferred kind can't run here, use another that can
  use: { image: openai }   # pin a backend per job kind: image, edit, text
  model: { image: gpt-image-1 }
```

Each routed job is recorded in `.build/_router/records.jsonl` (backend, model, seed), so a result can be made again.
A provider's image is cached apart from the local model's, so switching back never reuses it.

## Where the time goes

`studio build my-site --profile` times every stage and backend, prints the slowest and writes
`.build/profile.json`. Measure before speeding anything up.
