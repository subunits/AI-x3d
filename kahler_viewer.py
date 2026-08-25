"""
Kähler / Hyperkähler Geometry Viewer
Standalone FastAPI app — serves an X3D interactive explorer of differential-geometric surfaces.
"""
import math, os, re
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Color utilities ────────────────────────────────────────────────────────────

def curvature_color(k, k_min=-2.0, k_max=2.0):
    t = (k - k_min) / (k_max - k_min)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        s = t * 2
        return (0.22 * s, 0.76 * s + 0.22 * (1 - s), 0.97 * (1 - s) + 0.22 * s)
    else:
        s = (t - 0.5) * 2
        return (0.98 * s + 0.22 * (1 - s), 0.55 * (1 - s) + 0.08 * s, 0.08 * (1 - s))

def ifs(pts, idxs, colors=None, crease=1.2):
    pts_str = " ".join(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}" for p in pts)
    idx_str = " ".join(idxs)
    if colors:
        col_str = " ".join(f"{c[0]:.3f} {c[1]:.3f} {c[2]:.3f}" for c in colors)
        return (f'<IndexedFaceSet coordIndex="{idx_str}" colorPerVertex="true" '
                f'solid="false" creaseAngle="{crease}">'
                f'<Coordinate point="{pts_str}"/>'
                f'<Color color="{col_str}"/>'
                f'</IndexedFaceSet>')
    return (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="{crease}">'
            f'<Coordinate point="{pts_str}"/>'
            f'</IndexedFaceSet>')

def grid_mesh(pts, Nu, Nv, colors=None):
    idxs = []
    for i in range(Nu - 1):
        for j in range(Nv - 1):
            a = i * Nv + j
            b = a + 1
            c = (i + 1) * Nv + j + 1
            d = (i + 1) * Nv + j
            idxs.append(f"{a} {b} {c} {d} -1")
    return ifs(pts, idxs, colors)

# ── Surface generators ─────────────────────────────────────────────────────────

def surface_fubini_study(N=60, scale=2.0):
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            u = (i / (N - 1)) * 2 * math.pi
            v = (j / (N - 1)) * math.pi
            pts.append((math.sin(v)*math.cos(u)*scale, math.cos(v)*scale, math.sin(v)*math.sin(u)*scale))
            colors.append(curvature_color(1.0, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    return f'<Shape>{geo}<Appearance><Material transparency="0.05"/></Appearance></Shape>\n'

def surface_poincare_disk(N=55, R=2.5):
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            r = 0.92 * i / (N - 1)
            theta = 2 * math.pi * j / (N - 1)
            x = r * math.cos(theta) * R
            z = r * math.sin(theta) * R
            phi = -math.log(max(1e-8, 1 - r * r)) if r < 0.999 else 3.0
            y = min(phi * 0.3, 3.0)
            pts.append((x, y, z))
            colors.append(curvature_color(-1.0, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    return f'<Shape>{geo}<Appearance><Material transparency="0.05"/></Appearance></Shape>\n'

def surface_kahler_potential(N=55, t=1.0, scale=2.5):
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            x = -scale + 2 * scale * i / (N - 1)
            z = -scale + 2 * scale * j / (N - 1)
            r2 = x * x + z * z
            if t != 0:
                phi = math.log(max(1e-8, 1 + t * r2)) / t
                K = t / max(1e-8, (1 + t * r2) ** 2)
            else:
                phi = r2
                K = 0.0
            y = min(max(phi * 0.5, -2.0), 3.5)
            pts.append((x, y, z))
            colors.append(curvature_color(K * 4, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    return f'<Shape>{geo}<Appearance><Material transparency="0.05"/></Appearance></Shape>\n'

def surface_taub_nut(N=40, c=1.0, scale=1.6):
    xml = ""
    n_shells, n_u, n_v = 7, 28, 16
    r_values = [0.3 + 3.5 * (k / (n_shells - 1)) ** 1.4 for k in range(n_shells)]
    for r in r_values:
        V = 1.0 + c / max(r, 0.01)
        R = r * math.sqrt(V) * scale / 3.5
        transparency = 0.15 + 0.55 * (r / 3.8)
        col = curvature_color(V - 1.0, 0.0, 3.5)
        pts, colors = [], []
        for i in range(n_u):
            for j in range(n_v):
                theta = math.pi * j / (n_v - 1)
                phi_a = 2 * math.pi * i / (n_u - 1)
                pts.append((R*math.sin(theta)*math.cos(phi_a), R*math.cos(theta), R*math.sin(theta)*math.sin(phi_a)))
                colors.append(col)
        geo = grid_mesh(pts, n_u, n_v, colors)
        xml += f'<Shape>{geo}<Appearance><Material transparency="{transparency:.2f}"/></Appearance></Shape>\n'
    return xml

def surface_eguchi_hanson(N=52, a=1.0, scale=1.5):
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            t = i / (N - 1)
            r = a + 4.0 * t ** 1.2
            phi_a = 2 * math.pi * j / (N - 1)
            f2 = max(0.0, 1.0 - (a / max(r, 1e-6)) ** 4)
            R_base = r * math.sqrt(f2) * scale / 3.0
            pts.append((R_base*math.cos(phi_a), (r-a)*scale/3.0, R_base*math.sin(phi_a)))
            curv = 12 * a**4 / max(r**6, 1e-6)
            colors.append(curvature_color(curv * 2 - 0.5, -0.5, 2.0))
    geo = grid_mesh(pts, N, N, colors)
    return f'<Shape>{geo}<Appearance><Material transparency="0.05"/></Appearance></Shape>\n'

def surface_cy_slice(N=58, scale=1.8):
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            r1 = 0.05 + 1.5 * i / (N - 1)
            theta1 = 2 * math.pi * j / (N - 1)
            z1_5r = r1**5 * math.cos(5 * theta1)
            z1_5i = r1**5 * math.sin(5 * theta1)
            w_r, w_i = -1 - z1_5r, -z1_5i
            w_mod = math.sqrt(w_r**2 + w_i**2)
            if w_mod < 1e-9:
                pts.append((0, 0, 0)); colors.append((0.2, 0.8, 0.5)); continue
            r2 = w_mod ** 0.2
            theta2 = math.atan2(w_i, w_r) / 5.0
            pts.append((r2*math.cos(theta2)*scale, r1*math.cos(theta1)*scale, r2*math.sin(theta2)*scale))
            colors.append(curvature_color(1.0/max(r1*r2, 0.1) - 2, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    return f'<Shape>{geo}<Appearance><Material transparency="0.05"/></Appearance></Shape>\n'

def surface_hk_flat(N=32, scale=2.2):
    xml = ""
    planes = [
        ((1,0,0),(0,1,0),(0.31,0.43,0.97),"I"),
        ((1,0,0),(0,0,1),(0.75,0.25,0.92),"J"),
        ((0,1,0),(0,0,1),(0.20,0.83,0.55),"K"),
    ]
    for (e1, e2, col, label) in planes:
        r, g, b = col
        pts_list, idxs = [], []
        for i in range(N):
            for j in range(N):
                u = -scale + 2*scale*i/(N-1)
                v = -scale + 2*scale*j/(N-1)
                pts_list.append((e1[0]*u+e2[0]*v, e1[1]*u+e2[1]*v, e1[2]*u+e2[2]*v))
        for i in range(N-1):
            for j in range(N-1):
                aa=i*N+j; bb=aa+1; cc=(i+1)*N+j+1; dd=(i+1)*N+j
                idxs.append(f"{aa} {bb} {cc} {dd} -1")
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts_list)
        idx_str = " ".join(idxs)
        geo = (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="0">'
               f'<Coordinate point="{pts_str}"/></IndexedFaceSet>')
        xml += (f'<Shape>{geo}<Appearance><Material diffuseColor="{r:.2f} {g:.2f} {b:.2f}" '
                f'transparency="0.50"/></Appearance></Shape>\n')
        line_mat = (f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}" '
                    f'transparency="0.3"/></Appearance>')
        for k in range(9):
            t = -scale + 2*scale*k/8
            for (ea, eb) in [(e1,e2),(e2,e1)]:
                p0=(ea[0]*t+eb[0]*(-scale), ea[1]*t+eb[1]*(-scale), ea[2]*t+eb[2]*(-scale))
                p1=(ea[0]*t+eb[0]*( scale), ea[1]*t+eb[1]*( scale), ea[2]*t+eb[2]*( scale))
                ps=f"{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f}"
                xml += (f'<Shape><IndexedLineSet coordIndex="0 1 -1">'
                        f'<Coordinate point="{ps}"/></IndexedLineSet>{line_mat}</Shape>\n')
    return xml

def geodesic_grid(N=24, R=2.0, col=(0.22, 0.55, 0.97)):
    xml = ""
    r,g,b = col
    mat_str = f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}" transparency="0.3"/></Appearance>'
    for k in range(12):
        phi_offset = math.pi * k / 12
        pts = [(R*math.cos(2*math.pi*i/N)*math.sin(phi_offset),
                R*math.cos(phi_offset),
                R*math.sin(2*math.pi*i/N)*math.sin(phi_offset)) for i in range(N+1)]
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts)
        idx_str = " ".join(str(i) for i in range(N+1)) + " -1"
        xml += (f'<Shape><IndexedLineSet coordIndex="{idx_str}">'
                f'<Coordinate point="{pts_str}"/></IndexedLineSet>{mat_str}</Shape>\n')
    return xml

def poincare_geodesics(N=32, R=2.5):
    xml = ""
    mat_str = '<Appearance><Material emissiveColor="0.22 0.70 0.97" transparency="0.4"/></Appearance>'
    for k in range(8):
        angle = math.pi * k / 8
        pts = []
        for i in range(N+1):
            s = -1.0 + 2.0*i/N
            r = abs(s)*0.88
            theta = angle + (math.pi if s < 0 else 0)
            x = r*math.cos(theta)*R
            z = r*math.sin(theta)*R
            y = min(-math.log(max(1e-8, 1-r*r))*0.3, 3.0) if r < 0.999 else 3.0
            pts.append((x, y, z))
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts)
        idx_str = " ".join(str(i) for i in range(N+1)) + " -1"
        xml += (f'<Shape><IndexedLineSet coordIndex="{idx_str}">'
                f'<Coordinate point="{pts_str}"/></IndexedLineSet>{mat_str}</Shape>\n')
    return xml

# ── Centroid + scene builder ───────────────────────────────────────────────────

SURFACES = {
    "fubini_study":    {"label":"CP¹ — Fubini-Study",        "category":"kähler",      "param":None},
    "poincare":        {"label":"Poincaré Disk — H²",         "category":"kähler",      "param":None},
    "potential_family":{"label":"Kähler Potential Family",    "category":"kähler",      "param":"t"},
    "taub_nut":        {"label":"Taub-NUT Space",              "category":"hyperkähler", "param":"c"},
    "eguchi_hanson":   {"label":"Eguchi-Hanson Space",         "category":"hyperkähler", "param":"a"},
    "cy_quintic":      {"label":"Calabi-Yau Quintic (slice)",  "category":"hyperkähler", "param":None},
    "hk_flat":         {"label":"ℝ⁴ — Flat Hyperkähler",      "category":"hyperkähler", "param":None},
}

def _centroid(xml_fragment):
    coords = re.findall(r'point="([^"]+)"', xml_fragment)
    pts = []
    for c in coords:
        nums = c.split()
        for i in range(0, len(nums)-2, 3):
            try: pts.append((float(nums[i]), float(nums[i+1]), float(nums[i+2])))
            except: pass
    if not pts: return (0.0, 0.0, 0.0)
    return (sum(p[0] for p in pts)/len(pts),
            sum(p[1] for p in pts)/len(pts),
            sum(p[2] for p in pts)/len(pts))

def build_x3d(surface_id, param=1.0):
    cat = SURFACES.get(surface_id, {}).get("category", "kähler")
    sky = "0.04 0.05 0.10" if cat == "kähler" else "0.07 0.04 0.12"
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
           f'<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "">\n'
           f'<X3D profile="Immersive" version="3.3">\n  <Scene>\n'
           f'    <Background skyColor="{sky}"/>\n'
           f'    <NavigationInfo type="EXAMINE ANY"/>\n'
           f'    <DirectionalLight direction="-1 -2 -1" intensity="1.2"/>\n'
           f'    <DirectionalLight direction="1 1 0.5" intensity="0.5" color="0.8 0.85 1"/>\n'
           f'    <Viewpoint position="0 0 9" orientation="0 1 0 0"/>\n')
    builders = {
        "fubini_study":    lambda: surface_fubini_study() + geodesic_grid(),
        "poincare":        lambda: surface_poincare_disk() + poincare_geodesics(),
        "potential_family":lambda: surface_kahler_potential(t=param),
        "taub_nut":        lambda: surface_taub_nut(c=param),
        "eguchi_hanson":   lambda: surface_eguchi_hanson(a=param),
        "cy_quintic":      lambda: surface_cy_slice(),
        "hk_flat":         lambda: surface_hk_flat(),
    }
    geo = builders.get(surface_id, builders["fubini_study"])()
    cx, cy, cz = _centroid(geo)
    xml += f'    <Transform translation="{-cx:.3f} {-cy:.3f} {-cz:.3f}">\n{geo}    </Transform>\n'
    xml += '  </Scene>\n</X3D>\n'
    return xml

# ── API ────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML

@app.get("/scene/{surface_id}")
async def get_scene(surface_id: str, param: float = 1.0):
    xml = build_x3d(surface_id, param)
    return HTMLResponse(content=xml, media_type="model/x3d+xml",
        headers={"Cache-Control": "no-cache, no-store"})

@app.get("/surfaces")
async def list_surfaces():
    return JSONResponse({"surfaces": SURFACES})

# ── HTML ───────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Kähler · Hyperkähler Geometry</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/x_ite@16.1.2/dist/x_ite.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --void:#07080c; --panel:#0d0f18; --border:#1a1f35;
      --accent:#4f6ef7; --accent2:#c084fc; --accent3:#34d399;
      --hot:#f97316; --cold:#38bdf8; --text:#e2e8f0; --muted:#4a5568;
      --mono:'Space Mono',monospace; --sans:'Inter',sans-serif;
      --sat:env(safe-area-inset-top,0px); --sab:env(safe-area-inset-bottom,0px);
      --sal:env(safe-area-inset-left,0px); --sar:env(safe-area-inset-right,0px);
    }
    html, body {
      height: 100%; background: var(--void); color: var(--text);
      font-family: var(--sans); position: fixed; width: 100%;
      overflow: hidden; -webkit-text-size-adjust: 100%;
    }

    /* ── Shell ── */
    .shell {
      display: flex; flex-direction: column;
      /* Use dvh so iOS toolbar doesn't cause reflow */
      height: 100dvh;
      padding-top: var(--sat); padding-left: var(--sal); padding-right: var(--sar);
    }

    /* ── Header ── */
    header {
      flex: 0 0 48px; background: var(--panel); border-bottom: 1px solid var(--border);
      display: flex; align-items: center; padding: 0 16px; gap: 12px; z-index: 10;
    }
    .logo { font-family: var(--mono); font-size: 13px; color: var(--accent);
      letter-spacing: .04em; white-space: nowrap; }
    .logo span { color: var(--accent2); }
    .header-tags { display: flex; gap: 6px; margin-left: auto; }
    .tag {
      font-family: var(--mono); font-size: 9px; padding: 3px 7px;
      border-radius: 3px; letter-spacing: .06em; white-space: nowrap;
      cursor: pointer; opacity: .45; transition: opacity .15s;
      -webkit-tap-highlight-color: transparent; user-select: none;
    }
    .tag.active { opacity: 1; }
    .tag-k  { background: rgba(79,110,247,.15); color: var(--accent);  border: 1px solid rgba(79,110,247,.3); }
    .tag-hk { background: rgba(192,132,252,.15); color: var(--accent2); border: 1px solid rgba(192,132,252,.3); }

    /* ── Body ── */
    .body { flex: 1; display: flex; flex-direction: column; min-height: 0; }

    /* ── Viewport ── */
    .viewport { flex: 1; background: #050609; min-height: 0; position: relative; overflow: hidden; }
    x3d-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }

    /* ── Drawer: FIXED height so nothing ever shifts layout ── */
    .drawer {
      flex: 0 0 44vh;          /* fixed — will never grow or shrink */
      display: flex; flex-direction: column;
      background: var(--panel); border-top: 1px solid var(--border);
      overflow: hidden;        /* contain everything inside */
      padding-bottom: var(--sab);
    }

    /* Tab bar */
    .drawer-tabs {
      flex: 0 0 44px; display: flex;
      border-bottom: 1px solid var(--border);
    }
    .dtab {
      flex: 1; font-size: 11px; font-weight: 600; text-align: center;
      color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent;
      text-transform: uppercase; letter-spacing: .05em;
      display: flex; align-items: center; justify-content: center;
      -webkit-tap-highlight-color: transparent; user-select: none;
    }
    .dtab.active { color: var(--accent); border-bottom-color: var(--accent); }
    .dtab.active.hk { color: var(--accent2); border-bottom-color: var(--accent2); }

    /* Pane stack: all panes sit in the same absolute space */
    .drawer-body { position: relative; flex: 1; min-height: 0; overflow: hidden; }
    .drawer-pane {
      position: absolute; inset: 0;
      display: flex; flex-direction: column; overflow: hidden;
      visibility: hidden; pointer-events: none;
    }
    .drawer-pane.active { visibility: visible; pointer-events: auto; }

    /* Surfaces pane */
    .surface-list {
      flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
      padding: 4px 10px 8px;
    }
    .section-label {
      font-family: var(--mono); font-size: 9px; letter-spacing: .12em;
      color: var(--muted); text-transform: uppercase; padding: 10px 6px 5px;
    }
    .surface-item {
      padding: 10px 12px; border-radius: 8px; cursor: pointer;
      margin-bottom: 2px; border: 1px solid transparent;
      min-height: 50px; display: flex; flex-direction: column; justify-content: center;
      -webkit-tap-highlight-color: transparent; user-select: none;
    }
    .surface-item:active { opacity: .7; }
    .surface-item.active { background: rgba(79,110,247,.12); border-color: rgba(79,110,247,.3); }
    .surface-item.active.hk { background: rgba(192,132,252,.10); border-color: rgba(192,132,252,.25); }
    .surface-name { font-size: 13px; font-weight: 500; color: var(--text); }
    .surface-cat  { font-family: var(--mono); font-size: 9px; color: var(--muted);
      margin-top: 2px; text-transform: uppercase; letter-spacing: .08em; }

    /* Colormap strip */
    .cm-section {
      flex: 0 0 auto; padding: 8px 16px 10px;
      border-top: 1px solid var(--border);
    }
    .cm-label { font-family: var(--mono); font-size: 9px; color: var(--muted);
      text-transform: uppercase; letter-spacing: .1em; margin-bottom: 5px; }
    .cm-bar { height: 6px; border-radius: 3px; margin-bottom: 4px;
      background: linear-gradient(to right, var(--cold), var(--accent3), var(--hot)); }
    .cm-ticks { display: flex; justify-content: space-between;
      font-family: var(--mono); font-size: 9px; color: var(--muted); }

    /* Info pane */
    .info-pane { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; padding: 14px 16px; }
    .info-row { margin-bottom: 12px; }
    .info-key { font-family: var(--mono); font-size: 9px; color: var(--muted);
      text-transform: uppercase; letter-spacing: .1em; margin-bottom: 4px; }
    .info-val { font-family: var(--mono); font-size: 12px; color: var(--accent);
      line-height: 1.4; word-break: break-word; }
    .info-val.hk     { color: var(--accent2); }
    .info-val.ricci0 { color: var(--accent3); }
    .info-desc { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-top: 12px; }

    /* Param pane */
    .param-pane { flex: 1; padding: 18px 20px; display: flex; flex-direction: column; gap: 16px; }
    .param-pane.hidden { display: none; }
    .param-label { font-family: var(--mono); font-size: 10px; color: var(--muted);
      text-transform: uppercase; letter-spacing: .1em; }
    .param-row { display: flex; align-items: center; gap: 14px; }
    input[type=range] { flex: 1; height: 32px; accent-color: var(--accent);
      cursor: pointer; touch-action: none; }
    .param-val { font-family: var(--mono); font-size: 14px; color: var(--accent);
      min-width: 42px; text-align: right; }
    .param-note { font-size: 12px; color: var(--muted); line-height: 1.5; }

    /* ── Landscape / iPad ── */
    @media (min-width: 700px) and (orientation: landscape), (min-width: 900px) {
      .shell  { flex-direction: row; flex-wrap: wrap; }
      header  { flex: 0 0 48px; width: 100%; order: -1; }
      .body   { flex-direction: row; flex: 1; min-height: 0; width: 100%; }
      .viewport { flex: 1; }
      .drawer {
        flex: 0 0 300px; height: 100%;
        border-top: none; border-left: 1px solid var(--border);
        padding-bottom: 0; padding-right: var(--sar);
      }
    }
    @media (min-width: 1024px) { .drawer { flex-basis: 340px; } }
  </style>
</head>
<body>
<div class="shell">
  <header>
    <div class="logo">Kähler<span> / Hyperkähler</span></div>
    <div class="header-tags">
      <span class="tag tag-k  active" id="filterK"  onclick="toggleFilter('kähler')">KÄHLER</span>
      <span class="tag tag-hk active" id="filterHK" onclick="toggleFilter('hyperkähler')">HYPERKÄHLER</span>
    </div>
  </header>

  <div class="body">
    <div class="viewport">
      <x3d-canvas id="canvas" contentScale="auto" update="auto"></x3d-canvas>
    </div>

    <div class="drawer">
      <div class="drawer-tabs">
        <div class="dtab active" id="tab-surfaces" onclick="switchTab('surfaces')">Surfaces</div>
        <div class="dtab"        id="tab-info"     onclick="switchTab('info')">Info</div>
        <div class="dtab"        id="tab-param"    onclick="switchTab('param')">Parameter</div>
      </div>

      <div class="drawer-body">

        <div class="drawer-pane active" id="pane-surfaces">
          <div class="surface-list" id="surfaceList"></div>
          <div class="cm-section">
            <div class="cm-label">Curvature</div>
            <div class="cm-bar"></div>
            <div class="cm-ticks"><span>K &lt; 0</span><span>K = 0</span><span>K &gt; 0</span></div>
          </div>
        </div>

        <div class="drawer-pane" id="pane-info">
          <div class="info-pane">
            <div class="info-row">
              <div class="info-key">Kähler potential φ</div>
              <div class="info-val" id="infoEq">—</div>
            </div>
            <div class="info-row">
              <div class="info-key">Curvature</div>
              <div class="info-val" id="infoCurv">—</div>
            </div>
            <div class="info-row">
              <div class="info-key">Holonomy group</div>
              <div class="info-val" id="infoHol">—</div>
            </div>
            <div class="info-desc" id="infoDesc">Select a surface to see its geometry.</div>
          </div>
        </div>

        <div class="drawer-pane" id="pane-param">
          <div class="param-pane" id="paramPane">
            <div class="param-label">Parameter: <span id="paramName">t</span></div>
            <div class="param-row">
              <input type="range" id="paramSlider" min="0.05" max="3" step="0.05" value="1">
              <span class="param-val" id="paramDisplay">1.00</span>
            </div>
            <div class="param-note" id="paramNote">Drag to morph the surface.</div>
          </div>
          <div class="param-pane hidden" id="noParam">
            <div class="param-label">No parameter</div>
            <div class="param-note">This surface has no adjustable parameter.<br>
              Try Kähler Potential Family, Taub-NUT, or Eguchi-Hanson.</div>
          </div>
        </div>

      </div><!-- /drawer-body -->
    </div><!-- /drawer -->
  </div><!-- /body -->
</div><!-- /shell -->

<script>
const SURFACES = {
  fubini_study:    {label:"CP¹ — Fubini-Study",       category:"kähler",      eq:"φ = log(1 + |z|²)",                     curv:"K = +1",                  hol:"U(1)",        param:null, paramNote:null,
    desc:"The complex projective line CP¹ ≅ S² with the Fubini-Study metric. Positive constant holomorphic sectional curvature. Geodesics are great circles."},
  poincare:        {label:"Poincaré Disk — H²",        category:"kähler",      eq:"φ = −log(1 − |z|²)",                    curv:"K = −1",                  hol:"U(1)",        param:null, paramNote:null,
    desc:"The hyperbolic plane with its unique complete Kähler metric. Negative constant curvature. Geodesics are circular arcs perpendicular to the boundary."},
  potential_family:{label:"Kähler Potential Family",   category:"kähler",      eq:"φ_t = t⁻¹ log(1 + t|z|²)",             curv:"K(z) = t·(1+t|z|²)⁻²",  hol:"U(1)",        param:"t",  paramNote:"t=0: flat ℂ · t=1: Fubini-Study · t≫1: concentrated curvature",
    desc:"A one-parameter deformation between flat ℂ (t→0) and CP¹ (t=1). Height encodes the potential; color encodes position-dependent curvature K(z)."},
  taub_nut:        {label:"Taub-NUT Space",             category:"hyperkähler", eq:"V(r) = 1 + c/r",                        curv:"Ric = 0",                 hol:"Sp(1)≅SU(2)", param:"c",  paramNote:"c = NUT charge — larger c = stronger gravitational instanton",
    desc:"Complete hyperkähler 4-manifold with NUT charge c. Concentric shells warped by √V(r); inner shells orange (high curvature), outer shells green (V→1)."},
  eguchi_hanson:   {label:"Eguchi-Hanson Space",        category:"hyperkähler", eq:"f² = 1 − (a/r)⁴",                      curv:"Ric=0, |Rm|²∝(a/r)⁸",  hol:"Sp(1)",       param:"a",  paramNote:"a = bolt radius — curvature concentrates at the S² bolt at r = a",
    desc:"The simplest ALE gravitational instanton — a hyperkähler metric on T*CP¹. Contains a 2-sphere bolt at r=a. Curvature decays as r⁻⁸ away from the bolt."},
  cy_quintic:      {label:"Calabi-Yau Quintic (slice)", category:"hyperkähler", eq:"Σᵢ zᵢ⁵ = 0 ⊂ CP⁴",                   curv:"Ric = 0",                 hol:"SU(3)",       param:null, paramNote:null,
    desc:"Real 2-slice of the Fermat quintic — the most-studied compact CY threefold in string theory (h¹¹=1, h²¹=101). Color encodes |Ω|², the holomorphic 3-form."},
  hk_flat:         {label:"ℝ⁴ — Flat Hyperkähler",     category:"hyperkähler", eq:"ωI=dx¹∧dx², ωJ=dx¹∧dx³, ωK=dx²∧dx³", curv:"K = 0",                   hol:"Sp(1)⊂SO(4)", param:null, paramNote:null,
    desc:"The flat hyperkähler manifold ℝ⁴ ≅ ℍ. Three complex structures I, J, K satisfy IJ=K (quaternion algebra). Each orthogonal plane represents one Kähler form."},
};

let currentSurface = 'fubini_study', currentParam = 1.0;
const canvas = document.getElementById('canvas');

function loadSurface(id, param) {
  currentSurface = id;
  currentParam = (param != null) ? param : 1.0;
  const url = `/scene/${id}?param=${currentParam}&t=${Date.now()}`;
  try {
    if (canvas.browser && canvas.browser.loadURL) canvas.browser.loadURL(new X3D.MFString(url));
    else canvas.setAttribute('src', url);
  } catch(e) {
    canvas.removeAttribute('src');
    setTimeout(() => canvas.setAttribute('src', url), 10);
  }
  updateInfo(id); updateSidebarActive(id);
}

function updateInfo(id) {
  const s = SURFACES[id]; if (!s) return;
  document.getElementById('infoEq').textContent   = s.eq;
  document.getElementById('infoCurv').textContent = s.curv;
  document.getElementById('infoHol').textContent  = s.hol;
  document.getElementById('infoDesc').textContent = s.desc;
  const cv = document.getElementById('infoCurv');
  cv.className = 'info-val' + (s.curv.includes('Ric = 0')||s.curv==='K = 0' ? ' ricci0' : s.category==='hyperkähler' ? ' hk' : '');
  if (s.param) {
    document.getElementById('paramPane').classList.remove('hidden');
    document.getElementById('noParam').classList.add('hidden');
    document.getElementById('paramName').textContent = s.param;
    if (s.paramNote) document.getElementById('paramNote').textContent = s.paramNote;
  } else {
    document.getElementById('paramPane').classList.add('hidden');
    document.getElementById('noParam').classList.remove('hidden');
  }
  document.getElementById('tab-info').classList.toggle('hk', s.category==='hyperkähler');
}

function updateSidebarActive(id) {
  document.querySelectorAll('.surface-item').forEach(el => {
    const on = el.dataset.id === id;
    el.classList.toggle('active', on);
    el.classList.toggle('hk', on && SURFACES[id].category==='hyperkähler');
  });
}

function switchTab(name) {
  ['surfaces','info','param'].forEach(t => {
    document.getElementById('tab-' +t).classList.toggle('active', t===name);
    document.getElementById('pane-'+t).classList.toggle('active', t===name);
  });
}

const filterState = {'kähler':true,'hyperkähler':true};
function toggleFilter(cat) {
  const bothOn = filterState['kähler'] && filterState['hyperkähler'];
  if (bothOn) { filterState['kähler']=(cat==='kähler'); filterState['hyperkähler']=(cat==='hyperkähler'); }
  else        { filterState['kähler']=true; filterState['hyperkähler']=true; }
  document.getElementById('filterK') .classList.toggle('active', filterState['kähler']);
  document.getElementById('filterHK').classList.toggle('active', filterState['hyperkähler']);
  document.querySelectorAll('.surface-item').forEach(el => {
    const c = SURFACES[el.dataset.id]?.category;
    el.style.visibility  = filterState[c] ? '' : 'hidden';
    el.style.pointerEvents = filterState[c] ? '' : 'none';
  });
  document.querySelectorAll('.section-label').forEach(el => {
    if (el.dataset.cat) el.style.visibility = filterState[el.dataset.cat] ? '' : 'hidden';
  });
}

// Build surface list
const list = document.getElementById('surfaceList');
let lastCat = null;
Object.entries(SURFACES).forEach(([id, s]) => {
  if (s.category !== lastCat) {
    lastCat = s.category;
    const lbl = document.createElement('div');
    lbl.className='section-label'; lbl.dataset.cat=s.category;
    lbl.textContent = s.category==='kähler' ? 'Kähler' : 'Hyperkähler';
    list.appendChild(lbl);
  }
  const item = document.createElement('div');
  item.className='surface-item'; item.dataset.id=id;
  item.innerHTML=`<div class="surface-name">${s.label}</div>
    <div class="surface-cat">${s.category} · ${s.hol}</div>`;
  item.onclick = () => loadSurface(id, currentParam);
  list.appendChild(item);
});

// Param slider
const slider=document.getElementById('paramSlider'), display=document.getElementById('paramDisplay');
let debounce;
slider.addEventListener('input', () => {
  currentParam = parseFloat(slider.value);
  display.textContent = currentParam.toFixed(2);
  clearTimeout(debounce);
  debounce = setTimeout(() => { if (SURFACES[currentSurface].param) loadSurface(currentSurface, currentParam); }, 150);
});

window.addEventListener('load', () => setTimeout(() => loadSurface('fubini_study'), 300));
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
