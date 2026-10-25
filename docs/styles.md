# Styles

[← README](../README.md) · [Why Scroll Studio](why.md) · [What's new](whats-new.md) · [Examples](examples.md) · [Guide: make a site](guide.md) · [Styles](styles.md) · [Scenes](scenes.md) · [Licence](licence.md)


`theme: { style: <name> }` changes how a site is experienced: what scrolling does, how content is laid out and
arrives, how sections hand over, what the pointer does and what the call to action is. The same `site.yaml` reads
as a departures board, a comic, a terminal session, a game level or an anime opening. `theme.colors` and
`theme.fonts` still win, and `theme.from` puts a whole brand on any style: its palette and faces replace the style's
own while the experience stays ([themes and brands](guide.md#themes-and-brands)).

| Style | What scrolling is |
|---|---|
| `particles` | One swarm of points re-forming into each section's subject |
| `liquid-morph` | One body that morphs; nothing cuts, everything becomes |
| `holographic` | Rotating holographic plates; the information is in the angle |
| `neon-glow` | A night street where signs ignite as you arrive |
| `wireframe-3d` | Flying a camera through a world drawn in lines |
| `glassmorphism` | Windows over a living world moving behind them |
| `kinetic-type` | An instrument made of letters, played by scroll speed |
| `isometric` | A fixed-angle drone over a model world that builds itself |
| `clay-3d` | Soft toys on a table: mass, squash and wobble |
| `ascii-art` | A terminal session that types and prints |
| `gradient-mesh` | Weather: one breathing colour field that shifts with each chapter |
| `comic-book` | Reading a comic page panel by panel |
| `split-flap` | A departures board updating as the clock advances |
| `retro-vhs` | Operating a VCR: play, search, rewind |
| `halftone` | Reading a freshly printed newspaper |
| `bauhaus` | Composing a poster from shapes that persist and change role |
| `pixel-art` | Playing a side-scrolling game |
| `blueprint` | A technical drawing that drafts itself |
| `art-deco` | An opening night: doors, sunbursts, marquees |
| `neo-brutalism` | A desk you fill up and can mess with |
| `anime-intro` | Scrubbing the playhead of an anime opening, cut by cut |
| `flipbook` | Thumbing a pad of pencil drawings, one page per notch |
| `pop-up-book` | Opening a pop-up book: scenes fold up out of the gutter, tabs pull |
| `pinscreen` | A lamp-lit wall of pins; each picture rolls into the next in a wave |
| `sand` | A backlit sand table; a hand sweeps the grains into each scene |
| `zoetrope` | The page is one wheel of cards: spin it, land on one, open it to read |
| `stop-motion` | Scroll fires the shutter: felt and clay sets step on twos, dead still between exposures |
| `paper-cut-out` | Paper sheets swing off brass brads; hinged pieces sway, a jointed paper arm points |
| `scratch-film` | Scroll pulls a hand-scratched strip of film through the gate, frame by frame |
| `smears` | Spider-Verse timing: on twos, smear frames and multiples, impact frames between sheets |
| `paint-on-glass` | One living oil painting on lit glass, repainted stroke by stroke as you scroll; a finger smears it |
| `multiplane` | Painted glass plates at real depth; the camera trucks down through them with focus pulls |

```bash
studio looks examples/halcyon            # dist/looks/<style>/ for every style, plus a gallery at dist/looks/
studio looks my-site --styles split-flap,comic-book,anime-intro
```

### Art in the style's own medium

`theme.art` gives a style a picture to draw in its own medium. Describe it and it is generated locally (Z-Image); add
`motion:` and LTX-2.3 animates it into a seamless loop. `ascii-art` prints it in characters in the hero and plays it
in the render pane; `particles` fills the whole first screen with it as a field of points that drifts apart as you
scroll.

```yaml
theme:
  style: ascii-art
  art:
    prompt: "a basketball player dribbling on an empty court, side view, black background, strong rim light"
    motion: "he dribbles the ball low and steady, the camera stays still"
    label: "dribbling, frame by frame"
    seconds: 3          # 1-8 seconds of motion
    frames: 36          # frames kept for the loop
    width: 220          # detail of the sheet the runtime draws from
```

Use `file:` instead of `prompt:` to start from your own image. Plain, high-contrast subjects on a dark or light
background read best. Animation needs ComfyUI running (docs/INSTALL.md); a still needs only the image model.

A style is a folder (`engine/styles/<name>/`: tokens, stylesheet, its own block markup and page chrome) plus a
runtime module (`runtime/src/styles/<name>.ts`) with its scroll controller; the contract is in
[engine/styles/README.md](../engine/styles/README.md) and the research behind each one in [docs/styles](styles/).
