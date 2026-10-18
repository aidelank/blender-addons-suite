"""
Aidelank Production Tools Suite
Modular pipeline tooling for Blender 4.x hard-surface design, CAD measurement overlays,
procedural pipe routing, and rapid asset stamping.
"""

bl_info = {
    "name": "Aidelank Production Tools Suite",
    "author": "Lucas Yang (Aidelank)",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Aidelank Tools",
    "description": "Hard-surface pipeline automation: Precision CAD measurement overlay, procedural pipe routing, and rapid asset stamping.",
    "category": "3D View",
}

import importlib

if "precision_cad_overlay" in locals():
    importlib.reload(precision_cad_overlay)
    importlib.reload(pipe_router)
    importlib.reload(asset_stamper)
else:
    from .addons import precision_cad_overlay
    from .addons import pipe_router
    from .addons import asset_stamper

modules = (
    precision_cad_overlay,
    pipe_router,
    asset_stamper,
)


def register():
    for mod in modules:
        mod.register()


def unregister():
    for mod in reversed(modules):
        mod.unregister()


if __name__ == "__main__":
    register()
