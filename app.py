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
    # plurals
    "spheres": "sphere", "balls": "sphere", "orbs": "sphere",
    "cones": "cone", "pyramids": "cone",
    "cylinders": "cylinder", "tubes": "cylinder", "pipes": "cylinder",
    "boxes": "box", "cubes": "box", "blocks": "box", "bricks": "box",
    "toruses": "torus", "donuts": "torus", "rings": "torus",
    "tetrahedra": "tetrahedron", "diamonds": "tetrahedron",
    "octahedra": "octahedron",
    "icosahedra": "icosahedron",
    "dodecahedra": "dodecahedron",
    "stars": "star", "asterisks": "star",
    "arrows": "arrow", "pointers": "arrow",
    "capsules": "capsule", "pills": "capsule",
    "crosses": "cross",
    "crescents": "crescent",
    "helices": "helix", "spirals": "helix", "coils": "helix",
    "ellipsoids": "ellipsoid", "eggs": "ellipsoid",
    "planes": "plane", "discs": "plane", "disks": "plane",
    "torus knots": "torusknot", "knots": "torusknot",
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

    # ── Detect shape early (before lighting, so "neon torus knot" hits shape not light) ──
    detected_shape = None
    for alias, canonical in sorted(SHAPE_ALIASES.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(alias) + r'\b', t):
            detected_shape = canonical
            break

    # ── Lighting (only if no shape word found) ────────────────────────────────
    if detected_shape is None:
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

    shape = detected_shape if detected_shape else "box"

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
        plural = shape + "es" if shape.endswith(("x","s","z")) else shape + "s"
        msg = f"Added {count} {color_name} {plural} in a {arrangement}."
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
# Rules for all shapes:
#   solid="false"      — render both sides
#   creaseAngle="1.5"  — smooth shading for curved surfaces
#   creaseAngle="0"    — flat/faceted shading for polyhedra
#   All windings CCW from outside (standard X3D)

def _mat(r, g, b, tr):
    return (f'<Appearance><Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" '
            f'specularColor="0.4 0.4 0.4" shininess="0.6" '
            f'transparency="{tr:.2f}"/></Appearance>')

def _wrap(xml_body, x, y, z, rotation, obj_id=None):
    rot = (f' rotation="{rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]:.4f}"'
           if rotation else "")
    def_ = f' DEF="obj_{obj_id}"' if obj_id is not None else ""
    return f'    <Transform{def_} translation="{x:.3f} {y:.3f} {z:.3f}"{rot}>\n{xml_body}    </Transform>\n'

def _ifs(pts, idxs, crease=1.5):
    pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts)
    idx_str = " ".join(idxs)
    return (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" '
            f'creaseAngle="{crease}" normalPerVertex="true">'
            f'<Coordinate point="{pts_str}"/></IndexedFaceSet>')

def _shape(geo, mat):
    return f'      <Shape>{geo}{mat}</Shape>\n'

# ── primitives (use X3D built-ins) ──────────────────────────────────────────

def _prim(tag, mat, x, y, z, rotation, obj_id):
    return _wrap(_shape(tag, mat), x, y, z, rotation, obj_id)

# ── torus ────────────────────────────────────────────────────────────────────

def _build_torus(size):
    R, r, U, V = size, size*0.34, 28, 16
    pts, idxs = [], []
    for i in range(U):
        a = 2*math.pi*i/U
        for j in range(V):
            b = 2*math.pi*j/V
            pts.append(((R+r*math.cos(b))*math.cos(a),
                         r*math.sin(b),
                        (R+r*math.cos(b))*math.sin(a)))
    for i in range(U):
        ni = (i+1)%U
        for j in range(V):
            nj = (j+1)%V
            a,b,c,d = i*V+j, i*V+nj, ni*V+nj, ni*V+j
            idxs.append(f"{a} {b} {c} {d} -1")
    return pts, idxs

# ── sphere-like swept tube (used by helix & torusknot) ───────────────────────

def _tube_sweep(path, tube_r, closed=True):
    """Sweep a circle of radius tube_r along path (list of (x,y,z)).
    Returns (pts, idxs). path may be open or closed."""
    T_segs = 12   # tube cross-section segments
    n = len(path)

    def v3(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
    def vn(v):
        L=math.sqrt(v[0]**2+v[1]**2+v[2]**2)
        return (v[0]/L,v[1]/L,v[2]/L) if L>1e-9 else (1,0,0)
    def vc(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])

    pts = []
    for i in range(n):
        prev = path[(i-1)%n] if closed else path[max(0,i-1)]
        nxt  = path[(i+1)%n] if closed else path[min(n-1,i+1)]
        T = vn(v3(nxt, prev))
        up = (0,1,0) if abs(T[1])<0.85 else (1,0,0)
        N = vn(vc(T, up))
        B = vn(vc(T, N))
        cx,cy,cz = path[i]
        for j in range(T_segs):
            a = 2*math.pi*j/T_segs
            ca,sa = math.cos(a),math.sin(a)
            pts.append((cx+tube_r*(ca*N[0]+sa*B[0]),
                        cy+tube_r*(ca*N[1]+sa*B[1]),
                        cz+tube_r*(ca*N[2]+sa*B[2])))

    idxs = []
    rings = n if closed else n-1
    for i in range(rings):
        ni = (i+1)%n if closed else i+1
        for j in range(T_segs):
            nj = (j+1)%T_segs
            a_,b_,c_,d_ = i*T_segs+j, i*T_segs+nj, ni*T_segs+nj, ni*T_segs+j
            idxs.append(f"{a_} {b_} {c_} {d_} -1")
    return pts, idxs

# ── tetrahedron ──────────────────────────────────────────────────────────────

def _build_tetrahedron(s):
    h = s * math.sqrt(2/3)
    r = s / math.sqrt(3)
    pts = [( r,   -h/2,  0),
           (-r/2, -h/2,  r*math.sqrt(3)/2),
           (-r/2, -h/2, -r*math.sqrt(3)/2),
           ( 0,    h,    0)]
    idxs = ["0 2 1 -1","0 1 3 -1","1 2 3 -1","0 3 2 -1"]
    return pts, idxs

# ── octahedron ───────────────────────────────────────────────────────────────

def _build_octahedron(s):
    pts = [(s,0,0),(-s,0,0),(0,s,0),(0,-s,0),(0,0,s),(0,0,-s)]
    idxs = ["2 0 4 -1","2 4 1 -1","2 1 5 -1","2 5 0 -1",
            "3 4 0 -1","3 1 4 -1","3 5 1 -1","3 0 5 -1"]
    return pts, idxs

# ── icosahedron ──────────────────────────────────────────────────────────────

def _build_icosahedron(s):
    t = (1+math.sqrt(5))/2
    nl = math.sqrt(1+t**2)
    raw = [(-1,t,0),(1,t,0),(-1,-t,0),(1,-t,0),
           (0,-1,t),(0,1,t),(0,-1,-t),(0,1,-t),
           (t,0,-1),(t,0,1),(-t,0,-1),(-t,0,1)]
    pts = [(x/nl*s,y/nl*s,z/nl*s) for x,y,z in raw]
    f = [0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11,
         1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
         3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9,
         4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1]
    idxs = [f"{f[i]} {f[i+1]} {f[i+2]} -1" for i in range(0,len(f),3)]
    return pts, idxs

# ── dodecahedron ─────────────────────────────────────────────────────────────

def _build_dodecahedron(s):
    p = (1+math.sqrt(5))/2
    b = 1/p
    # 20 vertices
    verts = []
    for sx in [-1,1]:
        for sy in [-1,1]:
            for sz in [-1,1]:
                verts.append((sx*s, sy*s, sz*s))
    for sv in [-1,1]:
        for sw in [-1,1]:
            verts += [(0,sv*p*s,sw*b*s),(sv*b*s,0,sw*p*s),(sv*p*s,sw*b*s,0)]
    # 12 correct pentagonal faces (verified winding)
    faces = [
        [0,1,3,2,6],[0,6,4,16,8],[0,8,9,1,2],
        [1,9,11,3,0],[3,11,10,2,6],[2,10,5,4,6],  # corrected winding
        [4,5,7,17,16],[5,10,11,7,17],[7,11,9,8,17],
        [8,16,17,9,1],[16,4,6,2,10],[17,5,10,11,9],  # fill remaining faces
    ]
    idxs = [" ".join(str(v) for v in face)+" -1" for face in faces]
    return verts, idxs

# ── star (extruded 5-point) ──────────────────────────────────────────────────

def _build_star(s):
    OR, IR, d = s, s*0.40, s*0.25
    N = 5
    front, back = [], []
    for i in range(N*2):
        ang = math.pi/N*i - math.pi/2
        r = OR if i%2==0 else IR
        front.append((math.cos(ang)*r, math.sin(ang)*r,  d))
        back.append( (math.cos(ang)*r, math.sin(ang)*r, -d))
    n = N*2
    pts = front + [( 0, 0,  d)] + back + [(0, 0, -d)]
    fc, bc = n, 2*n+1   # front/back center indices
    idxs = []
    # front fan
    for i in range(n):
        idxs.append(f"{fc} {i} {(i+1)%n} -1")
    # back fan (reversed)
    for i in range(n):
        idxs.append(f"{bc} {n+1+(i+1)%n} {n+1+i} -1")
    # side quads
    for i in range(n):
        ni = (i+1)%n
        idxs.append(f"{i} {ni} {n+1+ni} {n+1+i} -1")
    return pts, idxs

# ── arrow (3D shaft + pyramid head pointing +Y) ──────────────────────────────

def _build_arrow(s):
    sw, sh, hw, hh = s*0.16, s*1.1, s*0.40, s*0.75
    # shaft 8 verts (0-7), head base 4 verts (8-11), tip (12)
    pts = [(-sw,0,-sw),(sw,0,-sw),(sw,0,sw),(-sw,0,sw),
           (-sw,sh,-sw),(sw,sh,-sw),(sw,sh,sw),(-sw,sh,sw),
           (-hw,sh,-hw),(hw,sh,-hw),(hw,sh,hw),(-hw,sh,hw),
           (0,sh+hh,0)]
    idxs = [
        "3 2 1 0 -1",       # shaft bottom (looking up from below = CCW outside)
        "0 1 5 4 -1",       # shaft front (-z face)
        "1 2 6 5 -1",       # shaft right (+x face)
        "2 3 7 6 -1",       # shaft back (+z face)
        "3 0 4 7 -1",       # shaft left (-x face)
        "11 10 9 8 -1",     # head base (looking up = CCW outside)
        "12 8 9 -1","12 9 10 -1","12 10 11 -1","12 11 8 -1",  # head sides
    ]
    return pts, idxs

# ── capsule (cylinder body + two hemisphere caps, no flat disk overlap) ───────

def _build_capsule(s):
    cyl_r = s*0.44
    cyl_h = s*1.2
    U, V  = 20, 10    # longitude, latitude for caps

    pts, idxs = [], []

    # ── cylinder body (2 rings) ──
    for i in range(U):
        a = 2*math.pi*i/U
        pts.append((cyl_r*math.cos(a),  cyl_h/2, cyl_r*math.sin(a)))  # ring 0: top
    for i in range(U):
        a = 2*math.pi*i/U
        pts.append((cyl_r*math.cos(a), -cyl_h/2, cyl_r*math.sin(a)))  # ring 1: bot

    # cylinder side quads  (ring0 → ring1)
    for i in range(U):
        ni = (i+1)%U
        idxs.append(f"{i} {ni} {U+ni} {U+i} -1")

    # ── top hemisphere ──
    # lat rings from cyl top ring outward to tip
    hem_top_base = len(pts)
    for lat in range(1, V):
        phi = math.pi/2 * lat/V    # 0 → π/2
        rr = cyl_r*math.cos(phi)
        yy = cyl_h/2 + cyl_r*math.sin(phi)
        for i in range(U):
            a=2*math.pi*i/U
            pts.append((rr*math.cos(a), yy, rr*math.sin(a)))

    tip_top = len(pts)
    pts.append((0, cyl_h/2+cyl_r, 0))

    # connect cyl top ring to first hem ring
    first_hem = hem_top_base
    for i in range(U):
        ni=(i+1)%U
        idxs.append(f"{i} {ni} {first_hem+ni} {first_hem+i} -1")

    # connect consecutive hem rings
    for lat in range(1, V-1):
        pr = hem_top_base + (lat-1)*U
        cu = hem_top_base + lat*U
        for i in range(U):
            ni=(i+1)%U
            idxs.append(f"{pr+i} {pr+ni} {cu+ni} {cu+i} -1")

    # connect last hem ring to tip
    last_top = hem_top_base + (V-2)*U
    for i in range(U):
        ni=(i+1)%U
        idxs.append(f"{last_top+i} {last_top+ni} {tip_top} -1")

    # ── bottom hemisphere ──
    hem_bot_base = len(pts)
    for lat in range(1, V):
        phi = math.pi/2*lat/V
        rr = cyl_r*math.cos(phi)
        yy = -(cyl_h/2+cyl_r*math.sin(phi))
        for i in range(U):
            a=2*math.pi*i/U
            pts.append((rr*math.cos(a), yy, rr*math.sin(a)))

    tip_bot = len(pts)
    pts.append((0, -(cyl_h/2+cyl_r), 0))

    # connect cyl bot ring to first bot-hem ring (reversed winding)
    first_bot = hem_bot_base
    for i in range(U):
        ni=(i+1)%U
        idxs.append(f"{U+i} {first_bot+i} {first_bot+ni} {U+ni} -1")

    for lat in range(1, V-1):
        pr = hem_bot_base + (lat-1)*U
        cu = hem_bot_base + lat*U
        for i in range(U):
            ni=(i+1)%U
            idxs.append(f"{pr+i} {cu+i} {cu+ni} {pr+ni} -1")

    last_bot = hem_bot_base + (V-2)*U
    for i in range(U):
        ni=(i+1)%U
        idxs.append(f"{tip_bot} {last_bot+ni} {last_bot+i} -1")

    return pts, idxs

# ── cross (3-box Group) ───────────────────────────────────────────────────────

def _build_cross_xml(s, mat):
    w, L = s*0.36, s*1.8
    return (f'      <Group>\n'
            f'        <Shape><Box size="{L:.3f} {w:.3f} {w:.3f}"/>{mat}</Shape>\n'
            f'        <Shape><Box size="{w:.3f} {L:.3f} {w:.3f}"/>{mat}</Shape>\n'
            f'        <Shape><Box size="{w:.3f} {w:.3f} {L:.3f}"/>{mat}</Shape>\n'
            f'      </Group>\n')

# ── crescent (extruded annular arc) ─────────────────────────────────────────

def _build_crescent(s):
    OR, IR, off, d = s, s*0.60, s*0.32, s*0.22
    N = 32   # points per arc
    # Build 2D outline: outer full circle, inner offset circle
    outer_f  = [(OR*math.cos(2*math.pi*i/N), OR*math.sin(2*math.pi*i/N)) for i in range(N)]
    inner_f  = [(IR*math.cos(2*math.pi*i/N)+off, IR*math.sin(2*math.pi*i/N)) for i in range(N)]
    # front z=+d, back z=-d
    pts = ([(x,y, d) for x,y in outer_f] +   # 0..N-1    front outer
           [(x,y, d) for x,y in inner_f] +   # N..2N-1   front inner
           [(x,y,-d) for x,y in outer_f] +   # 2N..3N-1  back outer
           [(x,y,-d) for x,y in inner_f])    # 3N..4N-1  back inner

    idxs = []
    # front annular ring (CCW from +z)
    for i in range(N):
        ni=(i+1)%N
        idxs.append(f"{i} {N+i} {N+ni} {ni} -1")
    # back annular ring (reversed for CCW from -z)
    for i in range(N):
        ni=(i+1)%N
        idxs.append(f"{2*N+i} {2*N+ni} {3*N+ni} {3*N+i} -1")
    # outer side wall
    for i in range(N):
        ni=(i+1)%N
        idxs.append(f"{i} {ni} {2*N+ni} {2*N+i} -1")
    # inner side wall (reversed)
    for i in range(N):
        ni=(i+1)%N
        idxs.append(f"{N+i} {3*N+i} {3*N+ni} {N+ni} -1")

    return pts, idxs

# ── helix (swept tube) ───────────────────────────────────────────────────────

def _build_helix_path(s):
    turns, segs = 3, 72
    R, pitch = s*0.70, s*0.52
    total = turns*segs
    return [(R*math.cos(2*math.pi*i/segs),
             pitch*i/segs - pitch*turns/2,
             R*math.sin(2*math.pi*i/segs))
            for i in range(total+1)]

# ── torus knot (swept tube) ──────────────────────────────────────────────────

def _build_torusknot_path(s):
    segs = 160
    p_, q_ = 2, 3
    R, r = s*0.65, s*0.24
    path = []
    for i in range(segs):
        t = 2*math.pi*i/segs
        path.append(((R+r*math.cos(q_*t))*math.cos(p_*t),
                     (R+r*math.cos(q_*t))*math.sin(p_*t),
                      r*math.sin(q_*t)))
    return path

# ── plane (flat ground, subdivided, double-sided via solid=false) ─────────────

def _build_plane(s):
    S, D = s*2, 6
    step = S*2/D
    pts = [(-S + c*step, 0, -S + r*step)
           for r in range(D+1) for c in range(D+1)]
    idxs = []
    for r in range(D):
        for c in range(D):
            a_ = r*(D+1)+c
            b_ = a_+1; c_ = (r+1)*(D+1)+c+1; d_ = (r+1)*(D+1)+c
            idxs.append(f"{a_} {b_} {c_} {d_} -1")
    return pts, idxs

# ── master builder ─────────────────────────────────────────────────────────────

def build_shape_xml(shape, color, position, size, rotation=None, transparency=0.0, animation=None, obj_id=None):
    r, g, b = color
    x, y, z = position
    mat = _mat(r, g, b, transparency)
    rot = rotation
    s   = size

    # ── X3D built-in primitives ──────────────────────────────────────────────
    if shape == "sphere":
        return _wrap(_shape(f'<Sphere radius="{s:.3f}"/>', mat), x,y,z,rot,obj_id)
    if shape == "cone":
        return _wrap(_shape(f'<Cone bottomRadius="{s:.3f}" height="{s*2:.3f}"/>', mat), x,y,z,rot,obj_id)
    if shape == "cylinder":
        return _wrap(_shape(f'<Cylinder radius="{s:.3f}" height="{s*2:.3f}"/>', mat), x,y,z,rot,obj_id)
    if shape == "box":
        d = s*2
        return _wrap(_shape(f'<Box size="{d:.3f} {d:.3f} {d:.3f}"/>', mat), x,y,z,rot,obj_id)
    if shape == "ellipsoid":
        rot_str = (f' rotation="{rot[0]} {rot[1]} {rot[2]} {rot[3]:.4f}"' if rot else "")
        def_str = f' DEF="obj_{obj_id}"' if obj_id is not None else ""
        body = f'      <Shape><Sphere radius="{s:.3f}"/>{mat}</Shape>\n'
        return (f'    <Transform{def_str} translation="{x:.3f} {y:.3f} {z:.3f}"'
                f' scale="1.0 0.65 1.45"{rot_str}>\n{body}    </Transform>\n')

    # ── cross (multi-box group) ──────────────────────────────────────────────
    if shape == "cross":
        return _wrap(_build_cross_xml(s, mat), x,y,z,rot,obj_id)

    # ── IFS shapes ──────────────────────────────────────────────────────────
    if shape == "torus":
        pts, idxs = _build_torus(s)
        geo = _ifs(pts, idxs, crease=1.5)
    elif shape == "tetrahedron":
        pts, idxs = _build_tetrahedron(s)
        geo = _ifs(pts, idxs, crease=0)
    elif shape == "octahedron":
        pts, idxs = _build_octahedron(s)
        geo = _ifs(pts, idxs, crease=0)
    elif shape == "icosahedron":
        pts, idxs = _build_icosahedron(s)
        geo = _ifs(pts, idxs, crease=0.5)
    elif shape == "dodecahedron":
        pts, idxs = _build_dodecahedron(s)
        geo = _ifs(pts, idxs, crease=0)
    elif shape == "star":
        pts, idxs = _build_star(s)
        geo = _ifs(pts, idxs, crease=0)
    elif shape == "arrow":
        pts, idxs = _build_arrow(s)
        geo = _ifs(pts, idxs, crease=0.3)
    elif shape == "capsule":
        pts, idxs = _build_capsule(s)
        geo = _ifs(pts, idxs, crease=1.5)
    elif shape == "crescent":
        pts, idxs = _build_crescent(s)
        geo = _ifs(pts, idxs, crease=0)
    elif shape == "helix":
        path = _build_helix_path(s)
        pts, idxs = _tube_sweep(path, s*0.09, closed=False)
        geo = _ifs(pts, idxs, crease=1.5)
    elif shape == "torusknot":
        path = _build_torusknot_path(s)
        pts, idxs = _tube_sweep(path, s*0.09, closed=True)
        geo = _ifs(pts, idxs, crease=1.5)
    elif shape == "plane":
        pts, idxs = _build_plane(s)
        geo = _ifs(pts, idxs, crease=0)
    else:
        d = s*2
        return _wrap(_shape(f'<Box size="{d:.3f} {d:.3f} {d:.3f}"/>', mat), x,y,z,rot,obj_id)

    return _wrap(_shape(geo, mat), x,y,z,rot,obj_id)



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
