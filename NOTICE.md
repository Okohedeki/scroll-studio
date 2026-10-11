# Scroll Studio: licence notice and additional terms

Copyright (C) 2026 Edeki Okoh (github.com/Okohedeki).

Scroll Studio is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General
Public License, version 3** (the "AGPL", in [LICENSE](LICENSE)), as published by the Free Software Foundation, together
with the additional terms below, which are permitted by section 7 of the AGPL. Scroll Studio is distributed WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the AGPL for
details.

In short: you may use, study, change and share Scroll Studio. If you distribute a modified version, or let people use
one over a network, you must release its complete source under the AGPL, keep the attribution notice below intact, and
not pass it off as the original or as your own work. Sites you *build* with Scroll Studio are yours (see the Output
Exception).

"Scroll Studio" or "the Program" means everything in this repository: the engine, the browser runtime, the Studio app,
templates, styles, prompts, examples and documentation. "The Findings" means the research and design analysis in this
repository, in particular `docs/styles/`, the style contract in `engine/styles/README.md`, and the market research and
design rationale in `docs/`.

## Additional terms (AGPL section 7)

### 1. Attribution must be preserved (section 7(b))

Every copy of the Program, every modified version, and every work based on the Program, in source or object form or
offered to users over a network, must keep this notice file and must preserve the following attribution notice
**exactly as written, without alteration**:

> Based on Scroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio (GNU AGPL-3.0)

The notice must appear:
- in the work's licence or notice file and its README (or equivalent top-level documentation);
- among the Appropriate Legal Notices of any interactive user interface, such as an About screen, a settings or
  credits page, the output of `--version` or `--help`, or the footer of a web app.

Any publication, product, documentation, dataset, course or service that uses or adapts **the Findings** must credit
them with this notice, exactly as written, where the Findings are used:

> Style research from Scroll Studio by Edeki Okoh: https://github.com/Okohedeki/scroll-studio

### 2. No misrepresentation (section 7(c))

- You may not misrepresent the origin of the Program or of the Findings, or claim either, in whole or in part, as your
  own original work.
- A modified version must be clearly marked as modified, in its notice file and wherever the attribution notice
  appears, with a statement of what was changed and when. It may not be presented as the original Scroll Studio.
- You may not remove, alter or obscure the attribution notices, this file, the licence headers, or the notice comment at
  the top of the browser runtime files.

### 3. Names (section 7(e))

The AGPL does not grant rights to use the name "Scroll Studio" (or a confusingly similar name or logo) as the name of a
modified version or of a product or service built from the Program. You may say truthfully that your work is "based on
Scroll Studio", as the attribution notice does.

### 4. Scroll Studio Output Exception (additional permission, section 7)

Websites and other output you generate by running Scroll Studio on your own specs and inputs, including the copy of
the browser runtime that the compiler places in that output (`dist/runtime/`, built from `runtime/`), are not
required to be licensed under the AGPL: you may license your sites however you like, as long as the notice comment at
the top of the runtime files is kept. This permission does not cover modified versions of the runtime or the engine,
or software that offers Scroll Studio's functionality to others (for example a site builder, a hosted service, a plugin
or an agent tool built from the Program); those remain under the AGPL and these terms.

## Using AI agents or models with this repository

The licence applies however a work is made. If you give this repository, or parts of it, to an AI agent, coding
assistant or model, as context, instructions, retrieval data or training data, and use what it produces, then to the
extent that output copies, translates, ports or adapts the Program's or the Findings' protected expression (code,
templates, prompts, styles, text, structure), it is a modified version or work based on the Program. It is covered by
the AGPL and these terms, including the attribution notice and the no-misrepresentation terms, exactly as if a person
had written it. "An AI rewrote it" is not an exception. [AGENTS.md](AGENTS.md) tells AI agents working with this
repository what this means for them.

This section explains how the AGPL and the terms above apply; it is not an extra restriction.

## Other licences

- Model weights that Scroll Studio downloads keep their own licences (see `engine/models.yaml`); some are
  non-commercial. Check them before commercial use.
- Third-party libraries in `node_modules` and Python packages keep their own licences.
- Example content (stock footage, data sets, photographs) keeps its own licence and credit, given in each example.

## Earlier versions

Versions of Scroll Studio published before this notice was added were released under the MIT licence. Those copies
remain available under MIT to whoever received them; this licence applies to this version and later ones.

## Commercial licence

If you want to use Scroll Studio under terms other than these (for example in a closed-source product), contact the
author through https://github.com/Okohedeki.
