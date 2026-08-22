import os
import re
import math
import json
import glob
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCENE_FILE  = "scene.x3d"
SAVES_DIR   = "saves"
os.makedirs(SAVES_DIR, exist_ok=True)

# Scene object registry (in-memory list mirroring what's in the file)
SCENE_OBJECTS = []

# ── Lighting state ─────────────────────────────────────────────────────────────
LIGHTING_STATE = {
    "ambient":    0.3,
    "intensity":  1.0,
    "sky":        (0.08, 0.08, 0.12),
    "lights":     [
        {"direction": "-1 -2 -1", "intensity": 1.0, "color": "1 1 1"},
        {"direction": "1 1 0.5",  "intensity": 0.5, "color": "0.8 0.8 1"},
    ],
}

def build_default_x3d():
    sky = LIGHTING_STATE["sky"]
    sky_str = f"{sky[0]:.2f} {sky[1]:.2f} {sky[2]:.2f}"
    lights_xml = ""
    for l in LIGHTING_STATE["lights"]:
        lights_xml += f'    <DirectionalLight direction="{l["direction"]}" intensity="{l["intensity"]:.2f}" color="{l["color"]}"/>\n'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "http://www.web3d.org/specifications/x3d-3.3.dtd">
<X3D profile="Immersive" version="3.3">
  <Scene>
    <Background skyColor="{sky_str}"/>
    <NavigationInfo type="EXAMINE ANY"/>
    <DirectionalLight direction="-1 -2 -1" intensity="1.0"/>
    <DirectionalLight direction="1 1 0.5" intensity="0.5" color="0.8 0.8 1"/>
  </Scene>
</X3D>
'''

DEFAULT_X3D = build_default_x3d()

# ── Colors ─────────────────────────────────────────────────────────────────────
COLORS = {
    "red":        (1.00, 0.00, 0.00),
    "green":      (0.00, 0.80, 0.00),
    "blue":       (0.00, 0.40, 1.00),
    "yellow":     (1.00, 1.00, 0.00),
    "orange":     (1.00, 0.50, 0.00),
    "purple":     (0.50, 0.00, 0.80),
    "pink":       (1.00, 0.40, 0.70),
    "magenta":    (1.00, 0.00, 1.00),
    "cyan":       (0.00, 1.00, 1.00),
    "teal":       (0.00, 0.50, 0.50),
    "white":      (1.00, 1.00, 1.00),
    "black":      (0.05, 0.05, 0.05),
    "gray":       (0.50, 0.50, 0.50),
    "grey":       (0.50, 0.50, 0.50),
    "brown":      (0.50, 0.25, 0.10),
    "gold":       (1.00, 0.84, 0.00),
    "silver":     (0.75, 0.75, 0.75),
    "lime":       (0.20, 1.00, 0.00),
    "indigo":     (0.29, 0.00, 0.51),
    "turquoise":  (0.25, 0.88, 0.82),
    "crimson":    (0.86, 0.08, 0.24),
    "coral":      (1.00, 0.50, 0.31),
    "salmon":     (0.98, 0.50, 0.45),
    "navy":       (0.00, 0.00, 0.50),
    "maroon":     (0.50, 0.00, 0.00),
    "olive":      (0.50, 0.50, 0.00),
    "tan":        (0.82, 0.71, 0.55),
    "beige":      (0.96, 0.96, 0.86),
    "ivory":      (1.00, 1.00, 0.94),
    "ruby":       (0.88, 0.07, 0.37),
    "emerald":    (0.31, 0.78, 0.47),
    "sapphire":   (0.06, 0.32, 0.73),
    "amber":      (1.00, 0.75, 0.00),
    "bronze":     (0.80, 0.50, 0.20),
    "copper":     (0.72, 0.45, 0.20),
    "neon":       (0.22, 1.00, 0.08),
    "electric":   (0.00, 0.60, 1.00),
    "hot":        (1.00, 0.07, 0.57),
    "dark":       (0.15, 0.15, 0.15),
    "light":      (0.85, 0.85, 0.85),
    "lavender":   (0.71, 0.49, 0.86),
    "mint":       (0.60, 1.00, 0.80),
    "peach":      (1.00, 0.80, 0.64),
    "rose":       (1.00, 0.30, 0.50),
    "lilac":      (0.78, 0.64, 0.78),
    "chartreuse": (0.50, 1.00, 0.00),
    "aqua":       (0.00, 1.00, 1.00),
    "sand":       (0.76, 0.70, 0.50),
    "rust":       (0.72, 0.25, 0.05),
    "scarlet":    (1.00, 0.14, 0.00),
    "violet":     (0.56, 0.00, 1.00),
    "plum":       (0.56, 0.27, 0.52),
    "slate":      (0.44, 0.50, 0.56),
    "cream":      (1.00, 0.99, 0.82),
    "jade":       (0.00, 0.66, 0.42),
    "cobalt":     (0.00, 0.28, 0.67),
    "magma":      (0.90, 0.20, 0.00),
    "ice":        (0.80, 0.95, 1.00),
    "lemon":      (1.00, 0.97, 0.00),
    "wine":       (0.45, 0.00, 0.13),
    "transparent":(0.50, 0.50, 0.50),
}

TWO_WORD_COLORS = {
    ("hot",     "pink"):    (1.00, 0.07, 0.57),
    ("dark",    "red"):     (0.55, 0.00, 0.00),
    ("dark",    "blue"):    (0.00, 0.00, 0.55),
    ("dark",    "green"):   (0.00, 0.39, 0.00),
    ("dark",    "purple"):  (0.25, 0.00, 0.40),
    ("dark",    "gray"):    (0.20, 0.20, 0.20),
    ("light",   "blue"):    (0.53, 0.81, 0.98),
    ("light",   "green"):   (0.56, 0.93, 0.56),
    ("light",   "pink"):    (1.00, 0.71, 0.76),
    ("light",   "gray"):    (0.83, 0.83, 0.83),
    ("neon",    "green"):   (0.22, 1.00, 0.08),
    ("neon",    "pink"):    (1.00, 0.08, 0.58),
    ("neon",    "yellow"):  (1.00, 1.00, 0.00),
    ("neon",    "orange"):  (1.00, 0.45, 0.00),
    ("neon",    "blue"):    (0.10, 0.40, 1.00),
    ("electric","blue"):    (0.00, 0.60, 1.00),
    ("electric","green"):   (0.00, 1.00, 0.20),
    ("deep",    "purple"):  (0.29, 0.00, 0.51),
    ("deep",    "blue"):    (0.00, 0.00, 0.70),
    ("deep",    "red"):     (0.60, 0.00, 0.00),
    ("bright",  "orange"):  (1.00, 0.65, 0.00),
    ("bright",  "yellow"):  (1.00, 1.00, 0.20),
    ("bright",  "green"):   (0.00, 1.00, 0.20),
    ("sky",     "blue"):    (0.53, 0.81, 0.98),
    ("forest",  "green"):   (0.13, 0.55, 0.13),
    ("lime",    "green"):   (0.20, 1.00, 0.00),
    ("baby",    "blue"):    (0.54, 0.81, 0.94),
    ("baby",    "pink"):    (1.00, 0.85, 0.88),
    ("ocean",   "blue"):    (0.00, 0.47, 0.75),
    ("fire",    "red"):     (1.00, 0.15, 0.00),
    ("fire",    "orange"):  (1.00, 0.40, 0.00),
    ("ice",     "blue"):    (0.80, 0.95, 1.00),
    ("rose",    "gold"):    (0.91, 0.67, 0.62),
    ("blood",   "red"):     (0.65, 0.00, 0.00),
    ("mint",    "green"):   (0.60, 1.00, 0.80),
    ("sand",    "brown"):   (0.76, 0.70, 0.50),
    ("pale",    "blue"):    (0.69, 0.87, 0.90),
    ("pale",    "pink"):    (0.98, 0.85, 0.87),
}

# ── Sizes ──────────────────────────────────────────────────────────────────────
SIZES = {
    "microscopic": 0.1, "atomic": 0.1, "invisible": 0.05,
    "tiny": 0.25, "mini": 0.3, "miniature": 0.3, "petite": 0.35,
    "small": 0.5, "little": 0.5, "compact": 0.5, "slim": 0.5,
    "medium": 0.8, "normal": 0.8, "average": 0.8, "standard": 0.8,
    "big": 1.3, "large": 1.5, "tall": 1.5, "wide": 1.5, "thick": 1.3,
    "huge": 2.0, "giant": 2.5, "enormous": 3.0, "massive": 3.5,
    "colossal": 4.0, "titanic": 4.5, "immense": 3.0, "grand": 2.0, "towering": 2.5,
}

# ── Named positions ────────────────────────────────────────────────────────────
POSITIONS = {
    "far left":    (-6.0,  0.0,  0.0), "far right":   ( 6.0,  0.0,  0.0),
    "far above":   ( 0.0,  6.0,  0.0), "far below":   ( 0.0, -6.0,  0.0),
    "far behind":  ( 0.0,  0.0, -6.0), "far front":   ( 0.0,  0.0,  6.0),
    "top left":    (-3.0,  3.0,  0.0), "top right":   ( 3.0,  3.0,  0.0),
    "bottom left": (-3.0, -3.0,  0.0), "bottom right":( 3.0, -3.0,  0.0),
    "upper left":  (-3.0,  3.0,  0.0), "upper right": ( 3.0,  3.0,  0.0),
    "lower left":  (-3.0, -3.0,  0.0), "lower right": ( 3.0, -3.0,  0.0),
    "on top":      ( 0.0,  3.5,  0.0), "up high":     ( 0.0,  5.0,  0.0),
    "way up":      ( 0.0,  6.0,  0.0), "way down":    ( 0.0, -6.0,  0.0),
    "in front":    ( 0.0,  0.0,  4.0), "in back":     ( 0.0,  0.0, -4.0),
    "underground": ( 0.0, -4.0,  0.0), "floating":    ( 0.0,  4.0,  0.0),
    "overhead":    ( 0.0,  5.0,  0.0),
    "left":    (-3.0,  0.0,  0.0), "right":   ( 3.0,  0.0,  0.0),
    "above":   ( 0.0,  3.0,  0.0), "up":      ( 0.0,  3.0,  0.0),
    "high":    ( 0.0,  4.0,  0.0), "below":   ( 0.0, -3.0,  0.0),
    "down":    ( 0.0, -3.0,  0.0), "beneath": ( 0.0, -3.0,  0.0),
    "under":   ( 0.0, -3.0,  0.0), "behind":  ( 0.0,  0.0, -3.0),
    "back":    ( 0.0,  0.0, -3.0), "front":   ( 0.0,  0.0,  3.0),
    "forward": ( 0.0,  0.0,  3.0), "near":    ( 0.0,  0.0,  3.0),
    "center":  ( 0.0,  0.0,  0.0), "middle":  ( 0.0,  0.0,  0.0),
    "here":    ( 0.0,  0.0,  0.0), "origin":  ( 0.0,  0.0,  0.0),
}

# ── Shape aliases ──────────────────────────────────────────────────────────────
SHAPE_ALIASES = {
    # sphere
    "sphere": "sphere", "ball": "sphere", "orb": "sphere", "globe": "sphere",
    "bubble": "sphere", "marble": "sphere", "bead": "sphere", "planet": "sphere", "moon": "sphere",
    # cone
    "cone": "cone", "pyramid": "cone", "triangle": "cone", "hat": "cone",
    "spike": "cone", "tip": "cone", "funnel": "cone", "mountain": "cone",
    # cylinder
    "cylinder": "cylinder", "tube": "cylinder", "pipe": "cylinder", "pillar": "cylinder",
    "column": "cylinder", "barrel": "cylinder", "rod": "cylinder", "pole": "cylinder",
    "straw": "cylinder", "can": "cylinder", "drum": "cylinder",
    # box
    "box": "box", "cube": "box", "block": "box", "brick": "box",
    "square": "box", "rectangle": "box", "crate": "box", "chest": "box",
    "slab": "box", "tile": "box",
    # torus
    "torus": "torus", "donut": "torus", "doughnut": "torus", "ring": "torus",
    "loop": "torus", "hoop": "torus", "wreath": "torus", "bracelet": "torus",
    "life preserver": "torus",
    # tetrahedron
    "tetrahedron": "tetrahedron", "diamond": "tetrahedron", "gem": "tetrahedron",
    "crystal": "tetrahedron", "prism": "tetrahedron",
    # octahedron
    "octahedron": "octahedron", "d8": "octahedron", "double pyramid": "octahedron",
    "bipyramid": "octahedron",
    # icosahedron
    "icosahedron": "icosahedron", "d20": "icosahedron", "geodesic": "icosahedron",
    "soccer": "icosahedron",
    # star
    "star": "star", "asterisk": "star", "burst": "star", "sparkle": "star", "starburst": "star",
    # arrow
    "arrow": "arrow", "pointer": "arrow", "chevron": "arrow",
    # plane
    "plane": "plane", "flat": "plane", "floor": "plane", "ground": "plane",
    "disc": "plane", "disk": "plane", "pad": "plane", "platform": "plane",
    "sheet": "plane", "surface": "plane",
    # ellipsoid
    "ellipsoid": "ellipsoid", "egg": "ellipsoid", "oval": "ellipsoid",
    "blob": "ellipsoid", "oblong": "ellipsoid",
    # helix
    "helix": "helix", "spiral": "helix", "coil": "helix", "spring": "helix", "screw": "helix",
    # NEW: capsule (true hemispherical caps)
    "capsule": "capsule", "pill": "capsule", "lozenge": "capsule",
    # NEW: dodecahedron
    "dodecahedron": "dodecahedron", "d12": "dodecahedron",
    # NEW: cross
    "cross": "cross", "plus": "cross", "crucifix": "cross", "crosshair": "cross",
    # NEW: crescent
    "crescent": "crescent", "moon crescent": "crescent",
    # NEW: torus knot
    "torus knot": "torusknot", "knot": "torusknot", "pretzel": "torusknot",
}

ADD_VERBS = (
    "add", "put", "place", "create", "make", "drop", "spawn",
    "throw", "insert", "include", "generate", "draw", "build",
    "give me", "show me", "i want", "i need", "gimme",
)

CLEAR_PHRASES = (
    "clear", "reset", "remove all", "delete all", "wipe", "empty",
    "start over", "start fresh", "start from scratch", "scratch this",
    "clean slate", "erase", "nuke", "blow it up", "destroy",
    "fresh start", "new scene",
)

REMOVE_PHRASES = (
    "remove", "delete", "undo", "take away", "get rid of",
    "pop", "erase last", "remove last", "delete last",
)

INSPECT_PHRASES = (
    "what's in", "what is in", "list", "show objects", "what do i have",
    "objects", "inspect", "describe scene", "what's here", "inventory",
    "count", "how many",
)

# ── Archive examples (curated from web3d.org) ─────────────────────────────────
ARCHIVE_EXAMPLES = {
    "hello":       "https://www.web3d.org/x3d/content/examples/HelloWorld.x3d",
    "helloworld":  "https://www.web3d.org/x3d/content/examples/HelloWorld.x3d",
    "ball":        "https://www.web3d.org/x3d/content/examples/Basic/UniversalMediaMaterials/UniversalMediaMaterials.x3d",
    "materials":   "https://www.web3d.org/x3d/content/examples/Basic/UniversalMediaMaterials/UniversalMediaMaterials.x3d",
    "lights":      "https://www.web3d.org/x3d/content/examples/Basic/LightSources/DirectionalLightExample.x3d",
    "fog":         "https://www.web3d.org/x3d/content/examples/Basic/EnvironmentalEffects/Fog.x3d",
    "text":        "https://www.web3d.org/x3d/content/examples/Basic/Text/HelloWorldCommented.x3d",
}

# ── Lighting command keywords ──────────────────────────────────────────────────
LIGHT_BRIGHT_PHRASES  = ("brighter", "more light", "increase light", "brighten", "lighter", "turn up light")
LIGHT_DIM_PHRASES     = ("dimmer", "less light", "decrease light", "dim", "darker", "turn down light", "darken")
LIGHT_NIGHT_PHRASES   = ("night", "nighttime", "night mode", "dark mode", "moonlight")
LIGHT_DAY_PHRASES     = ("day", "daytime", "daylight", "sun", "sunny", "noon")
LIGHT_SUNRISE_PHRASES = ("sunrise", "dawn", "golden hour", "warm light", "sunset")
LIGHT_NEON_PHRASES    = ("neon", "neon light", "club", "disco", "rave", "blacklight")
LIGHT_SPOT_PHRASES    = ("spotlight", "spot light", "add light", "add spotlight", "add a light")

# ── Camera command keywords ────────────────────────────────────────────────────
CAM_RESET_PHRASES   = ("reset camera", "reset view", "default view", "reset viewport")
CAM_TOP_PHRASES     = ("top view", "bird's eye", "birds eye", "look down", "view from top", "overhead view")
CAM_FRONT_PHRASES   = ("front view", "look from front", "face on", "straight on")
CAM_SIDE_PHRASES    = ("side view", "look from side", "profile view")
CAM_ISO_PHRASES     = ("isometric", "iso view", "3/4 view", "three quarter")

# ── Animation command keywords ─────────────────────────────────────────────────
ANIM_SPIN_PHRASES   = ("spin", "rotate", "spinning", "rotating", "make it spin", "make it rotate", "animate")
ANIM_BOUNCE_PHRASES = ("bounce", "bouncing", "bob", "bobbing", "oscillate", "float up and down")
ANIM_PULSE_PHRASES  = ("pulse", "pulsing", "breathe", "breathing", "throb", "grow and shrink")
ANIM_STOP_PHRASES   = ("stop", "freeze", "stop animation", "stop spinning", "stop bouncing", "no animation")


def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_X3D)


ensure_scene_file()


class PromptRequest(BaseModel):
    prompt: str

class SaveRequest(BaseModel):
    name: str


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_color(t: str):
    two_word = re.search(
        r'(hot|dark|light|neon|electric|deep|bright|pale|sky|forest|lime|baby|ocean|fire|ice|rose|blood|mint|sand)\s+'
        r'(red|green|blue|pink|orange|purple|yellow|cyan|gray|grey|brown|white|black|gold)', t)
    if two_word:
        key = (two_word.group(1), two_word.group(2))
        return TWO_WORD_COLORS.get(key, COLORS.get(two_word.group(2), (0.4, 0.6, 1.0)))

    hex_match = re.search(r'#([0-9a-f]{6}|[0-9a-f]{3})\b', t)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        return (int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)

    rgb_match = re.search(r'(?:rgb|color)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', t)
    if rgb_match:
        vals = [float(rgb_match.group(i)) for i in range(1, 4)]
        if max(vals) > 1.0:
            vals = [v/255 for v in vals]
        return tuple(vals)

    for name, rgb in COLORS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', t):
            return rgb
    return (0.4, 0.6, 1.0)


def parse_size(t: str):
    num_match = re.search(r'(?:size|radius|scale|width|height|length)\s+([\d.]+)', t)
    if num_match:
        return min(float(num_match.group(1)), 5.0)
    for word, s in SIZES.items():
        if re.search(r'\b' + re.escape(word) + r'\b', t):
            return s
    return 0.8


def parse_position(t: str):
    coord = re.search(
        r'(?:at|position|pos|translate|move to|place at|put at)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', t)
    if coord:
        return (float(coord.group(1)), float(coord.group(2)), float(coord.group(3)))
    for phrase, pos in sorted(POSITIONS.items(), key=lambda x: -len(x[0])):
        if phrase in t:
            return pos
    return (0.0, 0.0, 0.0)


def parse_rotation(t: str):
    axis_rot = re.search(r'rotat\w*\s+([-\d.]+)\s*(?:degrees?|deg)?\s*(?:around|along|on)?\s*(x|y|z)?', t)
    if axis_rot:
        deg = float(axis_rot.group(1))
        rad = deg * math.pi / 180
        axis = axis_rot.group(2) or "y"
        ax = (1, 0, 0) if axis == "x" else (0, 0, 1) if axis == "z" else (0, 1, 0)
        return (*ax, rad)
    if re.search(r'\b(tilt|tilted|lean|leaning|sideways|on its side|on its back)\b', t):
        return (0, 0, 1, math.pi / 2)
    if re.search(r'\b(upside down|inverted|flipped)\b', t):
        return (0, 0, 1, math.pi)
    if re.search(r'\b(diagonal|angled|slanted)\b', t):
        return (0, 0, 1, math.pi / 4)
    return None


def parse_count(t: str):
    """Parse a count like 'add 5 red spheres'."""
    m = re.search(r'\b(\d+)\b', t)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 20:
            return n
    words = {"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
    for w, n in words.items():
        if re.search(r'\b' + w + r'\b', t):
            return n
    return 1


def parse_arrangement(t: str):
    """Return arrangement type if found: row, circle, grid, random."""
    if re.search(r'\b(in a row|row|line|lined up|horizontal)\b', t):
        return "row"
    if re.search(r'\b(in a circle|circle|ring|circular|around)\b', t):
        return "circle"
    if re.search(r'\b(grid|matrix|formation)\b', t):
        return "grid"
    if re.search(r'\b(random|scattered|spread|everywhere)\b', t):
        return "random"
    return "row"  # default for multi


def parse_animation(t: str):
    if any(p in t for p in ANIM_STOP_PHRASES):
        return "stop"
    if any(p in t for p in ANIM_SPIN_PHRASES):
        return "spin"
    if any(p in t for p in ANIM_BOUNCE_PHRASES):
        return "bounce"
    if any(p in t for p in ANIM_PULSE_PHRASES):
        return "pulse"
    return None


def parse_prompt(text: str) -> dict:
    t = text.lower().strip()

    # ── Clear ─────────────────────────────────────────────────────────────────
    if any(w in t for w in CLEAR_PHRASES):
        return {"action": "clear", "message": "Scene cleared."}

    # ── Remove last ───────────────────────────────────────────────────────────
    if any(w in t for w in REMOVE_PHRASES):
        return {"action": "remove_last"}

    # ── Inspect ───────────────────────────────────────────────────────────────
    if any(w in t for w in INSPECT_PHRASES):
        return {"action": "inspect"}

    # ── Archive load ──────────────────────────────────────────────────────────
    archive_match = re.search(r'\b(load|fetch|import|open|get)\b.*\b(' + '|'.join(ARCHIVE_EXAMPLES.keys()) + r')\b', t)
    if archive_match:
        key = archive_match.group(2)
        return {"action": "load_archive", "key": key}

    # ── Camera ────────────────────────────────────────────────────────────────
    if any(p in t for p in CAM_RESET_PHRASES):
        return {"action": "camera", "view": "reset"}
    if any(p in t for p in CAM_TOP_PHRASES):
        return {"action": "camera", "view": "top"}
    if any(p in t for p in CAM_FRONT_PHRASES):
        return {"action": "camera", "view": "front"}
    if any(p in t for p in CAM_SIDE_PHRASES):
        return {"action": "camera", "view": "side"}
    if any(p in t for p in CAM_ISO_PHRASES):
        return {"action": "camera", "view": "iso"}

    # ── Lighting ──────────────────────────────────────────────────────────────
    if any(p in t for p in LIGHT_SPOT_PHRASES):
        return {"action": "add_light", "light_type": "spot"}
    if any(p in t for p in LIGHT_NIGHT_PHRASES):
        return {"action": "lighting", "preset": "night"}
    if any(p in t for p in LIGHT_DAY_PHRASES):
        return {"action": "lighting", "preset": "day"}
    if any(p in t for p in LIGHT_SUNRISE_PHRASES):
        return {"action": "lighting", "preset": "sunrise"}
    if any(p in t for p in LIGHT_NEON_PHRASES):
        return {"action": "lighting", "preset": "neon"}
    if any(p in t for p in LIGHT_BRIGHT_PHRASES):
        return {"action": "lighting", "preset": "brighter"}
    if any(p in t for p in LIGHT_DIM_PHRASES):
        return {"action": "lighting", "preset": "dimmer"}

    # ── Animation on last object ──────────────────────────────────────────────
    anim = parse_animation(t)
    if anim and not any(re.search(r'\b' + re.escape(a) + r'\b', t) for a in SHAPE_ALIASES):
        return {"action": "animate", "anim": anim}

    # ── Determine shape ───────────────────────────────────────────────────────
    shape = "box"
    for alias, canonical in sorted(SHAPE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(alias) + r'\b', t):
            shape = canonical
            break

    color        = parse_color(t)
    size         = parse_size(t)
    position     = parse_position(t)
    rotation     = parse_rotation(t)
    count        = parse_count(t)
    arrangement  = parse_arrangement(t) if count > 1 else None
    transparent  = any(w in t for w in (
        "transparent", "glass", "see through", "see-through", "translucent", "ghostly", "ghost", "crystal clear", "invisible"))
    transparency = 0.6 if transparent else 0.0
    animation    = parse_animation(t)

    color_name = next((n for n, rgb in COLORS.items() if rgb == color), "colored")
    if count > 1:
        msg = f"Added {count} {color_name} {shape}s in a {arrangement}."
    else:
        msg = f"Added {color_name} {shape} (size={size:.2f}) at {position}."

    return {
        "action":       "add",
        "shape":        shape,
        "color":        color,
        "position":     position,
        "size":         size,
        "rotation":     rotation,
        "transparency": transparency,
        "animation":    animation,
        "count":        count,
        "arrangement":  arrangement,
        "message":      msg,
    }


# ── Multi-position generator ───────────────────────────────────────────────────

def multi_positions(count, arrangement, base_pos, size):
    x0, y0, z0 = base_pos
    spacing = size * 2.5
    positions = []
    if arrangement == "row":
        total_w = (count - 1) * spacing
        for i in range(count):
            positions.append((x0 - total_w/2 + i * spacing, y0, z0))
    elif arrangement == "circle":
        radius = max(spacing * count / (2 * math.pi), spacing)
        for i in range(count):
            angle = 2 * math.pi * i / count
            positions.append((x0 + radius * math.cos(angle), y0, z0 + radius * math.sin(angle)))
    elif arrangement == "grid":
        cols = math.ceil(math.sqrt(count))
        for i in range(count):
            row, col = divmod(i, cols)
            positions.append((x0 + col * spacing - (cols-1)*spacing/2, y0, z0 + row * spacing))
    else:  # random
        import random
        random.seed(42)
        for i in range(count):
            positions.append((x0 + random.uniform(-4, 4), y0 + random.uniform(-1, 2), z0 + random.uniform(-2, 2)))
    return positions


# ── Shape XML builders ─────────────────────────────────────────────────────────

def build_capsule_xml(r, g, b, x, y, z, size, rotation, transparency):
    """True capsule: cylinder + 2 spheres."""
    h = size * 1.5
    rad = size * 0.5
    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    mat = f'<Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/>'
    app = f'<Appearance>{mat}</Appearance>'
    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape><Cylinder radius="{rad:.3f}" height="{h:.3f}"/>{app}</Shape>',
        f'      <Transform translation="0 {h/2:.3f} 0">',
        f'        <Shape><Sphere radius="{rad:.3f}"/>{app}</Shape>',
        f'      </Transform>',
        f'      <Transform translation="0 {-h/2:.3f} 0">',
        f'        <Shape><Sphere radius="{rad:.3f}"/>{app}</Shape>',
        f'      </Transform>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_dodecahedron_xml(r, g, b, x, y, z, size, rotation, transparency):
    """Dodecahedron via 20 vertices."""
    phi = (1 + math.sqrt(5)) / 2
    s = size
    verts_raw = []
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            for sz in [-1, 1]:
                verts_raw.append((sx*s, sy*s, sz*s))
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            verts_raw.append((0, sx*phi*s, sy*s/phi))
            verts_raw.append((sy*s/phi, 0, sx*phi*s))
            verts_raw.append((sx*phi*s, sy*s/phi, 0))
    faces = [
        [0,1,3,2,4],[5,4,2,6,7],[8,9,11,10,0],[1,3,11,9,13],
        [4,5,15,14,0],[6,7,17,16,2],[8,10,18,19,12],[11,13,19,18,9],
        [14,15,12,8,0],[16,17,18,19,6],[1,13,12,15,5],[3,11,19,16,7],
    ]
    pts_str = " ".join(f"{vx:.3f} {vy:.3f} {vz:.3f}" for vx, vy, vz in verts_raw)
    idx_str = " ".join(" ".join(str(f) for f in face) + " -1" for face in faces)
    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    geo = (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="0.5">'
           f'<Coordinate point="{pts_str}"/></IndexedFaceSet>')
    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape>{geo}',
        f'        <Appearance><Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/></Appearance>',
        f'      </Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_cross_xml(r, g, b, x, y, z, size, rotation, transparency):
    """3D cross from 3 overlapping boxes."""
    s = size
    t2 = size * 0.35
    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    mat = f'<Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/>'
    app = f'<Appearance>{mat}</Appearance>'
    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape><Box size="{s*2:.3f} {t2*2:.3f} {t2*2:.3f}"/>{app}</Shape>',
        f'      <Shape><Box size="{t2*2:.3f} {s*2:.3f} {t2*2:.3f}"/>{app}</Shape>',
        f'      <Shape><Box size="{t2*2:.3f} {t2*2:.3f} {s*2:.3f}"/>{app}</Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_crescent_xml(r, g, b, x, y, z, size, rotation, transparency):
    """Crescent via IndexedFaceSet arc subtraction approximation."""
    steps = 20
    outer_r, inner_r = size, size * 0.65
    offset = size * 0.25
    pts = []
    # outer arc
    for i in range(steps + 1):
        a = math.pi * i / steps
        pts.append(f"{outer_r*math.cos(a):.3f} {outer_r*math.sin(a):.3f} 0")
    # inner arc (shifted)
    for i in range(steps + 1):
        a = math.pi * i / steps
        pts.append(f"{inner_r*math.cos(a)+offset:.3f} {inner_r*math.sin(a):.3f} 0")
    # Build faces connecting outer and inner arcs
    idxs = []
    n = steps + 1
    for i in range(steps):
        idxs.append(f"{i} {i+1} {n+i+1} {n+i} -1")
    idx_str = " ".join(idxs)
    pts_str = " ".join(pts)
    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    geo = (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false">'
           f'<Coordinate point="{pts_str}"/></IndexedFaceSet>')
    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape>{geo}',
        f'        <Appearance><Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/></Appearance>',
        f'      </Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_torusknot_xml(r, g, b, x, y, z, size, rotation, transparency):
    """Torus knot (3,2) as a line set."""
    steps = 200
    p, q = 3, 2
    R, r2 = size, size * 0.3
    pts = []
    for i in range(steps + 1):
        t2 = 2 * math.pi * i / steps
        px = (R + r2 * math.cos(q * t2)) * math.cos(p * t2)
        py = (R + r2 * math.cos(q * t2)) * math.sin(p * t2)
        pz = r2 * math.sin(q * t2)
        pts.append(f"{px:.3f} {py:.3f} {pz:.3f}")
    idxs = " ".join(f"{i} {i+1} -1" for i in range(steps))
    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    geo = (f'<IndexedLineSet coordIndex="{idxs}">'
           f'<Coordinate point="{" ".join(pts)}"/>'
           f'<ColorRGBA color=""/>'
           f'</IndexedLineSet>')
    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape>',
        f'        <IndexedLineSet coordIndex="{idxs}">',
        f'          <Coordinate point="{" ".join(pts)}"/>',
        f'        </IndexedLineSet>',
        f'        <Appearance><Material emissiveColor="{r:.3f} {g:.3f} {b:.3f}"/></Appearance>',
        f'      </Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_animation_xml(anim_type, shape_id=None):
    """Return X3D animation nodes to wrap around the last Transform."""
    if anim_type == "spin":
        return f'''    <TimeSensor DEF="clock_{shape_id}" cycleInterval="3" loop="true"/>
    <OrientationInterpolator DEF="spin_{shape_id}" key="0 0.5 1" keyValue="0 1 0 0  0 1 0 3.14159  0 1 0 6.28318"/>
    <ROUTE fromNode="clock_{shape_id}" fromField="fraction_changed" toNode="spin_{shape_id}" toField="set_fraction"/>
    <ROUTE fromNode="spin_{shape_id}" fromField="value_changed" toNode="obj_{shape_id}" toField="rotation"/>
'''
    elif anim_type == "bounce":
        return f'''    <TimeSensor DEF="clock_{shape_id}" cycleInterval="1.5" loop="true"/>
    <PositionInterpolator DEF="bounce_{shape_id}" key="0 0.5 1" keyValue="0 0 0  0 1.5 0  0 0 0"/>
    <ROUTE fromNode="clock_{shape_id}" fromField="fraction_changed" toNode="bounce_{shape_id}" toField="set_fraction"/>
    <ROUTE fromNode="bounce_{shape_id}" fromField="value_changed" toNode="obj_{shape_id}" toField="translation"/>
'''
    elif anim_type == "pulse":
        return f'''    <TimeSensor DEF="clock_{shape_id}" cycleInterval="2" loop="true"/>
    <ScalarInterpolator DEF="pulse_{shape_id}" key="0 0.5 1" keyValue="1 1.5 1"/>
    <ROUTE fromNode="clock_{shape_id}" fromField="fraction_changed" toNode="pulse_{shape_id}" toField="set_fraction"/>
'''
    return ""


def build_shape_xml(shape, color, position, size, rotation=None, transparency=0.0, animation=None, obj_id=None):
    r, g, b = color
    x, y, z = position

    # special multi-node shapes
    if shape == "capsule":
        return build_capsule_xml(r, g, b, x, y, z, size, rotation, transparency)
    if shape == "dodecahedron":
        return build_dodecahedron_xml(r, g, b, x, y, z, size, rotation, transparency)
    if shape == "cross":
        return build_cross_xml(r, g, b, x, y, z, size, rotation, transparency)
    if shape == "crescent":
        return build_crescent_xml(r, g, b, x, y, z, size, rotation, transparency)
    if shape == "torusknot":
        return build_torusknot_xml(r, g, b, x, y, z, size, rotation, transparency)

    if shape == "sphere":
        geo = f'<Sphere radius="{size:.3f}"/>'
    elif shape == "cone":
        geo = f'<Cone bottomRadius="{size:.3f}" height="{size*2:.3f}"/>'
    elif shape == "cylinder":
        geo = f'<Cylinder radius="{size:.3f}" height="{size*2:.3f}"/>'
    elif shape == "torus":
        outer, inner, steps = size, size * 0.35, 24
        pts, idxs = [], []
        for i in range(steps):
            a = 2 * math.pi * i / steps
            for j in range(steps):
                b2 = 2 * math.pi * j / steps
                px = (outer + inner * math.cos(b2)) * math.cos(a)
                py = inner * math.sin(b2)
                pz = (outer + inner * math.cos(b2)) * math.sin(a)
                pts.append(f"{px:.3f} {py:.3f} {pz:.3f}")
        for i in range(steps):
            for j in range(steps):
                aa = i * steps + j
                bb = i * steps + (j+1) % steps
                cc = ((i+1) % steps) * steps + (j+1) % steps
                dd = ((i+1) % steps) * steps + j
                idxs.append(f"{aa} {bb} {cc} {dd} -1")
        geo = (f'<IndexedFaceSet coordIndex="{" ".join(idxs)}" solid="false">'
               f'<Coordinate point="{" ".join(pts)}"/></IndexedFaceSet>')
    elif shape == "tetrahedron":
        s = size
        geo = (f'<IndexedFaceSet coordIndex="0 1 2 -1 0 3 1 -1 1 3 2 -1 0 2 3 -1" solid="false" creaseAngle="0.5">'
               f'<Coordinate point="{s:.3f} 0 {-s*0.577:.3f}  -{s:.3f} 0 {-s*0.577:.3f}  0 0 {s*1.155:.3f}  0 {s*1.633:.3f} 0"/>'
               f'</IndexedFaceSet>')
    elif shape == "octahedron":
        s = size
        pts = f"0 {s:.3f} 0  {s:.3f} 0 0  0 0 {s:.3f}  -{s:.3f} 0 0  0 0 -{s:.3f}  0 -{s:.3f} 0"
        idx = "0 1 2 -1 0 2 3 -1 0 3 4 -1 0 4 1 -1 5 2 1 -1 5 3 2 -1 5 4 3 -1 5 1 4 -1"
        geo = (f'<IndexedFaceSet coordIndex="{idx}" solid="false" creaseAngle="0.5">'
               f'<Coordinate point="{pts}"/></IndexedFaceSet>')
    elif shape == "icosahedron":
        s = size
        t_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        raw = [(-1,t_ratio,0),(1,t_ratio,0),(-1,-t_ratio,0),(1,-t_ratio,0),
               (0,-1,t_ratio),(0,1,t_ratio),(0,-1,-t_ratio),(0,1,-t_ratio),
               (t_ratio,0,-1),(t_ratio,0,1),(-t_ratio,0,-1),(-t_ratio,0,1)]
        norm = math.sqrt(1 + t_ratio**2)
        verts = [f"{vx/norm*s:.3f} {vy/norm*s:.3f} {vz/norm*s:.3f}" for vx, vy, vz in raw]
        faces = [0,11,5,0,5,1,0,1,7,0,7,10,0,10,11,1,5,9,5,11,4,11,10,2,10,7,6,7,1,8,
                 3,9,4,3,4,2,3,2,6,3,6,8,3,8,9,4,9,5,2,4,11,6,2,10,8,6,7,9,8,1]
        idx_str = " ".join(f"{faces[i]} {faces[i+1]} {faces[i+2]} -1" for i in range(0, len(faces), 3))
        geo = (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="0.5">'
               f'<Coordinate point="{" ".join(verts)}"/></IndexedFaceSet>')
    elif shape == "star":
        pts = []
        outer_r, inner_r = size, size * 0.4
        points = 5
        for i in range(points * 2):
            angle = math.pi / points * i - math.pi / 2
            rad = outer_r if i % 2 == 0 else inner_r
            pts.append(f"{math.cos(angle)*rad:.3f} 0 {math.sin(angle)*rad:.3f}")
        center_idx = points * 2
        pts.append("0 0 0")
        idxs = [f"{center_idx} {i} {(i+1) % (points*2)} -1" for i in range(points * 2)]
        geo = (f'<IndexedFaceSet coordIndex="{" ".join(idxs)}" solid="false">'
               f'<Coordinate point="{" ".join(pts)}"/></IndexedFaceSet>')
    elif shape == "arrow":
        s = size
        shaft_w, head_w = s * 0.2, s * 0.5
        shaft_l, head_l = s * 1.2, s * 0.8
        pts = [f"-{shaft_w:.3f} 0 0", f"{shaft_w:.3f} 0 0",
               f"{shaft_w:.3f} 0 {-shaft_l:.3f}", f"-{shaft_w:.3f} 0 {-shaft_l:.3f}",
               f"-{head_w:.3f} 0 {-shaft_l:.3f}", f"0 0 {-(shaft_l+head_l):.3f}",
               f"{head_w:.3f} 0 {-shaft_l:.3f}"]
        geo = (f'<IndexedFaceSet coordIndex="0 1 2 3 -1 4 5 6 -1" solid="false">'
               f'<Coordinate point="{" ".join(pts)}"/></IndexedFaceSet>')
    elif shape == "helix":
        turns, steps_per_turn = 3, 24
        total = turns * steps_per_turn
        radius, pitch = size * 0.8, size * 0.5
        pts = []
        for i in range(total + 1):
            angle = 2 * math.pi * i / steps_per_turn
            px = radius * math.cos(angle)
            py = pitch * i / steps_per_turn - (pitch * turns / 2)
            pz = radius * math.sin(angle)
            pts.append(f"{px:.3f} {py:.3f} {pz:.3f}")
        idxs = " ".join(f"{i} {i+1} -1" for i in range(total))
        geo = (f'<IndexedLineSet coordIndex="{idxs}">'
               f'<Coordinate point="{" ".join(pts)}"/></IndexedLineSet>')
    elif shape == "plane":
        s = size * 2
        geo = (f'<IndexedFaceSet coordIndex="0 1 2 3 -1" solid="false">'
               f'<Coordinate point="-{s:.3f} 0 -{s:.3f}  {s:.3f} 0 -{s:.3f}  {s:.3f} 0 {s:.3f}  -{s:.3f} 0 {s:.3f}"/>'
               f'</IndexedFaceSet>')
    elif shape == "ellipsoid":
        geo = f'<Sphere radius="{size:.3f}"/>'
        rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
        def_str = f' DEF="obj_{obj_id}"' if obj_id else ""
        lines = [
            f'    <Transform{def_str} translation="{x:.3f} {y:.3f} {z:.3f}" scale="1.0 0.6 1.4"{rot_str}>',
            f'      <Shape>{geo}',
            f'        <Appearance><Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/></Appearance>',
            f'      </Shape>',
            f'    </Transform>',
        ]
        return "\n".join(lines) + "\n"
    else:
        s = size * 2
        geo = f'<Box size="{s:.3f} {s:.3f} {s:.3f}"/>'

    rot_str = f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"' if rotation else ""
    def_str = f' DEF="obj_{obj_id}"' if obj_id else ""

    lines = [
        f'    <Transform{def_str} translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape>',
        f'        {geo}',
        f'        <Appearance>',
        f'          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/>',
        f'        </Appearance>',
        f'      </Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


def build_lighting_xml(preset: str) -> str:
    """Return full X3D header with updated lighting for given preset."""
    presets = {
        "night":   {"sky": (0.0, 0.0, 0.05),  "lights": [{"d":"-0.3 -1 -0.5","i":0.3,"c":"0.7 0.7 1.0"},{"d":"0.5 0.5 0","i":0.1,"c":"0.9 0.9 1.0"}]},
        "day":     {"sky": (0.4, 0.6, 0.9),    "lights": [{"d":"-1 -2 -1","i":1.5,"c":"1 1 0.95"},{"d":"1 1 0.5","i":0.6,"c":"1 1 1"}]},
        "sunrise": {"sky": (0.6, 0.3, 0.1),    "lights": [{"d":"-1 -0.5 0","i":1.2,"c":"1.0 0.6 0.2"},{"d":"0 1 0","i":0.4,"c":"1.0 0.8 0.5"}]},
        "neon":    {"sky": (0.0, 0.0, 0.0),    "lights": [{"d":"-1 -1 0","i":1.0,"c":"1 0 1"},{"d":"1 -1 0","i":1.0,"c":"0 1 1"},{"d":"0 1 0","i":0.8,"c":"0 1 0"}]},
        "brighter":{"sky": (0.12,0.12,0.18),   "lights": [{"d":"-1 -2 -1","i":1.8,"c":"1 1 1"},{"d":"1 1 0.5","i":0.9,"c":"0.9 0.9 1"}]},
        "dimmer":  {"sky": (0.02,0.02,0.04),   "lights": [{"d":"-1 -2 -1","i":0.4,"c":"1 1 1"},{"d":"1 1 0.5","i":0.2,"c":"0.8 0.8 1"}]},
    }
    p = presets.get(preset, presets["day"])
    sky = p["sky"]
    sky_str = f"{sky[0]:.2f} {sky[1]:.2f} {sky[2]:.2f}"
    lights_xml = ""
    for l in p["lights"]:
        lights_xml += f'    <DirectionalLight direction="{l["d"]}" intensity="{l["i"]:.2f}" color="{l["c"]}"/>\n'
    return sky_str, lights_xml


def build_viewpoint_xml(view: str) -> str:
    viewpoints = {
        "reset": '<Viewpoint description="Default" position="0 0 10" orientation="0 1 0 0"/>',
        "top":   '<Viewpoint description="Top" position="0 12 0" orientation="1 0 0 -1.5708"/>',
        "front": '<Viewpoint description="Front" position="0 0 12" orientation="0 1 0 0"/>',
        "side":  '<Viewpoint description="Side" position="12 0 0" orientation="0 1 0 1.5708"/>',
        "iso":   '<Viewpoint description="Iso" position="7 7 7" orientation="0.577 0.577 0.577 -1.5708"/>',
    }
    return viewpoints.get(view, viewpoints["reset"])


def rebuild_scene_with_header(sky_str: str, lights_xml: str) -> str:
    """Re-read scene, replace Background and lights, keep objects."""
    ensure_scene_file()
    with open(SCENE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # Extract everything between <Scene> and </Scene>
    scene_match = re.search(r'<Scene>(.*?)</Scene>', content, re.DOTALL)
    if not scene_match:
        return DEFAULT_X3D
    inner = scene_match.group(1)
    # Remove old background, nav, lights
    inner = re.sub(r'\s*<Background[^/]*/>', '', inner)
    inner = re.sub(r'\s*<NavigationInfo[^/]*/>', '', inner)
    inner = re.sub(r'\s*<DirectionalLight[^/]*/>', '', inner)
    inner = re.sub(r'\s*<Viewpoint[^/]*/>', '', inner)
    new_header = (f'    <Background skyColor="{sky_str}"/>\n'
                  f'    <NavigationInfo type="EXAMINE ANY"/>\n'
                  + lights_xml)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "http://www.web3d.org/specifications/x3d-3.3.dtd">\n'
            f'<X3D profile="Immersive" version="3.3">\n'
            f'  <Scene>\n'
            f'{new_header}'
            f'{inner}'
            f'  </Scene>\n</X3D>\n')


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def get_viewer():
    return HTML


@app.get("/scene.x3d")
async def get_scene():
    ensure_scene_file()
    return FileResponse(SCENE_FILE, media_type="model/x3d+xml",
        headers={"Cache-Control": "no-cache, no-store", "Access-Control-Allow-Origin": "*"})


@app.post("/api/clear")
async def clear_scene():
    SCENE_OBJECTS.clear()
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        f.write(DEFAULT_X3D)
    return {"status": "success", "message": "Scene cleared."}


@app.get("/api/inspect")
async def inspect_scene():
    return {"status": "success", "objects": SCENE_OBJECTS, "count": len(SCENE_OBJECTS)}


@app.post("/api/save")
async def save_scene(req: SaveRequest):
    ensure_scene_file()
    name = re.sub(r'[^a-z0-9_\-]', '_', req.name.lower().strip())
    if not name:
        raise HTTPException(400, "Invalid save name")
    path = os.path.join(SAVES_DIR, f"{name}.x3d")
    with open(SCENE_FILE, "r") as src, open(path, "w") as dst:
        dst.write(src.read())
    meta_path = os.path.join(SAVES_DIR, f"{name}.json")
    with open(meta_path, "w") as f:
        json.dump({"name": name, "objects": SCENE_OBJECTS}, f)
    return {"status": "success", "message": f"Saved as '{name}'."}


@app.post("/api/load/{name}")
async def load_scene(name: str):
    name = re.sub(r'[^a-z0-9_\-]', '_', name.lower().strip())
    path = os.path.join(SAVES_DIR, f"{name}.x3d")
    if not os.path.exists(path):
        raise HTTPException(404, f"No save named '{name}'")
    with open(path, "r") as src, open(SCENE_FILE, "w") as dst:
        dst.write(src.read())
    meta_path = os.path.join(SAVES_DIR, f"{name}.json")
    SCENE_OBJECTS.clear()
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            data = json.load(f)
            SCENE_OBJECTS.extend(data.get("objects", []))
    return {"status": "success", "message": f"Loaded '{name}'."}


@app.get("/api/saves")
async def list_saves():
    saves = [os.path.splitext(os.path.basename(p))[0]
             for p in glob.glob(os.path.join(SAVES_DIR, "*.x3d"))]
    return {"status": "success", "saves": saves}


@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    try:
        result = parse_prompt(req.prompt)

        # ── Clear ─────────────────────────────────────────────────────────────
        if result["action"] == "clear":
            SCENE_OBJECTS.clear()
            with open(SCENE_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_X3D)
            return {"status": "success", "message": "Scene cleared."}

        # ── Remove last ───────────────────────────────────────────────────────
        if result["action"] == "remove_last":
            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            last = content.rfind("<Transform")
            if last != -1:
                content = content[:last] + "  </Scene>\n</X3D>"
                with open(SCENE_FILE, "w") as f:
                    f.write(content)
                if SCENE_OBJECTS:
                    removed = SCENE_OBJECTS.pop()
                    return {"status": "success", "message": f"Removed last shape ({removed.get('shape','object')})."}
            return {"status": "ok", "message": "Nothing to remove."}

        # ── Inspect ───────────────────────────────────────────────────────────
        if result["action"] == "inspect":
            if not SCENE_OBJECTS:
                return {"status": "ok", "message": "Scene is empty — no objects yet."}
            lines = [f"{i+1}. {o.get('color_name','?')} {o.get('shape','?')} at {o.get('position','?')}"
                     for i, o in enumerate(SCENE_OBJECTS)]
            return {"status": "success", "message": f"{len(SCENE_OBJECTS)} object(s):\n" + "\n".join(lines)}

        # ── Load archive ──────────────────────────────────────────────────────
        if result["action"] == "load_archive":
            key = result["key"]
            url = ARCHIVE_EXAMPLES.get(key)
            if not url:
                return {"status": "error", "message": f"Unknown archive scene: {key}"}
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:
                    data = resp.read().decode("utf-8", errors="replace")
                with open(SCENE_FILE, "w") as f:
                    f.write(data)
                SCENE_OBJECTS.clear()
                SCENE_OBJECTS.append({"shape": "archive", "color_name": key, "position": "(0,0,0)"})
                return {"status": "success", "message": f"Loaded archive scene: {key}"}
            except Exception as e:
                return {"status": "error", "message": f"Couldn't fetch archive scene: {e}"}

        # ── Lighting preset ───────────────────────────────────────────────────
        if result["action"] == "lighting":
            sky_str, lights_xml = build_lighting_xml(result["preset"])
            new_content = rebuild_scene_with_header(sky_str, lights_xml)
            with open(SCENE_FILE, "w") as f:
                f.write(new_content)
            return {"status": "success", "message": f"Lighting set to '{result['preset']}'."}

        # ── Add light ─────────────────────────────────────────────────────────
        if result["action"] == "add_light":
            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            spot = '    <SpotLight location="0 5 0" direction="0 -1 0" intensity="1.5" cutOffAngle="0.5" color="1 1 0.9"/>\n'
            updated = content.replace("</Scene>", spot + "  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)
            return {"status": "success", "message": "Added spotlight above the scene."}

        # ── Camera viewpoint ──────────────────────────────────────────────────
        if result["action"] == "camera":
            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            # Remove existing viewpoints
            content = re.sub(r'\s*<Viewpoint[^/]*/>', '', content)
            vp = build_viewpoint_xml(result["view"])
            updated = content.replace("</Scene>", f"    {vp}\n  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)
            return {"status": "success", "message": f"Camera set to {result['view']} view."}

        # ── Animation on last object ──────────────────────────────────────────
        if result["action"] == "animate":
            anim = result["anim"]
            if anim == "stop":
                # Strip all animation nodes
                ensure_scene_file()
                with open(SCENE_FILE, "r") as f:
                    content = f.read()
                content = re.sub(r'\s*<TimeSensor[^/]*/>', '', content)
                content = re.sub(r'\s*<OrientationInterpolator[^>]*/>', '', content)
                content = re.sub(r'\s*<PositionInterpolator[^>]*/>', '', content)
                content = re.sub(r'\s*<ScalarInterpolator[^>]*/>', '', content)
                content = re.sub(r'\s*<ROUTE[^/]*/>', '', content)
                with open(SCENE_FILE, "w") as f:
                    f.write(content)
                return {"status": "success", "message": "Animation stopped."}
            obj_id = len(SCENE_OBJECTS)
            anim_xml = build_animation_xml(anim, obj_id)
            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            # Tag the last Transform with a DEF
            content = content.replace("<Transform ", f'<Transform DEF="obj_{obj_id}" ', 1)
            updated = content.replace("</Scene>", anim_xml + "  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)
            return {"status": "success", "message": f"Applied {anim} animation to last object."}

        # ── Add shape(s) ──────────────────────────────────────────────────────
        if result["action"] == "add":
            count       = result.get("count", 1)
            arrangement = result.get("arrangement")
            shape       = result["shape"]
            color       = result["color"]
            size        = result["size"]
            rotation    = result.get("rotation")
            transparency= result.get("transparency", 0.0)
            animation   = result.get("animation")
            base_pos    = result["position"]
            color_name  = next((n for n, rgb in COLORS.items() if rgb == color), "colored")

            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            if "</Scene>" not in content:
                content = DEFAULT_X3D

            positions = multi_positions(count, arrangement, base_pos, size) if count > 1 else [base_pos]

            all_xml = ""
            for i, pos in enumerate(positions):
                obj_id = len(SCENE_OBJECTS) + i
                xml = build_shape_xml(shape, color, pos, size, rotation, transparency,
                                      animation=animation, obj_id=obj_id)
                all_xml += xml
                SCENE_OBJECTS.append({
                    "shape": shape,
                    "color_name": color_name,
                    "color": color,
                    "position": str(pos),
                    "size": size,
                })
                if animation:
                    all_xml += build_animation_xml(animation, obj_id)

            updated = content.replace("</Scene>", all_xml + "  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)
            return {"status": "success", "message": result["message"]}

        return {"status": "ok", "message": "Try: 'place a red sphere to the left'"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── HTML ───────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>X3D Agent</title>
  <script src="https://create3000.github.io/code/x_ite/latest/x_ite.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --accent:   #7c3aed;
      --accent-l: #a78bfa;
      --green:    #10b981;
      --green-l:  #6ee7b7;
      --red:      #ef4444;
      --red-l:    #fca5a5;
      --blue:     #3b82f6;
      --blue-l:   #93c5fd;
      --yellow:   #f59e0b;
      --yellow-l: #fcd34d;
      --bg:       #0d0d0d;
      --bg2:      #141414;
      --bg3:      #1a1a1a;
      --border:   #222;
      --text:     #e0e0e0;
      --muted:    #555;
      --safe-b:   env(safe-area-inset-bottom, 0px);
      --safe-t:   env(safe-area-inset-top, 0px);
      --safe-l:   env(safe-area-inset-left, 0px);
      --safe-r:   env(safe-area-inset-right, 0px);
    }
    html, body { height: 100%; background: var(--bg); color: var(--text);
      font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
      overflow: hidden; -webkit-text-size-adjust: 100%; }

    .shell { display: flex; flex-direction: column; height: 100dvh; padding-top: var(--safe-t); }

    header { flex-shrink: 0; padding: 10px 16px;
      padding-left: max(16px, var(--safe-l)); padding-right: max(16px, var(--safe-r));
      background: #161616; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    header h1 { font-size: 16px; font-weight: 700; color: #fff; }
    .badge { font-size: 10px; background: var(--accent); color: #fff;
      padding: 2px 8px; border-radius: 99px; font-weight: 700;
      letter-spacing: .06em; text-transform: uppercase; }
    .header-actions { margin-left: auto; display: flex; gap: 6px; align-items: center; }
    .hbtn { font-size: 11px; padding: 4px 10px; border-radius: 8px; border: 1px solid #333;
      background: #1e1e1e; color: #aaa; cursor: pointer; white-space: nowrap; }
    .hbtn:hover { background: #252525; color: #fff; }

    .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .viewport { flex: 1; background: #111; min-height: 0; position: relative; }
    x3d-canvas { width: 100%; height: 100%; display: block; touch-action: none; }

    /* Object list overlay */
    .obj-list { position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.7);
      border: 1px solid #333; border-radius: 10px; padding: 8px 10px;
      font-size: 11px; color: #aaa; max-height: 180px; overflow-y: auto;
      display: none; min-width: 160px; z-index: 10; }
    .obj-list.visible { display: block; }
    .obj-list h3 { font-size: 10px; color: #666; text-transform: uppercase;
      letter-spacing: .08em; margin-bottom: 6px; }
    .obj-item { padding: 3px 0; border-bottom: 1px solid #222; color: #ccc; }
    .obj-item:last-child { border-bottom: none; }

    .panel { flex-shrink: 0; display: flex; flex-direction: column;
      background: var(--bg2); border-top: 1px solid var(--border);
      max-height: 54vh; overflow: hidden; }

    .tab-bar { display: flex; border-bottom: 1px solid var(--border); background: #111; flex-shrink: 0; }
    .tab { flex: 1; padding: 8px 4px; font-size: 11px; font-weight: 600; text-align: center;
      color: #555; cursor: pointer; border-bottom: 2px solid transparent;
      text-transform: uppercase; letter-spacing: .05em; -webkit-tap-highlight-color: transparent; }
    .tab.active { color: var(--accent-l); border-bottom-color: var(--accent); }

    .tab-content { display: none; flex: 1; overflow: hidden; flex-direction: column; }
    .tab-content.active { display: flex; }

    .console-log { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
      padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
    .entry { border-radius: 8px; padding: 8px 10px; font-size: 13px; line-height: 1.5; }
    .entry.user  { background: #1e1e2e; border-left: 3px solid var(--accent);  color: #c4b5fd; }
    .entry.ai    { background: #0f1f18; border-left: 3px solid var(--green);   color: var(--green-l); }
    .entry.error { background: #1f0f0f; border-left: 3px solid var(--red);     color: var(--red-l); }
    .entry.info  { background: #0f1620; border-left: 3px solid var(--blue);    color: var(--blue-l); }
    .entry.sys   { color: var(--muted); font-size: 11px; font-style: italic; }
    .lbl { font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
      margin-bottom: 2px; opacity: .65; }

    /* Chips panel */
    .chips-panel { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: 8px 12px; }
    .chip-group { margin-bottom: 12px; }
    .chip-group-label { font-size: 10px; color: #444; text-transform: uppercase;
      letter-spacing: .08em; margin-bottom: 5px; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .chip { flex-shrink: 0; font-size: 12px; padding: 4px 10px; background: #1e1e2e;
      color: var(--accent-l); border-radius: 99px; cursor: pointer;
      border: 1px solid #2d2d4e; white-space: nowrap;
      -webkit-tap-highlight-color: transparent; user-select: none; }
    .chip.green  { background: #0f2018; color: var(--green-l); border-color: #1a4030; }
    .chip.blue   { background: #0f1830; color: var(--blue-l);  border-color: #1a2850; }
    .chip.yellow { background: #201a0a; color: var(--yellow-l); border-color: #3a2a10; }
    .chip.red    { background: #200f0f; color: var(--red-l);   border-color: #3a1a1a; }
    .chip:active { opacity: 0.7; }

    /* Saves panel */
    .saves-panel { flex: 1; overflow-y: auto; padding: 10px 12px; }
    .save-row { display: flex; gap: 8px; margin-bottom: 8px; }
    .save-input { flex: 1; padding: 8px 10px; background: var(--bg3);
      border: 1px solid #333; border-radius: 8px; color: var(--text);
      font-size: 13px; outline: none; }
    .save-input:focus { border-color: var(--accent); }
    .save-btn { padding: 8px 14px; border: none; border-radius: 8px; cursor: pointer;
      font-size: 13px; font-weight: 600; background: var(--accent); color: #fff; }
    .saves-list { display: flex; flex-direction: column; gap: 5px; margin-top: 10px; }
    .save-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
      background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; }
    .save-item-name { flex: 1; font-size: 13px; color: #ccc; }
    .save-item-btn { font-size: 11px; padding: 3px 8px; border: 1px solid #333;
      background: #222; color: #aaa; border-radius: 6px; cursor: pointer; }
    .save-item-btn:hover { background: #2a2a2a; color: #fff; }
    .saves-empty { color: #444; font-size: 12px; font-style: italic; margin-top: 8px; }

    .input-area { flex-shrink: 0; padding: 10px 12px;
      padding-bottom: max(10px, var(--safe-b));
      padding-left: max(12px, var(--safe-l)); padding-right: max(12px, var(--safe-r));
      border-top: 1px solid var(--border); display: flex; flex-direction: column;
      gap: 8px; background: var(--bg2); }
    textarea { width: 100%; padding: 10px 12px; background: var(--bg3);
      border: 1px solid #333; border-radius: 10px; color: var(--text);
      font-size: 16px; line-height: 1.4; resize: none; outline: none;
      font-family: inherit; -webkit-appearance: none; }
    textarea:focus { border-color: var(--accent); }
    .btn-row { display: flex; gap: 8px; }
    button { flex: 1; padding: 11px; border: none; border-radius: 10px; cursor: pointer;
      font-size: 14px; font-weight: 700; -webkit-tap-highlight-color: transparent;
      touch-action: manipulation; }
    button:active { opacity: .75; }
    button:disabled { opacity: .4; cursor: not-allowed; }
    #runBtn   { background: var(--accent); color: #fff; }
    #clearBtn { background: #222; color: #aaa; border: 1px solid #333; }
    .hint { font-size: 11px; color: #3a3a3a; text-align: center; }

    @media (min-width: 700px) {
      .main { flex-direction: row; }
      .viewport { flex: 1; }
      .panel { width: 340px; max-height: none; height: 100%;
        border-top: none; border-left: 1px solid var(--border); }
      textarea { font-size: 13px; }
    }
    @media (min-width: 1024px) {
      .panel { width: 380px; }
      header h1 { font-size: 18px; }
    }
  </style>
</head>
<body>
<div class="shell">
  <header>
    <h1>X3D Agent</h1>
    <span class="badge">Rule-Based NL</span>
    <div class="header-actions">
      <button class="hbtn" onclick="toggleObjList()" title="Show/hide object list">&#9776; Objects</button>
      <button class="hbtn" onclick="quick('reset camera')">&#8635; View</button>
    </div>
  </header>

  <div class="main">
    <div class="viewport">
      <x3d-canvas id="canvas" src="/scene.x3d"></x3d-canvas>
      <div class="obj-list" id="objList">
        <h3>Scene Objects</h3>
        <div id="objListItems"><em style="color:#444">Empty</em></div>
      </div>
    </div>

    <div class="panel">
      <div class="tab-bar">
        <div class="tab active" onclick="switchTab('console')">Console</div>
        <div class="tab" onclick="switchTab('chips')">Chips</div>
        <div class="tab" onclick="switchTab('saves')">Saves</div>
      </div>

      <!-- Console tab -->
      <div class="tab-content active" id="tab-console">
        <div class="console-log" id="log">
          <div class="entry sys">Scene ready — type a command or switch to Chips.</div>
        </div>
      </div>

      <!-- Chips tab -->
      <div class="tab-content" id="tab-chips">
        <div class="chips-panel">
          <div class="chip-group">
            <div class="chip-group-label">Shapes</div>
            <div class="chips">
              <span class="chip" onclick="quick('place a red sphere to the left')">red sphere</span>
              <span class="chip" onclick="quick('spawn a huge gold torus in the center')">gold torus</span>
              <span class="chip" onclick="quick('create a tiny cyan cube floating')">floating cube</span>
              <span class="chip" onclick="quick('drop a purple cone to the right')">purple cone</span>
              <span class="chip" onclick="quick('make a neon green icosahedron')">icosahedron</span>
              <span class="chip" onclick="quick('place a gold star overhead')">star</span>
              <span class="chip" onclick="quick('spawn a crimson octahedron to the right')">octahedron</span>
              <span class="chip" onclick="quick('add a rose gold spiral up high')">helix</span>
              <span class="chip" onclick="quick('drop a tilted orange arrow in front')">arrow</span>
              <span class="chip" onclick="quick('put a white plane below')">ground plane</span>
              <span class="chip" onclick="quick('add a silver capsule to the left')">capsule</span>
              <span class="chip" onclick="quick('spawn a jade dodecahedron')">dodecahedron</span>
              <span class="chip" onclick="quick('place a gold cross in the center')">cross</span>
              <span class="chip" onclick="quick('add a cyan crescent above')">crescent</span>
              <span class="chip" onclick="quick('spawn a neon blue torus knot')">torus knot</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Multi-Shape</div>
            <div class="chips">
              <span class="chip blue" onclick="quick('add 5 red spheres in a row')">5 spheres row</span>
              <span class="chip blue" onclick="quick('spawn 8 blue cubes in a circle')">8 cubes circle</span>
              <span class="chip blue" onclick="quick('create 6 gold stars in a grid')">6 stars grid</span>
              <span class="chip blue" onclick="quick('place 4 cyan cones scattered')">4 cones random</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Animation</div>
            <div class="chips">
              <span class="chip yellow" onclick="quick('spin')">spin last</span>
              <span class="chip yellow" onclick="quick('bounce')">bounce last</span>
              <span class="chip yellow" onclick="quick('pulse')">pulse last</span>
              <span class="chip yellow" onclick="quick('stop animation')">stop anim</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Lighting</div>
            <div class="chips">
              <span class="chip green" onclick="quick('day')">day</span>
              <span class="chip green" onclick="quick('night')">night</span>
              <span class="chip green" onclick="quick('sunrise')">sunrise</span>
              <span class="chip green" onclick="quick('neon lights')">neon</span>
              <span class="chip green" onclick="quick('brighter')">brighter</span>
              <span class="chip green" onclick="quick('dimmer')">dimmer</span>
              <span class="chip green" onclick="quick('add spotlight')">spotlight</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Camera</div>
            <div class="chips">
              <span class="chip" onclick="quick('reset camera')">reset</span>
              <span class="chip" onclick="quick('top view')">top</span>
              <span class="chip" onclick="quick('front view')">front</span>
              <span class="chip" onclick="quick('side view')">side</span>
              <span class="chip" onclick="quick('isometric view')">iso</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Archive</div>
            <div class="chips">
              <span class="chip red" onclick="quick('load hello')">hello world</span>
              <span class="chip red" onclick="quick('load fog')">fog</span>
              <span class="chip red" onclick="quick('load text')">text</span>
            </div>
          </div>
          <div class="chip-group">
            <div class="chip-group-label">Scene</div>
            <div class="chips">
              <span class="chip" onclick="quick('what is in the scene')">inspect</span>
              <span class="chip" onclick="quick('undo')">undo</span>
              <span class="chip" onclick="quick('clear')">clear</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Saves tab -->
      <div class="tab-content" id="tab-saves">
        <div class="saves-panel">
          <div class="save-row">
            <input class="save-input" id="saveName" placeholder="scene name…" />
            <button class="save-btn" onclick="saveScene()">Save</button>
          </div>
          <div class="saves-list" id="savesList">
            <div class="saves-empty">No saved scenes yet.</div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <textarea id="inp" rows="2" placeholder="spawn a ruby donut… add 5 spheres in a row… night… spin…"></textarea>
        <div class="btn-row">
          <button id="runBtn" onclick="run()">&#9654; Run</button>
          <button id="clearBtn" onclick="clearAll()">&#10005; Clear</button>
        </div>
        <div class="hint">Enter to run &bull; Drag to orbit &bull; Scroll to zoom</div>
      </div>
    </div>
  </div>
</div>

<script>
  const logEl   = document.getElementById('log');
  const inp     = document.getElementById('inp');
  const runBtn  = document.getElementById('runBtn');
  const canvas  = document.getElementById('canvas');

  // ── Tabs ────────────────────────────────────────────────────────────────────
  function switchTab(name) {
    document.querySelectorAll('.tab').forEach((t,i) => {
      const names = ['console','chips','saves'];
      t.classList.toggle('active', names[i] === name);
    });
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    if (name === 'saves') loadSavesList();
  }

  // ── Object list ─────────────────────────────────────────────────────────────
  let objListVisible = false;
  function toggleObjList() {
    objListVisible = !objListVisible;
    document.getElementById('objList').classList.toggle('visible', objListVisible);
    if (objListVisible) refreshObjList();
  }
  async function refreshObjList() {
    const res = await fetch('/api/inspect');
    const data = await res.json();
    const el = document.getElementById('objListItems');
    if (!data.objects || data.objects.length === 0) {
      el.innerHTML = '<em style="color:#444">Empty</em>';
    } else {
      el.innerHTML = data.objects.map((o,i) =>
        `<div class="obj-item">${i+1}. ${o.color_name || ''} ${o.shape}</div>`
      ).join('');
    }
  }

  // ── Logging ─────────────────────────────────────────────────────────────────
  function addLog(cls, label, text) {
    const d = document.createElement('div');
    d.className = 'entry ' + cls;
    d.innerHTML = '<div class="lbl">' + label + '</div>' +
      String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/\\n/g,'<br>');
    logEl.appendChild(d);
    logEl.scrollTop = logEl.scrollHeight;
    // Auto-switch to console tab to show response
    switchTab('console');
  }

  // ── Reload scene ────────────────────────────────────────────────────────────
  function reload() {
    const url = '/scene.x3d?t=' + Date.now();
    try {
      if (canvas.browser) canvas.browser.loadURL(new X3D.MFString(url));
      else canvas.setAttribute('src', url);
    } catch(e) { canvas.setAttribute('src', url); }
    if (objListVisible) setTimeout(refreshObjList, 300);
  }

  // ── Run prompt ──────────────────────────────────────────────────────────────
  async function run() {
    const text = inp.value.trim();
    if (!text) return;
    addLog('user', 'You', text);
    inp.value = '';
    runBtn.disabled = true;
    try {
      const res  = await fetch('/api/agent', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: text})
      });
      const data = await res.json();
      if (res.ok) {
        const cls = data.status === 'success' ? 'ai' : 'info';
        addLog(cls, 'Scene', data.message);
        reload();
      } else {
        addLog('error', 'Error', data.detail || 'Unknown error');
      }
    } catch(e) { addLog('error', 'Network', e.message); }
    finally { runBtn.disabled = false; }
  }

  async function clearAll() {
    await fetch('/api/clear', {method: 'POST'});
    addLog('sys', 'System', 'Scene cleared.');
    reload();
  }

  function quick(text) { inp.value = text; run(); }

  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run(); }
  });

  // ── Saves ────────────────────────────────────────────────────────────────────
  async function saveScene() {
    const name = document.getElementById('saveName').value.trim();
    if (!name) return;
    const res = await fetch('/api/save', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    const data = await res.json();
    addLog('ai', 'Save', data.message || 'Saved.');
    document.getElementById('saveName').value = '';
    loadSavesList();
  }

  async function loadSaveScene(name) {
    const res = await fetch('/api/load/' + encodeURIComponent(name), {method: 'POST'});
    const data = await res.json();
    addLog('ai', 'Load', data.message || 'Loaded.');
    reload();
  }

  async function loadSavesList() {
    const res = await fetch('/api/saves');
    const data = await res.json();
    const el = document.getElementById('savesList');
    if (!data.saves || data.saves.length === 0) {
      el.innerHTML = '<div class="saves-empty">No saved scenes yet.</div>';
    } else {
      el.innerHTML = data.saves.map(name =>
        `<div class="save-item">
          <span class="save-item-name">&#128190; ${name}</span>
          <button class="save-item-btn" onclick="loadSaveScene('${name}')">Load</button>
        </div>`
      ).join('');
    }
  }
</script>
</body>
</html>
"""
