# Build the docs

The docs are Markdown files in `docs/`, built into a site with [MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. Pull requests build the site, and every push to `main`
publishes it to GitHub Pages at <https://okohedeki.github.io/scroll-studio/>.

## Build it locally

```bash
pip install -e ".[docs]"                  # the engine plus MkDocs, pinned to exact versions
python -m engine.docsgen docs/reference   # the generated references (git-ignored)
mkdocs serve                              # http://127.0.0.1:8000, rebuilds when a page changes
```

`mkdocs build --strict` builds the site into `site/` and fails on any warning, as the pull request check does.

Run `python -m engine.docsgen docs/reference` again after changing `engine/spec.py`, `engine/cli.py` or
`engine/mcp_server.py`. It needs neither a GPU nor the `ml` extra.

## What is generated

| Page | Source | Written to |
| --- | --- | --- |
| [site.yaml reference](../reference/spec/index.md) | `engine/spec.py`: every model, field, type, default, allowed value and `description` | `docs/reference/spec/` |
| [Command line](../reference/cli.md) | the typer app in `engine/cli.py` | `docs/reference/cli.md` |
| [MCP tools](../reference/mcp.md) | the tools registered in `engine/mcp_server.py` | `docs/reference/mcp.md` |

These files are git-ignored: never edit or commit them. To change what they say, change the source. A field's text is
its `description` in `engine/spec.py`; a command's is its docstring and `help=`; a tool's is its docstring.

## The root files

`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CLA.md`, `AGENTS.md`, `CHANGELOG.md` and `NOTICE.md` live at
the repository root, where GitHub looks for them, and appear on the site as pages. `mkdocs_hooks.py` adds them while
the site is built and rewrites their links. Edit the file at the root; the edit button on its page opens it.

## Writing pages

- Add the page to `nav` in `mkdocs.yml`. The strict build fails on a page that is in no menu.
- Link to other pages and to files in the repository with relative paths, as you would on GitHub
  (`scenes.md#the-one-take-page-journey`, `../examples/fenmoor/site.yaml`). The build turns a link to a page into a
  site link and a link to any other file into the file on GitHub. A link to a file that does not exist fails the build.
- Put images in `docs/media/`.
- Plain, specific, British spelling. No machine paths: use `/path/to/...` placeholders. `tests/test_no_local_paths.py`
  checks every file.

To add a page another pull request introduces (`GOVERNANCE.md`, `MAINTAINERS.md`, `SUPPORT.md`, `docs/rfcs/`), add its
line to `nav` in `mkdocs.yml`. The root files are already mapped in `mkdocs_hooks.py` and are skipped until they exist.

## YAML snippets are tested

Every `yaml` code block in `docs/` and the README is checked against `engine/spec.py` by `tests/test_docs.py`, so an
example that stops being valid fails the tests. A block is checked as:

- **A whole site or a part of one:** a mapping whose keys are all `site.yaml` keys (`name`, `theme`, `sections`,
  `product`, `pages`, `trailer`, ...) is validated as a site. `name` and `sections` are filled in when the block leaves
  them out.
- **A list of sections:** a list whose items have a `type` is validated as sections.
- **A fragment:** any other mapping (`beats:`, `image:`, `steps:`) must validate as the fields of a model that has all
  of those fields.
- **Placeholders:** a value of `...` stands for more of the same and is not checked.

A block that is not meant to be valid, such as a design that is not built yet or pseudo-YAML, starts with the comment
`# docs: no-validate`, ideally with the reason after it.

## Links

The pull request check fails on a broken internal link or anchor. A weekly workflow checks external links with
[lychee](https://github.com/lycheeverse/lychee) and fails its own run when one is dead; it does not block pull requests.
