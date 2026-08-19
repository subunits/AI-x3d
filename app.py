import os
import re
import xml.etree.ElementTree as ET
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI()
FILE_PATH = "scene.x3d"

# Initialize default X3D scene with a ground box if it doesn't exist
if not os.path.exists(FILE_PATH):
    root = ET.Element("X3D", version="3.3", profile="Immersive")
    scene = ET.SubElement(root, "Scene")
    transform = ET.SubElement(scene, "Transform", DEF="Ground", translation="0 -1 0")
    shape = ET.SubElement(transform, "Shape")
    appearance = ET.SubElement(shape, "Appearance")
    ET.SubElement(appearance, "Material", diffuseColor="0.2 0.7 0.2")
    ET.SubElement(shape, "Box", size="10 0.1 10")
    ET.ElementTree(root).write(FILE_PATH)

def add_shape_mock(prompt: str) -> str:
    # Basic keyword extraction for shapes
    shape_type = "Box"
    p = prompt.lower()
    if "sphere" in p: shape_type = "Sphere"
    elif "cylinder" in p: shape_type = "Cylinder"
    elif "cone" in p: shape_type = "Cone"
    
    # Basic keyword extraction for colors
    color = "1 0 0" # Default red
    if "blue" in p: color = "0 0 1"
    elif "green" in p: color = "0 1 0"
    elif "yellow" in p: color = "1 1 0"
    elif "white" in p: color = "1 1 1"
    elif "orange" in p: color = "1 0.5 0"
    
    # Extract coordinates if provided (e.g., "0 2 -2")
    coords = "0 1 -3"
    match = re.search(r'(-?\d+\.?\d*\s+-?\d+\.?\d*\s+-?\d+\.?\d*)', prompt)
    if match:
        coords = match.group(1)

    # Mutate the XML file
    tree = ET.parse(FILE_PATH)
    scene = tree.getroot().find(".//Scene")
    def_name = f"Object_{len(scene)}"
    
    transform = ET.SubElement(scene, "Transform", DEF=def_name, translation=coords)
    shape = ET.SubElement(transform, "Shape")
    appearance = ET.SubElement(shape, "Appearance")
    ET.SubElement(appearance, "Material", diffuseColor=color)
    ET.SubElement(shape, shape_type)
    tree.write(FILE_PATH)
    
    return f"Added {shape_type} at {coords} with color {color}."

class PromptRequest(BaseModel):
    prompt: str

@app.post("/api/agent")
async def run_agent(req: PromptRequest):
    try:
        response_msg = add_shape_mock(req.prompt)
        return {"status": "success", "response": response_msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scene.x3d")
async def get_x3d_file():
    return FileResponse(FILE_PATH, media_type="application/xml")

@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    return """<!DOCTYPE html>
<html>
<head>
<title>X3D Agent Viewer</title>
<script src="https://create3d.org/x-ite/latest/x-ite.min.js"></script>
<style>
body { font-family: sans-serif; display: flex; height: 100vh; margin: 0; background: #121212; color: #fff; }
#viewer { flex: 2; height: 100%; }
#control-panel { flex: 1; padding: 20px; display: flex; flex-direction: column; background: #1e1e1e; border-left: 1px solid #333; }
textarea { width: 100%; height: 100px; background: #2d2d2d; color: #fff; border: 1px solid #444; padding: 10px; margin-bottom: 10px; resize: none; }
button { padding: 10px; background: #007acc; color: white; border: none; cursor: pointer; font-weight: bold; }
button:hover { background: #005999; }
#log { flex-grow: 1; background: #111; padding: 10px; margin-top: 10px; overflow-y: auto; font-family: monospace; font-size: 12px; border: 1px solid #333; }
</style>
</head>
<body>
<div id="viewer">
    <x3d><scene><inline url="scene.x3d"></inline></scene></x3d>
</div>
<div id="control-panel">
    <h3>3D Scene Controller</h3>
    <textarea id="promptInput" placeholder="Type something like: Add an orange sphere at 0 2 -2"></textarea>
    <button onclick="sendPrompt()">Run Command</button>
    <div id="log">System ready...</div>
</div>
<script>
async function sendPrompt() {
    const promptInput = document.getElementById('promptInput');
    const prompt = promptInput.value;
    const log = document.getElementById('log');
    if (!prompt.trim()) return;
    
    log.innerHTML += `<div>Sending: ${prompt}</div>`;
    try {
        const res = await fetch('/api/agent', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt})
        });
        const data = await res.json();
        log.innerHTML += `<div><b>System:</b> ${data.response}</div>`;
        // Force X-ite inline viewer to reload the mutated X3D file
        document.querySelector('inline').loadURL(["scene.x3d?" + Date.now()]);
    } catch (err) {
        log.innerHTML += `<div style="color:red;">Error: ${err}</div>`;
    }
    log.scrollTop = log.scrollHeight;
    promptInput.value = '';
}
</script>
</body>
</html>"""
