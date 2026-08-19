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

COLORS = {
    "red":    (1.0, 0.0, 0.0), "green":  (0.0, 0.8, 0.0),
    "blue":   (0.0, 0.4, 1.0), "yellow": (1.0, 1.0, 0.0),
    "orange": (1.0, 0.5, 0.0), "purple": (0.5, 0.0, 0.8),
    "pink":   (1.0, 0.4, 0.7), "cyan":   (0.0, 1.0, 1.0),
    "white":  (1.0, 1.0, 1.0), "black":  (0.05, 0.05, 0.05),
    "gray":   (0.5, 0.5, 0.5), "grey":   (0.5, 0.5, 0.5),
    "brown":  (0.5, 0.25, 0.1),"gold":   (1.0, 0.84, 0.0),
}
SIZES = {
    "tiny": 0.3, "small": 0.5, "little": 0.5,
    "big": 1.3, "large": 1.5, "huge": 2.0, "giant": 2.5,
}
POSITIONS = {
    "left":   (-3.0, 0.0, 0.0), "right":  (3.0, 0.0, 0.0),
    "above":  (0.0, 3.0, 0.0),  "up":     (0.0, 3.0, 0.0),
    "below":  (0.0,-3.0, 0.0),  "down":   (0.0,-3.0, 0.0),
    "behind": (0.0, 0.0,-3.0),  "front":  (0.0, 0.0, 3.0),
    "center": (0.0, 0.0, 0.0),
}

def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_X3D)

ensure_scene_file()

class PromptRequest(BaseModel):
    prompt: str

def parse_prompt(text):
    t = text.lower()
    if any(w in t for w in ("clear", "reset", "remove all", "delete all", "wipe")):
        return {"action": "clear", "message": "Scene cleared."}
    shape = "box"
    if "sphere" in t or "ball" in t or "orb" in t: shape = "sphere"
    elif "cone" in t: shape = "cone"
    elif "cylinder" in t or "tube" in t: shape = "cylinder"
    color = (0.4, 0.6, 1.0)
    for name, rgb in COLORS.items():
        if name in t: color = rgb; break
    size = 0.8
    for word, s in SIZES.items():
        if word in t: size = s; break
    position = (0.0, 0.0, 0.0)
    m = re.search(r'at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)', t)
    if m:
        position = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    else:
        for word, pos in POSITIONS.items():
            if word in t: position = pos; break
    color_name = next((n for n, rgb in COLORS.items() if rgb == color), "blue")
    return {"action":"add","shape":shape,"color":color,"position":position,"size":size,
            "message": f"Added {color_name} {shape} (size {size}) at {position}."}

def build_shape_xml(shape, color, position, size):
    r, g, b = color
    x, y, z = position
    if shape == "sphere":   geo = f'<Sphere radius="{size:.3f}"/>'
    elif shape == "cone":   geo = f'<Cone bottomRadius="{size:.3f}" height="{size*2:.3f}"/>'
    elif shape == "cylinder": geo = f'<Cylinder radius="{size:.3f}" height="{size*2:.3f}"/>'
    else:
        s = size * 2
        geo = f'<Box size="{s:.3f} {s:.3f} {s:.3f}"/>'
    return (
        f'    <Transform translation="{x:.3f} {y:.3f} {z:.3f}">\n'
        f'      <Shape>\n'
        f'        {geo}\n'
        f'        <Appearance>\n'
        f'          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" specularColor="0.4 0.4 0.4" shininess="0.6"/>\n'
        f'        </Appearance>\n'
        f'      </Shape>\n'
        f'    </Transform>\n'
    )

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
    .sidebar{width:320px;background:#141414;border-left:1px solid #222;display:flex;flex-direction:column}
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
        <div class="entry sys">Scene ready. Try: "add a red sphere"</div>
      </div>
      <div class="input-area">
        <textarea id="inp" rows="3" placeholder="add a big blue sphere to the left&#10;put a yellow cone above&#10;clear"></textarea>
        <div class="btn-row">
          <button id="runBtn" onclick="run()">&#9654; Run</button>
          <button id="clearBtn" onclick="clearAll()">&#10005; Clear</button>
        </div>
        <div class="hint">Enter or click Run</div>
      </div>
    </div>
  </div>
  <script>
    const log = document.getElementById('log');
    const inp = document.getElementById('inp');
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
      if (canvas.browser) {
        canvas.browser.loadURL(new X3D.MFString(url));
      } else {
        canvas.setAttribute('src', url);
      }
    }

    async function run() {
      const text = inp.value.trim();
      if (!text) return;
      addLog('user', 'You', text);
      inp.value = '';
      runBtn.disabled = true;
      try {
        const res = await fetch('/api/agent', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({prompt: text})
        });
        const data = await res.json();
        if (res.ok) { addLog('ai', 'Scene', data.message); reload(); }
        else { addLog('error', 'Error', data.detail || 'Unknown'); }
      } catch(e) { addLog('error', 'Network', e.message); }
      finally { runBtn.disabled = false; }
    }

    async function clearAll() {
      await fetch('/api/clear', {method:'POST'});
      addLog('sys', 'System', 'Scene cleared.');
      reload();
    }

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
        headers={"Cache-Control":"no-cache, no-store","Access-Control-Allow-Origin":"*"})

@app.post("/api/clear")
async def clear_scene():
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        f.write(DEFAULT_X3D)
    return {"status":"success","message":"Scene cleared."}

@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    try:
        result = parse_prompt(req.prompt)
        if result["action"] == "clear":
            with open(SCENE_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_X3D)
            return {"status":"success","message":result["message"]}
        if result["action"] == "add":
            xml = build_shape_xml(result["shape"],result["color"],result["position"],result["size"])
            ensure_scene_file()
            with open(SCENE_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if "</Scene>" not in content:
                content = DEFAULT_X3D
            updated = content.replace("</Scene>", xml + "  </Scene>")
            with open(SCENE_FILE, "w", encoding="utf-8") as f:
                f.write(updated)
            return {"status":"success","message":result["message"]}
        return {"status":"ok","message":"Try: 'add a red sphere'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
