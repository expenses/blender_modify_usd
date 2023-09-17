import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
import copy
import sys
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf
import os

base_transforms = {}
root_filename = None


def store_current_transforms():
    base_transforms.clear()
    for object in bpy.data.objects:
        if "usd_prim_path" in object:
            base_transforms[object] = copy.copy(object.matrix_basis)


def write_override(filename):
    try:
        stage = Usd.Stage.Open(filename)
    except Exception as e:
        stage = Usd.Stage.CreateNew(filename)

    for object in base_transforms.keys():
        # Got some errors here
        if not object:
            print(object)
            continue

        for child in object.children:
            if "usd_prim_path" in child and child not in base_transforms:
                # Sanitise name for USD. This ensures there won't be any naming conflicts.
                # An example of how things could go wrong otherwise:
                # /root/cube is cloned as cube.001. It is then stored in the usd file
                # as /root/cube_001. The file is reloaded and /root/cube is cloned again,
                # also being called cube.001. we'd then have to make sure there isn't also an object
                # called cube_001 before storing it into the usd.
                child.name = child.name.replace(".", "_")

                path = Sdf.Path(object["usd_prim_path"]).AppendPath(child.name)
                prim_type = "Xform"
                if "usd_type_name" in child:
                    prim_type = child["usd_type_name"]
                prim = stage.DefinePrim(path, prim_type)

                if "target_prim" in child and "target_layer" in child:
                    prim.SetInstanceable(True)
                    rel_path = os.path.relpath(
                        child["target_layer"], os.path.dirname(filename)
                    )
                    prim.GetReferences().AddReference(rel_path, child["target_prim"])

                if "variant_name" in child and "variant_selection" in child:
                    prim.GetVariantSets().AddVariantSet(
                        child["variant_name"]
                    ).SetVariantSelection(child["variant_selection"])

                prim = UsdGeom.Xformable(prim)

                pos, rot, scale = child.matrix_basis.decompose()

                prim.ClearXformOpOrder()
                prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
                prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))

    for object, base_transform in base_transforms.items():
        if not object:
            print(object)
            continue

        if object.matrix_basis != base_transform:
            prim = stage.OverridePrim(object["usd_prim_path"])
            prim = UsdGeom.Xformable(prim)

            pos, rot, scale = object.matrix_basis.decompose()

            prim.ClearXformOpOrder()
            prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))

    stage.GetRootLayer().Save()

    store_current_transforms()

    if root_filename is not None:
        root_stage = Usd.Stage.Open(root_filename)
        root_layer = root_stage.GetRootLayer()

        rel_layer_path = os.path.relpath(
            stage.GetRootLayer().identifier, os.path.dirname(root_layer.identifier)
        )

        # https://docs.omniverse.nvidia.com/dev-guide/latest/programmer_ref/usd/layers/add-sublayer.html
        root_layer.subLayerPaths.insert(0, rel_layer_path)
        root_layer.Save()


class StoreCurrentTransforms(bpy.types.Operator):
    bl_idname = "object.store_current_transforms"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Store Current Transforms (for manually loaded scenes)"  # Display name in the interface.
    bl_options = {"REGISTER", "UNDO"}  # Enable undo for the operator.

    def execute(self, context):  # execute() is called when running the operator.
        store_current_transforms()
        return {"FINISHED"}  # Lets Blender know the operator finished successfully.


class Reload(bpy.types.Operator):
    bl_idname = "object.usd_reload"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Reload root usd"  # Display name in the interface.
    bl_options = {"REGISTER", "UNDO"}  # Enable undo for the operator.

    filename_ext = ".usda"

    def execute(self, context):  # execute() is called when running the operator.
        for object in bpy.data.objects:
            bpy.data.objects.remove(object, do_unlink=True)
            
        for collection in bpy.data.collections:
            bpy.data.collections.remove(collection)

        if root_filename is not None:
            bpy.ops.wm.usd_import(
                filepath=root_filename,
                use_instancing=True,
                apply_unit_conversion_scale=False,
            )

        store_current_transforms()

        return {"FINISHED"}  # Lets Blender know the operator finished successfully.


class WriteOverride(bpy.types.Operator, ExportHelper):
    bl_idname = "object.write_override"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Write Override"  # Display name in the interface.
    bl_options = {"REGISTER", "UNDO"}  # Enable undo for the operator.

    filename_ext = ".usda"

    def execute(self, context):  # execute() is called when running the operator.
        write_override(self.filepath)

        return {"FINISHED"}  # Lets Blender know the operator finished successfully.


class OT_TestOpenFilebrowser(bpy.types.Operator, ImportHelper):
    bl_idname = "object.filebrowser_usd"
    bl_label = "Select root usd"

    filter_glob: bpy.props.StringProperty(default="*.usd*", options={"HIDDEN"})

    def execute(self, context):
        global root_filename
        root_filename = self.filepath
        # One less click.
        store_current_transforms()

        return {"FINISHED"}


class SaveLoadPanel(bpy.types.Panel):
    bl_label = "Save/Load"
    bl_category = "USD"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.row().label(text=root_filename or "None")
        box.row().operator("object.filebrowser_usd")
        box.row().operator("object.usd_reload")
        box.row().operator("object.write_override")
        box.row().operator("object.store_current_transforms")


bpy.utils.register_class(Reload)
bpy.utils.register_class(OT_TestOpenFilebrowser)
bpy.utils.register_class(StoreCurrentTransforms)
bpy.utils.register_class(WriteOverride)
bpy.utils.register_class(SaveLoadPanel)
