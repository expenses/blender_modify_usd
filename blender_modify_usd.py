from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Tf
import bpy
import copy

stage = None
object_to_prim = {}

def load(filename):
    global stage
    object_to_prim.clear()
    stage = Usd.Stage.Open(filename)
    cache = UsdGeom.XformCache()
    stack = [(stage.GetDefaultPrim(), None)]
    prototype_collection = bpy.data.collections.new("prototypes")
    bpy.context.scene.collection.children.link(prototype_collection)

    reference_collections = {}

    # Todo: we can probably just traverse the stage normally but
    # this makes setting the parent object slightly easier.
    while len(stack) > 0:
        (prim, parent_obj) = stack.pop()

        object = bpy.data.objects.new(str(prim.GetPath()), None)
        object.matrix_basis = list(cache.GetLocalTransformation(prim)[0])
        object_to_prim[object] = [prim, copy.copy(object.matrix_basis)]
        bpy.context.scene.collection.objects.link(object)


        if parent_obj is not None:
            object.parent = parent_obj

        arcs = Usd.PrimCompositionQuery.GetDirectReferences(prim).GetCompositionArcs()

        if len(arcs) > 0:
            direct_ref = arcs[0]
            rel_path_from_base_dir = os.path.relpath(direct_ref.GetTargetLayer().realPath, os.path.dirname(stage.GetRootLayer().realPath))
            collection_name = rel_path_from_base_dir + direct_ref.GetTargetPrimPath().pathString

            object.instance_type = "COLLECTION"

            if collection_name in reference_collections:
                object.instance_collection = reference_collections[collection_name]
            else:
                collection = bpy.data.collections.new(collection_name)
                prototype_collection.children.link(collection)
                reference_collections[collection_name] = collection
                object.instance_collection = collection
        else:
            for child in prim.GetChildren():
                stack.append((child, object))

def save():
    for object, (prim, original_matrix) in object_to_prim.items():
        if object.matrix_basis == original_matrix:
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
        elif types == ["xformOp:translate", "xformOp:orient", "xformOp:scale"]:
            if pos_modifed:
                xform_ops[0].Set(Gf.Vec3d(list(pos)))
            if rot_modified:
                xform_ops[1].Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                pass
                #xform_ops[2].Set(Gf.Vec3d(list(scale)))
        elif types == ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]:
            if pos_modifed:
                xform_ops[0].Set(Gf.Vec3d(list(pos)))
            # Todo: quaternion to xyz.
            if rot_modified:
                pass
                #xform_ops[1].Set(Gf.Quatd(*list(rot)))
            if scale_modified:
                xform_ops[2].Set(Gf.Vec3d(list(scale)))
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
            assert is_known_unsupported

            #prim.ClearXformOpOrder()
            #prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            #prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            #prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))

        stage.GetRootLayer().Save()

class LoadScene(bpy.types.Operator):
    bl_idname = "object.load_scene"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Load Scene"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        load("C:\\Users\\Ashley\\Desktop\\Kitchen_set\\Kitchen_set_instanced.usd")

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class SaveScene(bpy.types.Operator):
    bl_idname = "object.save_scene"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Save Scene"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        save()

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.


class SaveLoadPanel(bpy.types.Panel):
    bl_label = "Save/Load"
    bl_category = "USD"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        #box.label(text="Selection Tools")
        #box.operator("object.select_all").action = 'TOGGLE'
        row = box.row()
        #row.operator("object.select_all").action = 'INVERT'
        row.operator("object.load_scene")
        row.operator("object.save_scene")

bpy.utils.register_class(LoadScene)
bpy.utils.register_class(SaveScene)
bpy.utils.register_class(SaveLoadPanel)
