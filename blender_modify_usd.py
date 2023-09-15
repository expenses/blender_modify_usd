from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Tf
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
import copy
import os
import itertools

stage = None
object_to_prim = {}

def move_objects_between_collections(objects, from_col, to_col):
    for object in objects:
        to_col.objects.link(object)
        from_col.objects.unlink(object)

def load(filename):
    global stage
    object_to_prim.clear()
    prim_to_object = {}
    stage = Usd.Stage.Open(filename)
    cache = UsdGeom.XformCache()

    prototype_collection = bpy.data.collections.new("prototypes")
    prototype_collection.hide_viewport = True
    bpy.context.scene.collection.children.link(prototype_collection)

    reference_collections = {}

    for prim in stage.Traverse():
        object = bpy.data.objects.new(str(prim.GetPath()), None)
        object.matrix_basis = list(cache.GetLocalTransformation(prim)[0])
        object_to_prim[object] = [prim, copy.copy(object.matrix_basis)]
        prim_to_object[prim] = object

        prim_parent = prim.GetParent()
        if prim_parent and prim_parent in prim_to_object:
            object.parent = prim_to_object[prim_parent]

        bpy.context.scene.collection.objects.link(object)

        if UsdGeom.Imageable(prim).ComputeVisibility() == "invisible":
            object.hide_set(True)

        # Todo: we want to import prims if they're not referenced at all.
        #if prim.GetTypeName() == "Mesh":
        #    bpy.ops.wm.usd_import(filepath = filename, prim_path_mask = str(prim.GetPath()))

        arcs = Usd.PrimCompositionQuery.GetDirectReferences(prim).GetCompositionArcs()

        if len(arcs) > 0:
            direct_ref = arcs[0]
            filepath = direct_ref.GetTargetLayer().realPath
            prim_path = direct_ref.GetTargetPrimPath().pathString
            rel_path_from_base_dir = os.path.relpath(filepath, os.path.dirname(stage.GetRootLayer().realPath))
            collection_name = rel_path_from_base_dir + prim_path

            object.instance_type = "COLLECTION"

            if collection_name in reference_collections:
                object.instance_collection = reference_collections[collection_name]
            else:
                collection = bpy.data.collections.new(collection_name)
                prototype_collection.children.link(collection)
                reference_collections[collection_name] = collection
                object.instance_collection = collection

                #if prim.IsInstance():
                # Import the referenced prims into the new collection
                bpy.ops.wm.usd_import(filepath = filepath, prim_path_mask = prim_path)
                move_objects_between_collections(bpy.context.selected_objects, bpy.context.scene.collection, collection)

def save():
    for object, (prim, original_matrix) in object_to_prim.items():
        try:
            if object.matrix_basis == original_matrix:
                continue
        except Exception as e:
            print(e)
            continue

        original_pos, original_rot, original_scale = original_matrix.decompose()

        pos, rot, scale = object.matrix_basis.decompose()

        pos_modifed = pos != original_pos
        rot_modified = rot != original_rot
        scale_modified = scale != original_scale

        prim = UsdGeom.Xformable(prim)
        xform_ops = prim.GetOrderedXformOps()

        types = [xform_op.GetOpName() for xform_op in xform_ops]

        if types == ["xformOp:transform"]:
            xform_ops[0].Set(Gf.Matrix4d(list(object.matrix_basis)))
        elif types == ["xformOp:translate"]:
            if pos_modifed:
                xform_ops[0].Set(Gf.Vec3d(list(pos)))
            if rot_modified:
                prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))
        elif types == ["xformOp:translate", "xformOp:orient", "xformOp:scale"]:
            if pos_modifed:
                xform_ops[0].Set(Gf.Vec3d(list(pos)))
            if rot_modified:
                xform_ops[1].Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                xform_ops[2].Set(Gf.Vec3d(list(scale)))
        elif types == ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]:

            if pos_modifed:
                pass
                #xform_ops[0].Set(Gf.Vec3d(list(pos)))
            # Todo: quaternion to xyz.
            if rot_modified:
                pass
                #xform_ops[1].Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                pass
                #xform_ops[2].Set(Gf.Vec3d(list(scale)))
            prim.ClearXformOpOrder()
            prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            try:
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))
            except Exception as e:
                print(e)
        elif types == []:
            if pos_modifed:
                prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            if rot_modified:
                prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))
        else:
            print(types)

            is_known_unsupported = False
            # Try and gather up the xform orders we find in the wild to see if they can be supported.
            # Pivot types are hard to support.
            if 'xformOp:translate:pivot' in types:
                is_known_unsupported = True
            unsupported = [
                # potentially supportable
                ['xformOp:translate', 'xformOp:rotateX'],
                ['xformOp:translate', 'xformOp:rotateY'],
                ['xformOp:translate', 'xformOp:rotateZ'],
                ['xformOp:translate', 'xformOp:rotateXYZ'],
                ['xformOp:translate', 'xformOp:rotateX', 'xformOp:scale'],
                ['xformOp:translate', 'xformOp:rotateY', 'xformOp:scale'],
                ['xformOp:translate', 'xformOp:scale']
            ]
            for x in unsupported:
                if types == x:
                    is_known_unsupported = True
            #assert is_known_unsupported

            prim.ClearXformOpOrder()
            prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            try:
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))
            except Exception as e:
                print(e)

    stage.GetRootLayer().Save()

class LoadScene(bpy.types.Operator):
    bl_idname = "object.reload_scene"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Reload Scene"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        load("C:\\Users\\Ashley\\Desktop\\Kitchen_set\\Kitchen_set.usd")

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class SaveScene(bpy.types.Operator):
    bl_idname = "object.save_scene"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Save Scene"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        save()

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class OT_TestOpenFilebrowser(Operator, ImportHelper):

    bl_idname = "object.filebrowser_usd"
    bl_label = "Select a USD to load"

    filter_glob: StringProperty(
        default='*.usd*',
        options={'HIDDEN'}
    )

    def execute(self, context):
        load(self.filepath)

        return {'FINISHED'}

class SaveLoadPanel(bpy.types.Panel):
    bl_label = "Save/Load"
    bl_category = "USD"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        #row = box.row()
        box.row().operator("object.filebrowser_usd")
        #box.row().operator("object.reload_scene")
        box.row().operator("object.save_scene")


bpy.utils.register_class(LoadScene)
bpy.utils.register_class(SaveScene)
bpy.utils.register_class(SaveLoadPanel)
bpy.utils.register_class(OT_TestOpenFilebrowser)
