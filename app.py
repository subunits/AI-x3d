import os
import re
import math
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SCENE_FILE = "scene.x3d"
DEFAULT_X3D = '''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "http://www.web3d.org/specifications/x3d-3.3.dtd">
<X3D profile="Immersive" version="3.3">
  <Scene>
    <Background skyColor="0.08 0.08 0.12"/>
    <NavigationInfo type="EXAMINE ANY"/>
    <DirectionalLight direction="-1 -2 -1" intensity="1.0"/>
    <DirectionalLight direction="1 1 0.5" intensity="0.5" color="0.8 0.8 1"/>
  </Scene>
</X3D>
'''

# ── Colors ────────────────────────────────────────────────────────────────────
COLORS = {
    "red":       (1.00, 0.00, 0.00),
    "green":     (0.00, 0.80, 0.00),
    "blue":      (0.00, 0.40, 1.00),
    "yellow":    (1.00, 1.00, 0.00),
    "orange":    (1.00, 0.50, 0.00),
    "purple":    (0.50, 0.00, 0.80),
    "violet":    (0.50, 0.00, 0.80),
    "pink":      (1.00, 0.40, 0.70),
    "magenta":   (1.00, 0.00, 1.00),
    "cyan":      (0.00, 1.00, 1.00),
    "teal":      (0.00, 0.50, 0.50),
    "white":     (1.00, 1.00, 1.00),
    "black":     (0.05, 0.05, 0.05),
    "gray":      (0.50, 0.50, 0.50),
    "grey":      (0.50, 0.50, 0.50),
    "brown":     (0.50, 0.25, 0.10),
    "gold":      (1.00, 0.84, 0.00),
    "silver":    (0.75, 0.75, 0.75),
    "lime":      (0.20, 1.00, 0.00),
    "indigo":    (0.29, 0.00, 0.51),
    "turquoise": (0.25, 0.88, 0.82),
    "crimson":   (0.86, 0.08, 0.24),
    "coral":     (1.00, 0.50, 0.31),
    "salmon":    (0.98, 0.50, 0.45),
    "navy":      (0.00, 0.00, 0.50),
    "maroon":    (0.50, 0.00, 0.00),
    "olive":     (0.50, 0.50, 0.00),
    "tan":       (0.82, 0.71, 0.55),
    "beige":     (0.96, 0.96, 0.86),
    "ivory":     (1.00, 1.00, 0.94),
    "ruby":      (0.88, 0.07, 0.37),
    "emerald":   (0.31, 0.78, 0.47),
    "sapphire":  (0.06, 0.32, 0.73),
    "amber":     (1.00, 0.75, 0.00),
    "bronze":    (0.80, 0.50, 0.20),
    "copper":    (0.72, 0.45, 0.20),
    "neon":      (0.22, 1.00, 0.08),
    "electric":  (0.00, 0.60, 1.00),
    "hot":       (1.00, 0.07, 0.57),
    "dark":      (0.15, 0.15, 0.15),
    "light":     (0.85, 0.85, 0.85),
    "transparent":(0.50, 0.50, 0.50),
    # new
    "lavender":  (0.71, 0.49, 0.86),
    "mint":      (0.60, 1.00, 0.80),
    "peach":     (1.00, 0.80, 0.64),
    "rose":      (1.00, 0.30, 0.50),
    "lilac":     (0.78, 0.64, 0.78),
    "chartreuse":(0.50, 1.00, 0.00),
    "aqua":      (0.00, 1.00, 1.00),
    "sand":      (0.76, 0.70, 0.50),
    "rust":      (0.72, 0.25, 0.05),
    "scarlet":   (1.00, 0.14, 0.00),
    "violet":    (0.56, 0.00, 1.00),
    "plum":      (0.56, 0.27, 0.52),
    "slate":     (0.44, 0.50, 0.56),
    "cream":     (1.00, 0.99, 0.82),
    "jade":      (0.00, 0.66, 0.42),
    "cobalt":    (0.00, 0.28, 0.67),
    "magma":     (0.90, 0.20, 0.00),
    "ice":       (0.80, 0.95, 1.00),
    "lemon":     (1.00, 0.97, 0.00),
    "wine":      (0.45, 0.00, 0.13),
}

# ── Sizes ─────────────────────────────────────────────────────────────────────
SIZES = {
    "microscopic": 0.1,
    "atomic":      0.1,
    "invisible":   0.05,
    "tiny":        0.25,
    "mini":        0.3,
    "miniature":   0.3,
    "petite":      0.35,
    "small":       0.5,
    "little":      0.5,
    "compact":     0.5,
    "slim":        0.5,
    "medium":      0.8,
    "normal":      0.8,
    "average":     0.8,
    "standard":    0.8,
    "big":         1.3,
    "large":       1.5,
    "tall":        1.5,
    "wide":        1.5,
    "thick":       1.3,
    "huge":        2.0,
    "giant":       2.5,
    "enormous":    3.0,
    "massive":     3.5,
    "colossal":    4.0,
    "titanic":     4.5,
    "immense":     3.0,
    "grand":       2.0,
    "towering":    2.5,
}

# ── Named positions ───────────────────────────────────────────────────────────
POSITIONS = {
    # two-word first (sorted by length in parse_position)
    "far left":      (-6.0,  0.0,  0.0),
    "far right":     ( 6.0,  0.0,  0.0),
    "far above":     ( 0.0,  6.0,  0.0),
    "far below":     ( 0.0, -6.0,  0.0),
    "far behind":    ( 0.0,  0.0, -6.0),
    "far front":     ( 0.0,  0.0,  6.0),
    "top left":      (-3.0,  3.0,  0.0),
    "top right":     ( 3.0,  3.0,  0.0),
    "bottom left":   (-3.0, -3.0,  0.0),
    "bottom right":  ( 3.0, -3.0,  0.0),
    "upper left":    (-3.0,  3.0,  0.0),
    "upper right":   ( 3.0,  3.0,  0.0),
    "lower left":    (-3.0, -3.0,  0.0),
    "lower right":   ( 3.0, -3.0,  0.0),
    "on top":        ( 0.0,  3.5,  0.0),
    "up high":       ( 0.0,  5.0,  0.0),
    "way up":        ( 0.0,  6.0,  0.0),
    "way down":      ( 0.0, -6.0,  0.0),
    "in front":      ( 0.0,  0.0,  4.0),
    "in back":       ( 0.0,  0.0, -4.0),
    "underground":   ( 0.0, -4.0,  0.0),
    "floating":      ( 0.0,  4.0,  0.0),
    "overhead":      ( 0.0,  5.0,  0.0),
    # single-word
    "left":          (-3.0,  0.0,  0.0),
    "right":         ( 3.0,  0.0,  0.0),
    "above":         ( 0.0,  3.0,  0.0),
    "up":            ( 0.0,  3.0,  0.0),
    "high":          ( 0.0,  4.0,  0.0),
    "below":         ( 0.0, -3.0,  0.0),
    "down":          ( 0.0, -3.0,  0.0),
    "beneath":       ( 0.0, -3.0,  0.0),
    "under":         ( 0.0, -3.0,  0.0),
    "behind":        ( 0.0,  0.0, -3.0),
    "back":          ( 0.0,  0.0, -3.0),
    "front":         ( 0.0,  0.0,  3.0),
    "forward":       ( 0.0,  0.0,  3.0),
    "near":          ( 0.0,  0.0,  3.0),
    "center":        ( 0.0,  0.0,  0.0),
    "middle":        ( 0.0,  0.0,  0.0),
    "here":          ( 0.0,  0.0,  0.0),
    "origin":        ( 0.0,  0.0,  0.0),
}

# ── Shapes ────────────────────────────────────────────────────────────────────
SHAPE_ALIASES = {
    # sphere
    "sphere":        "sphere",
    "ball":          "sphere",
    "orb":           "sphere",
    "globe":         "sphere",
    "bubble":        "sphere",
    "marble":        "sphere",
    "bead":          "sphere",
    "planet":        "sphere",
    "moon":          "sphere",
    # cone
    "cone":          "cone",
    "pyramid":       "cone",
    "triangle":      "cone",
    "hat":           "cone",
    "spike":         "cone",
    "tip":           "cone",
    "funnel":        "cone",
    "mountain":      "cone",
    # cylinder
    "cylinder":      "cylinder",
    "tube":          "cylinder",
    "pipe":          "cylinder",
    "pillar":        "cylinder",
    "column":        "cylinder",
    "barrel":        "cylinder",
    "capsule":       "cylinder",
    "rod":           "cylinder",
    "pole":          "cylinder",
    "straw":         "cylinder",
    "can":           "cylinder",
    "drum":          "cylinder",
    # box
    "box":           "box",
    "cube":          "box",
    "block":         "box",
    "brick":         "box",
    "square":        "box",
    "rectangle":     "box",
    "crate":         "box",
    "chest":         "box",
    "slab":          "box",
    "tile":          "box",
    # torus
    "torus":         "torus",
    "donut":         "torus",
    "doughnut":      "torus",
    "ring":          "torus",
    "loop":          "torus",
    "hoop":          "torus",
    "wreath":        "torus",
    "bracelet":      "torus",
    "life preserver":"torus",
    # tetrahedron
    "tetrahedron":   "tetrahedron",
    "diamond":       "tetrahedron",
    "gem":           "tetrahedron",
    "crystal":       "tetrahedron",
    "prism":         "tetrahedron",
    # octahedron (new)
    "octahedron":    "octahedron",
    "d8":            "octahedron",
    "double pyramid":"octahedron",
    "bipyramid":     "octahedron",
    # icosahedron (new)
    "icosahedron":   "icosahedron",
    "d20":           "icosahedron",
    "geodesic":      "icosahedron",
    "soccer":        "icosahedron",
    # star (new)
    "star":          "star",
    "asterisk":      "star",
    "burst":         "star",
    "sparkle":       "star",
    "starburst":     "star",
    # arrow (new)
    "arrow":         "arrow",
    "pointer":       "arrow",
    "chevron":       "arrow",
    # plane
    "plane":         "plane",
    "flat":          "plane",
    "floor":         "plane",
    "ground":        "plane",
    "disc":          "plane",
    "disk":          "plane",
    "pad":           "plane",
    "platform":      "plane",
    "sheet":         "plane",
    "surface":       "plane",
    # ellipsoid
    "ellipsoid":     "ellipsoid",
    "egg":           "ellipsoid",
    "oval":          "ellipsoid",
    "blob":          "ellipsoid",
    "oblong":        "ellipsoid",
    # helix (new)
    "helix":         "helix",
    "spiral":        "helix",
    "coil":          "helix",
    "spring":        "helix",
    "screw":         "helix",
}

# ── Add-intent verbs ──────────────────────────────────────────────────────────
ADD_VERBS = (
    "add", "put", "place", "create", "make", "drop", "spawn",
    "throw", "insert", "include", "generate", "draw", "build",
    "give me", "show me", "i want", "i need", "gimme",
)

# ── Clear-intent phrases ──────────────────────────────────────────────────────
CLEAR_PHRASES = (
    "clear", "reset", "remove all", "delete all", "wipe", "empty",
    "start over", "start fresh", "start from scratch", "scratch this",
    "clean slate", "erase", "nuke", "blow it up", "destroy",
    "fresh start", "new scene",
)

# ── Remove-last intent ────────────────────────────────────────────────────────
REMOVE_PHRASES = (
    "remove", "delete", "undo", "take away", "get rid of",
    "pop", "erase last", "remove last", "delete last",
)


def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_X3D)


ensure_scene_file()


class PromptRequest(BaseModel):
    prompt: str


def parse_color(t: str):
    # Multi-word colors (e.g. "hot pink", "dark blue")
    two_word = re.search(
        r'(hot|dark|light|neon|electric|deep|bright|pale|sky|forest|lime|baby|ocean|fire|ice|rose|blood|mint|sand)\s+'
        r'(red|green|blue|pink|orange|purple|yellow|cyan|gray|grey|brown|white|black|gold)',
        t
    )
    if two_word:
        modifier = two_word.group(1)
        base = two_word.group(2)
        combos = {
            ("hot",    "pink"):   (1.00, 0.07, 0.57),
            ("dark",   "red"):    (0.55, 0.00, 0.00),
            ("dark",   "blue"):   (0.00, 0.00, 0.55),
            ("dark",   "green"):  (0.00, 0.39, 0.00),
            ("dark",   "purple"): (0.25, 0.00, 0.40),
            ("dark",   "gray"):   (0.20, 0.20, 0.20),
            ("dark",   "grey"):   (0.20, 0.20, 0.20),
            ("light",  "blue"):   (0.53, 0.81, 0.98),
            ("light",  "green"):  (0.56, 0.93, 0.56),
            ("light",  "pink"):   (1.00, 0.71, 0.76),
            ("light",  "gray"):   (0.83, 0.83, 0.83),
            ("light",  "grey"):   (0.83, 0.83, 0.83),
            ("neon",   "green"):  (0.22, 1.00, 0.08),
            ("neon",   "pink"):   (1.00, 0.08, 0.58),
            ("neon",   "yellow"): (1.00, 1.00, 0.00),
            ("neon",   "orange"): (1.00, 0.45, 0.00),
            ("neon",   "blue"):   (0.10, 0.40, 1.00),
            ("electric","blue"):  (0.00, 0.60, 1.00),
            ("electric","green"): (0.00, 1.00, 0.20),
            ("deep",   "purple"): (0.29, 0.00, 0.51),
            ("deep",   "blue"):   (0.00, 0.00, 0.70),
            ("deep",   "red"):    (0.60, 0.00, 0.00),
            ("bright", "orange"): (1.00, 0.65, 0.00),
            ("bright", "yellow"): (1.00, 1.00, 0.20),
            ("bright", "green"):  (0.00, 1.00, 0.20),
            ("sky",    "blue"):   (0.53, 0.81, 0.98),
            ("forest", "green"):  (0.13, 0.55, 0.13),
            ("lime",   "green"):  (0.20, 1.00, 0.00),
            ("baby",   "blue"):   (0.54, 0.81, 0.94),
            ("baby",   "pink"):   (1.00, 0.85, 0.88),
            ("ocean",  "blue"):   (0.00, 0.47, 0.75),
            ("fire",   "red"):    (1.00, 0.15, 0.00),
            ("fire",   "orange"): (1.00, 0.40, 0.00),
            ("ice",    "blue"):   (0.80, 0.95, 1.00),
            ("rose",   "gold"):   (0.91, 0.67, 0.62),
            ("blood",  "red"):    (0.65, 0.00, 0.00),
            ("mint",   "green"):  (0.60, 1.00, 0.80),
            ("sand",   "brown"):  (0.76, 0.70, 0.50),
            ("pale",   "blue"):   (0.69, 0.87, 0.90),
            ("pale",   "pink"):   (0.98, 0.85, 0.87),
        }
        return combos.get((modifier, base), COLORS.get(base, (0.4, 0.6, 1.0)))

    # Hex color: #rrggbb or #rgb
    hex_match = re.search(r'#([0-9a-f]{6}|[0-9a-f]{3})\b', t)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        return (int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)

    # RGB values: "rgb 255 0 0" or "color 1.0 0 0"
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
    # Explicit number: "size 2.5" or "radius 1.5" or "scale 3"
    num_match = re.search(r'(?:size|radius|scale|width|height|length)\s+([\d.]+)', t)
    if num_match:
        return min(float(num_match.group(1)), 5.0)
    for word, s in SIZES.items():
        if re.search(r'\b' + re.escape(word) + r'\b', t):
            return s
    return 0.8


def parse_position(t: str):
    # Explicit coords: "at X Y Z" or "position X Y Z"
    coord = re.search(
        r'(?:at|position|pos|translate|move to|place at|put at)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', t
    )
    if coord:
        return (float(coord.group(1)), float(coord.group(2)), float(coord.group(3)))
    # Two-word (and longer) positions first, sorted by descending length
    for phrase, pos in sorted(POSITIONS.items(), key=lambda x: -len(x[0])):
        if phrase in t:
            return pos
    return (0.0, 0.0, 0.0)


def parse_rotation(t: str):
    # "rotated 45 degrees around X" — axis-aware
    axis_rot = re.search(r'rotat\w*\s+([-\d.]+)\s*(?:degrees?|deg)?\s*(?:around|along|on)?\s*(x|y|z)?', t)
    if axis_rot:
        deg = float(axis_rot.group(1))
        rad = deg * math.pi / 180
        axis = axis_rot.group(2) or "y"
        ax = (1, 0, 0) if axis == "x" else (0, 0, 1) if axis == "z" else (0, 1, 0)
        return (*ax, rad)

    # "tilted" / "leaning" / "on its side" → 90° around Z
    if re.search(r'\b(tilt|tilted|lean|leaning|sideways|on its side|on its back)\b', t):
        return (0, 0, 1, math.pi / 2)

    # "upside down" → 180° around Z
    if re.search(r'\b(upside down|inverted|flipped)\b', t):
        return (0, 0, 1, math.pi)

    # "diagonal" → 45° around Z
    if re.search(r'\b(diagonal|angled|slanted)\b', t):
        return (0, 0, 1, math.pi / 4)

    return None


def parse_prompt(text: str) -> dict:
    t = text.lower().strip()

    # ── Clear ────────────────────────────────────────────────────────────────
    if any(w in t for w in CLEAR_PHRASES):
        return {"action": "clear", "message": "Scene cleared."}

    # ── Remove last ──────────────────────────────────────────────────────────
    if any(w in t for w in REMOVE_PHRASES):
        return {"action": "remove_last", "message": "Removed last shape."}

    # ── Determine shape ──────────────────────────────────────────────────────
    shape = "box"
    for alias, canonical in SHAPE_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', t):
            shape = canonical
            break

    color       = parse_color(t)
    size        = parse_size(t)
    position    = parse_position(t)
    rotation    = parse_rotation(t)

    # ── Transparency ─────────────────────────────────────────────────────────
    transparent = any(w in t for w in (
        "transparent", "glass", "see through", "see-through",
        "translucent", "ghostly", "ghost", "crystal clear", "invisible"
    ))
    transparency = 0.6 if transparent else 0.0

    color_name = next((n for n, rgb in COLORS.items() if rgb == color), "colored")
    msg = f"Added {color_name} {shape} (size={size:.2f}) at {position}."

    return {
        "action":       "add",
        "shape":        shape,
        "color":        color,
        "position":     position,
        "size":         size,
        "rotation":     rotation,
        "transparency": transparency,
        "message":      msg,
    }


def build_shape_xml(shape, color, position, size, rotation=None, transparency=0.0):
    r, g, b = color
    x, y, z = position

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
                a = i * steps + j
                b2 = i * steps + (j+1) % steps
                c2 = ((i+1) % steps) * steps + (j+1) % steps
                d = ((i+1) % steps) * steps + j
                idxs.append(f"{a} {b2} {c2} {d} -1")
        geo = (
            f'<IndexedFaceSet coordIndex="{" ".join(idxs)}" solid="false">'
            f'<Coordinate point="{" ".join(pts)}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "tetrahedron":
        s = size
        geo = (
            f'<IndexedFaceSet coordIndex="0 1 2 -1 0 3 1 -1 1 3 2 -1 0 2 3 -1" solid="false" creaseAngle="0.5">'
            f'<Coordinate point="{s:.3f} 0 {-s*0.577:.3f}  -{s:.3f} 0 {-s*0.577:.3f}  0 0 {s*1.155:.3f}  0 {s*1.633:.3f} 0"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "octahedron":
        s = size
        pts = f"0 {s:.3f} 0  {s:.3f} 0 0  0 0 {s:.3f}  -{s:.3f} 0 0  0 0 -{s:.3f}  0 -{s:.3f} 0"
        idx = "0 1 2 -1 0 2 3 -1 0 3 4 -1 0 4 1 -1 5 2 1 -1 5 3 2 -1 5 4 3 -1 5 1 4 -1"
        geo = (
            f'<IndexedFaceSet coordIndex="{idx}" solid="false" creaseAngle="0.5">'
            f'<Coordinate point="{pts}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "icosahedron":
        s = size
        t_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        raw = [
            (-1,  t_ratio, 0), ( 1,  t_ratio, 0), (-1, -t_ratio, 0), ( 1, -t_ratio, 0),
            ( 0, -1,  t_ratio), ( 0,  1,  t_ratio), ( 0, -1, -t_ratio), ( 0,  1, -t_ratio),
            ( t_ratio, 0, -1), ( t_ratio, 0,  1), (-t_ratio, 0, -1), (-t_ratio, 0,  1),
        ]
        norm = math.sqrt(1 + t_ratio**2)
        verts = [f"{x/norm*s:.3f} {y/norm*s:.3f} {z/norm*s:.3f}" for x, y, z in raw]
        faces = [
            0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11,
            1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
            3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9,
            4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1,
        ]
        idx_str = " ".join(f"{faces[i]} {faces[i+1]} {faces[i+2]} -1" for i in range(0, len(faces), 3))
        geo = (
            f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="0.5">'
            f'<Coordinate point="{" ".join(verts)}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "star":
        # 2D 5-pointed star extruded in XZ plane
        pts = []
        idxs = []
        outer_r, inner_r = size, size * 0.4
        points = 5
        for i in range(points * 2):
            angle = math.pi / points * i - math.pi / 2
            rad = outer_r if i % 2 == 0 else inner_r
            pts.append(f"{math.cos(angle)*rad:.3f} 0 {math.sin(angle)*rad:.3f}")
        # fan from center
        center_idx = points * 2
        pts.append("0 0 0")
        for i in range(points * 2):
            idxs.append(f"{center_idx} {i} {(i+1) % (points*2)} -1")
        geo = (
            f'<IndexedFaceSet coordIndex="{" ".join(idxs)}" solid="false">'
            f'<Coordinate point="{" ".join(pts)}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "arrow":
        s = size
        shaft_w = s * 0.2
        head_w  = s * 0.5
        shaft_l = s * 1.2
        head_l  = s * 0.8
        pts = [
            f"-{shaft_w:.3f} 0 0",
            f"{shaft_w:.3f} 0 0",
            f"{shaft_w:.3f} 0 {-shaft_l:.3f}",
            f"-{shaft_w:.3f} 0 {-shaft_l:.3f}",
            f"-{head_w:.3f} 0 {-shaft_l:.3f}",
            f"0 0 {-(shaft_l+head_l):.3f}",
            f"{head_w:.3f} 0 {-shaft_l:.3f}",
        ]
        idx = "0 1 2 3 -1 4 5 6 -1"
        geo = (
            f'<IndexedFaceSet coordIndex="{idx}" solid="false">'
            f'<Coordinate point="{" ".join(pts)}"/>'
            f'</IndexedFaceSet>'
        )

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
        geo = (
            f'<IndexedLineSet coordIndex="{idxs}">'
            f'<Coordinate point="{" ".join(pts)}"/>'
            f'</IndexedLineSet>'
        )

    elif shape == "plane":
        s = size * 2
        geo = (
            f'<IndexedFaceSet coordIndex="0 1 2 3 -1" solid="false">'
            f'<Coordinate point="-{s:.3f} 0 -{s:.3f}  {s:.3f} 0 -{s:.3f}  {s:.3f} 0 {s:.3f}  -{s:.3f} 0 {s:.3f}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "ellipsoid":
        geo = f'<Sphere radius="{size:.3f}"/>'
        lines = [
            f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}" scale="1.0 0.6 1.4">',
            f'      <Shape>',
            f'        {geo}',
            f'        <Appearance>',
            f'          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/>',
            f'        </Appearance>',
            f'      </Shape>',
            f'    </Transform>',
        ]
        return "\n".join(lines) + "\n"

    else:  # box default
        s = size * 2
        geo = f'<Box size="{s:.3f} {s:.3f} {s:.3f}"/>'

    rot_str = ""
    if rotation:
        rx, ry, rz, ra = rotation
        rot_str = f' rotation="{rx} {ry} {rz} {ra:.4f}"'

    lines = [
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}"{rot_str}>',
        f'      <Shape>',
        f'        {geo}',
        f'        <Appearance>',
        f'          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6" transparency="{transparency:.2f}"/>',
        f'        </Appearance>',
        f'      </Shape>',
        f'    </Transform>',
    ]
    return "\n".join(lines) + "\n"


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>X3D Agent Console</title>
  <script src="https://create3000.github.io/code/x_ite/latest/x_ite.min.js"></script>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0d0d;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
    header{padding:14px 24px;background:#161616;border-bottom:1px solid #2a2a2a;display:flex;align-items:center;gap:12px}
    header h1{font-size:18px;font-weight:600;color:#fff}
    .badge{font-size:11px;background:#7c3aed;color:white;padding:2px 8px;border-radius:99px;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
    .main{display:flex;flex:1;overflow:hidden}
    .viewport{flex:1;background:#111;min-height:0}
    x3d-canvas{width:100%;height:100%;display:block}
    .sidebar{width:340px;background:#141414;border-left:1px solid #222;display:flex;flex-direction:column}
    .console-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
    .entry{border-radius:6px;padding:8px 10px;font-size:13px;line-height:1.5}
    .entry.user{background:#1e1e2e;border-left:3px solid #7c3aed;color:#c4b5fd}
    .entry.ai{background:#0f1f18;border-left:3px solid #10b981;color:#6ee7b7}
    .entry.error{background:#1f0f0f;border-left:3px solid #ef4444;color:#fca5a5}
    .entry.sys{color:#555;font-size:11px;font-style:italic}
    .lbl{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:2px;opacity:.7}
    .input-area{padding:12px;border-top:1px solid #222;display:flex;flex-direction:column;gap:8px}
    textarea{width:100%;padding:10px;background:#1a1a1a;border:1px solid #333;border-radius:6px;color:#e0e0e0;font-size:13px;resize:none;outline:none;font-family:inherit}
    textarea:focus{border-color:#7c3aed}
    .btn-row{display:flex;gap:8px}
    button{flex:1;padding:9px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}
    button:hover{opacity:.85}
    button:disabled{opacity:.4;cursor:not-allowed}
    #runBtn{background:#7c3aed;color:white}
    #clearBtn{background:#222;color:#aaa;border:1px solid #333}
    .hint{font-size:11px;color:#444;text-align:center}
    .chips{display:flex;flex-wrap:wrap;gap:4px;padding:0 12px 8px}
    .chip{font-size:11px;padding:3px 8px;background:#1e1e2e;color:#a78bfa;border-radius:99px;cursor:pointer;border:1px solid #2d2d4e}
    .chip:hover{background:#2d2d4e}
  </style>
</head>
<body>
  <header>
    <h1>X3D Agent Console</h1>
    <span class="badge">Rule-Based NL</span>
  </header>
  <div class="main">
    <div class="viewport">
      <x3d-canvas id="canvas" src="/scene.x3d" style="width:100%;height:100%"></x3d-canvas>
    </div>
    <div class="sidebar">
      <div class="console-log" id="log">
        <div class="entry sys">Scene ready. Try the examples below or type your own.</div>
      </div>
      <div class="chips">
        <span class="chip" onclick="quick('place a red sphere to the left')">red sphere</span>
        <span class="chip" onclick="quick('spawn a huge gold torus in the center')">gold torus</span>
        <span class="chip" onclick="quick('create a tiny cyan cube floating')">floating cube</span>
        <span class="chip" onclick="quick('drop a purple cone to the right')">purple cone</span>
        <span class="chip" onclick="quick('give me a ghost blue sphere')">ghost sphere</span>
        <span class="chip" onclick="quick('build a giant emerald cylinder behind')">emerald cylinder</span>
        <span class="chip" onclick="quick('make a neon green icosahedron')">icosahedron</span>
        <span class="chip" onclick="quick('place a gold star overhead')">gold star</span>
        <span class="chip" onclick="quick('spawn a crimson octahedron to the right')">octahedron</span>
        <span class="chip" onclick="quick('add a rose gold spiral up high')">helix</span>
        <span class="chip" onclick="quick('drop a tilted orange arrow in front')">arrow</span>
        <span class="chip" onclick="quick('put a white plane below')">ground plane</span>
        <span class="chip" onclick="quick('undo')">undo</span>
        <span class="chip" onclick="quick('clear')">clear</span>
      </div>
      <div class="input-area">
        <textarea id="inp" rows="3" placeholder="spawn a huge ruby donut at 0 1 0&#10;place a tilted neon green icosahedron above&#10;give me a ghost blue sphere to the right&#10;clear"></textarea>
        <div class="btn-row">
          <button id="runBtn" onclick="run()">&#9654; Run</button>
          <button id="clearBtn" onclick="clearAll()">&#10005; Clear</button>
        </div>
        <div class="hint">Enter or click Run &bull; Drag to orbit in viewport</div>
      </div>
    </div>
  </div>
  <script>
    const log    = document.getElementById('log');
    const inp    = document.getElementById('inp');
    const runBtn = document.getElementById('runBtn');
    const canvas = document.getElementById('canvas');

    function addLog(cls, label, text) {
      const d = document.createElement('div');
      d.className = 'entry ' + cls;
      d.innerHTML = '<div class="lbl">' + label + '</div>' +
        String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      log.appendChild(d);
      log.scrollTop = log.scrollHeight;
    }

    function reload() {
      const url = '/scene.x3d?t=' + Date.now();
      try {
        if (canvas.browser) canvas.browser.loadURL(new X3D.MFString(url));
        else canvas.setAttribute('src', url);
      } catch(e) { canvas.setAttribute('src', url); }
    }

    async function run() {
      const text = inp.value.trim();
      if (!text) return;
      addLog('user', 'You', text);
      inp.value = '';
      runBtn.disabled = true;
      try {
        const res  = await fetch('/api/agent', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({prompt: text})
        });
        const data = await res.json();
        if (res.ok) { addLog('ai', 'Scene', data.message); reload(); }
        else        { addLog('error', 'Error', data.detail || 'Unknown'); }
      } catch(e) { addLog('error', 'Network', e.message); }
      finally { runBtn.disabled = false; }
    }

    async function clearAll() {
      await fetch('/api/clear', {method:'POST'});
      addLog('sys', 'System', 'Scene cleared.');
      reload();
    }

    function quick(text) { inp.value = text; run(); }

    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); run(); }
    });
  </script>
</body>
</html>
"""


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
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        f.write(DEFAULT_X3D)
    return {"status": "success", "message": "Scene cleared."}


@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    try:
        result = parse_prompt(req.prompt)

        if result["action"] == "clear":
            with open(SCENE_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_X3D)
            return {"status": "success", "message": result["message"]}

        if result["action"] == "remove_last":
            ensure_scene_file()
            with open(SCENE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            last = content.rfind("<Transform")
            if last != -1:
                content = content[:last] + "  </Scene>\n</X3D>"
                with open(SCENE_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"status": "success", "message": "Removed last shape."}
            return {"status": "ok", "message": "Nothing to remove."}

        if result["action"] == "add":
            xml = build_shape_xml(
                result["shape"], result["color"], result["position"],
                result["size"], result.get("rotation"), result.get("transparency", 0.0)
            )
            ensure_scene_file()
            with open(SCENE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if "</Scene>" not in content:
                content = DEFAULT_X3D
            updated = content.replace("</Scene>", xml + "  </Scene>")
            with open(SCENE_FILE, "w", encoding="utf-8") as f:
                f.write(updated)
            return {"status": "success", "message": result["message"]}

        return {"status": "ok", "message": "Try: 'place a red sphere to the left'"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
