# X3D Studio

Two FastAPI apps for building and exploring 3D geometry in the browser, both rendered via [X_ite](https://create3000.github.io/x_ite/) (X3D WebGL engine). Run them side by side in a GitHub Codespace — each gets its own port and browser tab.

| App | File | Port | What it does |
|-----|------|------|--------------|
| X3D Agent | `app.py` | 8000 | Natural language 3D scene builder |
| Kähler Viewer | `kahler_viewer.py` | 8001 | Interactive differential geometry explorer |

---

## Installation

```bash
pip install fastapi uvicorn pydantic
```

```bash
# Terminal 1
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
uvicorn kahler_viewer:app --host 0.0.0.0 --port 8001 --reload
```

In a GitHub Codespace both ports appear in the **Ports** tab and open in separate browser tabs.

---

## X3D Agent (`app.py`)

A rule-based natural language interface for building and exploring live X3D scenes. Type a command; the parser converts it to X3D geometry and serves it instantly.

### Architecture

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as X_ite Viewer
    participant API as FastAPI :8000
    participant File as scene.x3d
    participant Saves as saves/

    User->>Browser: Types prompt & clicks Run
    Browser->>API: POST /api/agent { prompt }
    Note over API: Rule-based NL parse<br/>shape · color · size · position<br/>count · arrangement · animation
    API->>File: Validates XML, writes updated scene
    API-->>Browser: { status, message }
    Browser->>API: GET /scene.x3d?t={timestamp}
    API-->>Browser: X3D XML
    Browser->>User: Re-renders 3D viewport

    User->>Browser: Clicks Save
    Browser->>API: POST /api/save { name }
    API->>Saves: writes .x3d + .json metadata

    User->>Browser: Clicks Load
    Browser->>API: POST /api/load/{name}
    API->>File: Restores saved scene
```

### Parser pipeline

```mermaid
flowchart LR
    P[Prompt] --> SD[Shape\ndetect]
    P --> CD[Color\nparse]
    P --> SZ[Size\nparse]
    P --> PO[Position\nparse]
    P --> CN[Count\nparse]
    P --> AN[Animation\nparse]

    SD --> ACT{Action}
    CD --> ACT
    SZ --> ACT
    PO --> ACT
    CN --> ACT
    AN --> ACT

    ACT -->|add| BLD[Build\nshape XML]
    ACT -->|lighting| LGT[Lighting\npreset]
    ACT -->|camera| CAM[Viewpoint\nnode]
    ACT -->|animate| ANM[TimeSensor\n+ ROUTE]
    ACT -->|clear| CLR[Reset\nscene]
    ACT -->|inspect| INS[Registry\nlist]

    BLD --> VAL[Validate\nXML]
    LGT --> VAL
    CAM --> VAL
    ANM --> VAL
    VAL --> SCN[scene.x3d]
    SCN --> X3D[X_ite\nrenderer]
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Viewer UI |
| `GET` | `/scene.x3d` | Current X3D scene |
| `POST` | `/api/agent` | `{ prompt }` → mutates scene |
| `POST` | `/api/clear` | Reset to empty scene |
| `GET` | `/api/inspect` | List objects in scene |
| `POST` | `/api/save` | Save scene as `{ name }` |
| `POST` | `/api/load/{name}` | Load saved scene |
| `GET` | `/api/saves` | List saved scene names |

### Shapes

18 solid geometry types — all with verified face windings, correct normals, and smooth shading:

```mermaid
mindmap
  root((Shapes))
    Primitives
      sphere
      cone
      cylinder
      box
      ellipsoid
    Polyhedra
      tetrahedron
      octahedron
      icosahedron
      dodecahedron
    Flat
      plane
      star
      crescent
    Volumetric
      capsule
      cross
      arrow
      torus
    Swept
      helix
      torus knot
```

### What you can say

**Shapes**
```
add a red sphere to the left
spawn a huge gold torus in the center
place a silver capsule far right
add a neon blue torus knot below
drop a tilted orange arrow in front
add a cyan crescent above
spawn a jade dodecahedron
put a white plane below
```

**Colors** — 60+ named, two-word combos, hex, RGB:
```
rose gold · neon green · dark blue · electric cyan
#ff6600
color 255 128 0
transparent · glass · ghost
```

**Sizes**
```
tiny · small · medium · large · huge · massive · colossal
size 2.5 · radius 1.0
```

**Positions**
```
to the left · right · above · below · in front · behind
top left · bottom right · far above · underground · floating
at 2 3 -1
```

**Multi-shape**
```
add 5 red spheres in a row
spawn 8 blue cubes in a circle
create 6 gold stars in a grid
place 4 cyan cones scattered
```

**Lighting**
```
day · night · sunrise · neon · brighter · dimmer · add spotlight
```

**Camera**
```
reset camera · top view · front view · side view · isometric · zoom in · zoom out
```

**Animation** — applied to last object, or inline on add:
```
spin · bounce · pulse · stop
add a spinning red sphere
```

**Scene**
```
what's in the scene? · inventory · how many objects?
undo · clear · new scene
load hello · load fog · load text
```

### UI tabs

- **Console** — command log, auto-focuses after each run
- **Chips** — grouped shortcut buttons (Shapes, Multi, Animation, Lighting, Camera, Archive, Scene)
- **Saves** — name and persist scenes; reload any saved scene

### Notes

- Parsing is **rule-based regex** — no LLM required
- Corrupt `scene.x3d` auto-recovers to default on next command
- Saves persist as `.x3d` + `.json` in `saves/`
- Archive import fetches live from `web3d.org` (requires internet)
- Spotlight capped at 3; size clamped to `[0.05, 5.0]`; RGB clamped to `[0.0, 1.0]`
- Rendered via X_ite 16.1.2

---

## Kähler / Hyperkähler Viewer (`kahler_viewer.py`)

An interactive browser for differential-geometric surfaces from Kähler and hyperkähler geometry. Surfaces are colored by curvature using a spectral heatmap: **blue = negative · green = zero / Ricci-flat · orange = positive**.

### Architecture

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as X_ite Viewer
    participant API as FastAPI :8001
    participant Builder as Surface Builder
    participant Centroid as Centroid Corrector

    User->>Browser: Selects surface or moves slider
    Browser->>API: GET /scene/{id}?param={value}
    API->>Builder: Calls surface_*() function
    Builder-->>API: Raw X3D geometry fragment
    API->>Centroid: _centroid(geo) → (cx, cy, cz)
    Centroid-->>API: offset = (-cx, -cy, -cz)
    Note over API: Wraps geo in<br/><Transform translation="-cx -cy -cz">
    API-->>Browser: Complete X3D scene
    Browser->>User: Renders centered surface
```

### Surface taxonomy

```mermaid
flowchart TD
    ROOT[Differential Geometry\nSurfaces] --> K[Kähler\nHolonomy ⊆ U&#40;n&#41;]
    ROOT --> HK[Hyperkähler\nHolonomy ⊆ Sp&#40;n&#41;]

    K --> FS["CP¹ Fubini-Study\nK = +1\nφ = log&#40;1+|z|²&#41;"]
    K --> PD["Poincaré Disk H²\nK = −1\nφ = −log&#40;1−|z|²&#41;"]
    K --> KF["Kähler Potential Family\nK&#40;z&#41; = t&#40;1+t|z|²&#41;⁻²\nparameter t ∈ &#40;0,3&#41;"]

    HK --> TN["Taub-NUT\nRic = 0\nV&#40;r&#41; = 1 + c/r\nparameter c"]
    HK --> EH["Eguchi-Hanson\nRic = 0  |Rm|²∝&#40;a/r&#41;⁸\nparameter a"]
    HK --> CY["Calabi-Yau Quintic\nRic = 0  SU&#40;3&#41;\nΣzᵢ⁵ = 0 ⊂ CP⁴"]
    HK --> FL["Flat ℝ⁴\nK = 0\nωI ωJ ωK"]

    style FS  fill:#1a2040,stroke:#4f6ef7,color:#a5b4fc
    style PD  fill:#0f2030,stroke:#38bdf8,color:#7dd3fc
    style KF  fill:#1a2040,stroke:#4f6ef7,color:#a5b4fc
    style TN  fill:#200a30,stroke:#c084fc,color:#d8b4fe
    style EH  fill:#200a30,stroke:#c084fc,color:#d8b4fe
    style CY  fill:#0a2018,stroke:#34d399,color:#6ee7b7
    style FL  fill:#200a30,stroke:#c084fc,color:#d8b4fe
```

### Surfaces

**Kähler manifolds** — holonomy ⊆ U(1)

| Surface | Kähler potential φ | Curvature | Holonomy | Parameter |
|---------|-------------------|-----------|----------|-----------|
| CP¹ Fubini-Study | log(1 + \|z\|²) | K = +1 | U(1) | — |
| Poincaré Disk H² | −log(1 − \|z\|²) | K = −1 | U(1) | — |
| Kähler Potential Family | t⁻¹ log(1 + t\|z\|²) | K(z) = t(1+t\|z\|²)⁻² | U(1) | t |

**Hyperkähler manifolds** — holonomy ⊆ Sp(1), Ricci-flat

| Surface | Metric / equation | \|Rm\|² | Holonomy | Parameter |
|---------|------------------|---------|----------|-----------|
| Taub-NUT | V(r) = 1 + c/r | decays as r⁻⁴ | Sp(1) ≅ SU(2) | c (NUT charge) |
| Eguchi-Hanson | f² = 1 − (a/r)⁴ | ∝ (a/r)⁸ | Sp(1) | a (bolt radius) |
| CY Quintic (slice) | Σᵢ zᵢ⁵ = 0 ⊂ CP⁴ | — | SU(3) | — |
| Flat ℝ⁴ | ωI, ωJ, ωK | 0 | Sp(1) ⊂ SO(4) | — |

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Viewer UI |
| `GET` | `/scene/{surface_id}?param=1.0` | X3D scene for given surface |
| `GET` | `/surfaces` | JSON index of all surfaces |

### Surface IDs

```
fubini_study    poincare    potential_family
taub_nut        eguchi_hanson    cy_quintic    hk_flat
```

### UI

- **Surfaces tab** — tap any surface to load it; KÄHLER / HYPERKÄHLER buttons in the header filter the list
- **Info tab** — Kähler potential, curvature, holonomy group, geometric description
- **Parameter tab** — live slider for surfaces that have one; updates on drag with 150ms debounce
- Curvature colormap strip at the bottom of the Surfaces tab: blue → green → orange

### Centering

Every surface is automatically centered at the origin by computing the mean of all coordinate points in the generated X3D fragment and injecting the negated centroid as the outer `<Transform translation>`. This runs on every request, so parametric surfaces stay centered as their slider value changes.

### References

- Huybrechts, *Complex Geometry* — Kähler manifolds and Hodge theory
- Joyce, *Compact Manifolds with Special Holonomy* — hyperkähler and Calabi-Yau
- Eguchi & Hanson (1978), *Asymptotically flat self-dual solutions to Euclidean gravity*
- Taub (1951), Newman, Unti & Tamburino (1963) — NUT space
- Candelas, Horowitz, Strominger & Witten (1985) — CY quintic in string compactification
