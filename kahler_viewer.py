"""
Kähler / Hyperkähler Geometry Viewer
Standalone FastAPI app — serves an X3D interactive explorer of differential-geometric surfaces.
"""
import math, os
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
            # K = +1 everywhere on S²
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
    lim = 0.92   # stay inside disk
    for i in range(N):
        for j in range(N):
            # polar grid
            r = lim * i / (N - 1)
            theta = 2 * math.pi * j / (N - 1)
            x = r * math.cos(theta) * R
            z = r * math.sin(theta) * R
            # height = Kähler potential derivative (metric factor)
            if r < 0.999:
                phi = -math.log(max(1e-8, 1 - r * r))
                y = min(phi * 0.3, 3.0)
            else:
                y = 3.0
            pts.append((x, y, z))
            # K = -1 everywhere
            colors.append(curvature_color(-1.0, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_kahler_potential(N=55, t=1.0, scale=2.5):
    """
    Family of Kähler potentials: φ_t = (1/t) log(1 + t|z|²)
    t→0: flat C (φ = |z|²)
    t=1: Fubini-Study
    t→-1: Poincaré disk
    Visualized as height field over R².
    Colors encode Gaussian curvature K = t / (1 + t|z|²)².
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
    """
    Taub-NUT space — hyperkähler 4-manifold with U(1) isometry.
    V(r) = 1 + c/r  (NUT charge c).

    Visualization: concentric spherical shells at discrete r values,
    each warped by sqrt(V(r)) and colored by the NUT potential.
    Inner shells are small (high V) → orange; outer shells large (V→1) → green.
    """
    xml = ""
    n_shells = 7
    n_u, n_v = 28, 16
    r_values = [0.3 + 3.5 * (k / (n_shells - 1)) ** 1.4 for k in range(n_shells)]

    for r in r_values:
        V = 1.0 + c / max(r, 0.01)
        R = r * math.sqrt(V) * scale / 3.5
        transparency = 0.15 + 0.55 * (r / 3.8)   # inner shells more opaque
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
    """
    Eguchi-Hanson space — the simplest ALE (asymptotically locally Euclidean) 
    hyperkähler 4-manifold. Metric:
    ds² = (1 - (a/r)⁴)⁻¹ dr² + r²/4 [(σ₁² + σ₂²) + (1-(a/r)⁴)σ₃²]
    
    Has a 2-sphere (the 'bolt') at r=a where the U(1) fiber degenerates.
    Visualized as a warped S² that opens into a trumpet as r→∞.
    Color = |Riemann|² ∝ (a/r)⁴ — concentrated at the bolt.
    """
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            t = i / (N - 1)
            r = a + 4.0 * t ** 1.2   # r ranges from a to a+4
            phi_a = 2 * math.pi * j / (N - 1)
            
            # metric factor for the S² base
            f2 = max(0.0, 1.0 - (a / max(r, 1e-6)) ** 4)
            R_base = r * math.sqrt(f2) * scale / 3.0
            
            x = R_base * math.cos(phi_a)
            z = R_base * math.sin(phi_a)
            y = (r - a) * scale / 3.0
            
            pts.append((x, y, z))
            # Curvature concentrated at bolt
            curv = 12 * a**4 / max(r**6, 1e-6)
            colors.append(curvature_color(curv * 2 - 0.5, -0.5, 2.0))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_cy_slice(N=58, phase=0.0, scale=1.8):
    """
    Calabi-Yau quintic cross-section.
    The quintic CY3 is defined in CP⁴ by: z₀⁵+z₁⁵+z₂⁵+z₃⁵+z₄⁵ = ψ z₀z₁z₂z₃z₄
    
    Real 2-slice: set z₃=z₄=0, parameterize (z₀:z₁:z₂) with z₀=1.
    Then: 1 + z₁⁵ + z₂⁵ = 0.
    Parameterize z₁=r·e^(iθ), find z₂ = (-1-z₁⁵)^(1/5).
    Plot Re(z₂), Im(z₂) as (x,z) and Re(z₁) as height.
    Color = |dω| (holomorphic 2-form magnitude proxy).
    """
    pts, colors = [], []
    for i in range(N):
        for j in range(N):
            r1 = 0.05 + 1.5 * i / (N - 1)
            theta1 = 2 * math.pi * j / (N - 1) + phase
            z1r = r1 * math.cos(theta1)
            z1i = r1 * math.sin(theta1)
            # z2^5 = -1 - z1^5
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
            theta2 = w_arg / 5.0  # principal branch, consistent
            z2r = r2 * math.cos(theta2)
            z2i = r2 * math.sin(theta2)
            x = z2r * scale
            z_pos = z2i * scale
            y = z1r * scale
            pts.append((x, y, z_pos))
            # |Ω|² proxy: 1/(r1·r2)
            omega_mag = 1.0 / max(r1 * r2, 0.1)
            colors.append(curvature_color(omega_mag - 2, -1.5, 1.5))
    geo = grid_mesh(pts, N, N, colors)
    m = '<Appearance><Material transparency="0.05"/></Appearance>'
    return f'<Shape>{geo}{m}</Shape>\n'


def surface_hk_flat(N=32, scale=2.2):
    """
    Flat ℝ⁴ ≅ ℍ with hyperkähler structure.
    Three Kähler forms: ωI = dx¹∧dx², ωJ = dx¹∧dx³, ωK = dx²∧dx³.
    Visualized as three mutually orthogonal planes through the origin in ℝ³,
    each labeled by one complex structure I, J, K.
    Grid lines on each plane show the corresponding holomorphic foliation.
    """
    xml = ""
    # Three orthogonal planes: XY (I), XZ (J), YZ (K)
    # Each defined by two orthogonal basis vectors in ℝ³
    planes = [
        # ωI = dx¹∧dx²: the XY-plane
        ((1,0,0), (0,1,0), (0.31, 0.43, 0.97), "I"),   # blue
        # ωJ = dx¹∧dx³: the XZ-plane
        ((1,0,0), (0,0,1), (0.75, 0.25, 0.92), "J"),   # violet
        # ωK = dx²∧dx³: the YZ-plane
        ((0,1,0), (0,0,1), (0.20, 0.83, 0.55), "K"),   # green
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

        # Grid lines on this plane
        n_lines = 8
        line_mat = (f'<Appearance><Material emissiveColor="{r:.2f} {g:.2f} {b:.2f}" '
                    f'transparency="0.3"/></Appearance>')
        for k in range(n_lines + 1):
            t = -scale + 2*scale*k/n_lines
            # lines parallel to e2
            p0 = (e1[0]*t + e2[0]*(-scale), e1[1]*t + e2[1]*(-scale), e1[2]*t + e2[2]*(-scale))
            p1 = (e1[0]*t + e2[0]*( scale), e1[1]*t + e2[1]*( scale), e1[2]*t + e2[2]*( scale))
            pts_str2 = f"{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f}"
            xml += (f'<Shape><IndexedLineSet coordIndex="0 1 -1">'
                    f'<Coordinate point="{pts_str2}"/></IndexedLineSet>{line_mat}</Shape>\n')
            # lines parallel to e1
            p0 = (e1[0]*(-scale) + e2[0]*t, e1[1]*(-scale) + e2[1]*t, e1[2]*(-scale) + e2[2]*t)
            p1 = (e1[0]*( scale) + e2[0]*t, e1[1]*( scale) + e2[1]*t, e1[2]*( scale) + e2[2]*t)
            pts_str2 = f"{p0[0]:.3f} {p0[1]:.3f} {p0[2]:.3f} {p1[0]:.3f} {p1[1]:.3f} {p1[2]:.3f}"
            xml += (f'<Shape><IndexedLineSet coordIndex="0 1 -1">'
                    f'<Coordinate point="{pts_str2}"/></IndexedLineSet>{line_mat}</Shape>\n')
    return xml


def geodesic_grid(N=24, R=2.0, col=(0.22, 0.55, 0.97)):
    """Draw geodesic grid lines on a sphere (representing CP¹ holomorphic curves)."""
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
    """Draw hyperbolic geodesics in the Poincaré disk model."""
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
        "description": "The complex projective line CP¹ ≅ S² with the Fubini-Study metric. The Kähler form ω = i∂∂̄φ gives a round sphere. Positive constant holomorphic sectional curvature.",
    },
    "poincare": {
        "label": "Poincaré Disk — H²",
        "category": "kähler",
        "equation": "φ = −log(1 − |z|²)",
        "curvature": "K = −1",
        "holonomy": "U(1)",
        "description": "The hyperbolic plane with its unique (up to scale) complete Kähler metric. Geodesics are circular arcs meeting the boundary at right angles. Negative constant curvature.",
    },
    "potential_family": {
        "label": "Kähler Potential Family",
        "category": "kähler",
        "equation": "φ_t = t⁻¹ log(1 + t|z|²)",
        "curvature": "K(z) = t(1 + t|z|²)⁻²",
        "holonomy": "U(1)",
        "description": "A one-parameter family of Kähler metrics on ℂ. At t=0: flat Euclidean. At t→+∞: approaches CP¹. At t→−1: approaches the Poincaré disk. Height encodes the potential φ.",
    },
    "taub_nut": {
        "label": "Taub-NUT Space",
        "category": "hyperkähler",
        "equation": "ds² = V(dr²+r²dΩ²) + V⁻¹(dψ+A)²",
        "curvature": "Ric = 0",
        "holonomy": "Sp(1) ≅ SU(2)",
        "description": "A complete hyperkähler 4-manifold with NUT charge c and U(1) isometry. V(r) = 1 + c/r. Ricci-flat. The fiber S¹ over the asymptotic ℝ³ base is visualized via metric distortion. Color encodes the NUT potential.",
    },
    "eguchi_hanson": {
        "label": "Eguchi-Hanson Space",
        "category": "hyperkähler",
        "equation": "ds² = (1−(a/r)⁴)⁻¹dr² + r²/4 Σσᵢ²",
        "curvature": "Ric = 0, |Rm|² ~ (a/r)⁸",
        "holonomy": "Sp(1)",
        "description": "The simplest ALE (asymptotically locally Euclidean) gravitational instanton. A hyperkähler metric on T*CP¹. Contains a 2-sphere 'bolt' at r=a where the U(1) fiber degenerates. Curvature concentrated at the bolt.",
    },
    "cy_quintic": {
        "label": "Calabi-Yau Quintic (slice)",
        "category": "hyperkähler",
        "equation": "z₀⁵+z₁⁵+z₂⁵+z₃⁵+z₄⁵ = 0 ⊂ CP⁴",
        "curvature": "Ric = 0",
        "holonomy": "SU(3)",
        "description": "A real 2-dimensional slice of the Fermat quintic Calabi-Yau threefold in CP⁴. The quintic CY3 is the most-studied compact Calabi-Yau manifold in string theory. This cross-section shows the branch structure of the holomorphic form Ω.",
    },
    "hk_flat": {
        "label": "ℝ⁴ — Flat Hyperkähler",
        "category": "hyperkähler",
        "equation": "ωI = dx¹∧dx² + dx³∧dx⁴",
        "curvature": "K = 0",
        "holonomy": "Sp(1) ⊂ SO(4)",
        "description": "The simplest hyperkähler manifold: ℝ⁴ ≅ ℍ with its flat metric. Three complex structures I, J, K satisfy IJ=K (quaternion relations). Each colored plane represents one complex structure acting on tangent space.",
    },
}


def _centroid(xml_fragment):
    """Compute mean of all coordinate points in an XML fragment."""
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
    # Build surface geometry, then auto-center by negating its centroid
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
      /* safe areas */
      --sat: env(safe-area-inset-top,    0px);
      --sab: env(safe-area-inset-bottom, 0px);
      --sal: env(safe-area-inset-left,   0px);
      --sar: env(safe-area-inset-right,  0px);
    }

    html, body {
      height: 100%;
      background: var(--void);
      color: var(--text);
      font-family: var(--sans);
      /* never let iOS bounce-scroll the shell */
      position: fixed;
      width: 100%;
      overflow: hidden;
      -webkit-text-size-adjust: 100%;
    }

    /* ── Shell: stack vertically on portrait, side-by-side on landscape/iPad ── */
    .shell {
      display: flex;
      flex-direction: column;
      height: 100%;
      padding-top: var(--sat);
      padding-left: var(--sal);
      padding-right: var(--sar);
    }

    /* ── Header ── */
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
    }
    .tag-k  { background: rgba(79,110,247,0.15); color: var(--accent);  border: 1px solid rgba(79,110,247,0.3); }
    .tag-hk { background: rgba(192,132,252,0.15); color: var(--accent2); border: 1px solid rgba(192,132,252,0.3); }

    /* ── Body: viewport + drawer ── */
    .body {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-height: 0;
      position: relative;
    }

    /* ── Viewport ── */
    .viewport {
      flex: 1;
      background: #050609;
      min-height: 0;
      position: relative;
    }
    x3d-canvas {
      width: 100%;
      height: 100%;
      display: block;
    }

    /* ── Bottom drawer (collapsed by default on mobile, expands on tap) ── */
    .drawer {
      flex-shrink: 0;
      background: var(--panel);
      border-top: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      max-height: 48vh;
      padding-bottom: var(--sab);
    }

    /* Drawer handle + tab bar */
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

    /* Tab panes */
    .drawer-pane { display: none; flex: 1; overflow: hidden; flex-direction: column; min-height: 0; }
    .drawer-pane.active { display: flex; }

    /* Surfaces list */
    .surface-list {
      flex: 1;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      padding: 6px 10px 10px;
    }
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

    /* Info pane */
    .info-pane {
      flex: 1;
      overflow-y: auto;
      -webkit-overflow-scrolling: touch;
      padding: 14px 16px;
    }
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
    .info-val.hk      { color: var(--accent2); }
    .info-val.ricci0  { color: var(--accent3); }
    .info-desc        { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-top: 12px; }

    /* Param pane */
    .param-pane {
      flex: 1;
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
      height: 32px;          /* big enough for thumb on iOS */
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

    /* Colormap */
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

    /* ── Landscape / iPad: side-by-side ── */
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

    /* iPad Pro 12.9" landscape */
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
      <span class="tag tag-k">KÄHLER</span>
      <span class="tag tag-hk">HYPERKÄHLER</span>
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
            <div class="info-key">Holonomy group</div>
            <div class="info-val" id="infoHol">—</div>
          </div>
          <div class="info-desc" id="infoDesc">Select a surface to see its geometry.</div>
        </div>
      </div>

      <!-- Parameter pane -->
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
          <div class="param-note">This surface has no adjustable parameter.<br>Switch to a surface like Kähler Potential Family, Taub-NUT, or Eguchi-Hanson.</div>
        </div>
      </div>
    </div>
  </div>

</div>

<script>
const SURFACES = {
  fubini_study:    { label:"CP¹ — Fubini-Study",       category:"kähler",       eq:"φ = log(1 + |z|²)",                      curv:"K = +1",                   hol:"U(1)",        param:null, paramNote:null,
    desc:"The complex projective line CP¹ ≅ S² with the Fubini-Study metric. Positive constant holomorphic sectional curvature. Geodesics are great circles." },
  poincare:        { label:"Poincaré Disk — H²",        category:"kähler",       eq:"φ = −log(1 − |z|²)",                     curv:"K = −1",                   hol:"U(1)",        param:null, paramNote:null,
    desc:"The hyperbolic plane with its unique complete Kähler metric. Negative constant curvature. Geodesics are circular arcs perpendicular to the boundary." },
  potential_family:{ label:"Kähler Potential Family",   category:"kähler",       eq:"φ_t = t⁻¹ log(1 + t|z|²)",              curv:"K(z) = t·(1+t|z|²)⁻²",   hol:"U(1)",        param:"t",  paramNote:"t=0: flat ℂ · t=1: Fubini-Study · t≫1: concentrated curvature",
    desc:"A one-parameter deformation between flat ℂ (t→0) and CP¹ (t=1). Height encodes the potential; color encodes position-dependent curvature K(z)." },
  taub_nut:        { label:"Taub-NUT Space",             category:"hyperkähler",  eq:"V(r) = 1 + c/r",                         curv:"Ric = 0",                  hol:"Sp(1)≅SU(2)", param:"c",  paramNote:"c = NUT charge — larger c = stronger gravitational instanton",
    desc:"Complete hyperkähler 4-manifold with NUT charge c. The orbit space ℝ³ is visualized with distortion from V(r). Ricci-flat; color encodes the NUT potential." },
  eguchi_hanson:   { label:"Eguchi-Hanson Space",        category:"hyperkähler",  eq:"f² = 1 − (a/r)⁴",                       curv:"Ric=0, |Rm|²∝(a/r)⁸",   hol:"Sp(1)",       param:"a",  paramNote:"a = bolt radius — curvature concentrates at the S² bolt at r = a",
    desc:"The simplest ALE gravitational instanton — a hyperkähler metric on T*CP¹. Contains a 2-sphere bolt at r=a. Curvature decays as r⁻⁸ away from the bolt." },
  cy_quintic:      { label:"Calabi-Yau Quintic (slice)", category:"hyperkähler",  eq:"Σᵢ zᵢ⁵ = 0 ⊂ CP⁴",                    curv:"Ric = 0",                  hol:"SU(3)",       param:null, paramNote:null,
    desc:"Real 2-slice of the Fermat quintic — the most-studied compact CY threefold in string theory (h¹¹=1, h²¹=101). Color encodes |Ω|², the holomorphic 3-form." },
  hk_flat:         { label:"ℝ⁴ — Flat Hyperkähler",     category:"hyperkähler",  eq:"ωI=dx¹∧dx², ωJ=dx¹∧dx³, ωK=dx²∧dx³", curv:"K = 0",                    hol:"Sp(1)⊂SO(4)", param:null, paramNote:null,
    desc:"The flat hyperkähler manifold ℝ⁴ ≅ ℍ. Three complex structures I, J, K satisfy IJ=K (quaternion algebra). Each colored plane represents one Kähler form." },
};

let currentSurface = 'fubini_study';
let currentParam   = 1.0;
const canvas = document.getElementById('canvas');

function loadSurface(id, param) {
  currentSurface = id;
  currentParam   = (param != null) ? param : 1.0;
  const url = `/scene/${id}?param=${currentParam}&t=${Date.now()}`;
  try {
    if (canvas.browser && canvas.browser.loadURL) {
      canvas.browser.loadURL(new X3D.MFString(url));
    } else {
      canvas.setAttribute('src', url);
    }
  } catch(e) {
    canvas.removeAttribute('src');
    setTimeout(() => canvas.setAttribute('src', url), 10);
  }
  updateInfo(id);
  updateSidebarActive(id);
}

function updateInfo(id) {
  const s = SURFACES[id];
  if (!s) return;
  document.getElementById('infoEq').textContent   = s.eq;
  document.getElementById('infoCurv').textContent = s.curv;
  document.getElementById('infoHol').textContent  = s.hol;
  document.getElementById('infoDesc').textContent = s.desc;
  const cv = document.getElementById('infoCurv');
  cv.className = 'info-val' + (s.curv.includes('Ric = 0') || s.curv === 'K = 0' ? ' ricci0' : s.category === 'hyperkähler' ? ' hk' : '');

  // Parameter pane
  if (s.param) {
    document.getElementById('paramPane').classList.remove('hidden');
    document.getElementById('noParam').classList.add('hidden');
    document.getElementById('paramName').textContent = s.param;
    if (s.paramNote) document.getElementById('paramNote').textContent = s.paramNote;
  } else {
    document.getElementById('paramPane').classList.add('hidden');
    document.getElementById('noParam').classList.remove('hidden');
  }

  // Update tab styling
  const infoTab = document.getElementById('tab-info');
  infoTab.classList.toggle('hk', s.category === 'hyperkähler');
}

function updateSidebarActive(id) {
  document.querySelectorAll('.surface-item').forEach(el => {
    const isActive = el.dataset.id === id;
    el.classList.toggle('active', isActive);
    el.classList.toggle('hk', isActive && SURFACES[id].category === 'hyperkähler');
  });
}

function switchTab(name) {
  ['surfaces','info','param'].forEach(t => {
    document.getElementById('tab-'  + t).classList.toggle('active', t === name);
    document.getElementById('pane-' + t).classList.toggle('active', t === name);
  });
}

// Build surface list
const list = document.getElementById('surfaceList');
let lastCat = null;
Object.entries(SURFACES).forEach(([id, s]) => {
  if (s.category !== lastCat) {
    lastCat = s.category;
    const lbl = document.createElement('div');
    lbl.className = 'section-label';
    lbl.textContent = s.category === 'kähler' ? 'Kähler' : 'Hyperkähler';
    list.appendChild(lbl);
  }
  const item = document.createElement('div');
  item.className = 'surface-item';
  item.dataset.id = id;
  item.innerHTML = `<div class="surface-name">${s.label}</div>
    <div class="surface-cat">${s.category} · ${s.hol}</div>`;
  item.onclick = () => {
    loadSurface(id, currentParam);
    // On mobile auto-switch to viewport after selection
    if (window.innerWidth < 700) {
      // small nudge so user sees the load started
    }
  };
  list.appendChild(item);
});

// Param slider
const slider  = document.getElementById('paramSlider');
const display = document.getElementById('paramDisplay');
let debounce;
slider.addEventListener('input', () => {
  currentParam = parseFloat(slider.value);
  display.textContent = currentParam.toFixed(2);
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    if (SURFACES[currentSurface].param) loadSurface(currentSurface, currentParam);
  }, 150);
});

// Load default on ready
window.addEventListener('load', () => {
  setTimeout(() => loadSurface('fubini_study'), 300);
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
