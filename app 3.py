import os
import json
import re
import anthropic
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

SYSTEM_PROMPT = """You are an X3D scene builder assistant. When the user gives a natural language instruction, you must respond with ONLY a valid JSON object (no markdown, no explanation) describing the 3D operation to perform.

The JSON must have this exact structure:
{
  "action": "add" | "clear" | "none",
  "shape": "box" | "sphere" | "cone" | "cylinder",
  "color": [R, G, B],         // floats 0.0–1.0
  "position": [X, Y, Z],      // floats, world coords
  "size": float,               // uniform scale factor (default 1.0)
  "message": "short human-friendly confirmation string"
}

Rules:
- Parse color names into RGB floats: red=[1,0,0], green=[0,1,0], blue=[0,0,1], yellow=[1,1,0], orange=[1,0.5,0], purple=[0.5,0,0.5], white=[1,1,1], black=[0,0,0], pink=[1,0.75,0.8], cyan=[0,1,1], gray=[0.5,0.5,0.5]
- Parse position from phrases like "at 0 1 -3", "at the top", "in the center" → [0,0,0], "to the left" → [-2,0,0], "to the right" → [2,0,0], "above" → [0,2,0], "behind" → [0,0,-2]
- Parse size from words like "big/large" → 2.0, "small/tiny" → 0.5, "huge/giant" → 3.0, otherwise 1.0
- If the user says "clear", "reset", or "remove everything", set action to "clear"
- If the instruction is ambiguous or non-scene-related, set action to "none"
- Default shape is "box" if not specified
- Default color is [0.8, 0.2, 0.9] (purple) if not specified
- Respond with ONLY the JSON object. No markdown, no commentary.
"""

def ensure_scene_file():
    if not os.path.exists(SCENE_FILE):
        with open(SCENE_FILE, "w") as f:
            f.write(DEFAULT_X3D)

ensure_scene_file()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class PromptRequest(BaseModel):
    prompt: str

def build_shape_xml(shape: str, color: list, position: list, size: float) -> str:
    r, g, b = color
    x, y, z = position

    geometry = ""
    if shape == "sphere":
        geometry = f'<Sphere radius="{size}"/>'
    elif shape == "cone":
        geometry = f'<Cone bottomRadius="{size}" height="{size * 2}"/>'
    elif shape == "cylinder":
        geometry = f'<Cylinder radius="{size}" height="{size * 2}"/>'
    else:  # box default
        s = size * 2
        geometry = f'<Box size="{s} {s} {s}"/>'

    return f"""    <Transform translation="{x} {y} {z}">
      <Shape>
        {geometry}
        <Appearance>
          <Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}"/>
        </Appearance>
      </Shape>
    </Transform>
"""

@app.get("/", response_class=HTMLResponse)
async def get_viewer():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI X3D Console</title>
    <script src="https://create3000.github.io/code/x_ite/latest/x_ite.min.js" defer></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #0d0d0d;
            color: #e0e0e0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            padding: 14px 24px;
            background: #161616;
            border-bottom: 1px solid #2a2a2a;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        header h1 { font-size: 18px; font-weight: 600; color: #fff; }
        header span {
            font-size: 11px;
            background: #7c3aed;
            color: white;
            padding: 2px 8px;
            border-radius: 99px;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .main {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        .viewport {
            flex: 1;
            position: relative;
            background: #111;
        }
        x3d-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }
        .sidebar {
            width: 340px;
            background: #141414;
            border-left: 1px solid #222;
            display: flex;
            flex-direction: column;
        }
        .console-log {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .log-entry {
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 13px;
            line-height: 1.5;
        }
        .log-entry.user {
            background: #1e1e2e;
            border-left: 3px solid #7c3aed;
            color: #c4b5fd;
        }
        .log-entry.ai {
            background: #0f1f18;
            border-left: 3px solid #10b981;
            color: #6ee7b7;
        }
        .log-entry.error {
            background: #1f0f0f;
            border-left: 3px solid #ef4444;
            color: #fca5a5;
        }
        .log-entry.system {
            background: #1a1a1a;
            color: #666;
            font-size: 11px;
            font-style: italic;
        }
        .log-label {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 4px;
            opacity: 0.7;
        }
        .input-area {
            padding: 14px;
            border-top: 1px solid #222;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        textarea {
            width: 100%;
            padding: 10px 12px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            color: #e0e0e0;
            font-size: 13px;
            resize: none;
            outline: none;
            font-family: inherit;
            line-height: 1.5;
        }
        textarea:focus { border-color: #7c3aed; }
        .btn-row { display: flex; gap: 8px; }
        button {
            flex: 1;
            padding: 9px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: opacity 0.15s;
        }
        button:hover { opacity: 0.85; }
        button:disabled { opacity: 0.4; cursor: not-allowed; }
        #runBtn { background: #7c3aed; color: white; }
        #clearBtn { background: #222; color: #aaa; border: 1px solid #333; }
        .hint {
            font-size: 11px;
            color: #444;
            text-align: center;
        }
        .spinner {
            display: inline-block;
            width: 10px; height: 10px;
            border: 2px solid #7c3aed;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            margin-right: 6px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <header>
        <h1>X3D AI Console</h1>
        <span>Claude Powered</span>
    </header>
    <div class="main">
        <div class="viewport">
            <x3d-canvas src="scene.x3d" id="x3dCanvas"></x3d-canvas>
        </div>
        <div class="sidebar">
            <div class="console-log" id="log">
                <div class="log-entry system">Scene initialized. Type a prompt to add objects.</div>
            </div>
            <div class="input-area">
                <textarea id="promptInput" rows="3" placeholder="e.g. Add a large red sphere at 2 0 -1&#10;Put a tiny yellow cube to the left&#10;Clear the scene"></textarea>
                <div class="btn-row">
                    <button id="runBtn" onclick="sendPrompt()">▶ Run</button>
                    <button id="clearBtn" onclick="clearScene()">✕ Clear</button>
                </div>
                <div class="hint">Enter or click Run • Claude parses your intent</div>
            </div>
        </div>
    </div>

    <script>
        const log = document.getElementById('log');
        const input = document.getElementById('promptInput');
        const runBtn = document.getElementById('runBtn');

        function addLog(type, label, text) {
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.innerHTML = '<div class="log-label">' + label + '</div>' + escapeHtml(text);
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
            return entry;
        }

        function escapeHtml(t) {
            return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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

            const thinking = addLog('ai', 'AI', '<span class="spinner"></span>Thinking…');

            try {
                const res = await fetch('/api/agent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                });
                const data = await res.json();
                thinking.remove();

                if (res.ok) {
                    addLog('ai', 'AI', data.message);
                    await reloadScene();
                } else {
                    addLog('error', 'Error', data.detail || 'Unknown error');
                }
            } catch (err) {
                thinking.remove();
                addLog('error', 'Network', err.message);
            } finally {
                runBtn.disabled = false;
            }
        }

        async function clearScene() {
            try {
                const res = await fetch('/api/clear', { method: 'POST' });
                const data = await res.json();
                addLog('system', 'System', data.message);
                await reloadScene();
            } catch (err) {
                addLog('error', 'Error', err.message);
            }
        }

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendPrompt();
            }
        });
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
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": req.prompt}]
        )

        raw = response.content[0].text.strip()

        # Strip markdown fences if model wraps output
        raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE).strip()

        parsed = json.loads(raw)
        action = parsed.get("action", "none")
        message = parsed.get("message", "Done.")

        if action == "clear":
            with open(SCENE_FILE, "w") as f:
                f.write(DEFAULT_X3D)
            return {"status": "success", "message": message}

        elif action == "add":
            shape = parsed.get("shape", "box")
            color = parsed.get("color", [0.8, 0.2, 0.9])
            position = parsed.get("position", [0, 0, 0])
            size = float(parsed.get("size", 1.0))

            shape_xml = build_shape_xml(shape, color, position, size)

            ensure_scene_file()
            with open(SCENE_FILE, "r") as f:
                content = f.read()

            if "</Scene>" not in content:
                content = DEFAULT_X3D

            updated = content.replace("</Scene>", f"{shape_xml}  </Scene>")
            with open(SCENE_FILE, "w") as f:
                f.write(updated)

            return {"status": "success", "message": message}

        else:
            return {"status": "ok", "message": message or "I didn't understand that. Try: 'Add a red sphere at 0 1 0'"}

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)}")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
