"""
Kähler / Hyperkähler Geometry Viewer
Standalone FastAPI app — serves an X3D interactive explorer of differential-geometric surfaces.
"""
import math, os, re
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Color utilities ────────────────────────────────────────────────────────────

def curvature_color(k, k_min=-2.0, k_max=2.0):
    """Map curvature k to RGB using a blue-green-orange spectral map."""
    t = (k - k_min) / (k_max - k_min)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        s = t * 2
        return (0.22 * s, 0.76 * s + 0.22 * (1 - s), 0.97 * (1 - s) + 0.22 * s)
    else:
        s = (t - 0.5) * 2
        return (0.98 * s + 0.22 * (1 - s), 0.55 * (1 - s) + 0.08 * s, 0.08 * (1 - s))


def mat(r, g, b, transparency=0.0, emit=False):
    if emit:
        return (f'<Appearance><Material emissiveColor="{r:.3f} {g:.3f} {b:.3f}" '
                f'transparency="{transparency:.2f}"/></Appearance>')
    return (f'<Appearance><Material diffuseColor="{r:.3f} {g:.3f} {b:.3f}" '
            f'specularColor="0.3 0.3 0.4" shininess="0.5" '
            f'transparency="{transparency:.2f}"/></Appearance>')


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


def ils(pts, col):
    """IndexedLineSet for grid lines."""
    pts_str = " ".join(f"{p[0]:.4f} {p[1]:.4f} {p[2]:.4f}" for p in pts)
    idx_str = " ".join(str(i) for i in range(len(pts))) + " -1"
    r,g,b = col
    return (f'<Shape><IndexedLineSet coordIndex="{idx_str}">'
            f'<Coordinate point="{pts_str}"/></IndexedLineSet>'
            f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}"/></Appearance>'
            f'</Shape>')


def grid_mesh(pts, Nu, Nv, colors=None):
    """Build quad mesh indices from Nu×Nv grid of points."""
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
    """
    CP¹ with Fubini-Study metric — stereographic projection of S².
    Kähler potential: φ = log(1 + |z|²)
    Gaussian curvature: K = +1 everywhere (unit sphere, radius=1 mathematically;
    displayed at scale=2 for visibility)
    """
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            u = (i / (N - 1)) * 2 * math.pi
            v = (j / (N - 1)) * math.pi
            x = math.sin(v) * math.cos(u) * scale
            y = math.cos(v) * scale
            z = math.sin(v) * math.sin(u) * scale
            pts.append((x, y, z))
            colors.append(curvature_color(1.0, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_poincare_disk(N=55, R=2.5):
    """
    Poincaré disk model of H² — hyperbolic plane.
    Kähler potential: φ = -log(1 - |z|²)
    Gaussian curvature: K = -1 everywhere
    Visualized as the Beltrami-Klein embedding in 3D (height = hyperbolic area element)
    """
    pts, colors = [], []
    lim = 0.92
    for i in range(N):
        for j in range(N):
            r = lim * i / (N - 1)
            theta = 2 * math.pi * j / (N - 1)
            x = r * math.cos(theta) * R
            z = r * math.sin(theta) * R
            if r < 0.999:
                phi = -math.log(max(1e-8, 1 - r * r))
                y = min(phi * 0.3, 3.0)
            else:
                y = 3.0
            pts.append((x, y, z))
            colors.append(curvature_color(-1.0, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_kahler_potential(N=55, t=1.0, scale=2.5):
    """
    Family of Kähler potentials: φ_t = (1/t) log(1 + t|z|²)
    """
    pts, colors = [], []
    lim = scale
    for i in range(N):
        for j in range(N):
            x = -lim + 2 * lim * i / (N - 1)
            z = -lim + 2 * lim * j / (N - 1)
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
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_taub_nut(N=40, c=1.0, scale=1.6):
    """Taub-NUT space — hyperkähler 4-manifold with U(1) isometry."""
    xml = ""
    n_shells = 7
    n_u, n_v = 28, 16
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
                x = R * math.sin(theta) * math.cos(phi_a)
                y = R * math.cos(theta)
                z = R * math.sin(theta) * math.sin(phi_a)
                pts.append((x, y, z))
                colors.append(col)
        geo = grid_mesh(pts, n_u, n_v, colors)
        m = f'<Appearance><Material transparency="{transparency:.2f}"/></Appearance>'
        xml += f'<Shape>{geo}{m}</Shape>\n'
    return xml


def surface_eguchi_hanson(N=52, a=1.0, scale=1.5):
    """Eguchi-Hanson space — hyperkähler 4-manifold."""
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            t = i / (N - 1)
            r = a + 4.0 * t ** 1.2
            phi_a = 2 * math.pi * j / (N - 1)
            f2 = max(0.0, 1.0 - (a / max(r, 1e-6)) ** 4)
            R_base = r * math.sqrt(f2) * scale / 3.0
            x = R_base * math.cos(phi_a)
            z = R_base * math.sin(phi_a)
            y = (r - a) * scale / 3.0
            pts.append((x, y, z))
            curv = 12 * a**4 / max(r**6, 1e-6)
            colors.append(curvature_color(curv * 2 - 0.5, -0.5, 2.0))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_cy_slice(N=58, phase=0.0, scale=1.8):
    """Calabi-Yau quintic cross-section."""
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            r1 = 0.05 + 1.5 * i / (N - 1)
            theta1 = 2 * math.pi * j / (N - 1) + phase
            z1r = r1 * math.cos(theta1)
            z1i = r1 * math.sin(theta1)
            z1_5r = r1**5 * math.cos(5 * theta1)
            z1_5i = r1**5 * math.sin(5 * theta1)
            w_r = -1 - z1_5r
            w_i = -z1_5i
            w_mod = math.sqrt(w_r**2 + w_i**2)
            if w_mod < 1e-9:
                pts.append((0, 0, 0))
                colors.append((0.2, 0.8, 0.5))
                continue
            w_arg = math.atan2(w_i, w_r)
            r2 = w_mod ** 0.2
            theta2 = w_arg / 5.0
            z2r = r2 * math.cos(theta2)
            z2i = r2 * math.sin(theta2)
            x = z2r * scale
            z_pos = z2i * scale
            y = z1r * scale
            pts.append((x, y, z_pos))
            omega_mag = 1.0 / max(r1 * r2, 0.1)
            colors.append(curvature_color(omega_mag - 2, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_hk_flat(N=32, scale=2.2):
    """Flat ℝ⁴ ≅ ℍ with hyperkähler structure."""
    xml = ""
    planes = [
        ((1,0,0), (0,1,0), (0.31, 0.43, 0.97), "I"),
        ((1,0,0), (0,0,1), (0.75, 0.25, 0.92), "J"),
        ((0,1,0), (0,0,1), (0.20, 0.83, 0.55), "K"),
    ]
    for (e1, e2, col, label) in planes:
        r, g, b = col
        pts_list, idxs = [], []
        for i in range(N):
            for j in range(N):
                u = -scale + 2*scale*i/(N-1)
                v = -scale + 2*scale*j/(N-1)
                x = e1[0]*u + e2[0]*v
                y = e1[1]*u + e2[1]*v
                z = e1[2]*u + e2[2]*v
                pts_list.append((x, y, z))
        for i in range(N-1):
            for j in range(N-1):
                aa = i*N+j; bb = aa+1; cc = (i+1)*N+j+1; dd = (i+1)*N+j
                idxs.append(f"{aa} {bb} {cc} {dd} -1")
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts_list)
        idx_str = " ".join(idxs)
        geo = (f'<IndexedFaceSet coordIndex="{idx_str}" solid="false" creaseAngle="0">'
               f'<Coordinate point="{pts_str}"/></IndexedFaceSet>')
        m = (f'<Appearance><Material diffuseColor="{r:.2f} {g:.2f} {b:.2f}" '
             f'transparency="0.50"/></Appearance>')
        xml += f'<Shape>{geo}{m}</Shape>\n'

        n_lines = 8
        line_mat = (f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}" '
                    f'transparency="0.3"/></Appearance>')
        for k in range(n_lines + 1):
            t = -scale + 2*scale*k/n_lines
            p0 = (e1[0]*t + e2[0]*(-scale), e1[1]*t + e2[1]*(-scale), e1[2]*t + e2[2]*(-scale))
            p1 = (e1[0]*t + e2[0]*( scale), e1[1]*t + e2[1]*( scale), e1[2]*t + e2[2]*( scale))
            pts_str2 = f"{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f}"
            xml += (f'<Shape><IndexedLineSet coordIndex="0 1 -1">'
                    f'<Coordinate point="{pts_str2}"/></IndexedLineSet>{line_mat}</Shape>\n')
            p0 = (e1[0]*(-scale) + e2[0]*t, e1[1]*(-scale) + e2[1]*t, e1[2]*(-scale) + e2[2]*t)
            p1 = (e1[0]*( scale) + e2[0]*t, e1[1]*( scale) + e2[1]*t, e1[2]*( scale) + e2[2]*t)
            pts_str2 = f"{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f}"
            xml += (f'<Shape><IndexedLineSet coordIndex="0 1 -1">'
                    f'<Coordinate point="{pts_str2}"/></IndexedLineSet>{line_mat}</Shape>\n')
    return xml


def geodesic_grid(N=24, R=2.0, col=(0.22, 0.55, 0.97)):
    xml = ""
    n_lines = 12
    r,g,b = col
    mat_str = f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}" transparency="0.3"/></Appearance>'
    for k in range(n_lines):
        pts = []
        phi_offset = math.pi * k / n_lines
        for i in range(N + 1):
            t = 2 * math.pi * i / N
            x = R * math.cos(t) * math.sin(phi_offset)
            y = R * math.cos(phi_offset)
            z = R * math.sin(t) * math.sin(phi_offset)
            pts.append((x, y, z))
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts)
        idx_str = " ".join(str(i) for i in range(N + 1)) + " -1"
        xml += (f'<Shape><IndexedLineSet coordIndex="{idx_str}">'
                f'<Coordinate point="{pts_str}"/></IndexedLineSet>'
                f'{mat_str}</Shape>\n')
    return xml


def poincare_geodesics(N=32, R=2.5):
    xml = ""
    mat_str = '<Appearance><Material emissiveColor="0.22 0.70 0.97" transparency="0.4"/></Appearance>'
    n_geo = 8
    for k in range(n_geo):
        angle = math.pi * k / n_geo
        pts = []
        for i in range(N + 1):
            s = -1.0 + 2.0 * i / N
            r = abs(s) * 0.88
            theta = angle + (math.pi if s < 0 else 0)
            x = r * math.cos(theta) * R
            z = r * math.sin(theta) * R
            rr = r
            y = -math.log(max(1e-8, 1 - rr*rr)) * 0.3 if rr < 0.999 else 3.0
            pts.append((x, y, z))
        pts_str = " ".join(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}" for p in pts)
        idx_str = " ".join(str(i) for i in range(N + 1)) + " -1"
        xml += (f'<Shape><IndexedLineSet coordIndex="{idx_str}">'
                f'<Coordinate point="{pts_str}"/></IndexedLineSet>'
                f'{mat_str}</Shape>\n')
    return xml


# ── X3D scene builder ─────────────────────────────────────────────────────────

SURFACES = {
    "fubini_study": {
        "label": "CP¹ — Fubini-Study",
        "category": "kähler",
        "equation": "φ = log(1 + |z|²)",
        "curvature": "K = +1",
        "holonomy": "U(1)",
        "description": "The complex projective line CP¹ ≅ S² with the Fubini-Study metric.",
    },
    "poincare": {
        "label": "Poincaré Disk — H²",
        "category": "kähler",
        "equation": "φ = −log(1 − |z|²)",
        "curvature": "K = −1",
        "holonomy": "U(1)",
        "description": "The hyperbolic plane with its unique complete Kähler metric.",
    },
    "potential_family": {
        "label": "Kähler Potential Family",
        "category": "kähler",
        "equation": "φ_t = t⁻¹ log(1 + t|z|²)",
        "curvature": "K(z) = t(1 + t|z|²)⁻²",
        "holonomy": "U(1)",
        "description": "A one-parameter family of Kähler metrics on ℂ.",
    },
    "taub_nut": {
        "label": "Taub-NUT Space",
        "category": "hyperkähler",
        "equation": "ds² = V(dr²+r²dΩ²) + V⁻¹(dψ+A)²",
        "curvature": "Ric = 0",
        "holonomy": "Sp(1) ≅ SU(2)",
        "description": "A complete hyperkähler 4-manifold with NUT charge c.",
    },
    "eguchi_hanson": {
        "label": "Eguchi-Hanson Space",
        "category": "hyperkähler",
        "equation": "ds² = (1−(a/r)⁴)⁻¹dr² + r²/4 Σσᵢ²",
        "curvature": "Ric = 0, |Rm|² ~ (a/r)⁸",
        "holonomy": "Sp(1)",
        "description": "The simplest ALE gravitational instanton.",
    },
    "cy_quintic": {
        "label": "Calabi-Yau Quintic (slice)",
        "category": "hyperkähler",
        "equation": "z₀⁵+z₁⁵+z₂⁵+z₃⁵+z₄⁵ = 0 ⊂ CP⁴",
        "curvature": "Ric = 0",
        "holonomy": "SU(3)",
        "description": "A real 2-dimensional slice of the Fermat quintic Calabi-Yau threefold.",
    },
    "hk_flat": {
        "label": "ℝ⁴ — Flat Hyperkähler",
        "category": "hyperkähler",
        "equation": "ωI = dx¹∧dx² + dx³∧dx⁴",
        "curvature": "K = 0",
        "holonomy": "Sp(1) ⊂ SO(4)",
        "description": "The simplest hyperkähler manifold: ℝ⁴ ≅ ℍ with its flat metric.",
    },
}


def _centroid(xml_fragment):
    coords = re.findall(r'point="([^"]+)"', xml_fragment)
    pts = []
    for c in coords:
        nums = c.split()
        for i in range(0, len(nums) - 2, 3):
            try: pts.append((float(nums[i]), float(nums[i+1]), float(nums[i+2])))
            except: pass
    if not pts:
        return (0.0, 0.0, 0.0)
    return (sum(p[0] for p in pts)/len(pts),
            sum(p[1] for p in pts)/len(pts),
            sum(p[2] for p in pts)/len(pts))


def build_x3d(surface_id, param=1.0):
    s = SURFACES.get(surface_id, SURFACES["fubini_study"])
    cat = s["category"]

    sky = "0.04 0.05 0.10" if cat == "kähler" else "0.07 0.04 0.12"
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE X3D PUBLIC "http://www.web3d.org/specifications/x3d-3.3.dtd" "">
<X3D profile="Immersive" version="3.3">
  <Scene>
    <Background skyColor="{sky}"/>
    <NavigationInfo type="EXAMINE ANY"/>
    <DirectionalLight direction="-1 -2 -1" intensity="1.2"/>
    <DirectionalLight direction="1 1 0.5" intensity="0.5" color="0.8 0.85 1"/>
    <Viewpoint position="0 0 9" orientation="0 1 0 0"/>
'''
    if surface_id == "fubini_study":
        geo = surface_fubini_study() + geodesic_grid()
    elif surface_id == "poincare":
        geo = surface_poincare_disk() + poincare_geodesics()
    elif surface_id == "potential_family":
        geo = surface_kahler_potential(t=param)
    elif surface_id == "taub_nut":
        geo = surface_taub_nut(c=param)
    elif surface_id == "eguchi_hanson":
        geo = surface_eguchi_hanson(a=param)
    elif surface_id == "cy_quintic":
        geo = surface_cy_slice()
    elif surface_id == "hk_flat":
        geo = surface_hk_flat()
    else:
        geo = ""

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
    return JSONResponse({"surfaces": {k: {**v} for k, v in SURFACES.items()}})


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
      --void:    #07080c;
      --panel:   #0d0f18;
      --panel2:  #111420;
      --border:  #1a1f35;
      --accent:  #4f6ef7;
      --accent2: #c084fc;
      --accent3: #34d399;
      --hot:     #f97316;
      --cold:    #38bdf8;
      --text:    #e2e8f0;
      --muted:   #4a5568;
      --mono:    'Space Mono', monospace;
      --sans:    'Inter', sans-serif;
      --sat: env(safe-area-inset-top,    0px);
      --sab: env(safe-area-inset-bottom, 0px);
      --sal: env(safe-area-inset-left,   0px);
      --sar: env(safe-area-inset-right,  0px);
    }

    html, body {
      height: 100vh;
      height: 100dvh;
      background: var(--void);
      color: var(--text);
      font-family: var(--sans);
      position: fixed;
      width: 100vw;
      overflow: hidden;
      -webkit-text-size-adjust: 100%;
    }

    .shell {
      display: flex;
      flex-direction: column;
      height: 100%;
      width: 100%;
      overflow: hidden;
      padding-top: var(--sat);
      padding-left: var(--sal);
      padding-right: var(--sar);
    }

    header {
      flex-shrink: 0;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      padding: 0 16px;
      height: 48px;
      gap: 12px;
      z-index: 10;
    }
    .logo {
      font-family: var(--mono);
      font-size: 13px;
      color: var(--accent);
      letter-spacing: 0.04em;
      white-space: nowrap;
    }
    .logo span { color: var(--accent2); }
    .header-tags { display: flex; gap: 6px; margin-left: auto; }
    .tag {
      font-family: var(--mono);
      font-size: 9px;
      padding: 3px 7px;
      border-radius: 3px;
      letter-spacing: 0.06em;
      white-space: nowrap;
      cursor: pointer;
      opacity: 0.45;
      transition: opacity 0.15s;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    .tag.active { opacity: 1.0; }
    .tag-k  { background: rgba(79,110,247,0.15); color: var(--accent);  border: 1px solid rgba(79,110,247,0.3); }
    .tag-hk { background: rgba(192,132,252,0.15); color: var(--accent2); border: 1px solid rgba(192,132,252,0.3); }

    .body {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
      position: relative;
      overflow: hidden;
    }

    .viewport {
      flex: 1;
      background: #050609;
      min-height: 0;
      position: relative;
      overflow: hidden;
    }
    x3d-canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      display: block;
    }

    .drawer {
      flex-shrink: 0;
      background: var(--panel);
      border-top: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      max-height: 48vh;
      min-height: 0;
      padding-bottom: var(--sab);
      overflow: hidden;
    }

    .drawer-tabs {
      display: flex;
      align-items: center;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .dtab {
      flex: 1;
      padding: 12px 4px;
      font-size: 11px;
      font-weight: 600;
      text-align: center;
      color: var(--muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: center;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    .dtab.active { color: var(--accent); border-bottom-color: var(--accent); }
    .dtab.active.hk { color: var(--accent2); border-bottom-color: var(--accent2); }

    .drawer-pane {
      display: none;
      flex: 1;
      overflow: hidden;
      flex-direction: column;
      min-height: 0;
    }
    .drawer-pane.active { display: flex; }

    .surface-list, .info-pane, .param-pane {
      flex: 1;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      min-height: 0;
    }

    .surface-list { padding: 6px 10px 10px; }
    .section-label {
      font-family: var(--mono);
      font-size: 9px;
      letter-spacing: 0.12em;
      color: var(--muted);
      text-transform: uppercase;
      padding: 10px 6px 5px;
    }
    .surface-item {
      padding: 12px 12px;
      border-radius: 8px;
      cursor: pointer;
      margin-bottom: 3px;
      border: 1px solid transparent;
      min-height: 52px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    .surface-item:active { opacity: 0.7; }
    .surface-item.active { background: rgba(79,110,247,0.12); border-color: rgba(79,110,247,0.3); }
    .surface-item.active.hk { background: rgba(192,132,252,0.10); border-color: rgba(192,132,252,0.25); }
    .surface-name { font-size: 13px; font-weight: 500; color: var(--text); }
    .surface-cat  { font-family: var(--mono); font-size: 9px; color: var(--muted);
      margin-top: 2px; text-transform: uppercase; letter-spacing: 0.08em; }

    .surface-item.hidden, .section-label.hidden { display: none !important; }

    .info-pane { padding: 14px 16px; }
    .info-row { margin-bottom: 12px; }
    .info-key {
      font-family: var(--mono);
      font-size: 9px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 4px;
    }
    .info-val {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--accent);
      line-height: 1.4;
      word-break: break-word;
    }
    .info-val.hk       { color: var(--accent2); }
    .info-val.ricci0   { color: var(--accent3); }
    .info-desc         { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-top: 12px; }

    .param-pane {
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .param-pane.hidden { display: none; }
    .param-label {
      font-family: var(--mono);
      font-size: 10px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }
    .param-row { display: flex; align-items: center; gap: 14px; }
    input[type=range] {
      flex: 1;
      height: 32px;
      accent-color: var(--accent);
      cursor: pointer;
      touch-action: none;
    }
    .param-val {
      font-family: var(--mono);
      font-size: 14px;
      color: var(--accent);
      min-width: 42px;
      text-align: right;
    }
    .param-note {
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
    }

    .cm-section {
      padding: 10px 16px 12px;
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }
    .cm-label { font-family: var(--mono); font-size: 9px; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 5px; }
    .cm-bar { height: 6px; border-radius: 3px;
      background: linear-gradient(to right, var(--cold), var(--accent3), var(--hot));
      margin-bottom: 4px; }
    .cm-ticks { display: flex; justify-content: space-between;
      font-family: var(--mono); font-size: 9px; color: var(--muted); }

    @media (min-width: 700px) and (orientation: landscape),
           (min-width: 900px) {
      .shell    { flex-direction: row; flex-wrap: wrap; }
      header    { width: 100%; order: -1; }
      .body     { flex-direction: row; flex: 1; min-height: 0; width: 100%; }
      .viewport { flex: 1; }
      .drawer   {
        width: 300px;
        max-height: none;
        height: 100%;
        border-top: none;
        border-left: 1px solid var(--border);
        flex-shrink: 0;
        padding-bottom: 0;
        padding-right: var(--sar);
      }
      .drawer-tabs { border-bottom: 1px solid var(--border); }
    }

    @media (min-width: 1024px) {
      .drawer { width: 340px; }
      .surface-name { font-size: 13px; }
    }
  </style>
</head>
<body>
<div class="shell">

  <header>
    <div class="logo">Kähler<span> / Hyperkähler</span></div>
    <div class="header-tags">
      <span class="tag tag-k active" id="filterK"  onclick="toggleFilter('kähler')">KÄHLER</span>
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

      <!-- Surfaces pane -->
      <div class="drawer-pane active" id="pane-surfaces">
        <div class="surface-list" id="surfaceList"></div>
        <div class="cm-section">
          <div class="cm-label">Curvature</div>
          <div class="cm-bar"></div>
          <div class="cm-ticks"><span>K &lt; 0</span><span>K = 0</span><span>K &gt; 0</span></div>
        </div>
      </div>

      <!-- Info pane -->
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
            <div class="info-key">Holonomy</div>
            <div class="info-val" id="infoHol">—</div>
          </div>
          <div class="info-desc" id="infoDesc">—</div>
        </div>
      </div>

      <!-- Parameter pane -->
      <div class="drawer-pane" id="pane-param">
        <div class="param-pane" id="paramPaneContent">
          <div class="param-label" id="paramLabel">Parameter</div>
          <div class="param-row">
            <input type="range" id="paramSlider" min="0.1" max="3.0" step="0.1" value="1.0" oninput="updateParam(this.value)">
            <div class="param-val" id="paramVal">1.0</div>
          </div>
          <div class="param-note" id="paramNote">Adjusts metric deformation or parameter scaling.</div>
        </div>
      </div>

    </div>
  </div>

</div>

<script>
  let surfacesData = {};
  let currentSurface = 'fubini_study';
  let activeFilters = { 'kähler': true, 'hyperkähler': true };
  let currentParam = 1.0;

  async function init() {
    const res = await fetch('/surfaces');
    const data = await res.json();
    surfacesData = data.surfaces;
    renderSurfacesList();
    selectSurface('fubini_study', false);
  }

  function renderSurfacesList() {
    const listEl = document.getElementById('surfaceList');
    listEl.innerHTML = '';
    
    let currentCat = '';
    for (const [id, s] of Object.entries(surfacesData)) {
      if (s.category !== currentCat) {
        currentCat = s.category;
        const header = document.createElement('div');
        header.className = `section-label ${!activeFilters[currentCat] ? 'hidden' : ''}`;
        header.id = `label-${currentCat}`;
        header.innerText = currentCat === 'kähler' ? 'Kähler Manifolds' : 'Hyperkähler Manifolds';
        listEl.appendChild(header);
      }

      const item = document.createElement('div');
      item.className = `surface-item ${id === currentSurface ? 'active' : ''} ${s.category === 'hyperkähler' ? 'hk' : ''} ${!activeFilters[s.category] ? 'hidden' : ''}`;
      item.id = `item-${id}`;
      item.onclick = () => selectSurface(id);
      item.innerHTML = `
        <div class="surface-name">${s.label}</div>
        <div class="surface-cat">${s.category}</div>
      `;
      listEl.appendChild(item);
    }
  }

  function selectSurface(id, loadScene = true) {
    currentSurface = id;
    document.querySelectorAll('.surface-item').forEach(el => el.classList.remove('active'));
    const activeItem = document.getElementById(`item-${id}`);
    if (activeItem) activeItem.classList.add('active');

    const s = surfacesData[id];
    if (s) {
      document.getElementById('infoEq').innerText = s.equation;
      document.getElementById('infoCurv').innerText = s.curvature;
      document.getElementById('infoHol').innerText = s.holonomy;
      document.getElementById('infoDesc').innerText = s.description;

      const isHK = s.category === 'hyperkähler';
      ['infoEq', 'infoHol'].forEach(elId => {
        const el = document.getElementById(elId);
        if (isHK) el.classList.add('hk'); else el.classList.remove('hk');
      });

      // Configure parameter slider per surface
      const paramPane = document.getElementById('tab-param');
      if (['potential_family', 'taub_nut', 'eguchi_hanson'].includes(id)) {
        paramPane.style.display = 'flex';
        const slider = document.getElementById('paramSlider');
        if (id === 'potential_family') {
          slider.min = '-0.9'; slider.max = '3.0'; slider.step = '0.1'; slider.value = '1.0';
          document.getElementById('paramLabel').innerText = 'Potential Parameter (t)';
          document.getElementById('paramNote').innerText = 't=0: flat C, t>0: Fubini-Study variant, t<0: Poincaré disk variant.';
        } else if (id === 'taub_nut') {
          slider.min = '0.2'; slider.max = '4.0'; slider.step = '0.2'; slider.value = '1.0';
          document.getElementById('paramLabel').innerText = 'NUT Charge (c)';
          document.getElementById('paramNote').innerText = 'Controls the topological charge and metric warping of the U(1) fiber.';
        } else if (id === 'eguchi_hanson') {
          slider.min = '0.5'; slider.max = '2.5'; slider.step = '0.1'; slider.value = '1.0';
          document.getElementById('paramLabel').innerText = 'Bolt Radius (a)';
          document.getElementById('paramNote').innerText = 'Determines the size of the Eguchi-Hanson bolt where the fiber degenerates.';
        }
        currentParam = parseFloat(slider.value);
        document.getElementById('paramVal').innerText = currentParam;
      } else {
        paramPane.style.display = 'none';
        if (document.getElementById('pane-param').classList.contains('active')) {
          switchTab('surfaces');
        }
      }
    }

    if (loadScene) {
      loadCanvasScene(id, currentParam);
    }
  }

  function loadCanvasScene(id, param) {
    const canvas = document.getElementById('canvas');
    canvas.setAttribute('url', `/scene/${id}?param=${param}`);
  }

  function updateParam(val) {
    currentParam = parseFloat(val);
    document.getElementById('paramVal').innerText = currentParam;
    loadCanvasScene(currentSurface, currentParam);
  }

  function toggleFilter(cat) {
    activeFilters[cat] = !activeFilters[cat];
    const tag = document.getElementById(cat === 'kähler' ? 'filterK' : 'filterHK');
    if (activeFilters[cat]) tag.classList.add('active'); else tag.classList.remove('active');

    for (const [id, s] of Object.entries(surfacesData)) {
      if (s.category === cat) {
        const item = document.getElementById(`item-${id}`);
        if (item) {
          if (activeFilters[cat]) item.classList.remove('hidden'); else item.classList.add('hidden');
        }
      }
    }
    const label = document.getElementById(`label-${cat}`);
    if (label) {
      if (activeFilters[cat]) label.classList.remove('hidden'); else label.classList.add('hidden');
    }
  }

  function switchTab(tabName) {
    document.querySelectorAll('.dtab').forEach(t => t.classList.remove('active', 'hk'));
    document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));

    const tab = document.getElementById(`tab-${tabName}`);
    const pane = document.getElementById(`pane-${tabName}`);
    
    tab.classList.add('active');
    if (currentSurface && surfacesData[currentSurface]?.category === 'hyperkähler' && tabName === 'surfaces') {
      tab.classList.add('hk');
    }
    pane.classList.add('active');
  }

  window.onload = init;
</script>
</body>
</html>
"""
