# Maintainers

Who looks after which part of Scroll Studio. Roles are described in [GOVERNANCE.md](GOVERNANCE.md); review rules per
area are in [CONTRIBUTING.md](CONTRIBUTING.md#rules-per-area) and enforced through [CODEOWNERS](.github/CODEOWNERS).

## Maintainer

- [@Okohedeki](https://github.com/Okohedeki): project lead; final say on core designs, merges and releases.

## Area maintainers

| Area | Paths | Maintainers |
|---|---|---|
| Runtime | `runtime/`, `engine/compile/static/runtime/` | @Okohedeki |
| Spec | `engine/spec.py` | @Okohedeki |
| Compiler and themes | `engine/compile/`, `engine/themes.yaml` | @Okohedeki |
| Styles | `engine/styles/`, `runtime/src/styles/`, `docs/styles/` | @Okohedeki |
| Scenes and builders | `engine/scenes/`, `engine/*.py` | @Okohedeki |
| Models and backends | `engine/backends/`, `engine/models.yaml` | @Okohedeki |
| CLI, MCP and the Studio app | `engine/cli.py`, `engine/mcp_server.py`, `engine/server/`, `ui/` | @Okohedeki |
| CI, security and releases | `.github/`, `SECURITY.md`, `pyproject.toml` | @Okohedeki |
| Docs | `docs/`, `*.md` | @Okohedeki |

## Triagers

None yet. See [GOVERNANCE.md](GOVERNANCE.md#becoming-a-triager-or-area-maintainer).

## Emeritus

None yet.
