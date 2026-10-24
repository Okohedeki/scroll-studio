# Security policy

## Reporting a problem

Please do not report security problems in public issues, pull requests or discussions. Use GitHub's private
reporting instead: **[Report a vulnerability](https://github.com/Okohedeki/scroll-studio/security/advisories/new)**.
Only the maintainers see the report.

Include what you found, how to reproduce it (a spec, a request, a file), what an attacker could do with it, and the
version or commit you tested.

## What happens next

| When | What |
|---|---|
| Within 2 days | We confirm we have the report. |
| Within 7 days | We tell you whether we can reproduce it, how serious we think it is, and the plan to fix it. |
| Within 90 days | The fix is released, sooner for serious problems. If it needs longer, we agree a date with you. |
| On release | We publish a GitHub security advisory (with a CVE where it applies) and credit you, if you want credit. |

The project pays no bug bounties ([CONTRIBUTING.md](CONTRIBUTING.md#no-bounties)); reporters are credited in the
advisory.

Please give us the chance to release a fix before you talk about the problem in public. We will keep you updated
throughout and will not take legal action against good-faith research that follows this policy.

## What is in scope

- The engine and CLI (`engine/`), including the Studio app's local server (`studio ui`), the preview and editor
  servers, and the MCP server.
- The browser runtime that ships inside every built site (`runtime/`, `engine/compile/static/runtime/`).
- Anything that lets a `site.yaml`, a project input, a downloaded model, or a request to a local server run code,
  read or write files it should not, or attack visitors of a built site.
- The project's CI and release process (`.github/`).

What Scroll Studio trusts and why is described in the [threat model](docs/security/threat-model.md). Problems in
ComfyUI, Blender, browsers or model weights themselves should go to their own projects; tell us too if Scroll Studio
makes them worse.

## Supported versions

| Version | Security fixes |
|---|---|
| Latest minor release (1.4.x today) | Yes |
| Older releases | No; upgrade to the latest release |
| `main` | Fixed before release |

## For maintainers

1. Acknowledge the report, then reproduce it in a private fork created from the advisory ("Start a temporary private
   fork"). Never discuss details in public issues or pull requests.
2. Agree the severity (CVSS) with the reporter and request a CVE from the advisory if it applies.
3. Fix it in the private fork with a test, release a patch version, then publish the advisory crediting the reporter.
4. Note the fix under "Security" in the changelog, without exploit details.
