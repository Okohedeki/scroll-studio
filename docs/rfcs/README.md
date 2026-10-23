# Design proposals (RFCs)

Large or core changes are designed in writing before they are built, so the people affected can weigh in and nobody
spends weeks on code that won't be merged.

## When you need one

You need an RFC for:

- a new scene type, a new top-level spec section, or a change to how layouts, themes or styles work;
- a change to what an existing spec builds (a `breaking-change`), or a deprecation;
- a change to the runtime's architecture, its loading or its public behaviour in built pages;
- a new kind of model or backend, or a new external tool the engine depends on;
- a change to the ground rules, the governance or the licence terms.

For a smaller core change (a new spec field on an existing scene, a runtime fix that changes behaviour), a **design
section in the issue** is enough: what changes in `site.yaml`, what the page does differently, how it is tested
without a GPU, and what happens to existing sites.

Not needed for bug fixes that restore documented behaviour, new styles that follow the style contract (they have their
own research brief), docs and tests.

## How it works

1. **Start a discussion** in [Discussions → Proposals](https://github.com/Okohedeki/scroll-studio/discussions) with
   the idea in a few paragraphs. This is the cheapest place to find out it won't fly.
2. **Write the RFC**: copy [0000-template.md](0000-template.md) to `docs/rfcs/0000-short-name.md` and open a pull
   request, linked to the issue for the work, labelled `type: rfc`. Keep the number `0000` until it is accepted.
3. **Discuss** on the pull request. The author updates the text as the design changes; the conversation stays on the
   pull request so the reasoning is kept.
4. **Decide.** The maintainer (or the area maintainer) accepts, asks for changes, or declines with a reason. Accepted
   RFCs get the next number and are merged; their issue is labelled `status: design-approved`. Declined RFCs are
   closed, not merged, and stay readable on the pull request.
5. **Build.** The implementation pull requests link the issue. If the design has to change along the way, update the
   RFC in the same pull request.

## Accepted RFCs

| # | Title | Status |
|---|---|---|
| — | [1.5: Make it yours](../design/1.5-make-it-yours.md) (written before this process; treated as accepted) | Accepted |
