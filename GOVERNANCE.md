# Governance

How Scroll Studio is run: who decides, how decisions are made, and how contributors take on more of the project.

## Roles

| Role | Who | Can |
|---|---|---|
| **User** | Anyone building sites with Scroll Studio | Ask questions, report bugs, propose features, share what they built |
| **Contributor** | Anyone with a merged pull request | Everything a user can, plus take issues and review others' pull requests (reviews help, but don't count toward merging) |
| **Triager** | Invited contributors | Label, deduplicate and close issues; ask for information; mark issues `good first issue` |
| **Area maintainer** | Invited for one area of the code ([MAINTAINERS.md](MAINTAINERS.md)) | Review and approve pull requests in their area; accept issues in it; their approval counts as a code-owner review |
| **Maintainer** | The project lead ([MAINTAINERS.md](MAINTAINERS.md)) | Everything: merge, release, accept core designs, change these rules |

Today the project has one maintainer, who holds every role. The rules below are written so that adding people later
needs no change to how things work, only names in [MAINTAINERS.md](MAINTAINERS.md) and
[CODEOWNERS](.github/CODEOWNERS).

## How decisions are made

- **Most decisions happen on issues and pull requests.** A proposal with no objection after a reasonable time (three
  working days for standard changes) is accepted by the triager or maintainer labelling it `status: accepted`.
- **Core changes need a written design** ([CONTRIBUTING.md](CONTRIBUTING.md#rules-per-area)): either a design section
  in the issue, or a proposal in [docs/rfcs/](docs/rfcs/) for anything large. The maintainer accepts it by labelling
  the issue `status: design-approved`.
- **Disagreements** are settled by the area maintainer, and, if still unresolved, by the maintainer, who explains the
  decision on the issue. "No" always comes with a reason.
- **The ground rules** in [CONTRIBUTING.md](CONTRIBUTING.md#ground-rules) (engine features, local models only, the spec
  as the source of truth, old sites keep building, nothing from one machine, accessible by default) are what make
  Scroll Studio what it is. Changing one needs an RFC and the maintainer's approval.
- **The roadmap** lives in the [milestones](https://github.com/Okohedeki/scroll-studio/milestones) and
  [docs/directions.md](docs/directions.md). Anyone can propose a change to it in Discussions.

## Becoming a triager or area maintainer

There is no application form. The maintainer invites people who have shown, over a few months:

- several merged pull requests or reviews in an area, done to the ground rules and consistency rules;
- good judgement and patience on issues, including saying no kindly;
- care for the project's users and contributors, in line with the [code of conduct](CODE_OF_CONDUCT.md).

An invitation names the area and the role, and is recorded in [MAINTAINERS.md](MAINTAINERS.md) and CODEOWNERS in a
pull request. Anyone can step down at any time by saying so; a maintainer who has been inactive for six months moves to
emeritus, with thanks, and can come back by asking.

## Licence, CLA and the hosted version

Scroll Studio is licensed under the AGPL-3.0 with additional terms ([LICENSE](LICENSE), [NOTICE.md](NOTICE.md)).
Contributors sign the [CLA](CLA.md), which lets the project also be offered in other forms, such as a hosted service run
by the maintainer. The open-source engine stays complete: features are not held back from it for the hosted version.

## Changing this document

Through a pull request with an RFC-style explanation, linked to an issue labelled `status: design-approved`, merged by
the maintainer.
