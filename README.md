# Blender Addons Suite — Production Tooling for Hard-Surface & CAD Modeling

A modular Python toolkit engineered for **Blender 4.x** to accelerate solo hard-surface concept design, dimensional clearance verification, and procedural greeble placement. Built for industrial designers, technical artists, and mechanical modelers who require sub-millimeter precision and rapid non-destructive iteration.

---

## Overview

Modern hard-surface production pipelines demand high visual density and engineering plausibility. `blender-addons-suite` bridges the gap between artistic freedom and CAD-grade precision by providing three native Blender 4.x operators directly integrated into the 3D Viewport sidebar (`Aidelank Tools`).

---

## Tool Breakdown

### 1. Precision CAD Overlay (`precision_cad_overlay.py`)
Interactive viewport modal inspection tool leveraging Blender 4's modern `gpu` module and dependency graph evaluation (`context.evaluated_depsgraph_get`).

- **Real-Time Millimeter Measurement**: Accurately computes world-space edge lengths in metric units across both Object and Edit modes.
- **Clearance & Chamfer Breach Detection**: Instantly flags sub-tolerance features (e.g., $0.14\,\text{mm}$ manufacturing tolerances) with dynamic high-contrast warning overlays.
- **Screen-Space GPU Callouts**: Renders high-performance 2D numeric labels and depth-tested 3D shader batches without viewport stutter.
- **Interactive Modal Controls**:
  - `[C]`: Toggle between full geometry inspection and clearance breach isolation.
  - `[UP / DOWN ARROW]`: Adjust clearance threshold on the fly.
  - `[ESC / RMB]`: Graceful modal exit with automatic draw handler teardown.

### 2. Procedural Pipe Router (`pipe_router.py`)
Procedural spline bridge generator connecting selected mesh vertices, edge loops, or 3D markers into industrial conduits, hydraulic lines, and electrical harnesses.

- **Non-Destructive Spline Generation**: Automatically builds 3D Bezier or orthogonal Manhattan-style pipelines with parametric bevel depth and resolution.
- **Continuous Tangent Smoothing**: Calculates aligned Bezier vector handles to maintain smooth mechanical curvature without pinching.
- **Automated Flange Collars**: Procedurally synthesizes concentric mechanical flange rings and couplings at pipe endpoints and junctions with user-defined thickness and outer diameter ratios.

### 3. Asset Stamper & Greeble Manager (`asset_stamper.py`)
Normal-aligned rapid stamping and detailing utility designed for complex mechanical hull detailing and subassembly greebling.

- **Surface Normal Alignment**: Projects and aligns asset local $+Z$ coordinates to target polygon normals using evaluated geometry transforms.
- **Hard-Surface Rotation Snapping**: Restricts rotational jitter to cardinal mechanical increments ($90^\circ$ industrial snap, $45^\circ$ octagonal snap, or free continuous jitter).
- **Linked Instance Duplication**: Creates linked mesh duplicates (`Alt+D` paradigm) to maintain low memory footprints and GPU VRAM efficiency during dense hull scattering.
- **Automatic Collection Grouping**: Automatically routes new subassemblies into designated `Stamped_Greebles` collections for clean scene organization.

---

## Installation Guide

### Option A: Direct Git Clone
Clone directly into your Blender 4.x addons directory:

```bash
# macOS
git clone https://github.com/aidelank/blender-addons-suite.git ~/.config/blender/4.0/scripts/addons/blender-addons-suite

# Linux
git clone https://github.com/aidelank/blender-addons-suite.git ~/.config/blender/4.0/scripts/addons/blender-addons-suite

# Windows (PowerShell)
git clone https://github.com/aidelank/blender-addons-suite.git "$env:APPDATA\Blender Foundation\Blender\4.0\scripts\addons\blender-addons-suite"
```

### Option B: Zip Archive
1. Download this repository as a `.zip` archive.
2. Open Blender 4.x.
3. Navigate to **Edit > Preferences > Add-ons**.
4. Click the dropdown arrow in the upper right, choose **Install from Disk...**, and select the `.zip` file.
5. Search for **"Aidelank Production Tools Suite"** and check the enable box.

---

## Technical Highlights

- **Dependency Graph Evaluation**: Rigorously evaluates modifiers, shape keys, and transforms via `context.evaluated_depsgraph_get()` and `obj.evaluated_get(depsgraph)` to ensure measurements match true rendered surfaces.
- **Blender 4.0 GPU Modernization**: Complies with the modern `gpu` and `gpu_extras.batch` APIs, replacing legacy OpenGL calls (`bgl`) with clean `batch_for_shader` shaders (`UNIFORM_COLOR`).
- **Modal Event Architecture**: Utilizes non-blocking `PASS_THROUGH` modal loops, allowing standard navigation (orbit, pan, zoom, transform) while real-time HUD overlays remain responsive.
- **Fail-Safe Handler Teardown**: Guaranteed removal of `POST_PIXEL` and `POST_VIEW` draw handlers on operator cancel, addon unregister, or scene switches, preventing viewport memory leaks.

---

## Repository Structure

```
blender-addons-suite/
├── LICENSE                          # MIT License
├── README.md                        # Documentation & pipeline guide
├── __init__.py                      # Addon registry and suite metadata
└── addons/
    ├── __init__.py                  # Package exports
    ├── asset_stamper.py             # Normal-aligned greeble & subassembly placement
    ├── pipe_router.py               # Procedural spline routing with flange collars
    └── precision_cad_overlay.py     # Real-time GPU modal CAD measurement overlay
```

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2026 Lucas Yang (Aidelank).
