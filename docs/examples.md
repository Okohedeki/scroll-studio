# Examples

[← README](../README.md) · [Why Scroll Studio](why.md) · [What's new](whats-new.md) · [Examples](examples.md) · [Guide: make a site](guide.md) · [Styles](styles.md) · [Scenes](scenes.md) · [Licence](licence.md)


**Live samples: https://okohedeki.github.io/scroll-studio-showcase/**

Make previews for any project with
`studio previews <project> ... --out <folder>` (a video and a poster each), or a single poster at a chosen
moment with `studio poster <project> --at <scene>:<progress> --out poster.jpg`. Previews stay out of git. To put several built sites online together (GitHub Pages or any static host):
`studio publish <project> ... --out <folder> --home showcase`.

The [showcase site](../examples/showcase/site.yaml) puts every example on one page with its preview.

Every example is a `site.yaml` in [`examples/`](../examples/) and rebuilds with `studio build examples/<name>`.

| Scene | Field | Example | What scrolling does |
|---|---|---|---|
| **One-take page** | `film` + `journey:` | [Fenmoor](../examples/fenmoor/site.yaml) | The whole page is one camera journey through a farmhouse; each section waits at its stop |
| **Cinemagraphs** | `cinemagraph:` | [Tern House](../examples/tern-house/site.yaml) | Stills where one thing moves: steam, a curtain, smoke, water |
| **Light as the scroll** | `light` | [Quay House](../examples/harbour-light/site.yaml) | One harbour from dawn to night; windows and lamps come on |
| **Inside the product** | `inside` | [Inside the mainboard](../examples/inside-board/site.yaml) | A macro flight into the Framework Laptop 12 mainboard's 3D model |
| **Miniature world** | `diorama` | [Harbourlight](../examples/little-harbour/site.yaml) | A tilt-shift harbour you orbit; it dives to each place |
| **Placing words** | `at`, `enter`, `exit` | [Margin](../examples/margin-notes/site.yaml) | A miniature desk; each caption sits in its own place (a grid slot, a corner, a box) and arrives its own way (wipe, type-on, scale) |
| **Film cuts** | `transition:` | [Halo Coffee](../examples/film-cuts/site.yaml) | A logo becomes the sun becomes a cup; iris, wipe, whip, carry |
| **Type in the world (film)** | `place:` | [Stillwater](../examples/type-in-the-world/site.yaml) | Headlines behind a spruce, painted on the deck, in the haze |
| **Type in the world (photos)** | `place:` + `parallax` | [Casa Alta](../examples/type-in-the-world-stills/site.yaml) | Headlines behind the house and the olive tree |
| **One medium, art-directed** | `imagery.medium` | [Kitewell](../examples/kitewell/site.yaml) | A fintech page in risograph: the hero in the brand's two inks, calm where the headline sits, illustrated product panels and feature cards, a toile band to close |
| **A light in your hand** | `imagery.medium` + `pointer: light` | [Gloamery](../examples/gloamery/site.yaml) | An AI painting tool in gouache: the studio is dark and the lamplight follows your pointer; dust turns in the light (`live:`) |
| **Colour under a lens** | two media + `pointer: lens` | [Tarnhollow](../examples/tarnhollow/site.yaml) | Walking holidays: one watercolour printed as an engraving, its colour showing through a lens that follows the pointer |
| **Halftone on a deep colour** | `imagery.paper: bg` + light `inks` | [Tidelow](../examples/tidelow/site.yaml) | A sleep speaker printed as a negative halftone on indigo: cream and coral dots, a sea that breathes (`live: flow`), a line of type that grows heavier |
| **Words in their slots** | `at: {grid}` + `code` | [Millrace](../examples/millrace/site.yaml) | A job queue in brush and ink: three captions take their own thirds of the grid over the mill race, then the change flies by as live code in a dark editor room |
| **Remake, then art-direct** | `studio remake` + `imagery.medium` | [Bramblecote](../examples/bramblecote/site.yaml) | An invented seed company's plain landing page (in `inputs/source/`) read by `studio remake`, its words and brand kept, then repainted in gouache |
| **Direction boards** | `studio directions` | [Kiln & Kettle](../examples/kiln-and-kettle/site.yaml) | Six art directions for one brief, side by side |
| **One take with a real product** | `film` + `take` | [Stillwater](../examples/one-take/site.yaml) | A mountain ridge down to a bottle on a lakeside table; the bottle is its real 3D model |
| **Story film** | `film` | [Lodestar Orbital](../examples/lodestar-orbital/site.yaml) | A rocket launch to orbit, generated locally |
| **Aerial film** | `film` | [Meridian](../examples/meridian/site.yaml) | A jet descends through cloud over London |
| **Story in shots** | `film` + `beats:` | [Feel](../examples/feel/site.yaml) | A door opens onto an oasis; every sentence its own shot |
| **Gaussian splat** | `splat` | [Hollis House](../examples/hollis-house/site.yaml) | A walk through a scanned house, room by room |
| **Product sequence** | `sequence` | [Fischer & Vale](../examples/fischer-vale/site.yaml) | A glass chess set lifts off its board (Blender) |
| **Artwork** | `artwork` | [Atelier Sfumato](../examples/atelier-sfumato/site.yaml) | The Mona Lisa drawn and painted in five lessons |
| **The pointer reveals** | `pointer:` + `parallax` | [Atelier Sfumato](../examples/atelier-sfumato/site.yaml) | A torch over the Mona Lisa; her colour through a lens on the grey |
| **Construction drawing** | `artwork` | [Hale & Rowe](../examples/hale-rowe/site.yaml) | A house drawn from construction lines to finished photo |
| **Live 3D** | `scene3d` | [Cellwright Bio](../examples/cellwright-bio/site.yaml) | From tissue to a molecule docking on DNA |
| **Cosmic zoom** | `scene3d` | [Northstar Observatory](../examples/northstar-observatory/site.yaml) | A fall from the whole galaxy to one living planet |
| **Map journey** | `map` | [Tidewater Lines](../examples/tidewater-lines/site.yaml) | Shanghai to Rotterdam, port by port |
| **Charts from the data** | `chart` | [Pelorus](../examples/pelorus/site.yaml) | Every figure read from Our World in Data at build time |
| **Data story** | `chart` | [Daybreak Institute](../examples/daybreak-institute/site.yaml) | Fifteen years of real solar data |
| **Vector line art** | `vector` | [Wunderkammer](../examples/wunderkammer/site.yaml) | Dürer's *Rhinoceros* re-cut line by line |
| **Kinetic type** | `type` | [FORM/26](../examples/form-conference/site.yaml) | A conference site told in moving type |
| **Photo parallax** | `parallax` | [Casa Alta](../examples/casa-alta/site.yaml) | A cliff hotel's photos given depth and a slow camera |
| **Landing page kit** | `badge`, `rating`, `signup`, `logos`, `frame` | [Larkspur](../examples/larkspur/site.yaml) | A framed hero on calm art with a badge link, icon buttons, a rating, figures and a logo strip; no GPU |
| **Stacked panels** | `stack` layout | [Hushwell](../examples/hushwell/site.yaml) | Full-screen panels slide over each other |
| **Thirty-two styles** | `theme.style` | [Halcyon](../examples/halcyon/site.yaml) | One product page as thirty-two experiences (`studio looks`) |

The examples show what each scene does; they are not templates. Every one rebuilds with your own photos, footage,
3D models, logo and copy, or from a brief.
