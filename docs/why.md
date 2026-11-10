# Why DesignAI

[← README](../README.md) · [Why DesignAI](why.md) · [What's new](whats-new.md) · [Examples](examples.md) · [Guide: make a site](guide.md) · [Styles](styles.md) · [Scenes](scenes.md) · [Licence](licence.md)


- **Local only. Nothing to pay per site.** Every image and video is generated on your own GPU with open models
  (Z-Image, Qwen-Image-Edit, LTX-2.3, SeedVR2). No API keys, no credits, no cloud account, no per-clip bill. Your
  brief, your brand and your footage never leave your machine, and a site costs the electricity to render it.
- **10 to 30 times fewer tokens.** When an AI agent builds the site, it writes a short spec, not the code. The
  engine already holds the markup, the stylesheets, the scroll physics and the players, so the agent only writes
  the words and the choices. An agent coding the same page by hand has to write and debug all of it, for every
  site and every revision.
- **An engine, not one effect.** Twenty-six styles and eleven scene types from the same spec. Switching a whole site
  from a pop-up book to a pinscreen is one word, not a rebuild.
- **Plain output.** Static HTML, CSS and JS that drops into any host or framework.

### Token savings, worked example: Halcyon as a zoetrope

[Halcyon](../examples/halcyon/site.yaml) with `theme: { style: zoetrope }` is a landing page that is one spinning wheel
of cards: 19 cards, each with its own animation, prize-wheel physics, cards that fly out to be read. What an agent
writes for it:

| | Tokens the agent writes |
|---|---:|
| **With DesignAI:** `site.yaml` (content, order, `style: zoetrope`) | **1,241** |
| **By hand,** the same page: | |
| &nbsp;&nbsp;Page markup and copy | 15,934 |
| &nbsp;&nbsp;Stylesheets | 16,821 |
| &nbsp;&nbsp;Wheel, physics, strobe, open and close | 15,321 |
| &nbsp;&nbsp;The 45 card animations | 29,882 |
| &nbsp;&nbsp;Scrolling, loader and art helpers | 6,574 |
| &nbsp;&nbsp;**Total** | **84,532** |

That is about **68 times fewer** for a full experience like this one, before counting the debugging rounds a
hand-built page needs. A simpler hand-built scroll page lands at 10 to 30 times. Every later change is a line in the
spec rather than a rewrite, and the agent reads the skill once per session (about 1,100 tokens). Counted with
tiktoken (`cl100k_base`) on the files in this repo; other tokenizers differ by roughly 10 to 20%.
