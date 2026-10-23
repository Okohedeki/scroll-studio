# Security policy

## Reporting a problem

Please do not report security problems in public issues or pull requests. Use GitHub's private reporting instead:
**[Report a vulnerability](https://github.com/Okohedeki/scroll-studio/security/advisories/new)**. Only the
maintainer sees the report.

Include what you found, how to reproduce it, and what an attacker could do with it. You will get a reply within a week,
and credit in the fix's release notes if you want it.

## What is in scope

- The engine and CLI (`engine/`), including the Studio app's local server (`studio ui`) and the MCP server.
- The browser runtime that ships inside every built site (`runtime/`, `engine/compile/static/runtime/`).
- Anything that lets a `site.yaml`, a downloaded model or input, or a built page run code or read files it should not.

## Supported versions

Fixes go into the latest release. Upgrade to it before reporting, if you can.
