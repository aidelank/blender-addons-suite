"""
Procedural Pipe Router Addon for Blender 4.x
Generates procedural 3D curve-based pipelines between selected mesh vertices
or markers with automatic bend smoothing, bevel depth, and flange collars.
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
import math


def create_flange_mesh(location, direction, outer_radius, inner_radius, length, name="Pipe_Flange"):
    """Generate a procedural flange collar mesh at a pipe junction."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Build concentric cylinder / washer collar
    segments = 16
    rot = direction.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    trans = Matrix.Translation(location)
    mat = trans @ rot

    half_len = length * 0.5
    outer_verts_top = []
    outer_verts_bot = []
    inner_verts_top = []
    inner_verts_bot = []

    for i in range(segments):
        angle = (2.0 * math.pi * i) / segments
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        v_out_top = mat @ Vector((cos_a * outer_radius, sin_a * outer_radius, half_len))
        v_out_bot = mat @ Vector((cos_a * outer_radius, sin_a * outer_radius, -half_len))
        v_in_top = mat @ Vector((cos_a * inner_radius, sin_a * inner_radius, half_len))
        v_in_bot = mat @ Vector((cos_a * inner_radius, sin_a * inner_radius, -half_len))

        outer_verts_top.append(bm.verts.new(v_out_top))
        outer_verts_bot.append(bm.verts.new(v_out_bot))
        inner_verts_top.append(bm.verts.new(v_in_top))
        inner_verts_bot.append(bm.verts.new(v_in_bot))

    bm.verts.ensure_lookup_table()

    # Create side faces and rim caps
    for i in range(segments):
        next_i = (i + 1) % segments
        # Outer shell
        bm.faces.new([outer_verts_bot[i], outer_verts_bot[next_i], outer_verts_top[next_i], outer_verts_top[i]])
        # Top rim
        bm.faces.new([outer_verts_top[i], outer_verts_top[next_i], inner_verts_top[next_i], inner_verts_top[i]])
        # Bottom rim
        bm.faces.new([inner_verts_bot[i], inner_verts_bot[next_i], outer_verts_bot[next_i], outer_verts_bot[i]])

    bm.to_mesh(mesh)
    bm.free()
    return mesh


class VIEW3D_OT_procedural_pipe_router(bpy.types.Operator):
    """Generate procedural curved pipes connecting selected vertices with automated flanges"""
    bl_idname = "view3d.procedural_pipe_router"
    bl_label = "Procedural Pipe Router"
    bl_options = {'REGISTER', 'UNDO'}

    pipe_radius: bpy.props.FloatProperty(
        name="Pipe Radius",
        description="Outer radius of the routed pipe",
        default=0.04,
        min=0.001,
        max=5.0,
        unit='LENGTH'
    )

    bevel_resolution: bpy.props.IntProperty(
        name="Bevel Resolution",
        description="Circumferential segment resolution",
        default=6,
        min=2,
        max=32
    )

    routing_mode: bpy.props.EnumProperty(
        name="Routing Mode",
        description="Path generation algorithm",
        items=[
            ('BEZIER_SMOOTH', "Smooth Bezier", "Continuous smooth organic or hydraulic curve routing"),
            ('MANHATTAN_90', "Orthogonal 90°", "Industrial right-angle conduit routing"),
            ('DIRECT_POLY', "Direct Poly", "Direct straight segment piping"),
        ],
        default='BEZIER_SMOOTH'
    )

    handle_smoothness: bpy.props.FloatProperty(
        name="Handle Smoothness",
        description="Curvature tension for bezier handles",
        default=0.35,
        min=0.05,
        max=1.0
    )

    generate_flanges: bpy.props.BoolProperty(
        name="Generate Flange Collars",
        description="Create mechanical junction flange rings",
        default=True
    )

    flange_radius_factor: bpy.props.FloatProperty(
        name="Flange Outer Factor",
        description="Multiplier of pipe radius for flange outer edge",
        default=1.65,
        min=1.1,
        max=4.0
    )

    flange_thickness: bpy.props.FloatProperty(
        name="Flange Thickness",
        description="Width of flange collar along pipe axis",
        default=0.03,
        min=0.002,
        max=1.0,
        unit='LENGTH'
    )

    flange_at_endpoints: bpy.props.BoolProperty(
        name="Flange at Endpoints",
        default=True
    )

    flange_at_junctions: bpy.props.BoolProperty(
        name="Flange at Junctions",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def get_selected_points(self, context):
        """Extract ordered or selected world-space coordinates from mesh or scene selection."""
        obj = context.active_object
        coords = []

        if obj.type == 'MESH' and context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(obj.data)
            mat = obj.matrix_world
            selected_verts = [v for v in bm.verts if v.select]
            if len(selected_verts) >= 2:
                coords = [mat @ v.co for v in selected_verts]
        elif len(context.selected_objects) >= 2:
            # Multi-object centroids as routing nodes
            coords = [o.matrix_world.translation.copy() for o in context.selected_objects]

        return coords

    def execute(self, context):
        points = self.get_selected_points(context)

        # Fallback default path if fewer than 2 points selected
        if len(points) < 2:
            base_loc = context.scene.cursor.location
            points = [
                base_loc + Vector((-1.0, 0.0, 0.0)),
                base_loc + Vector((-0.2, 0.8, 0.5)),
                base_loc + Vector((0.6, -0.4, 0.9)),
                base_loc + Vector((1.2, 0.3, 0.2)),
            ]
            self.report({'INFO'}, "Created default pipeline nodes around 3D cursor")

        # Build intermediate orthogonal route if Manhattan is selected
        if self.routing_mode == 'MANHATTAN_90':
            routed_points = [points[0]]
            for i in range(len(points) - 1):
                p_start = points[i]
                p_end = points[i + 1]
                delta = p_end - p_start
                corner1 = p_start + Vector((delta.x, 0, 0))
                corner2 = corner1 + Vector((0, delta.y, 0))
                routed_points.extend([corner1, corner2, p_end])
            points = routed_points

        # Create Curve Data and Object
        curve_data = bpy.data.curves.new("Procedural_Pipe_Curve", type='CURVE')
        curve_data.dimensions = '3D'
        curve_data.bevel_depth = self.pipe_radius
        curve_data.bevel_resolution = self.bevel_resolution
        curve_data.use_fill_caps = True

        spline = curve_data.splines.new('BEZIER' if self.routing_mode == 'BEZIER_SMOOTH' else 'POLY')
        spline.points.add(len(points) - 1) if self.routing_mode != 'BEZIER_SMOOTH' else spline.bezier_points.add(len(points) - 1)

        pipe_obj = bpy.data.objects.new("Procedural_Pipeline", curve_data)
        context.collection.objects.link(pipe_obj)

        if self.routing_mode == 'BEZIER_SMOOTH':
            for i, pt in enumerate(points):
                bp = spline.bezier_points[i]
                bp.co = pt

                # Compute tangent directions
                if i == 0:
                    tangent = (points[1] - points[0]).normalized()
                elif i == len(points) - 1:
                    tangent = (points[-1] - points[-2]).normalized()
                else:
                    tangent = ((points[i + 1] - points[i - 1]) * 0.5).normalized()

                dist_fwd = (points[min(i + 1, len(points) - 1)] - pt).length
                dist_bwd = (pt - points[max(0, i - 1)]).length
                span = max(dist_fwd, dist_bwd) * self.handle_smoothness

                bp.handle_left_type = 'ALIGNED'
                bp.handle_right_type = 'ALIGNED'
                bp.handle_left = pt - tangent * span
                bp.handle_right = pt + tangent * span
        else:
            for i, pt in enumerate(points):
                spline.points[i].co = (pt.x, pt.y, pt.z, 1.0)

        # Generate Flange Collars if enabled
        if self.generate_flanges:
            flange_outer_r = self.pipe_radius * self.flange_radius_factor
            flange_inner_r = self.pipe_radius * 1.02
            flange_objects = []

            for i, pt in enumerate(points):
                is_endpoint = (i == 0 or i == len(points) - 1)
                is_junction = not is_endpoint

                if (is_endpoint and not self.flange_at_endpoints) or (is_junction and not self.flange_at_junctions):
                    continue

                if i == 0:
                    dir_vec = (points[1] - points[0]).normalized()
                elif i == len(points) - 1:
                    dir_vec = (points[-1] - points[-2]).normalized()
                else:
                    dir_vec = ((points[i + 1] - points[i - 1]) * 0.5).normalized()

                flange_mesh = create_flange_mesh(
                    location=pt,
                    direction=dir_vec,
                    outer_radius=flange_outer_r,
                    inner_radius=flange_inner_r,
                    length=self.flange_thickness,
                    name=f"Flange_{i}"
                )
                flange_obj = bpy.data.objects.new(f"Flange_Collar_{i}", flange_mesh)
                context.collection.objects.link(flange_obj)
                flange_obj.parent = pipe_obj
                flange_objects.append(flange_obj)

        # Focus new pipeline
        bpy.ops.object.select_all(action='DESELECT')
        pipe_obj.select_set(True)
        context.view_layer.objects.active = pipe_obj

        self.report({'INFO'}, f"Procedural Pipe created: {len(points)} nodes, radius {self.pipe_radius:.3f}m")
        return {'FINISHED'}


class VIEW3D_PT_pipe_router_panel(bpy.types.Panel):
    """Panel in Sidebar for Procedural Pipe Router"""
    bl_label = "Procedural Pipe Router"
    bl_idname = "VIEW3D_PT_pipe_router_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Aidelank Tools'

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Spline Bridge & Conduits", icon='CURVE_DATA')
        box.operator("view3d.procedural_pipe_router", text="Route Pipeline from Selection", icon='MOD_CURVE')


classes = (
    VIEW3D_OT_procedural_pipe_router,
    VIEW3D_PT_pipe_router_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
