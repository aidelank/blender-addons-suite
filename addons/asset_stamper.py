"""
Hard-Surface Asset Stamper & Greeble Manager for Blender 4.x
Aligns selected mesh subassemblies and greebles to target surface normals
with normal snapping, random rotation jitter, boundary offsets, and collection grouping.
"""

import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, Euler
import random
import math


class VIEW3D_OT_asset_stamper(bpy.types.Operator):
    """Align and stamp selected asset onto target surface with rotation jitter and normal alignment"""
    bl_idname = "view3d.asset_stamper"
    bl_label = "Stamp Asset to Surface"
    bl_options = {'REGISTER', 'UNDO'}

    rotation_snap_step: bpy.props.EnumProperty(
        name="Rotation Snap",
        description="Step angle for hard-surface orientation alignment",
        items=[
            ('FREE', "Free Jitter (0-360°)", "Full continuous rotational randomization"),
            ('STEP_90', "90° Industrial Snap", "Constrain to cardinal mechanical quadrants (0°, 90°, 180°, 270°)"),
            ('STEP_45', "45° Octagonal Snap", "Constrain to 45° mechanical increments"),
            ('NONE', "Fixed (0°)", "Keep default orientation relative to surface tangent"),
        ],
        default='STEP_90'
    )

    scale_jitter: bpy.props.FloatProperty(
        name="Scale Variation",
        description="Random scale deviation (+/- %)",
        default=0.08,
        min=0.0,
        max=0.5
    )

    embed_offset: bpy.props.FloatProperty(
        name="Surface Offset",
        description="Displacement along normal vector (negative to embed into hull)",
        default=0.002,
        min=-1.0,
        max=1.0,
        unit='LENGTH'
    )

    duplicate_linked: bpy.props.BoolProperty(
        name="Linked Duplicates",
        description="Create linked copies (Alt+D) to conserve VRAM during dense greebling",
        default=True
    )

    group_collection: bpy.props.BoolProperty(
        name="Group into Greebles Collection",
        default=True
    )

    scatter_count: bpy.props.IntProperty(
        name="Batch Stamp Count",
        description="Number of instances to distribute across target faces",
        default=6,
        min=1,
        max=100
    )

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) >= 1

    def execute(self, context):
        active_obj = context.active_object
        selected_objs = [o for o in context.selected_objects if o != active_obj and o.type == 'MESH']

        # Determine asset and target surface
        if selected_objs:
            # Multi-selection: active object is the target surface, other selected is the asset stamp
            target_obj = active_obj
            source_asset = selected_objs[0]
        else:
            # Single object selected: use it as asset, raycast downward to scene floor or create preview
            source_asset = active_obj
            target_obj = None

        # Setup destination collection
        target_collection = context.collection
        if self.group_collection:
            coll_name = "Stamped_Greebles"
            if coll_name in bpy.data.collections:
                target_collection = bpy.data.collections[coll_name]
            else:
                target_collection = bpy.data.collections.new(coll_name)
                context.scene.collection.children.link(target_collection)

        # Evaluate target surface geometry
        stamped_instances = []

        if target_obj and target_obj.type == 'MESH':
            depsgraph = context.evaluated_depsgraph_get()
            eval_target = target_obj.evaluated_get(depsgraph)
            mesh = eval_target.to_mesh()

            num_polys = len(mesh.polygons)
            if num_polys == 0:
                eval_target.to_mesh_clear()
                self.report({'WARNING'}, "Target mesh has no polygons")
                return {'CANCELLED'}

            # Pick target faces
            sample_count = min(self.scatter_count, num_polys)
            sampled_indices = random.sample(range(num_polys), sample_count)

            mat_target = target_obj.matrix_world

            for poly_idx in sampled_indices:
                poly = mesh.polygons[poly_idx]
                center_local = poly.center
                normal_local = poly.normal

                # Compute world coordinates and normal
                center_world = mat_target @ center_local
                normal_world = (mat_target.to_3x3() @ normal_local).normalized()

                # Calculate rotation aligning source Z-axis to surface normal
                z_axis = Vector((0.0, 0.0, 1.0))
                quat = z_axis.rotation_difference(normal_world)

                # Determine in-plane jitter angle
                if self.rotation_snap_step == 'STEP_90':
                    angle = random.choice([0, math.pi * 0.5, math.pi, math.pi * 1.5])
                elif self.rotation_snap_step == 'STEP_45':
                    angle = random.choice([i * math.pi * 0.25 for i in range(8)])
                elif self.rotation_snap_step == 'FREE':
                    angle = random.uniform(0.0, 2.0 * math.pi)
                else:
                    angle = 0.0

                jitter_quat = Quaternion(normal_world, angle)
                final_rot = jitter_quat @ quat

                # Calculate scale variation
                jitter_val = 1.0 + random.uniform(-self.scale_jitter, self.scale_jitter)
                scale_vec = source_asset.scale * jitter_val

                # Offset along normal
                pos_world = center_world + normal_world * self.embed_offset

                # Instantiate new asset
                if self.duplicate_linked:
                    new_obj = bpy.data.objects.new(f"{source_asset.name}_stamp", source_asset.data)
                else:
                    new_obj = bpy.data.objects.new(f"{source_asset.name}_stamp", source_asset.data.copy())

                target_collection.objects.link(new_obj)
                new_obj.matrix_world = Matrix.LocRotScale(pos_world, final_rot, scale_vec)
                stamped_instances.append(new_obj)

            eval_target.to_mesh_clear()
        else:
            # Standalone placement at cursor with 3D normal alignment
            cursor_loc = context.scene.cursor.location
            cursor_rot = context.scene.cursor.rotation_euler.to_quaternion()
            pos = cursor_loc + Vector((0, 0, self.embed_offset))

            new_obj = bpy.data.objects.new(f"{source_asset.name}_stamp", source_asset.data if self.duplicate_linked else source_asset.data.copy())
            target_collection.objects.link(new_obj)
            new_obj.matrix_world = Matrix.LocRotScale(pos, cursor_rot, source_asset.scale)
            stamped_instances.append(new_obj)

        self.report({'INFO'}, f"Stamped {len(stamped_instances)} instances to collection '{target_collection.name}'")
        return {'FINISHED'}


class VIEW3D_PT_asset_stamper_panel(bpy.types.Panel):
    """Panel in Sidebar for Hard-Surface Asset Stamper"""
    bl_label = "Asset Stamper & Greebles"
    bl_idname = "VIEW3D_PT_asset_stamper_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Aidelank Tools'

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Hard-Surface Subassemblies", icon='STICKY_UVS_LOC')
        box.operator("view3d.asset_stamper", text="Stamp Asset to Normal", icon='SNAP_NORMAL')


classes = (
    VIEW3D_OT_asset_stamper,
    VIEW3D_PT_asset_stamper_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
