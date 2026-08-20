import os
import re
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
}

# ── Sizes ─────────────────────────────────────────────────────────────────────
SIZES = {
    "microscopic": 0.1,
    "tiny":        0.25,
    "mini":        0.3,
    "small":       0.5,
    "little":      0.5,
    "medium":      0.8,
    "normal":      0.8,
    "big":         1.3,
    "large":       1.5,
    "huge":        2.0,
    "giant":       2.5,
    "enormous":    3.0,
    "massive":     3.5,
    "colossal":    4.0,
}

# ── Named positions ───────────────────────────────────────────────────────────
POSITIONS = {
    "left":        (-3.0,  0.0,  0.0),
    "far left":    (-6.0,  0.0,  0.0),
    "right":       ( 3.0,  0.0,  0.0),
    "far right":   ( 6.0,  0.0,  0.0),
    "above":       ( 0.0,  3.0,  0.0),
    "up":          ( 0.0,  3.0,  0.0),
    "high":        ( 0.0,  4.0,  0.0),
    "below":       ( 0.0, -3.0,  0.0),
    "down":        ( 0.0, -3.0,  0.0),
    "behind":      ( 0.0,  0.0, -3.0),
    "back":        ( 0.0,  0.0, -3.0),
    "front":       ( 0.0,  0.0,  3.0),
    "forward":     ( 0.0,  0.0,  3.0),
    "center":      ( 0.0,  0.0,  0.0),
    "middle":      ( 0.0,  0.0,  0.0),
    "top left":    (-3.0,  3.0,  0.0),
    "top right":   ( 3.0,  3.0,  0.0),
    "bottom left": (-3.0, -3.0,  0.0),
    "bottom right":( 3.0, -3.0,  0.0),
    "upper left":  (-3.0,  3.0,  0.0),
    "upper right": ( 3.0,  3.0,  0.0),
    "lower left":  (-3.0, -3.0,  0.0),
    "lower right": ( 3.0, -3.0,  0.0),
}

# ── Shapes ────────────────────────────────────────────────────────────────────
SHAPE_ALIASES = {
    "sphere":      "sphere",
    "ball":        "sphere",
    "orb":         "sphere",
    "globe":       "sphere",
    "bubble":      "sphere",
    "cone":        "cone",
    "pyramid":     "cone",
    "triangle":    "cone",
    "hat":         "cone",
    "cylinder":    "cylinder",
    "tube":        "cylinder",
    "pipe":        "cylinder",
    "pillar":      "cylinder",
    "column":      "cylinder",
    "barrel":      "cylinder",
    "capsule":     "cylinder",
    "box":         "box",
    "cube":        "box",
    "block":       "box",
    "brick":       "box",
    "square":      "box",
    "rectangle":   "box",
    "torus":       "torus",
    "donut":       "torus",
    "doughnut":    "torus",
    "ring":        "torus",
    "loop":        "torus",
    "tetrahedron": "tetrahedron",
    "diamond":     "tetrahedron",
    "gem":         "tetrahedron",
    "crystal":     "tetrahedron",
    "plane":       "plane",
    "flat":        "plane",
    "floor":       "plane",
    "ground":      "plane",
    "disc":        "plane",
    "disk":        "plane",
    "ellipsoid":   "ellipsoid",
    "egg":         "ellipsoid",
    "oval":        "ellipsoid",
}


def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_X3D)


ensure_scene_file()


class PromptRequest(BaseModel):
    prompt: str


def parse_color(t: str):
    # Check multi-word colors first (e.g. "hot pink", "dark blue")
    two_word = re.search(
        r'(hot|dark|light|neon|electric|deep|bright|pale|sky|forest|lime|baby)\s+'
        r'(red|green|blue|pink|orange|purple|yellow|cyan|gray|grey|brown)',
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
            ("light",  "blue"):   (0.53, 0.81, 0.98),
            ("light",  "green"):  (0.56, 0.93, 0.56),
            ("neon",   "green"):  (0.22, 1.00, 0.08),
            ("neon",   "pink"):   (1.00, 0.08, 0.58),
            ("electric","blue"):  (0.00, 0.60, 1.00),
            ("deep",   "purple"): (0.29, 0.00, 0.51),
            ("bright", "orange"): (1.00, 0.65, 0.00),
            ("sky",    "blue"):   (0.53, 0.81, 0.98),
            ("forest", "green"):  (0.13, 0.55, 0.13),
            ("lime",   "green"):  (0.20, 1.00, 0.00),
            ("baby",   "blue"):   (0.54, 0.81, 0.94),
        }
        return combos.get((modifier, base), COLORS.get(base, (0.4, 0.6, 1.0)))

    # Hex color: #rrggbb or #rgb
    hex_match = re.search(r'#([0-9a-f]{6}|[0-9a-f]{3})\b', t)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

    # RGB values: "rgb 255 0 0" or "color 1.0 0 0"
    rgb_match = re.search(r'(?:rgb|color)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', t)
    if rgb_match:
        vals = [float(rgb_match.group(i)) for i in range(1,4)]
        if max(vals) > 1.0:
            vals = [v/255 for v in vals]
        return tuple(vals)

    for name, rgb in COLORS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', t):
            return rgb

    return (0.4, 0.6, 1.0)


def parse_size(t: str):
    # Explicit number: "size 2.5" or "radius 1.5" or "scale 3"
    num_match = re.search(r'(?:size|radius|scale|width|height)\s+([\d.]+)', t)
    if num_match:
        return min(float(num_match.group(1)), 5.0)
    for word, s in SIZES.items():
        if re.search(r'\b' + re.escape(word) + r'\b', t):
            return s
    return 0.8


def parse_position(t: str):
    # Explicit coords: "at X Y Z" or "position X Y Z"
    coord = re.search(r'(?:at|position|pos|translate|move to)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', t)
    if coord:
        return (float(coord.group(1)), float(coord.group(2)), float(coord.group(3)))
    # Two-word positions first
    for phrase, pos in sorted(POSITIONS.items(), key=lambda x: -len(x[0])):
        if phrase in t:
            return pos
    return (0.0, 0.0, 0.0)


def parse_rotation(t: str):
    # "rotated X degrees" or "rotate 45"
    rot = re.search(r'rotat\w*\s+([-\d.]+)\s*(?:degrees?|deg)?', t)
    if rot:
        deg = float(rot.group(1))
        rad = deg * 3.14159 / 180
        return (0, 1, 0, rad)  # rotate around Y axis
    return None


def parse_prompt(text: str) -> dict:
    t = text.lower().strip()

    # Clear
    if any(w in t for w in ("clear", "reset", "remove all", "delete all", "wipe", "empty", "start over")):
        return {"action": "clear", "message": "Scene cleared."}

    # Remove / delete specific shape (future: by index or last)
    if any(w in t for w in ("remove", "delete", "undo", "take away")):
        return {"action": "remove_last", "message": "Removed last shape."}

    # Determine shape
    shape = "box"
    for alias, canonical in SHAPE_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', t):
            shape = canonical
            break

    color    = parse_color(t)
    size     = parse_size(t)
    position = parse_position(t)
    rotation = parse_rotation(t)

    # Transparency hint
    transparent = "transparent" in t or "glass" in t or "see through" in t or "translucent" in t
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
        # X3D has no native torus; approximate with an IndexedFaceSet
        outer, inner, steps = size, size * 0.35, 24
        pts, idxs = [], []
        for i in range(steps):
            a = 2 * 3.14159 * i / steps
            for j in range(steps):
                b2 = 2 * 3.14159 * j / steps
                px = (outer + inner * __import__('math').cos(b2)) * __import__('math').cos(a)
                py = inner * __import__('math').sin(b2)
                pz = (outer + inner * __import__('math').cos(b2)) * __import__('math').sin(a)
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

    elif shape == "plane":
        s = size * 2
        geo = (
            f'<IndexedFaceSet coordIndex="0 1 2 3 -1" solid="false">'
            f'<Coordinate point="-{s:.3f} 0 -{s:.3f}  {s:.3f} 0 -{s:.3f}  {s:.3f} 0 {s:.3f}  -{s:.3f} 0 {s:.3f}"/>'
            f'</IndexedFaceSet>'
        )

    elif shape == "ellipsoid":
        geo = f'<Sphere radius="{size:.3f}"/>'
        # We'll apply a scale transform to squash it
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
  <title>X3D AI Console</title>
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
    <h1>X3D AI Console</h1>
    <span class="badge">NL Powered</span>
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
        <span class="chip" onclick="quick('add a red sphere to the left')">red sphere left</span>
        <span class="chip" onclick="quick('add a huge gold torus in the center')">gold torus</span>
        <span class="chip" onclick="quick('add a tiny cyan cube above')">tiny cyan cube</span>
        <span class="chip" onclick="quick('add a purple cone to the right')">purple cone</span>
        <span class="chip" onclick="quick('add a transparent blue sphere')">glass sphere</span>
        <span class="chip" onclick="quick('add a giant emerald cylinder behind')">emerald cylinder</span>
        <span class="chip" onclick="quick('add a neon green tetrahedron')">neon tetrahedron</span>
        <span class="chip" onclick="quick('add a white plane below')">white plane</span>
        <span class="chip" onclick="quick('clear')">clear</span>
      </div>
      <div class="input-area">
        <textarea id="inp" rows="3" placeholder="add a huge ruby donut at 0 1 0&#10;put a tiny neon green tetrahedron above&#10;add a transparent blue sphere to the right&#10;clear"></textarea>
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
            # Remove last <Transform ...> block
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

        return {"status": "ok", "message": "Try: 'add a red sphere to the left'"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
