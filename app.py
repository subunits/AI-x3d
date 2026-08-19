import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI()

SCENE_FILE = "scene.x3d"
DEFAULT_X3D = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "http://www.web3d.org/specifications/x3d-3.3.dtd">
<X3D profile="Interchange" version="3.3" xmlns:xsd="http://www.w3.org/2001/XMLSchema-instance" xsd:noNamespaceSchemaLocation="http://www.web3d.org/specifications/x3d-3.3.dtd">
  <Scene>
  </Scene>
</X3D>
"""

COLORS = {
    "red":     (1.0, 0.0, 0.0),
    "green":   (0.0, 0.8, 0.0),
    "blue":    (0.0, 0.3, 1.0),
    "yellow":  (1.0, 1.0, 0.0),
    "orange":  (1.0, 0.5, 0.0),
    "purple":  (0.5, 0.0, 0.8),
    "pink":    (1.0, 0.4, 0.7),
    "cyan":    (0.0, 1.0, 1.0),
    "white":   (1.0, 1.0, 1.0),
    "black":   (0.05, 0.05, 0.05),
    "gray":    (0.5, 0.5, 0.5),
    "grey":    (0.5, 0.5, 0.5),
    "brown":   (0.5, 0.25, 0.1),
    "gold":    (1.0, 0.84, 0.0),
    "silver":  (0.75, 0.75, 0.75),
}

SIZES = {
    "tiny":   0.3,
    "small":  0.5,
    "little": 0.5,
    "medium": 0.8,
    "big":    1.3,
    "large":  1.5,
    "huge":   2.0,
    "giant":  2.5,
}

POSITIONS = {
    "left":   (-2.5, 0.0, 0.0),
    "right":  ( 2.5, 0.0, 0.0),
    "above":  ( 0.0, 2.5, 0.0),
    "up":     ( 0.0, 2.5, 0.0),
    "below":  ( 0.0,-2.5, 0.0),
    "down":   ( 0.0,-2.5, 0.0),
    "behind": ( 0.0, 0.0,-3.0),
    "front":  ( 0.0, 0.0, 2.0),
    "center": ( 0.0, 0.0, 0.0),
}


def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w") as f:
            f.write(DEFAULT_X3D)


ensure_scene_file()


class PromptRequest(BaseModel):
    prompt: str


def parse_prompt(text: str) -> dict:
    t = text.lower()

    # Action
    if any(w in t for w in ("clear", "reset", "remove all", "delete all", "wipe")):
        return {"action": "clear", "message": "Scene cleared."}

    # Shape
    shape = "box"
    if "sphere" in t or "ball" in t or "orb" in t:
        shape = "sphere"
    elif "cone" in t:
        shape = "cone"
    elif "cylinder" in t or "tube" in t or "pipe" in t:
        shape = "cylinder"
    elif "box" in t or "cube" in t or "block" in t:
        shape = "box"

    # Color
    color = (0.4, 0.6, 1.0)
    for name, rgb in COLORS.items():
        if name in t:
            color = rgb
            break

    # Size
    size = 0.8
    for word, s in SIZES.items():
        if word in t:
            size = s
            break

    # Explicit coords: "at X Y Z"
    position = (0.0, 0.0, 0.0)
    coord_match = re.search(r'at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', t)
    if coord_match:
        position = (float(coord_match.group(1)),
                    float(coord_match.group(2)),
                    float(coord_match.group(3)))
    else:
        for word, pos in POSITIONS.items():
            if word in t:
                position = pos
                break

    color_name = next((n for n, rgb in COLORS.items() if rgb == color), "blue")
    msg = f"Added {size:.1f}-unit {color_name} {shape} at {position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f}."

    return {
        "action": "add",
        "shape": shape,
        "color": color,
        "position": position,
        "size": size,
        "message": msg,
    }


def build_shape_xml(shape: str, color: tuple, position: tuple, size: float) -> str:
    r, g, b = color
    x, y, z = position

    if shape == "sphere":
        geo = f'<Sphere radius="{size:.3f}"/>'
    elif shape == "cone":
        geo = f'<Cone bottomRadius="{size:.3f}" height="{size * 2:.3f}"/>'
    elif shape == "cylinder":
        geo = f'<Cylinder radius="{size:.3f}" height="{size * 2:.3f}"/>'
    else:
        s = size * 2
        geo = f'<Box size="{s:.3f} {s:.3f} {s:.3f}"/>'

    return f"""    <Transform translation="{x:.3f} {y:.3f} {z:.3f}">
      <Shape>
        {geo}
        <Appearance>
          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}"/>
        </Appearance>
      </Shape>
    </Transform>
"""


@app.get("/", response_class=HTMLResponse)
async def get_viewer():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>X3D AI Console</title>
    <script src="https://create3000.github.io/code/x_ite/latest/x_ite.min.js" defer></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d0d0d; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
        header { padding: 14px 24px; background: #161616; border-bottom: 1px solid #2a2a2a; display: flex; align-items: center; gap: 12px; }
        header h1 { font-size: 18px; font-weight: 600; color: #fff; }
        header .badge { font-size: 11px; background: #7c3aed; color: white; padding: 2px 8px; border-radius: 99px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }
        .main { display: flex; flex: 1; overflow: hidden; }
        .viewport { flex: 1; background: #111; }
        x3d-canvas { width: 100%; height: 100%; display: block; }
        .sidebar { width: 340px; background: #141414; border-left: 1px solid #222; display: flex; flex-direction: column; }
        .console-log { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
        .log-entry { border-radius: 8px; padding: 10px 12px; font-size: 13px; line-height: 1.5; }
        .log-entry.user { background: #1e1e2e; border-left: 3px solid #7c3aed; color: #c4b5fd; }
        .log-entry.ai   { background: #0f1f18; border-left: 3px solid #10b981; color: #6ee7b7; }
        .log-entry.error{ background: #1f0f0f; border-left: 3px solid #ef4444; color: #fca5a5; }
        .log-entry.sys  { background: #1a1a1a; color: #555; font-size: 11px; font-style: italic; }
        .log-label { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 4px; opacity: 0.7; }
        .input-area { padding: 14px; border-top: 1px solid #222; display: flex; flex-direction: column; gap: 8px; }
        textarea { width: 100%; padding: 10px 12px; background: #1a1a1a; border: 1px solid #333; border-radius: 6px; color: #e0e0e0; font-size: 13px; resize: none; outline: none; font-family: inherit; line-height: 1.5; }
        textarea:focus { border-color: #7c3aed; }
        .btn-row { display: flex; gap: 8px; }
        button { flex: 1; padding: 9px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: opacity 0.15s; }
        button:hover { opacity: 0.85; }
        #runBtn   { background: #7c3aed; color: white; }
        #clearBtn { background: #222; color: #aaa; border: 1px solid #333; }
        .hint { font-size: 11px; color: #444; text-align: center; }
    </style>
</head>
<body>
    <header>
        <h1>X3D AI Console</h1>
        <span class="badge">NL Powered</span>
    </header>
    <div class="main">
        <div class="viewport">
            <x3d-canvas src="scene.x3d" id="x3dCanvas"></x3d-canvas>
        </div>
        <div class="sidebar">
            <div class="console-log" id="log">
                <div class="log-entry sys">Scene ready. Describe what to add.</div>
            </div>
            <div class="input-area">
                <textarea id="promptInput" rows="3" placeholder="e.g. Add a huge red sphere to the left&#10;Put a small yellow cone above&#10;Clear the scene"></textarea>
                <div class="btn-row">
                    <button id="runBtn"   onclick="sendPrompt()">&#9654; Run</button>
                    <button id="clearBtn" onclick="clearScene()">&#10005; Clear</button>
                </div>
                <div class="hint">Enter or click Run &bull; No API key required</div>
            </div>
        </div>
    </div>

    <script>
        const log    = document.getElementById('log');
        const input  = document.getElementById('promptInput');
        const runBtn = document.getElementById('runBtn');

        function addLog(type, label, text) {
            const e = document.createElement('div');
            e.className = 'log-entry ' + type;
            e.innerHTML = '<div class="log-label">' + label + '</div>' +
                text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
            log.appendChild(e);
            log.scrollTop = log.scrollHeight;
        }

        async function reloadScene() {
            const canvas = document.getElementById('x3dCanvas');
            if (canvas && canvas.browser) {
                await canvas.browser.loadURL(new X3D.MFString('scene.x3d?t=' + Date.now()));
            } else {
                canvas.src = 'scene.x3d?t=' + Date.now();
            }
        }

        async function sendPrompt() {
            const text = input.value.trim();
            if (!text) return;
            addLog('user', 'You', text);
            input.value = '';
            runBtn.disabled = true;
            try {
                const res  = await fetch('/api/agent', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({prompt: text}) });
                const data = await res.json();
                if (res.ok) { addLog('ai', 'Scene', data.message); await reloadScene(); }
                else        { addLog('error', 'Error', data.detail || 'Unknown error'); }
            } catch(err) {
                addLog('error', 'Network', err.message);
            } finally {
                runBtn.disabled = false;
            }
        }

        async function clearScene() {
            const res  = await fetch('/api/clear', {method:'POST'});
            const data = await res.json();
            addLog('sys', 'System', data.message);
            await reloadScene();
        }

        input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPrompt(); } });
    </script>
</body>
</html>
"""


@app.get("/scene.x3d")
async def get_scene():
    ensure_scene_file()
    return FileResponse(SCENE_FILE, media_type="model/x3d+xml")


@app.post("/api/clear")
async def clear_scene():
    with open(SCENE_FILE, "w") as f:
        f.write(DEFAULT_X3D)
    return {"status": "success", "message": "Scene cleared."}


@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    try:
        result = parse_prompt(req.prompt)

        if result["action"] == "clear":
            with open(SCENE_FILE, "w") as f:
                f.write(DEFAULT_X3D)
            return {"status": "success", "message": result["message"]}

        if result["action"] == "add":
            xml = build_shape_xml(
                result["shape"],
                result["color"],
                result["position"],
                result["size"],
            )
            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()
            if "</Scene>" not in content:
                content = DEFAULT_X3D
            updated = content.replace("</Scene>", f"{xml}  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)
            return {"status": "success", "message": result["message"]}

        return {"status": "ok", "message": "Try: 'Add a red sphere to the left'"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
