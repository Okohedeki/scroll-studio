"""The design vocabulary directions are written from: curated, combinable, no model needed.

A **school** is one coherent way to make a site look and move (an art movement, a printing process, a photographer's
light, a material, an era, a typographic school): it carries the concept lines, the palettes that suit it, the
typefaces that suit it, the imagery treatments (medium, light, lens, mood), which engine styles give it the right
*experience*, and how it moves. The writer (writer.py) picks schools that fit the brief and differ in kind, then
combines a school with a seed: which palette, which pairing, which look, which light, which style.

Everything is plain data so a designer can read it, argue with it and add to it. Add a school by appending to SCHOOLS;
tests check contrast, that every font is loadable and every style exists.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    mode: str          # light | dark
    bg: str
    bg2: str
    ink: str
    accent: str
    accent2: str
    accent_ink: str = ""    # text on an accent button (computed when empty)


@dataclass(frozen=True)
class Pairing:
    display: str
    body: str
    mono: str
    weight: int = 500           # display weight
    em: str = "accent"          # how <em> words are set: accent | bold | heavy
    italic_em: bool = False     # accent <em> in italic
    labels: str = "caps"        # caps | plain
    note: str = ""              # why they sit well together


@dataclass(frozen=True)
class Look:
    """An imagery treatment: how every generated image and film prompt is phrased."""
    medium: str
    lens: str
    mood: str
    palette: str                # the colour in words
    lights: tuple = ()          # keys of LIGHTS (a light is picked by seed); empty: `light` below
    light: str = ""
    family: str = ""            # the kind of picture it makes (for the diversity check)


@dataclass(frozen=True)
class School:
    key: str
    name: str
    kind: str                   # photo | cinema | illustration | typographic | dimensional | technical | craft | painterly | retro
    about: str                  # one line: what the school is
    moods: frozenset
    domains: dict               # domain -> 1..3 how well it suits the subject
    concepts: tuple             # templates with {name}
    palettes: tuple
    pairings: tuple
    looks: tuple
    styles: dict                # engine style (or "none": the default editorial layout) -> 1..3 fit
    motion: tuple               # (page, camera, type) notes
    voice: str                  # the tone of copy that suits it (never applied: copy is the owner's)
    pace: float = 1.0           # scroll.speed
    radius: str = ""
    board: str = "overlay"      # how the board sets a still: overlay | split | poster | plate | grid | terminal
    unit: str = "Plate"         # what a still is called under the plate layout: Plate, Spread, Layer, Sheet
    objects_only: bool = False  # its pictures are an object on a backdrop: it cannot hold a landscape or a room


def P(name, mode, bg, bg2, ink, accent, accent2, accent_ink=""):
    return Palette(name, mode, bg, bg2, ink, accent, accent2, accent_ink)


# --------------------------------------------------------------------------- photographers' light
LIGHTS = {
    "golden": "low golden-hour sun, long soft shadows, a warm rim on every edge",
    "blue-hour": "blue hour, cool ambient sky light against warm lit windows",
    "overcast": "flat overcast north light, no hard shadows, even and quiet",
    "window": "soft directional window light from the left, like a Vermeer interior",
    "rembrandt": "Rembrandt lighting, one soft key from the upper left, a triangle of light on the shadow side, deep falloff",
    "caravaggio": "chiaroscuro, a single hard source, tenebrist black shadows, glowing highlights",
    "hurrell": "butterfly light in the manner of George Hurrell, glossy high-contrast Hollywood glamour",
    "penn": "north-light studio, Irving Penn simplicity, delicate gradients on a plain ground",
    "noon": "hard noon sun, short black shadows, bleached highlights, high contrast",
    "softbox": "one large softbox, gentle wrapping shadows, clean highlights",
    "neon": "practical neon light, magenta and cyan spill, wet reflections on every surface",
    "candle": "candlelight, a warm flicker in a dark room, deep shadows",
    "dappled": "dappled light through leaves moving over the scene",
    "fog": "diffused fog light, low contrast, pearly and soft",
    "crewdson": "deep twilight with lit interiors, a staged cinematic glow in the manner of Gregory Crewdson",
    "sidelight": "raking side light across the texture, long gentle shadows",
}


SCHOOLS: tuple[School, ...] = (

    School(
        key="field-guide", name="Field Guide", kind="illustration",
        about="A naturalist's plate book: ink linework, watercolour wash, specimen labels, a numbered catalogue.",
        moods=frozenset({"calm", "intimate", "handmade", "scientific", "nostalgic", "quiet", "editorial"}),
        domains={"nature": 3, "science": 3, "hospitality": 2, "education": 2, "art": 2, "food": 1, "wellness": 1, "health": 1},
        concepts=("{name} as a field guide: every section a numbered plate, every claim a caption in a naturalist's hand.",
                  "{name} catalogued like a collection: specimens, Latin-flavoured labels, plates laid on cream paper."),
        palettes=(P("Herbarium", "light", "#f1ead8", "#e6dcc3", "#232a1e", "#4f6a2e", "#7d9654", "#f7f1df"),
                  P("Foxing", "light", "#efe5cf", "#e2d4b6", "#2b2218", "#8c3b22", "#b8683f", "#fbf3e2"),
                  P("Pressed Fern", "dark", "#10241f", "#17332c", "#e8eed9", "#c9b458", "#e3d58a", "#10241f")),
        pairings=(Pairing("Cormorant Garamond", "Karla", "Cutive Mono", 500, "accent", True, "plain", "an old-style serif for plate titles over a plain grotesque for captions"),
                  Pairing("EB Garamond", "Work Sans", "Courier Prime", 500, "accent", True, "plain", "Garamond's bookish colour, typewritten labels"),
                  Pairing("Libre Baskerville", "Hanken Grotesk", "DM Mono", 400, "accent", True, "caps", "a sturdy text serif with catalogue-number mono")),
        looks=(Look("antique botanical engraving, hand-coloured with watercolour wash, fine ink linework, on aged cream paper",
                    "orthographic specimen view, centred, generous margins, a numbered plate", "patient, scientific, quiet",
                    "moss green, foxed cream and iron-gall brown", light="even, flat archival light with no cast shadows", family="engraving"),
               Look("naturalist's pencil and watercolour field sketch on a notebook page, with handwritten margin notes",
                    "plan view, loosely framed, small studies around a main drawing", "curious, intimate, unhurried",
                    "sepia, sage and ochre", light="soft daylight falling on paper", family="engraving")),
        styles={"none": 3, "flipbook": 3, "pop-up-book": 1, "halftone": 1},
        motion=("Slow: sections arrive like plates laid down, a soft fade and a small settle, nothing flies in",
                "Camera on film: hold the specimen still, push in very slowly; no whip, no shake",
                "Type: labels draw in letter by letter like pen on paper; headlines never animate"),
        voice="Plain nouns, short declaratives, captions that name things exactly.", pace=0.85, radius="2px", board="plate"),

    School(
        key="swiss", name="Swiss Grid", kind="typographic",
        about="The International Typographic Style: a strict grid, one family, flat colour, facts doing the talking.",
        moods=frozenset({"precise", "minimal", "serious", "editorial", "technical", "bold", "quiet"}),
        domains={"tech": 3, "finance": 3, "architecture": 3, "events": 2, "education": 2, "media": 2, "science": 2, "retail": 1, "mobility": 1},
        concepts=("{name} on a strict grid: one typeface, one signal red, and the facts doing the talking.",
                  "{name} as a Swiss poster that keeps scrolling: flat fields, hard alignments, no ornament at all."),
        palettes=(P("Signal Red", "light", "#f4f2ee", "#e9e6e0", "#0e0e0e", "#e1251b", "#ff5a4d", "#ffffff"),
                  P("Ink & Cobalt", "light", "#f6f5f1", "#eae8e2", "#0b1020", "#1c3fd1", "#4c6cf0", "#ffffff"),
                  P("Night Grid", "dark", "#0c0c0d", "#151517", "#f2f2ee", "#ff4a1c", "#ff8a66", "#0c0c0d")),
        pairings=(Pairing("Inter Tight", "Inter", "JetBrains Mono", 700, "bold", False, "caps", "one neo-grotesque doing every job, in heavy and regular"),
                  Pairing("Archivo", "Archivo", "Space Mono", 800, "heavy", False, "caps", "a single wide grotesque; the mono is only for numbers"),
                  Pairing("Familjen Grotesk", "Instrument Sans", "DM Mono", 600, "bold", False, "caps", "two close grotesques with a small difference in width")),
        looks=(Look("black-and-white documentary photograph with a single flat red element, hard modernist composition",
                    "50mm, straight-on, strict geometry aligned to a grid", "precise, clear, unsentimental",
                    "black, white and one signal red", lights=("overcast", "noon"), family="mono-photo"),
               Look("flat vector poster in the International Typographic Style, geometric shapes on a strict grid, bold sans-serif forms",
                    "orthographic, centred, generous empty space", "exact, confident, quiet",
                    "off-white, black and one primary", light="flat, shadowless", family="flat-graphic")),
        styles={"none": 3, "bauhaus": 3, "kinetic-type": 2, "split-flap": 2, "neo-brutalism": 1},
        motion=("Page: hard cuts on the grid, 150 ms ease, content snaps into its column; nothing floats",
                "Camera on film: locked-off frames with a single straight push; cut, never dissolve",
                "Type: size and weight change, position never does; numbers tick up in place"),
        voice="Declarative, numbers first, no adjectives that cannot be checked.", pace=1.15, radius="0px", board="grid"),

    School(
        key="golden-hour", name="Golden Hour", kind="photo",
        about="Warm, unhurried magazine photography on film: honey light, soft grain, people-less rooms and horizons.",
        moods=frozenset({"warm", "calm", "luxurious", "intimate", "nostalgic", "editorial", "fresh"}),
        domains={"hospitality": 3, "food": 2, "wellness": 2, "fashion": 2, "nature": 2, "retail": 1, "architecture": 2, "luxury": 2},
        concepts=("{name} at the hour the light turns: warm, slow, shot like a magazine travel story.",
                  "{name} as a long weekend on film: honey light, soft grain, nothing to prove."),
        palettes=(P("Portra", "light", "#f6ecdf", "#eadbc7", "#2d1d12", "#c2612a", "#e08f55", "#fff6ea"),
                  P("Magic Hour", "dark", "#1a110c", "#251912", "#f8e9d6", "#f2a65a", "#ffd199", "#1a0f06"),
                  P("Saltwater", "light", "#eef1ec", "#e1e7e1", "#14231f", "#2f6f68", "#5a9b92", "#f1f6f3")),
        pairings=(Pairing("Instrument Serif", "Inter Tight", "DM Mono", 400, "accent", True, "plain", "a condensed editorial serif over a quiet sans, like a magazine standfirst"),
                  Pairing("Fraunces", "Figtree", "IBM Plex Mono", 400, "accent", True, "plain", "a warm soft serif with a friendly geometric text face"),
                  Pairing("Playfair Display", "Karla", "Courier Prime", 500, "accent", True, "plain", "high-contrast serif drama with an easy grotesque")),
        looks=(Look("35mm film photograph, Kodak Portra 400, fine grain, lifted blacks and honeyed highlights",
                    "35mm, eye level, shallow depth of field", "unhurried, sun-warmed, quietly luxurious",
                    "honey, terracotta and sea blue", lights=("golden", "blue-hour", "dappled"), family="film-photo"),
               Look("medium-format travel editorial photograph, Hasselblad, natural colour, soft contrast, clean detail",
                    "50mm, slightly elevated, deep focus, calm composition", "easy, spacious, sun-soaked",
                    "sand, lime-wash white and sky blue", lights=("golden", "fog", "window"), family="film-photo")),
        styles={"none": 3, "gradient-mesh": 2, "sand": 2, "glassmorphism": 1},
        motion=("Page: long 900 ms ease-out fades, text rises a few pixels and stays; scroll.speed lowered a notch",
                "Camera on film: slow dolly forward or a gentle drift sideways, never a cut inside a shot",
                "Type: italic accent words fade in a beat after the headline"),
        voice="Sensory, second person, one concrete detail per line (the figs, the light, the sound).", pace=0.85, radius="2px", board="overlay"),

    School(
        key="neon-noir", name="Neon Noir", kind="cinema",
        about="Night cinema: anamorphic flares, wet streets, signage light spilling on dark surfaces.",
        moods=frozenset({"dramatic", "cinematic", "futuristic", "bold", "raw", "loud"}),
        domains={"events": 3, "music": 3, "tech": 2, "media": 2, "games": 2, "mobility": 2, "fashion": 1, "food": 1, "space": 1},
        concepts=("{name} after midnight: a night street of signs that switch on as you reach them.",
                  "{name} as the opening of a neo-noir: rain, glass, one colour of light per scene."),
        palettes=(P("Rain Neon", "dark", "#07060d", "#100e1c", "#ece8ff", "#ff2d95", "#21e6ff", "#07060d"),
                  P("Tokyo Teal", "dark", "#04100f", "#0a1c1b", "#e4fffb", "#19f0c3", "#ff5d73", "#031311"),
                  P("Sodium", "dark", "#0d0a06", "#181109", "#fbe9c8", "#ffb02e", "#ff6a3d", "#1a0e00")),
        pairings=(Pairing("Syne", "Space Grotesk", "Space Mono", 700, "accent", False, "caps", "a wide, slightly odd display over a technical grotesque"),
                  Pairing("Unbounded", "Manrope", "JetBrains Mono", 500, "accent", False, "caps", "extended rounded capitals like tube lettering"),
                  Pairing("Big Shoulders Display", "Barlow", "Martian Mono", 800, "accent", False, "caps", "tall condensed signage capitals")),
        looks=(Look("cinematic still, anamorphic lens, 35mm film, heavy grain, rain-slicked streets and glass",
                    "anamorphic 40mm, low angle, deep focus with oval bokeh", "lonely, electric, after midnight",
                    "magenta, cyan and black", lights=("neon", "crewdson"), family="cine"),
               Look("night photograph with long-exposure light trails and glowing signage reflected in puddles",
                    "wide 24mm, street level, strong perspective lines", "restless, urban, humming",
                    "sodium orange, teal and black", lights=("neon", "blue-hour"), family="cine")),
        styles={"neon-glow": 3, "retro-vhs": 2, "holographic": 1, "glassmorphism": 1},
        motion=("Page: sections light up on arrival (a short flicker, then steady); the one behind you dims",
                "Camera on film: slow lateral tracking shots, lens flares crossing frame, hold on reflections",
                "Type: headlines stutter on once and stay lit; body text never glows"),
        voice="Short lines, present tense, night imagery; a joke every third sentence.", pace=1.0, radius="4px", board="overlay"),

    School(
        key="blueprint", name="Drafting Table", kind="technical",
        about="Engineering drawings: blueprint paper, dimension lines, exploded views, parts lists, a title block.",
        moods=frozenset({"technical", "precise", "serious", "scientific", "minimal", "futuristic"}),
        domains={"architecture": 3, "tech": 3, "science": 2, "mobility": 3, "space": 2, "finance": 1, "education": 1},
        concepts=("{name} drafted: every section a sheet, every claim a dimension line, the whole thing approved for build.",
                  "{name} as an engineering drawing set: exploded views, callouts and a bill of materials."),
        palettes=(P("Cyanotype", "dark", "#0f3563", "#0b2c54", "#e9f2ff", "#8fe3ff", "#ffb347", "#082244"),
                  P("Drafting Film", "light", "#f1f5f8", "#e3eaf0", "#11202e", "#0b63ce", "#e2552b", "#ffffff"),
                  P("Graphite", "dark", "#121417", "#1b1f24", "#dfe5ea", "#7cc4ff", "#b5e0ff", "#08141f")),
        pairings=(Pairing("IBM Plex Sans", "IBM Plex Sans", "IBM Plex Mono", 500, "accent", False, "caps", "one engineering family, sans for statements and mono for dimensions"),
                  Pairing("Space Grotesk", "Public Sans", "Azeret Mono", 500, "accent", False, "caps", "a technical grotesque with a clear text face"),
                  Pairing("Geologica", "Hanken Grotesk", "Martian Mono", 400, "accent", False, "caps", "a light precise display over a calm sans")),
        looks=(Look("technical blueprint drawing, white linework on prussian blue paper, dimension lines, callouts and a drafting grid",
                    "orthographic elevation and section views, annotated", "exact, methodical, unhurried",
                    "prussian blue, white and one orange mark", light="flat drawing, no light", family="diagram"),
               Look("exploded-view axonometric line drawing on drafting film, thin black technical pen, numbered parts",
                    "isometric, thirty degrees, every part labelled", "clear, analytical",
                    "black linework on pale film with one blue", light="flat drawing, no light", family="diagram")),
        styles={"blueprint": 3, "wireframe-3d": 3, "isometric": 2, "none": 1},
        motion=("Page: lines draw themselves at constant speed; the sheet number in the title block counts up",
                "Camera on film: orthographic slides and exploded-view pulls apart; nothing handheld",
                "Type: all-caps labels typed in, dimensions count to their values"),
        voice="Measured, numbered, exact units; every sentence could be a callout.", pace=1.0, radius="2px", board="terminal"),

    School(
        key="riso", name="Risograph Zine", kind="craft",
        about="Two-colour riso prints: spot inks, misregistration, coarse halftone, uncoated paper, a zine's energy.",
        moods=frozenset({"playful", "raw", "handmade", "bold", "loud", "fresh", "editorial"}),
        domains={"events": 3, "music": 3, "art": 3, "food": 2, "education": 2, "media": 2, "retail": 2, "fashion": 2},
        concepts=("{name} as a zine run on a risograph: two inks, a little misregistered, every section a spread.",
                  "{name} printed in fluorescent pink and blue on cheap paper, deliberately a bit rough."),
        palettes=(P("Fluoro Pink & Blue", "light", "#f7f0e3", "#efe5d0", "#1d1a3a", "#ff4d8d", "#2f6fff", "#1d1a3a"),
                  P("Sunprint", "light", "#fbf1d9", "#f4e4bb", "#1a1a2e", "#ff6b35", "#1b998b", "#1a1a2e"),
                  P("Forest & Flame", "light", "#f1efe4", "#e6e2d0", "#10261c", "#00a86b", "#ff7a2f", "#10261c")),
        pairings=(Pairing("Bricolage Grotesque", "DM Sans", "Space Mono", 800, "heavy", False, "caps", "a chunky, characterful grotesque with a plain text face"),
                  Pairing("Shrikhand", "Rubik", "Courier Prime", 400, "accent", False, "plain", "a fat italic display for shouting, a friendly sans below it"),
                  Pairing("Rubik", "Work Sans", "Space Mono", 800, "heavy", False, "caps", "soft-cornered and sturdy, like a rubber-stamped flyer")),
        looks=(Look("two-colour risograph print, misregistered layers, coarse halftone grain, flat spot inks on uncoated paper",
                    "bold flat composition, tightly cropped, big simple shapes", "playful, zine-like, a little rough",
                    "fluorescent pink, blue and cream", light="flat, printed, no light", family="print"),
               Look("screen-printed gig poster, three flat overprinting inks, visible paper texture, energetic shapes",
                    "frontal poster composition, bold cut-out silhouettes", "loud, hand-made, joyful",
                    "orange, teal and ink black on cream", light="flat, printed, no light", family="print")),
        styles={"halftone": 3, "neo-brutalism": 2, "comic-book": 2, "kinetic-type": 1},
        motion=("Page: layers slap down with a 2 px misregistration and settle; hover shifts an ink layer",
                "Camera on film: jump-cut at 12 fps, held frames, stepped like a flip of printed sheets",
                "Type: the headline prints in two passes, one ink then the other"),
        voice="Casual, a bit cheeky, first-person plural, lists and asides.", pace=1.1, radius="0px", board="poster"),

    School(
        key="gouache", name="Picture Book", kind="illustration",
        about="A storybook in gouache and pencil: flat warm shapes, visible brush, rounded forms, soft nostalgia.",
        moods=frozenset({"warm", "playful", "nostalgic", "handmade", "intimate", "fresh", "calm"}),
        domains={"kids": 3, "food": 3, "education": 2, "hospitality": 2, "nature": 2, "wellness": 2, "retail": 1, "health": 1},
        concepts=("{name} as a picture book: every section a spread, painted in gouache, with room to turn the page.",
                  "{name} told as a story in warm flat colour, the way a child's favourite book looks."),
        palettes=(P("Orchard", "light", "#f9efdc", "#f0e0c0", "#3a2418", "#d9542b", "#4a8c6f", "#fff7ea"),
                  P("Dusk Meadow", "dark", "#1e2430", "#272f3d", "#f6ead2", "#f2b84b", "#7fc5a3", "#1e2430"),
                  P("Seaside Pastel", "light", "#eaf3f1", "#dbeae6", "#1d3a4a", "#e8744f", "#3a8fa3", "#ffffff")),
        pairings=(Pairing("Young Serif", "Nunito", "DM Mono", 400, "accent", False, "plain", "a chunky friendly serif with a rounded sans"),
                  Pairing("Gloock", "Figtree", "Courier Prime", 400, "accent", False, "plain", "a soft-contrast serif with warm geometry"),
                  Pairing("Fraunces", "Quicksand", "DM Mono", 600, "accent", True, "plain", "a wonky soft serif and round text, easy to read aloud")),
        looks=(Look("gouache and coloured-pencil illustration on textured paper, flat shapes, visible brush strokes",
                    "storybook wide view, slightly raised horizon, simple depth", "tender, warm, a little nostalgic",
                    "ochre, tomato red and sea green", light="soft late-afternoon warmth painted as colour, no hard shadows", family="paint-illustration"),
               Look("mid-century children's picture-book illustration, lithograph texture, simple rounded shapes, scenery and objects",
                    "child's-eye view, layered foreground and background planes", "cosy, curious, gently funny",
                    "mustard, teal, coral and cream", light="gentle painted light, a soft glow from one window", family="paint-illustration")),
        styles={"pop-up-book": 3, "zoetrope": 2, "flipbook": 2, "none": 1},
        motion=("Page: sections open like spreads, a small fold and settle; pull-tabs and flaps for details",
                "Camera on film: gentle parallax between painted planes, no live-action camera shake",
                "Type: hand-set feel, headlines bounce once and stop"),
        voice="Warm and a little playful, short sentences you could read aloud.", pace=0.9, radius="14px", board="plate", unit="Spread"),

    School(
        key="clay", name="Soft Clay", kind="dimensional",
        about="A tabletop of clay and plasticine: soft rounded forms, fingerprints, candy colours, squishy physics.",
        moods=frozenset({"playful", "fresh", "warm", "bold", "loud", "intimate"}),
        domains={"kids": 3, "tech": 2, "wellness": 2, "food": 2, "education": 2, "retail": 2, "health": 2, "games": 2},
        concepts=("{name} sculpted from clay: soft, squishy, a little silly, impossible not to poke.",
                  "{name} as a tabletop of plasticine, lit by one softbox, every section a new little set."),
        palettes=(P("Marshmallow", "light", "#fdeff0", "#fadde3", "#3b2340", "#ff6f91", "#8f7bff", "#3b2340"),
                  P("Mint & Peach", "light", "#eefaf3", "#dcf1e5", "#1f3b33", "#ff8c6b", "#2fb58f", "#1f3b33"),
                  P("Sky Putty", "light", "#eaf4ff", "#d8e8fa", "#1b2a4a", "#ffb11a", "#4a7bff", "#1b2a4a")),
        pairings=(Pairing("Fredoka", "Nunito", "DM Mono", 600, "accent", False, "plain", "rounded and bouncy, made for soft shapes"),
                  Pairing("Outfit", "Quicksand", "DM Mono", 700, "accent", False, "plain", "clean geometric roundness"),
                  Pairing("Lexend", "Nunito", "JetBrains Mono", 700, "bold", False, "plain", "wide, friendly, very legible")),
        looks=(Look("soft 3D render of matte clay and plasticine, rounded chunky forms, fingerprints visible in the surface",
                    "macro tabletop, 50mm, shallow depth of field", "friendly, tactile, cheerful",
                    "pastel pink, mint and butter yellow", light="one large softbox, gentle shadows, clean ambient occlusion", family="render3d"),
               Look("stop-motion puppet set photographed on a miniature stage, felt and clay, tiny props",
                    "tabletop miniature, tilt-shift, slightly high angle", "whimsical, handmade, warm",
                    "sky blue, tangerine and cream", light="warm practical lamp on the set, soft glow", family="render3d")),
        styles={"clay-3d": 3, "liquid-morph": 3, "isometric": 1},
        motion=("Page: cards drop in and squash on landing, buttons push in under the finger, lots of overshoot",
                "Camera on film: slow turntable moves on a miniature set, stepped like stop-motion",
                "Type: letters wobble once on entry like jelly"),
        voice="Friendly, plain, lots of verbs; jokes allowed.", pace=0.95, radius="28px", board="poster"),

    School(
        key="noir", name="Silver Noir", kind="photo",
        about="Black-and-white studio and street photography: pushed grain, deep blacks, a single source of light.",
        moods=frozenset({"dramatic", "serious", "luxurious", "intimate", "quiet", "raw", "editorial"}),
        domains={"luxury": 3, "fashion": 3, "art": 2, "music": 2, "media": 2, "hospitality": 1, "architecture": 2, "events": 1},
        concepts=("{name} in black and white: one light, deep shadow, a face of the brand you remember.",
                  "{name} as a contact sheet from a long night shoot, grain and all."),
        palettes=(P("Silver Gelatin", "dark", "#0b0b0b", "#151515", "#eeeae2", "#d1332a", "#e8695f", "#0b0b0b"),
                  P("Chiaroscuro", "dark", "#100d0a", "#1a1510", "#f1e7d6", "#b8956a", "#d9bd94", "#100d0a"),
                  P("Paper Noir", "light", "#e9e6df", "#dcd8cf", "#101010", "#8f1d1d", "#b94545", "#f5f2ea")),
        pairings=(Pairing("Playfair Display", "Inter", "DM Mono", 500, "accent", True, "plain", "high-contrast Didone italics, like a magazine masthead"),
                  Pairing("Bodoni Moda", "Hanken Grotesk", "Space Mono", 500, "accent", True, "plain", "Bodoni's hairlines against a neutral grotesque"),
                  Pairing("Cormorant", "Albert Sans", "DM Mono", 500, "accent", True, "plain", "delicate display serif, plenty of air")),
        looks=(Look("black-and-white silver gelatin photograph, Tri-X pushed two stops, deep blacks, visible grain",
                    "85mm, low-key, compressed perspective", "dramatic, hushed, monumental",
                    "black, silver and ivory", lights=("rembrandt", "caravaggio", "hurrell"), family="mono-photo"),
               Look("high-contrast monochrome studio photograph in the manner of Irving Penn, a plain grey ground, delicate gradients",
                    "100mm, centred subject, large areas of empty tone", "still, exacting, elegant",
                    "monochrome with a trace of warm paper tone", lights=("penn", "window", "sidelight"), family="mono-photo")),
        styles={"pinscreen": 3, "none": 2, "particles": 2, "retro-vhs": 1},
        motion=("Page: slow cross-fades through black; one element at a time, long holds between",
                "Camera on film: motionless frames with a barely perceptible push; light is the movement",
                "Type: thin serif capitals fade up, letter-spaced wide"),
        voice="Spare, confident, withholding; one line where another brand would write a paragraph.", pace=0.8, radius="0px", board="overlay"),

    School(
        key="deco", name="Opening Night", kind="typographic",
        about="Art deco glamour: gold on black lacquer, symmetry, sunbursts, marquee bulbs, an invitation to attend.",
        moods=frozenset({"luxurious", "dramatic", "rich", "nostalgic", "bold", "editorial"}),
        domains={"luxury": 3, "hospitality": 3, "events": 3, "music": 2, "fashion": 2, "food": 2, "art": 1},
        concepts=("{name} as an opening night: gilded doors part on the centre line and the headline is lit by a spot.",
                  "{name} in black lacquer and gold leaf: symmetrical, ceremonial, a little theatrical."),
        palettes=(P("Gilded", "dark", "#0b0a08", "#14120e", "#efe3c3", "#cfa64a", "#ecd596", "#0b0a08"),
                  P("Emerald Lacquer", "dark", "#07201b", "#0d2c25", "#eadfc0", "#d6b25e", "#a8d5b8", "#07201b"),
                  P("Ivory & Jet", "light", "#f3ecdc", "#e8dfc9", "#14110d", "#a7812f", "#c9a95a", "#14110d")),
        pairings=(Pairing("Limelight", "Josefin Sans", "DM Mono", 400, "accent", False, "caps", "marquee capitals over a geometric deco sans"),
                  Pairing("Poiret One", "Josefin Sans", "Courier Prime", 400, "accent", False, "caps", "fine linear deco letters, very 1925"),
                  Pairing("Cinzel", "Lora", "DM Mono", 500, "accent", False, "caps", "Roman capitals with a bookish text face")),
        looks=(Look("art deco poster illustration, gold leaf on black lacquer, symmetrical geometric ornament, radiating sunburst rays",
                    "frontal, centred and symmetrical, tall proportions", "glamorous, ceremonial, opening night",
                    "black, gold and ivory", light="theatrical spotlight with a gold glow", family="deco-graphic"),
               Look("1920s grand-hotel lithograph, enamel-bright colours, stepped geometric borders and stylised architecture",
                    "elevation view, monumental, strict symmetry", "rich, confident, a little theatrical",
                    "emerald, brass and cream", light="even stage lighting, gilded highlights", family="deco-graphic")),
        styles={"art-deco": 3, "none": 1, "zoetrope": 1},
        motion=("Page: doors part on the centre axis; everything arrives mirrored, in pairs, then settles",
                "Camera on film: symmetrical one-point pushes through doors and lobbies",
                "Type: letter-spaced capitals illuminate bulb by bulb"),
        voice="Formal and flattering: invitations, 'you are expected', dress codes.", pace=0.9, radius="0px", board="poster"),

    School(
        key="collage", name="Cut Paper", kind="craft",
        about="Paper collage and pop-up craft: torn edges, layered sheets, shadow between layers, hand-cut shapes.",
        moods=frozenset({"handmade", "playful", "bold", "warm", "fresh", "raw"}),
        domains={"art": 3, "education": 3, "kids": 2, "food": 2, "events": 2, "nature": 2, "retail": 2, "wellness": 1},
        concepts=("{name} cut from paper: layers you can see the edges of, folded up one section at a time.",
                  "{name} as a collage made on a kitchen table: torn shapes, tape, and honest shadows."),
        palettes=(P("Construction Paper", "light", "#f3e6cf", "#e9d9bb", "#26201b", "#e0492f", "#2b6f8e", "#ffffff"),
                  P("Torn Teal", "light", "#ece8da", "#dfd9c4", "#10282a", "#0f7b78", "#f0a030", "#ffffff"),
                  P("Night Cut-Out", "dark", "#1b1626", "#251e33", "#f3e8d8", "#ff7a59", "#ffc857", "#1b1626")),
        pairings=(Pairing("DM Serif Display", "DM Sans", "DM Mono", 400, "accent", True, "plain", "a chunky serif with its own sans family"),
                  Pairing("Abril Fatface", "Work Sans", "Space Mono", 400, "accent", False, "caps", "a fat-face that looks cut out of a newspaper"),
                  Pairing("Gloock", "Karla", "Special Elite", 400, "accent", False, "plain", "a soft display with typewriter notes")),
        looks=(Look("layered cut-paper collage, hand-torn edges, visible paper fibre, soft shadows between the layers",
                    "flat top-down view, shallow depth between layers", "handmade, bold, lively",
                    "tomato red, teal, mustard and cream", light="soft overhead studio light, small crisp shadows", family="paper"),
               Look("mixed-media collage of painted paper shapes and halftone photo cut-outs, tape and staples",
                    "frontal, slightly askew, overlapping planes", "inventive, rough, joyful",
                    "mustard, ultramarine, coral and cream", light="even daylight on a table", family="paper")),
        styles={"pop-up-book": 3, "neo-brutalism": 1, "sand": 1, "none": 1},
        motion=("Page: sheets slide in on parallel folds and stay; shadows deepen as layers separate",
                "Camera on film: stepped moves at 8 fps, like a stop-motion table; no smooth glide",
                "Type: headline pieces snap in one word at a time, slightly rotated"),
        voice="Direct and warm, a craftsperson explaining how it is made.", pace=1.0, radius="6px", board="plate", unit="Layer"),

    School(
        key="travel-poster", name="Departure Poster", kind="illustration",
        about="Mid-century travel posters: four flat inks, a sun disc, bold diagonals, optimism about the next place.",
        moods=frozenset({"nostalgic", "bold", "fresh", "warm", "playful", "editorial", "rich"}),
        domains={"hospitality": 3, "mobility": 3, "events": 2, "food": 2, "nature": 2, "retail": 1, "media": 1},
        concepts=("{name} as a travel poster that keeps going: four flat inks, a sun disc, and somewhere to be.",
                  "{name} on the departures board and on the wall: screen-printed, optimistic, very 1958."),
        palettes=(P("Riviera", "light", "#f6e9cf", "#ecdcb9", "#17324d", "#e5533d", "#2a7f9e", "#ffffff"),
                  P("Desert Rail", "light", "#f0dcc0", "#e6cca6", "#3a1f12", "#c8452b", "#d99a2b", "#fff4e0"),
                  P("Night Ferry", "dark", "#0f2740", "#16334f", "#f7e8c8", "#f2a93b", "#e5533d", "#0f2740")),
        pairings=(Pairing("Abril Fatface", "Albert Sans", "DM Mono", 400, "accent", False, "caps", "a fat-face headline over a modern sans"),
                  Pairing("Bebas Neue", "Barlow", "Space Mono", 400, "accent", False, "caps", "tall poster capitals with a railway text face"),
                  Pairing("Rozha One", "Karla", "Courier Prime", 400, "accent", False, "plain", "a fat serif display with an easy text sans")),
        looks=(Look("mid-century travel poster, screenprint with four flat inks, bold simplified shapes, subtle grain",
                    "elevated vantage, strong diagonal composition, large sun disc", "optimistic, sunny, departure",
                    "vermilion, teal, sand and navy", light="flat colour planes with a sun disc, no shading", family="print-illustration"),
               Look("vintage railway and steamship poster lithograph, airbrushed gradients, crisp edges",
                    "dramatic perspective, low horizon, simple massed forms", "adventurous, glamorous, hopeful",
                    "cobalt, orange, cream and olive", light="airbrushed sky gradient, long clean shadows", family="print-illustration")),
        styles={"split-flap": 3, "none": 2, "bauhaus": 1, "isometric": 1},
        motion=("Page: the board updates row by row like a departures display; sections are destinations",
                "Camera on film: panoramic slow pans along a horizon; a poster-still hold at the end of each shot",
                "Type: flaps flip into place, uppercase only"),
        voice="Destination copy: places and times, 'now boarding', an invitation to go.", pace=1.0, radius="0px", board="poster"),

    School(
        key="dutch", name="Still Life", kind="painterly",
        about="Baroque oil painting: a dark ground, glazed colour, objects lit by one window, abundance and quiet.",
        moods=frozenset({"rich", "luxurious", "dramatic", "serious", "intimate", "nostalgic", "quiet"}),
        domains={"food": 3, "luxury": 3, "art": 3, "hospitality": 2, "wellness": 1, "fashion": 1, "education": 1},
        concepts=("{name} painted by candlelight: a dark table, a few perfect things, light from one window.",
                  "{name} as a Golden Age still life: slow, abundant, worth looking at twice."),
        palettes=(P("Umber", "dark", "#14100b", "#1d1812", "#eadcc2", "#b8472f", "#c9a34e", "#fff1d8"),
                  P("Oxblood Velvet", "dark", "#1a0a0c", "#25100f", "#f1e3d0", "#c4623a", "#d9a65a", "#1a0a0c"),
                  P("Pewter & Lemon", "dark", "#16181a", "#202427", "#e8e4d8", "#e5c442", "#f2dd85", "#16181a")),
        pairings=(Pairing("Cormorant Garamond", "EB Garamond", "Cutive Mono", 500, "accent", True, "plain", "one old-style world, display and text from the same century"),
                  Pairing("Playfair Display", "Crimson Pro", "DM Mono", 500, "accent", True, "plain", "dramatic contrast over a warm text serif"),
                  Pairing("Noto Serif Display", "Libre Baskerville", "Courier Prime", 400, "accent", True, "plain", "a refined display serif with Baskerville text")),
        looks=(Look("Dutch Golden Age oil painting, thick glazed paint, fine craquelure, a nearly black ground",
                    "still-life composition on a dark tabletop, painterly close view", "weighty, abundant, contemplative",
                    "umber, oxblood and tarnished gold", lights=("caravaggio", "window", "candle"), family="oil"),
               Look("baroque still life painting with a window glint on glass and silver, soft edges lost in shadow",
                    "slightly elevated, dense arrangement, shallow space", "quiet, opulent, patient",
                    "pewter, lemon yellow and deep green", lights=("window", "candle", "rembrandt"), family="oil")),
        styles={"none": 3, "sand": 1, "particles": 1, "art-deco": 1},
        motion=("Page: very slow fades from black; the headline arrives last, after the picture has settled",
                "Camera on film: a creeping push across a table; focus racks from foreground to the glint",
                "Type: italic serif fades up, no movement besides opacity"),
        voice="Unhurried, precise about materials and provenance.", pace=0.8, radius="2px", board="overlay"),

    School(
        key="y2k", name="Chrome Future", kind="dimensional",
        about="Y2K futurism: liquid chrome, translucent plastic, iridescent gradients, soft bloom, optimism about screens.",
        moods=frozenset({"futuristic", "playful", "bold", "fresh", "loud", "cinematic"}),
        domains={"tech": 3, "music": 2, "fashion": 2, "games": 2, "events": 2, "media": 2, "retail": 2, "space": 1},
        concepts=("{name} in liquid chrome and frosted plastic: the future as people imagined it in 2001.",
                  "{name} as a glossy 3D object that melts from one section into the next."),
        palettes=(P("Chrome Lilac", "light", "#eceaf8", "#dedcf2", "#15122e", "#7a4dff", "#00c2ff", "#ffffff"),
                  P("Aqua Pop", "dark", "#031b2e", "#082a45", "#dff6ff", "#4df0ff", "#b388ff", "#031b2e"),
                  P("Hot Plasma", "dark", "#0a0614", "#150d26", "#f6eaff", "#ff4fd8", "#6a5cff", "#0a0614")),
        pairings=(Pairing("Syne", "Sora", "JetBrains Mono", 700, "accent", False, "caps", "wide futurist display with a geometric text face"),
                  Pairing("Anybody", "Outfit", "Martian Mono", 800, "accent", False, "caps", "an extended expressive display with clean geometry"),
                  Pairing("Unbounded", "Albert Sans", "DM Mono", 600, "accent", False, "caps", "round extended capitals, glossy by shape alone")),
        looks=(Look("glossy 3D render, liquid chrome and iridescent gradients, Y2K futurism, soft bloom",
                    "wide 24mm, floating objects, a slight fisheye", "optimistic, digital, translucent",
                    "chrome, lilac and aqua", light="studio reflections with rainbow caustic highlights", family="render-gloss"),
               Look("frosted translucent plastic and glass materials on a gradient void, product-render polish",
                    "centred hero object, shallow depth of field, clean negative space", "smooth, weightless, a little dreamy",
                    "ice blue, pearl and magenta", light="large soft area lights with coloured rim light", family="render-gloss")),
        styles={"holographic": 3, "glassmorphism": 3, "liquid-morph": 2, "gradient-mesh": 1},
        motion=("Page: panels turn like foil in the light; the pointer is the light source",
                "Camera on film: orbit moves around a floating object, slow rotation, slight lens bloom",
                "Type: letters take on a sheen as they pass the pointer"),
        voice="Bright and confident, a little techno-utopian, short punchy nouns.", pace=1.0, radius="18px", board="overlay"),

    School(
        key="arcade", name="Arcade", kind="retro",
        about="16-bit games: pixel art, limited palettes, a title screen, levels, items and a course-clear card.",
        moods=frozenset({"playful", "nostalgic", "loud", "futuristic", "bold", "fresh"}),
        domains={"games": 3, "kids": 2, "tech": 2, "events": 2, "education": 1, "media": 1, "music": 1},
        concepts=("{name} as a side-scrolling game: PRESS START, every section a level, the call to action is COURSE CLEAR.",
                  "{name} in sixteen colours: pixels, items to collect, an NPC who knows the pricing."),
        palettes=(P("Pico", "dark", "#1d2b53", "#111a36", "#fff1e8", "#ffec27", "#00e436", "#1d2b53"),
                  P("Handheld", "dark", "#0f380f", "#0b2c0b", "#d6eaa0", "#f3ffc4", "#9bbc0f", "#0f380f"),
                  P("Sunset Console", "dark", "#2a1740", "#1d0f2f", "#fff2e0", "#ff7a59", "#35e0d0", "#2a1740")),
        pairings=(Pairing("Press Start 2P", "Pixelify Sans", "VT323", 400, "accent", False, "caps", "bitmap capitals for titles, a readable pixel text face"),
                  Pairing("Pixelify Sans", "Pixelify Sans", "Silkscreen", 600, "accent", False, "caps", "one pixel family at three sizes"),
                  Pairing("Silkscreen", "Space Grotesk", "VT323", 700, "accent", False, "caps", "tiny arcade capitals with a modern text face for long copy")),
        looks=(Look("16-bit pixel art scene, limited 32-colour palette, dithered shading, crisp square pixels",
                    "side-on game view, layered parallax backgrounds", "playful, nostalgic, quest-like",
                    "navy, yellow and green", light="pixel-shaded, bright sky, simple cast shadows", family="pixel"),
               Look("isometric pixel-art room diorama, clean palette, tiny charming details",
                    "isometric two-to-one pixel grid", "cosy, tidy, nostalgic",
                    "teal, orange and cream", light="soft pixel-gradient light from a window", family="pixel")),
        styles={"pixel-art": 3, "retro-vhs": 1},
        motion=("Page: scroll walks a sprite across the level in whole pixels; items pop out of blocks",
                "Camera on film: no film; use looping pixel animation between levels",
                "Type: letters print on in quantised steps with a blinking cursor"),
        voice="Game UI voice: ITEM GET, LEVEL UP, a wink at the player.", pace=1.0, radius="0px", board="terminal"),

    School(
        key="terminal", name="Phosphor", kind="technical",
        about="The terminal: green or amber phosphor, a prompt, command output printed line by line, a status bar.",
        moods=frozenset({"technical", "raw", "nostalgic", "quiet", "serious", "futuristic"}),
        domains={"tech": 3, "finance": 1, "games": 1, "education": 1, "media": 1, "science": 1},
        concepts=("{name} as a terminal session: every section a command, the answers printed back line by line.",
                  "{name} on an amber CRT at 2 a.m.: monospaced, patient, built by someone who reads man pages."),
        palettes=(P("Phosphor Green", "dark", "#040a05", "#09140b", "#7dff9a", "#c6ffa0", "#4fd16a", "#040a05"),
                  P("Amber CRT", "dark", "#0d0a04", "#140f06", "#ffb000", "#ffd27a", "#e8a33a", "#0d0a04"),
                  P("Paper Tape", "light", "#efece4", "#e4e0d4", "#1b1b1b", "#1f6f3a", "#2f8f55", "#efece4")),
        pairings=(Pairing("JetBrains Mono", "JetBrains Mono", "JetBrains Mono", 500, "accent", False, "plain", "one monospace everywhere, because the page is a terminal"),
                  Pairing("IBM Plex Mono", "IBM Plex Sans", "IBM Plex Mono", 500, "accent", False, "plain", "mono headlines, sans for long reading"),
                  Pairing("Martian Mono", "Space Mono", "Martian Mono", 600, "accent", False, "caps", "a wide mono display with a lighter mono body")),
        looks=(Look("image as shown on a green-phosphor CRT monitor in a dark room, scanlines, screen glow and bloom",
                    "close on the screen, slight curvature", "focused, nocturnal, patient",
                    "phosphor green on black", light="screen glow is the only light", family="crt"),
               Look("dark photograph lit only by a terminal window glow, cables and a desk lamp in the shadows",
                    "50mm, shallow depth of field, desk-level", "focused, workmanlike, late",
                    "amber, graphite and black", lights=("candle", "neon"), family="crt")),
        styles={"ascii-art": 3, "retro-vhs": 2, "wireframe-3d": 1},
        motion=("Page: each section types its command, then the reply prints line by line in quantised steps",
                "Camera on film: macro push-ins on glowing screens; scanline flicker only at cuts",
                "Type: a blinking block cursor; text never fades, it prints"),
        voice="Terse, command-line English; flags and man-page headings.", pace=1.0, radius="0px", board="terminal"),

    School(
        key="quiet-studio", name="Quiet Studio", kind="photo",
        objects_only=True,
        about="Clean product photography on seamless paper: plenty of space, soft shadow, one muted accent.",
        moods=frozenset({"minimal", "calm", "precise", "luxurious", "quiet", "fresh", "editorial"}),
        domains={"retail": 3, "tech": 3, "wellness": 3, "health": 3, "luxury": 2, "fashion": 2, "food": 1, "architecture": 1},
        concepts=("{name} on a seamless backdrop: a lot of white space, one soft shadow, nothing you do not need.",
                  "{name} as a quiet studio shoot: calm surfaces, honest materials, one idea per screen."),
        palettes=(P("Seamless", "light", "#f2f1ee", "#e8e6e1", "#181816", "#3d5a4c", "#6f8d7c", "#f2f1ee"),
                  P("Oat & Clay", "light", "#efe9df", "#e4dccf", "#2a2420", "#a65f3f", "#c98765", "#fff8ee"),
                  P("Studio Night", "dark", "#101111", "#181a1a", "#ecebe7", "#cfc3a4", "#e6dcc3", "#101111")),
        pairings=(Pairing("Inter Tight", "Inter", "DM Mono", 500, "accent", False, "plain", "neutral and exact; the product does the talking"),
                  Pairing("Instrument Sans", "Instrument Sans", "DM Mono", 500, "accent", False, "plain", "one understated family"),
                  Pairing("Schibsted Grotesk", "Hanken Grotesk", "Space Mono", 600, "bold", False, "plain", "a confident grotesque with a calm text companion")),
        looks=(Look("clean studio product photograph on a seamless paper backdrop, minimal composition, soft contact shadow",
                    "85mm, straight-on, generous negative space", "calm, precise, premium",
                    "oat, stone and one muted accent", lights=("softbox", "penn", "window"), family="studio-photo"),
               Look("still-life photograph of everyday objects on a pale plaster ledge, matte surfaces, restrained styling",
                    "50mm, slightly above, three objects at most", "quiet, considered, tactile",
                    "chalk, sage and warm grey", lights=("window", "softbox", "overcast"), family="studio-photo")),
        styles={"none": 3, "gradient-mesh": 3, "glassmorphism": 1, "particles": 1},
        motion=("Page: opacity-only reveals at 600 ms; sections never slide, they appear where they belong",
                "Camera on film: product turntables and slow macro drifts, always on a plain ground",
                "Type: no animation on headlines; numbers count up once"),
        voice="Calm, specific, no superlatives; what it is, what it does, what it costs.", pace=0.95, radius="10px", board="split"),

    School(
        key="documentary", name="Reportage", kind="photo",
        about="Documentary photography and newsprint: candid frames, available light, halftone, a newspaper's authority.",
        moods=frozenset({"raw", "serious", "intimate", "editorial", "bold", "quiet"}),
        domains={"media": 3, "education": 2, "events": 2, "finance": 1, "nature": 2, "wellness": 1, "hospitality": 1, "science": 1, "food": 1},
        concepts=("{name} as a photo essay: candid frames, plain captions, and the credit line under each one.",
                  "{name} printed on newsprint: halftone dots, a masthead, the lead story above the fold."),
        palettes=(P("Newsprint", "light", "#ece8de", "#e0dbce", "#121212", "#c8102e", "#e85468", "#ffffff"),
                  P("Tri-X", "dark", "#0e0e0e", "#171717", "#e8e8e8", "#f4c20d", "#f8dc6a", "#0e0e0e"),
                  P("Wire Service", "light", "#e5e7e8", "#d8dbdd", "#101820", "#0057b8", "#4b86d6", "#ffffff")),
        pairings=(Pairing("Newsreader", "Archivo", "Courier Prime", 500, "accent", True, "plain", "a newspaper serif with a stripped sans for datelines"),
                  Pairing("Libre Franklin", "Source Serif 4", "Space Mono", 700, "bold", False, "caps", "a gothic headline face over a reading serif"),
                  Pairing("Roboto Slab", "Work Sans", "DM Mono", 600, "accent", False, "caps", "slab headlines, wire-service plainness")),
        looks=(Look("documentary photograph on 35mm film, Tri-X or Portra, available light, candid, slightly imperfect framing",
                    "28mm, street level, in the moment, people at work in the distance", "honest, immediate, human",
                    "natural, muted, a little desaturated", light="available light, unposed", family="reportage"),
               Look("photojournalism in coarse newsprint halftone, black ink on cream stock, high contrast",
                    "35mm, tight crop on hands and objects", "factual, urgent, grounded",
                    "black on newsprint with one red", light="harsh available light, flat contrast", family="reportage")),
        styles={"halftone": 3, "none": 3, "split-flap": 1},
        motion=("Page: columns fill in reading order; pictures resolve from coarse dots to fine as they reach you",
                "Camera on film: handheld, observational, held shots of 4 to 6 seconds",
                "Type: bold headlines hold still; datelines type on"),
        voice="Inverted pyramid: the point first, then who, what, where, with quotes.", pace=1.0, radius="0px", board="grid"),

    School(
        key="wabi-sabi", name="Wabi-Sabi", kind="photo",
        about="Japanese stillness: handmade ceramics, raw linen, weathered wood, empty space and a thread of red.",
        moods=frozenset({"calm", "quiet", "minimal", "handmade", "intimate", "warm", "nostalgic"}),
        domains={"wellness": 3, "hospitality": 3, "food": 2, "health": 2, "art": 2, "nature": 2, "retail": 2, "luxury": 1, "architecture": 1},
        concepts=("{name} in a quiet room: raked sand, one good bowl, plenty of empty space to breathe.",
                  "{name} as a still life of imperfect things: handmade, weathered, and exactly enough."),
        palettes=(P("Raw Linen", "light", "#ebe6dc", "#e0dacd", "#2a2723", "#8a4b34", "#b27a5c", "#fbf5ea"),
                  P("Stone Garden", "light", "#d9d6cd", "#cdc9be", "#1f1e1b", "#b33a2a", "#cf6a58", "#fbf5ea"),
                  P("Ink Wash", "dark", "#121413", "#1b1e1d", "#e6e2d6", "#c9553b", "#e08d77", "#121413")),
        pairings=(Pairing("Shippori Mincho", "Karla", "DM Mono", 500, "accent", False, "plain", "a Japanese-influenced mincho with a quiet grotesque"),
                  Pairing("Cormorant", "Hanken Grotesk", "DM Mono", 400, "accent", True, "plain", "airy serif, wide spacing, light text"),
                  Pairing("Noto Serif Display", "Albert Sans", "DM Mono", 300, "accent", True, "plain", "a hairline serif display with a geometric sans")),
        looks=(Look("wabi-sabi photograph, matte textures in raw linen, weathered wood and unglazed clay, quiet and uneven",
                    "50mm, quiet asymmetric composition, lots of empty space", "still, humble, breathing",
                    "stone, bone and charcoal with a thread of vermilion", lights=("window", "overcast", "fog"), family="still-photo"),
               Look("quiet minimal photograph in the manner of Japanese architectural photography, matte and muted",
                    "35mm, low and level, a single horizontal line", "serene, spare, ancient",
                    "sand, cedar and moss grey", lights=("fog", "overcast", "dappled"), family="still-photo")),
        styles={"sand": 3, "none": 3, "pinscreen": 1, "particles": 1},
        motion=("Page: one gesture per scroll: sections are swept in like sand, then rest",
                "Camera on film: almost no movement; wind in a curtain, steam from a cup, long static holds",
                "Type: a few words per screen, set small and far apart"),
        voice="Few words, concrete things, no exclamation marks.", pace=0.8, radius="2px", board="split"),

    School(
        key="atlas", name="Old Atlas", kind="illustration",
        about="Cartography and exploration: hand-inked maps, hachures, muted tints, compass roses, a surveyor's patience.",
        moods=frozenset({"nostalgic", "scientific", "calm", "rich", "editorial", "handmade", "serious"}),
        domains={"mobility": 3, "nature": 3, "education": 2, "hospitality": 2, "science": 2, "finance": 1, "media": 1, "events": 1},
        concepts=("{name} surveyed and drawn: each section a map sheet, the route marked in red ink.",
                  "{name} as an old atlas: hachured hills, copperplate lettering, margins full of notes."),
        palettes=(P("Vellum", "light", "#efe6cf", "#e4d8bb", "#2a2a22", "#2f6f8f", "#b5432f", "#fbf5e4"),
                  P("Survey Green", "light", "#e8ecd9", "#dbe1c6", "#1c2a1a", "#3e7c3a", "#b5432f", "#f2f6e4"),
                  P("Nautical Chart", "dark", "#0b1f2e", "#12303f", "#e6efe9", "#e3b448", "#7fc4c7", "#0b1f2e")),
        pairings=(Pairing("Cormorant Garamond", "Libre Franklin", "Courier Prime", 500, "accent", True, "plain", "copperplate-ish display and a gothic for place names"),
                  Pairing("Lora", "Work Sans", "Courier Prime", 500, "accent", True, "plain", "a calm text serif that suits long captions"),
                  Pairing("Literata", "Karla", "DM Mono", 500, "accent", True, "plain", "a bookish serif with an easy sans")),
        looks=(Look("hand-inked antique map illustration, hachure shading, muted watercolour tints, copperplate lettering",
                    "bird's-eye cartographic view, compass rose, decorative border", "exploratory, patient, old-world",
                    "vellum, sea blue and iron red", light="flat, printed, no light", family="map-illustration"),
               Look("aerial survey photograph with fine contour lines drawn over it, topographic annotation, soft haze",
                    "high orthographic aerial view, a grid of coordinates", "measured, quiet, far-reaching",
                    "olive, sand and pale blue", lights=("fog", "overcast"), family="map-illustration")),
        styles={"isometric": 3, "none": 2, "blueprint": 1, "split-flap": 1},
        motion=("Page: the camera glides diagonally across one big map from district to district",
                "Camera on film: slow aerial drifts and a route drawing itself in red",
                "Type: place-name labels fade in as the view reaches them"),
        voice="Expedition-journal voice: dated entries, distances, what lies beyond.", pace=0.9, radius="2px", board="plate", unit="Sheet"),

    School(
        key="cel", name="Cel Animation", kind="illustration",
        about="Anime opening energy: painted skies, hard cuts on the beat, speed lines, title cards and freeze frames.",
        moods=frozenset({"bold", "dramatic", "playful", "loud", "cinematic", "fresh", "futuristic"}),
        domains={"games": 3, "events": 2, "music": 3, "media": 3, "kids": 1, "tech": 1, "fashion": 1},
        concepts=("{name} cut like an anime opening: hard cuts, a title card that smashes in, a freeze-frame for every feature.",
                  "{name} as the first episode: big skies, speed lines, and a NEXT EPISODE card as the call to action."),
        palettes=(P("Opening Titles", "dark", "#0a0a12", "#14141f", "#fff7ee", "#ff2b55", "#ffe600", "#ffffff"),
                  P("Summer Cel", "light", "#eaf6ff", "#d8ecfa", "#101a33", "#ff4b6e", "#1aa7ec", "#ffffff"),
                  P("Magic Hour Cel", "dark", "#1b1035", "#251648", "#fff2e0", "#ff8a3d", "#7be0ff", "#1b1035")),
        pairings=(Pairing("Dela Gothic One", "Rubik", "DM Mono", 400, "accent", False, "caps", "heavy display with a friendly sans"),
                  Pairing("Bebas Neue", "Barlow Condensed", "Space Mono", 400, "accent", False, "caps", "tall title-card capitals"),
                  Pairing("Anton", "Work Sans", "DM Mono", 400, "accent", False, "caps", "poster-thick capitals for cut cards")),
        looks=(Look("hand-painted 2D anime background art, cel-shaded, bold ink outlines, dramatic sky and rays of light",
                    "dramatic low angle, wide, a hint of speed lines", "epic, youthful, kinetic",
                    "saturated sky blue, crimson and gold", light="backlit clouds, long sun rays, lens flare", family="cel"),
               Look("flat-colour retro anime illustration, thick outlines, limited shading, big hard shadows, grain",
                    "cinematic wide with a tilted horizon", "adventurous, wistful, summery",
                    "teal, coral and cream", light="hard sun with flat cel shadows", family="cel")),
        styles={"anime-intro": 3, "comic-book": 2, "kinetic-type": 1},
        motion=("Page: hard cuts on the beat, freeze frames with a name card, one big smash-in title",
                "Camera on film: speed-line pushes and whip pans, hold on a held pose before the cut",
                "Type: slam in at 110% and settle to 100% in two frames"),
        voice="Big declarations, taglines, 'Episode 1'; every section ends on a hook.", pace=1.2, radius="0px", board="poster"),

    School(
        key="memphis", name="Pop Memphis", kind="typographic",
        about="Postmodern pop: terrazzo, squiggles, stripes, saturated primaries and joyful bad taste.",
        moods=frozenset({"loud", "playful", "bold", "fresh", "raw", "futuristic"}),
        domains={"events": 3, "music": 2, "retail": 3, "kids": 2, "fashion": 3, "food": 2, "education": 1, "media": 1},
        concepts=("{name} as a Memphis-Milano sideboard: terrazzo, squiggles and colours that argue happily.",
                  "{name} in pop primaries and stripes, a page that is clearly having fun."),
        palettes=(P("Pop Primary", "light", "#fff6e6", "#ffe9c2", "#111111", "#ff3d7f", "#1e6bff", "#ffffff"),
                  P("Terrazzo", "light", "#f7efe6", "#ecdfd0", "#17151f", "#00b3a4", "#ff7a3c", "#17151f"),
                  P("Sunny Day", "light", "#ffe45e", "#ffd83a", "#111111", "#ff4d4d", "#2457ff", "#ffffff")),
        pairings=(Pairing("Bungee", "Rubik", "Space Mono", 400, "accent", False, "caps", "signage capitals with a rounded text face"),
                  Pairing("Righteous", "Work Sans", "DM Mono", 400, "accent", False, "caps", "round retro-futurist display"),
                  Pairing("Rubik Mono One", "DM Sans", "Space Mono", 400, "accent", False, "caps", "monoline heavy capitals, built to be loud")),
        looks=(Look("Memphis-Milano pop collage, bold geometric patterns, squiggles and terrazzo, saturated flat colour, grainy print",
                    "frontal, playful cropping, objects floating on pattern", "loud, joyful, irreverent",
                    "pink, cobalt, yellow and black", light="flat, shadowless, with hard graphic drop shadows", family="print"),
               Look("studio photograph of objects on a terrazzo plinth against a hard-coloured backdrop, a slightly kitsch set",
                    "wide 28mm, objects arranged diagonally", "cheeky, saturated, sculptural",
                    "teal, tangerine and hot pink", lights=("softbox", "noon"), family="studio-photo")),
        styles={"neo-brutalism": 3, "kinetic-type": 2, "comic-book": 1, "clay-3d": 1},
        motion=("Page: things slap down with a spring and stay; stickers and cards can be grabbed and flung",
                "Camera on film: jump cuts, quick zooms, a rotating object on a patterned set",
                "Type: marquee bands race with scroll speed, headlines pop in huge"),
        voice="Loud and short, jokes in the headings, exclamation marks allowed.", pace=1.15, radius="10px", board="poster"),
)

SCHOOL = {s.key: s for s in SCHOOLS}


# --------------------------------------------------------------------------- styles: what each one is for the board
# cluster: styles in a cluster feel alike in use (the diversity check treats two of them as half as different);
# short: what the experience is in a few words (the engine's own about, trimmed, is shown on the board too).
STYLE_CLUSTER = {
    "none": "editorial", "gradient-mesh": "editorial", "glassmorphism": "glass", "holographic": "glass", "liquid-morph": "glass",
    "particles": "glass", "bauhaus": "print", "halftone": "print", "kinetic-type": "print", "neo-brutalism": "print",
    "comic-book": "print", "blueprint": "technical", "wireframe-3d": "technical", "isometric": "technical",
    "ascii-art": "technical", "pixel-art": "technical", "flipbook": "craft", "pop-up-book": "craft", "zoetrope": "craft",
    "sand": "craft", "pinscreen": "craft", "clay-3d": "soft3d", "neon-glow": "signage", "retro-vhs": "signage",
    "split-flap": "signage", "art-deco": "signage", "anime-intro": "signage",
}

# --------------------------------------------------------------------------- reading the brief
# domain -> words that put a site in it (lower case, matched on word starts)
DOMAIN_WORDS = {
    "hospitality": "hotel resort inn stay rooms suite villa lodge guest booking reserve retreat hostel airbnb getaway cliff coast beach ocean sea island",
    "tech": "software app platform api developer cloud saas data ai machine code startup product digital dashboard automation analytics tool engineer backend frontend server queue deploy repo repository database infrastructure devops framework library sdk cli terminal open-source",
    "science": "research lab laboratory biotech bio cell molecule dna genome institute scientific experiment study physics chemistry observatory",
    "art": "art gallery museum painting artist exhibition sculpture drawing studio atelier collection curator design illustration pottery ceramic ceramics clay kiln glaze craft maker workshop print printmaking",
    "luxury": "luxury bespoke handmade crafted jewel watch heritage atelier couture premium fine artisan commission walnut crystal",
    "food": "restaurant cafe coffee bakery bread kitchen chef menu wine cocktail bar food dining recipe farm roast tea teapot teas cups table drink",
    "wellness": "wellness spa yoga sleep mindful meditation calm skincare self-care massage fitness therapy rest",
    "health": "health clinic doctor patient care medical sleep therapy nurse hospital pharmacy treatment symptoms",
    "fashion": "fashion clothing collection runway wear apparel style garment boutique wardrobe",
    "events": "conference festival event summit expo tickets lineup speakers meetup weekend party launch",
    "finance": "bank finance invest fund payment fintech insurance accounting wealth lending crypto",
    "architecture": "architecture architect building construction interior house home design studio engineering renovation property",
    "space": "space rocket orbit satellite launch aerospace astronomy galaxy planet telescope mission",
    "kids": "kids children child family toy school learn playful parents baby",
    "nature": "nature forest garden outdoor mountain river wildlife plants botanical trail hiking sustainable environment climate",
    "music": "music band album tour concert record label festival dj studio song",
    "education": "school course learn lesson academy teach university student training workshop class",
    "retail": "shop store buy collection delivery brand goods marketplace order gifts",
    "mobility": "travel flight jet aviation airline car vehicle ship shipping freight logistics route rail cruise train transport port",
    "media": "magazine news journal podcast film video publication editorial story media press",
    "games": "game gaming play arcade esports console level quest",
}

# mood words (and their near neighbours) -> the canonical moods schools are tagged with
MOOD_WORDS = {
    "calm": "calm quiet gentle serene peaceful soft slow relaxed still restful",
    "quiet": "quiet hushed understated subtle restrained",
    "warm": "warm cosy cozy friendly welcoming homely sunny golden",
    "bold": "bold strong confident striking powerful brave",
    "loud": "loud vibrant energetic shouty maximalist exuberant colourful colorful",
    "playful": "playful fun cheeky quirky whimsical joyful lively",
    "technical": "technical engineered engineering precise analytical data-driven",
    "precise": "precise exact clean rigorous crisp structured",
    "raw": "raw gritty rough honest unpolished authentic",
    "nostalgic": "nostalgic retro vintage heritage classic old-world timeless",
    "futuristic": "futuristic modern digital cutting-edge next-gen sci-fi tomorrow",
    "handmade": "handmade crafted artisan hand-drawn analog tactile homemade",
    "luxurious": "luxurious luxury premium upscale elegant refined exclusive high-end sophisticated",
    "editorial": "editorial magazine journalistic publication",
    "minimal": "minimal minimalist simple spare uncluttered airy",
    "serious": "serious formal authoritative trustworthy credible institutional",
    "intimate": "intimate personal human close private",
    "cinematic": "cinematic dramatic filmic movie theatrical",
    "dramatic": "dramatic moody dark intense atmospheric",
    "scientific": "scientific rigorous research evidence academic",
    "fresh": "fresh bright light clean youthful new modern",
    "rich": "rich lush opulent abundant deep",
}

HUE_WORDS = {
    "red": (345, 15), "orange": (15, 45), "yellow": (45, 70), "green": (70, 165), "teal": (165, 195), "cyan": (165, 195),
    "blue": (195, 255), "purple": (255, 290), "violet": (255, 290), "pink": (290, 345), "magenta": (290, 345),
}

# the moods a subject usually wants when the owner has not said (counted at half weight next to the brief's own words)
DOMAIN_MOODS = {
    "hospitality": "warm calm luxurious intimate", "tech": "precise futuristic technical minimal",
    "science": "scientific precise calm", "art": "handmade editorial intimate bold", "luxury": "luxurious dramatic rich quiet",
    "food": "warm handmade rich fresh", "wellness": "calm quiet minimal warm", "health": "calm quiet fresh minimal",
    "fashion": "bold editorial luxurious dramatic", "events": "loud bold playful cinematic", "finance": "serious precise minimal",
    "architecture": "precise minimal quiet serious", "space": "futuristic cinematic dramatic", "kids": "playful warm fresh",
    "nature": "calm fresh warm", "music": "loud dramatic bold raw", "education": "playful fresh intimate",
    "retail": "fresh bold playful", "mobility": "bold nostalgic precise", "media": "editorial serious raw",
    "games": "playful loud futuristic nostalgic",
}
