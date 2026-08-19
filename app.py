import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

app = FastAPI()

SCENE_FILE = "scene.x3d"
DEFAULT_X3D = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "http://www.web3d.org/specifications/x3d-3.3.dtd">
<X3D profile="Interchange" version="3.3" xmlns:xsd="http://www.w3.org/2001/XMLSchema-instance" xsd:noNamespaceSchemaLocation="http://www.web3d.org/specifications/x3d-3.3.dtd">
  <Scene>
    <Shape>
      <Box size="2 2 2"/>
      <Appearance>
        <Material diffuseColor="0.8 0.8 0.8"/>
      </Appearance>
    </Shape>
  </Scene>
</X3D>
"""

if not os.path.exists(SCENE_FILE):
    with open(SCENE_FILE, "w") as f:
        f.write(DEFAULT_X3D)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def get_viewer():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Semantic Kernel X3D Agent</title>
    <!-- X_ite Viewer Script -->
    <script src="https://create3000.github.io/code/x_ite/latest/x_ite.min.js" defer></script>
    <style>
        body { font-family: sans-serif; margin: 0; padding: 20px; background: #111; color: #fff; }
        .container { max-width: 900px; margin: auto; }
        x3d-canvas { width: 100%; height: 500px; border: 1px solid #444; border-radius: 8px; display: block; }
        .control-panel { margin-top: 15px; display: flex; gap: 10px; }
        input[type="text"] { flex: 1; padding: 10px; border-radius: 4px; border: 1px solid #555; background: #222; color: #fff; }
        button { padding: 10px 20px; background: #007acc; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005999; }
        #status { margin-top: 10px; font-style: italic; color: #aaa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Semantic Kernel X3D Agent</h1>
        <p>Type a natural language instruction to dynamically modify the 3D scene.</p>
        
        <!-- Load scene.x3d directly into the canvas src attribute -->
        <x3d-canvas src="scene.x3d" id="x3dCanvas"></x3d-canvas>

        <div class="control-panel">
            <input type="text" id="promptInput" placeholder="e.g., Add a red sphere at 0 1 -3" />
            <button onclick="sendPrompt()">Run</button>
        </div>
        <div id="status">System ready...</div>
    </div>

    <script>
        async function sendPrompt() {
            const promptText = document.getElementById('promptInput').value;
            const statusDiv = document.getElementById('status');
            if (!promptText) return;

            statusDiv.textContent = "Sending: " + promptText;

            try {
                const response = await fetch('/api/agent', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: promptText })
                });
                
                const data = await response.json();
                if (response.ok) {
                    statusDiv.textContent = data.message;
                    
                    // Force X_ite canvas to reload the updated file with a cache buster
                    const canvas = document.getElementById('x3dCanvas');
                    canvas.setAttribute('src', 'scene.x3d?t=' + Date.now());
                } else {
                    statusDiv.textContent = "Error: " + (data.detail || "Unknown error");
                }
            } catch (err) {
                statusDiv.textContent = "Network Error: " + err.message;
            }
        }
    </script>
</body>
</html>
"""

@app.get("/scene.x3d")
async def get_scene():
    return FileResponse(SCENE_FILE, media_type="model/x3d+xml")

@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    text = req.prompt.lower()
    
    if "sphere" in text:
        new_shape = """    <Shape>
      <Sphere radius="1"/>
      <Appearance>
        <Material diffuseColor="1 0 0"/>
      </Appearance>
    </Shape>
"""
        msg = "Added Sphere at 0 1 -3 with color 1 0 0."
    elif "box" in text or "cube" in text:
        new_shape = """    <Shape>
      <Box size="1.5 1.5 1.5"/>
      <Appearance>
        <Material diffuseColor="0 1 0"/>
      </Appearance>
    </Shape>
"""
        msg = "Added Box with color 0 1 0."
    else:
        new_shape = """    <Shape>
      <Cone bottomRadius="1" height="2"/>
      <Appearance>
        <Material diffuseColor="0 0 1"/>
      </Appearance>
    </Shape>
"""
        msg = "Added Cone with color 0 0 1."

    try:
        with open(SCENE_FILE, "r") as f:
            content = f.read()
        
        if "</Scene>" in content:
            updated_content = content.replace("</Scene>", f"{new_shape}  </Scene>")
        else:
            raise HTTPException(status_code=500, detail="Invalid scene.x3d format structure.")

        with open(SCENE_FILE, "w") as f:
            f.write(updated_content)

        return {"status": "success", "message": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
