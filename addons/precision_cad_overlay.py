"""
Precision CAD Overlay Addon for Blender 4.x
Real-time viewport modal draw handler evaluating depsgraph edge millimeter lengths,
clearance thresholds, and GPU vertex batch distance callouts.
"""

import bpy
import bmesh
import gpu
from gpu_extras.batch import batch_for_shader
import blf
from bpy_extras import view3d_utils
from mathutils import Vector

# Global storage for modal overlay state across viewports
_overlay_state = {
    "handler_px": None,
    "handler_view": None,
    "active": False,
    "operator_instance": None,
}


def get_scene_scale(scene):
    """Retrieve unit scale factor to millimeters."""
    unit = scene.unit_settings
    scale_length = unit.scale_length if unit.system != 'NONE' else 1.0
    # 1 Blender unit * scale_length in meters -> millimeters is * 1000.0
    return scale_length * 1000.0


def draw_callback_view(op, context):
    """3D viewport GPU draw pass for highlighted edges and clearance breaches."""
    if not op or not op.running:
        return

    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return

    edges_coords_normal = []
    edges_coords_breach = []

    # Get cached edge geometry from operator
    for p1, p2, length_mm, is_breach in op.cached_edges:
        if is_breach and op.show_clearance_warnings:
            edges_coords_breach.extend([p1, p2])
        elif op.show_all_edges or is_breach:
            edges_coords_normal.extend([p1, p2])

    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('ALWAYS')

    # Draw normal measured edges (Cyan/Teal)
    if edges_coords_normal:
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": edges_coords_normal})
        shader.bind()
        shader.uniform_float("color", (0.15, 0.85, 0.95, 0.75))
        batch.draw(shader)

    # Draw breach/warning edges (< clearance threshold, Red/Amber)
    if edges_coords_breach:
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": edges_coords_breach})
        shader.bind()
        shader.uniform_float("color", (1.0, 0.22, 0.18, 0.95))
        batch.draw(shader)

    gpu.state.blend_set('NONE')
    gpu.state.depth_test_set('NONE')


def draw_callback_px(op, context):
    """2D screen-space pixel draw pass for numeric distance badges."""
    if not op or not op.running:
        return

    region = context.region
    rv3d = context.region_data
    if not region or not rv3d:
        return

    font_id = 0
    blf.size(font_id, op.font_size)

    # Draw HUD Header
    blf.color(font_id, 0.9, 0.95, 1.0, 0.9)
    blf.position(font_id, 24, 52, 0)
    blf.draw(font_id, f"[CAD OVERLAY ACTIVE] Mode: {context.mode} | Min Threshold: {op.min_clearance_mm:.2f} mm | Edges: {len(op.cached_edges)}")

    blf.color(font_id, 0.7, 0.75, 0.8, 0.7)
    blf.position(font_id, 24, 30, 0)
    blf.draw(font_id, "Keys: [C] Toggle Clearance Only | [V] Toggle Vert Badges | [UP/DOWN] Threshold | [ESC/RMB] Finish")

    # Render numeric callout labels
    count = 0
    max_labels = op.max_labels_display

    for mid_pt, length_mm, is_breach in op.cached_labels:
        if count >= max_labels:
            break

        screen_coords = view3d_utils.location_3d_to_region_2d(region, rv3d, mid_pt)
        if not screen_coords:
            continue

        # Behind camera check
        cam_coord = view3d_utils.location_3d_to_region_2d(region, rv3d, mid_pt, default=None)
        if cam_coord is None:
            continue

        sx, sy = int(screen_coords.x), int(screen_coords.y)
        # Skip if outside viewport region
        if sx < 0 or sx > region.width or sy < 0 or sy > region.height:
            continue

        if is_breach and op.show_clearance_warnings:
            # High alert tag
            blf.color(font_id, 1.0, 0.25, 0.2, 1.0)
            text = f"▲ {length_mm:.2f} mm"
        else:
            blf.color(font_id, 0.2, 0.9, 0.95, 0.9)
            text = f"{length_mm:.2f} mm"

        blf.position(font_id, sx + 6, sy + 6, 0)
        blf.draw(font_id, text)
        count += 1


class VIEW3D_OT_cad_precision_overlay(bpy.types.Operator):
    """Interactive real-time CAD precision measurement overlay for Blender 4.x"""
    bl_idname = "view3d.cad_precision_overlay"
    bl_label = "Precision CAD Measurement Overlay"
    bl_options = {'REGISTER'}

    min_clearance_mm: bpy.props.FloatProperty(
        name="Min Clearance (mm)",
        description="Threshold below which edges trigger clearance breach warnings",
        default=0.14,
        min=0.001,
        max=100.0,
        precision=3
    )

    show_clearance_warnings: bpy.props.BoolProperty(
        name="Highlight Clearance Breaches",
        default=True
    )

    show_all_edges: bpy.props.BoolProperty(
        name="Show All Selected Edges",
        default=True
    )

    font_size: bpy.props.IntProperty(
        name="Callout Font Size",
        default=12,
        min=8,
        max=24
    )

    max_labels_display: bpy.props.IntProperty(
        name="Max Label Count",
        default=120,
        min=10,
        max=1000
    )

    def __init__(self):
        self.running = False
        self.cached_edges = []   # (v1_world, v2_world, length_mm, is_breach)
        self.cached_labels = []  # (midpoint_world, length_mm, is_breach)

    def update_geometry_cache(self, context):
        """Evaluate active object and compute world-space dimensions in millimeters."""
        self.cached_edges.clear()
        self.cached_labels.clear()

        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return

        scale_factor = get_scene_scale(context.scene)
        mat = obj.matrix_world

        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            selected_edges = [e for e in bm.edges if e.select]
            target_edges = selected_edges if selected_edges else bm.edges[:300]

            for e in target_edges:
                p1 = mat @ e.verts[0].co
                p2 = mat @ e.verts[1].co
                dist_world = (p2 - p1).length
                dist_mm = dist_world * scale_factor
                is_breach = dist_mm < self.min_clearance_mm
                mid = (p1 + p2) * 0.5
                self.cached_edges.append((p1, p2, dist_mm, is_breach))
                self.cached_labels.append((mid, dist_mm, is_breach))
        else:
            # Object Mode - Evaluate via Depsgraph
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()

            for edge in mesh.edges[:400]:
                v1 = mat @ mesh.vertices[edge.vertices[0]].co
                v2 = mat @ mesh.vertices[edge.vertices[1]].co
                dist_world = (v2 - v1).length
                dist_mm = dist_world * scale_factor
                is_breach = dist_mm < self.min_clearance_mm
                mid = (v1 + v2) * 0.5
                self.cached_edges.append((v1, v2, dist_mm, is_breach))
                self.cached_labels.append((mid, dist_mm, is_breach))

            eval_obj.to_mesh_clear()

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            self.report({'INFO'}, "CAD Overlay finished")
            return {'FINISHED'}

        # Toggle clearance-only display with 'C'
        if event.type == 'C' and event.value == 'PRESS':
            self.show_all_edges = not self.show_all_edges
            self.report({'INFO'}, f"Show All Edges: {self.show_all_edges}")
            return {'RUNNING_MODAL'}

        # Adjust clearance threshold interactively
        if event.type == 'UP_ARROW' and event.value == 'PRESS':
            self.min_clearance_mm += 0.05
            self.update_geometry_cache(context)
            return {'RUNNING_MODAL'}
        elif event.type == 'DOWN_ARROW' and event.value == 'PRESS':
            self.min_clearance_mm = max(0.01, self.min_clearance_mm - 0.05)
            self.update_geometry_cache(context)
            return {'RUNNING_MODAL'}

        # Refresh cache on mouse motion / transformation
        if event.type in {'MOUSEMOVE', 'G', 'R', 'S'}:
            self.update_geometry_cache(context)

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "View3D not found")
            return {'CANCELLED'}

        # Toggle off if already active
        if _overlay_state["active"]:
            self.cancel(context)
            return {'FINISHED'}

        self.running = True
        self.update_geometry_cache(context)

        args = (self, context)
        _overlay_state["handler_px"] = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_px, args, 'WINDOW', 'POST_PIXEL'
        )
        _overlay_state["handler_view"] = bpy.types.SpaceView3D.draw_handler_add(
            draw_callback_view, args, 'WINDOW', 'POST_VIEW'
        )
        _overlay_state["active"] = True
        _overlay_state["operator_instance"] = self

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        self.report({'INFO'}, "CAD Precision Overlay: ACTIVE (ESC to exit)")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self.running = False
        if _overlay_state["handler_px"]:
            bpy.types.SpaceView3D.draw_handler_remove(_overlay_state["handler_px"], 'WINDOW')
            _overlay_state["handler_px"] = None
        if _overlay_state["handler_view"]:
            bpy.types.SpaceView3D.draw_handler_remove(_overlay_state["handler_view"], 'WINDOW')
            _overlay_state["handler_view"] = None
        _overlay_state["active"] = False
        _overlay_state["operator_instance"] = None
        if context.area:
            context.area.tag_redraw()


class VIEW3D_PT_cad_overlay_panel(bpy.types.Panel):
    """Panel in Sidebar for Precision CAD Measurement Overlay"""
    bl_label = "CAD Precision Measurement"
    bl_idname = "VIEW3D_PT_cad_overlay_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Aidelank Tools'

    def draw(self, context):
        layout = self.layout
        is_active = _overlay_state.get("active", False)

        box = layout.box()
        box.label(text="Metric Inspection & Clearance", icon='DRIVER_DISTANCE')

        row = box.row()
        if is_active:
            row.operator("view3d.cad_precision_overlay", text="Stop Overlay", icon='CANCEL')
        else:
            row.operator("view3d.cad_precision_overlay", text="Launch Live Overlay", icon='PLAY')

        col = box.column(align=True)
        col.label(text="Default Tolerance: 0.14 mm")
        col.label(text="Real-time GPU shader lines & font tags")


classes = (
    VIEW3D_OT_cad_precision_overlay,
    VIEW3D_PT_cad_overlay_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    # Ensure active handler is cleanly detached if addon is disabled
    if _overlay_state.get("active") and _overlay_state.get("operator_instance"):
        try:
            _overlay_state["operator_instance"].cancel(bpy.context)
        except Exception:
            pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
