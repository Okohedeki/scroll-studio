# DesignAI · From landing pages to a generation engine

Status: design, phase 0 approved ([#172](https://github.com/Okohedeki/scroll-studio/issues/172)).

## Why

Scroll Studio turns a spec into a page by sending it through fixed scene builders, templates and styles. That keeps
builds reliable, but projects start to look alike, and every output has to be shaped like a page. Product photos, ads,
short videos and listing copy have nowhere to live in `site.yaml`.

Most of the hard work already exists. Image and video generation, editing, depth, 3D, relighting, brand capture and
the polish checks are all built, but today they feed only one output.

The engine becomes a **generator**. A brief goes in and many distinct candidates come out. Templates and styles remain,
but as optional constraints rather than the mould every project passes through. The project is renamed **DesignAI**,
because the page is no longer the product. The new name waits on a name check before the rename lands.

## Decisions

| Area | Decision |
| --- | --- |
| Engine | Generates designs instead of filling templates; variety is a goal |
| Models | Local-first. Hosted provider APIs and MCP servers are optional backends, never required |
| Spec root | A new `project.yaml`; the site becomes `outputs.site` |
| First new output | E-commerce product imagery: pack shots, lifestyle scenes, on-model and detail shots |
| Speed | Profile a full build before choosing what to speed up |
| Process | One `status: design-approved` issue per phase, each shipped as several pull requests |

## How a candidate is made

1. **Brief.** The project's brief, brand and product.
2. **Directions.** A text model writes several divergent art directions: medium, light, setting, composition and
   mood. This replaces fixed style presets, and the existing `directions` boards become its output.
3. **Candidates.** Each direction is sampled across models and seeds.
4. **Critics.** The existing checks score every candidate, not just the final build. A novelty check drops candidates
   that sit too close to each other, or to the project's earlier outputs.
5. **Shortlist.** A varied set to choose from. "More like this" and "something different" feed back into step 2.
6. **Final.** The chosen candidate is rendered at full quality and finished.

**What stays fixed:**

- **Brand.** Colours, fonts and logo come from the brand kit.
- **Product accuracy.** The real product is composited from a cutout or a 3D render, never redrawn from scratch. A
  critic compares each candidate's product against the reference.
- **Required copy.** Prices, claims and legal lines appear exactly as written in the spec.

**Reproducible.** Each candidate records its direction, backend, model, prompt, seed and inputs, so any one of them
can be re-run exactly. Variety comes from sampling; reproducibility comes from the record.

## Architecture

| Layer | What it is |
| --- | --- |
| Project | `project.yaml`: brief, brand kit, product and `outputs:` |
| Generation | Directions, candidates, critics and shortlist, as above |
| Asset graph | Each output expands into assets (one pack shot, one ad size, one shot), each with an id, versions, a lock and a record. The stage cache keys on inputs, so fan-outs reuse shared work |
| Builders and tools | One builder per output type. Edit tools (cutout, inpaint, resize, reframe, relight, composite, trim) are stages that any builder can call |
| Model router | Picks a backend per job by capability, cost and speed. Builders ask for a capability, never a provider |
| Interfaces | CLI, MCP server, the Studio app's board and an API, all working through the same project and graph |

```yaml
# docs: no-validate (planned for phase 0 and later, not built yet)
name: example-planter
brief: An autumn range of glazed ceramic planters; calm, warm, natural light
brand:
  colours: ["#2f3b2c", "#efe7da"]
product:
  name: Example Planter
  photos: [assets/planter-front.jpg, assets/planter-top.jpg]
outputs:
  stills:
    shots: [packshot, lifestyle, detail]
    candidates: 8
  site:
    sections: [...]     # today's Site model, unchanged
models:
  prefer: local
```

### Models and backends

| Route | Who uses it | Notes |
| --- | --- | --- |
| Local | Anyone with a GPU | ComfyUI, Hugging Face models and Blender, as today |
| Provider APIs | Anyone with a key | Image, video, voice and music providers, each enabled only when its key is set |
| MCP | Agents and provider tools | Provider MCP servers used as backends |

Builds with no keys keep working. Each backend declares its licence or terms in the same way `engine/models.yaml` does
today. Voice and music come from provider APIs, or from open models whose licences allow commercial use.

### Speed

1. **Profile first:** seconds per stage, per backend and per output on a full build (phase 0).
2. **Do less work:** reuse cached stages across outputs, and render sketch and draft tiers before the final one.
3. **Keep models warm and batch:** long-lived workers, with each candidate fan-out sent as one batched job.
4. **Fewer steps, lower precision:** distilled checkpoints for drafts, and quantized weights where quality holds.

## Previews: the board

The Studio app gets a board rather than a node canvas. It shows every asset in a project on one screen, each with its
versions. It grows out of `studio storyboard` and the stage cache, which already produce real first frames before a
full render.

1. **Show every asset**, grouped by output, at its real size and crop.
2. **Stream progress:** a card shows a stand-in first, then each stage as it lands.
3. **Compare** two or more versions side by side, with the `studio inspect` findings shown as badges.
4. **Redo one:** change a prompt, seed, crop or model on one card, and only that asset rebuilds.
5. **Lock and approve:** a locked card never rebuilds, and approvals are recorded in the project file.
6. **Write back:** every change lands in the project file as a diff, so agents and the board stay in step.

| Tier | Purpose | Uses |
| --- | --- | --- |
| Sketch | Layout and crop, in seconds | Stand-ins and existing first frames |
| Draft | Look and motion, in minutes | `studio build --draft`, with fewer steps and a lower resolution |
| Final | Ship quality | Full build, finishing stage and inspect |

A wired node canvas stays out of scope. If it comes later, it will be another view of the same asset graph.

## Phases

| Phase | Scope | Gate |
| --- | --- | --- |
| 0 · Foundations ([#172](https://github.com/Okohedeki/scroll-studio/issues/172)) | `project.yaml` root and compatibility loader, model router, build profile, rename | Every example builds the same way through both roots |
| 1 · Product imagery | Directions, candidates, critics and shortlist for stills | A product photo becomes a reviewed set of shots |
| 2 · The board | Previews, compare, redo, lock and write-back in the Studio app | Every asset can be reviewed and redone from one screen |
| 3 · More outputs | Short video with voiceover, ad sizes, generated page layouts, listing copy | Each output reuses the shared assets |
| Later | Other audiences and team features | Decided after phase 3 |

Each phase gets its own design-approved issue, and every pull request keeps every example building.

## Compatibility

- `site.yaml` keeps building. It loads as `outputs.site`, with a deprecation notice, and `designai migrate` converts it
  on request.
- The `studio` command and the MCP tool names stay as aliases for at least one release after the rename.
- The local-models-only ground rule becomes "local-first, hosted backends optional". The contributing guide and issue
  templates change in the same pull request as the router.
- LICENSE, NOTICE.md and AGENTS.md are untouched.

## Testing

- Loader and migrate round trips run on every example, and both must give an identical build.
- Router policy is tested with stand-in backends, including a fake hosted backend that runs without network access.
- Critics and novelty checks are tested on fixed images, without a GPU.
- Coverage floors stay where they are.

## Open questions

- [ ] Which provider backends are wired up first?
- [ ] How does the product-accuracy critic score a match, and what score fails a candidate?
- [ ] How many candidates per asset by default, balancing variety against build time?
