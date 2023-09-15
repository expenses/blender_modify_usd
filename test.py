import bpy
from bpy_extras.io_utils import ExportHelper
import copy
import sys 
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

base_transforms = {}

def store_current_transforms():
    base_transforms.clear()
    for object in bpy.data.objects:
        if "usd_path" in object:
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
            if "usd_path" in child and child not in base_transforms:
                pos, rot, scale = child.matrix_basis.decompose()

                path = Sdf.Path(object["usd_path"]).AppendPath(child.name.replace(".", "_"))
                prim = stage.DefinePrim(path, "Xform")
                
                if "target_prim" in child and "target_layer" in child:
                    prim.SetInstanceable(True)
                    prim.GetReferences().AddReference(child["target_layer"], child["target_prim"]) 
                
                if "variant_name" in child and "variant_selection" in child:
                    prim.GetVariantSets().AddVariantSet(child["variant_name"]).SetVariantSelection(child["variant_selection"])
                
                prim = UsdGeom.Xformable(prim)
                prim.ClearXformOpOrder()
                prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
                prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
                prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))                

    for object, base_transform in base_transforms.items():
        if not object:
            print(object)
            continue
        
        if object.matrix_basis != base_transform:
            prim = stage.OverridePrim(object["usd_path"])
            prim = UsdGeom.Xformable(prim)
            
            pos, rot, scale = object.matrix_basis.decompose()
            
            prim.ClearXformOpOrder()
            prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))

    stage.GetRootLayer().Save()

    store_current_transforms()

class StoreCurrentTransforms(bpy.types.Operator):
    bl_idname = "object.store_current_transforms"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Store Current Transforms"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    def execute(self, context):        # execute() is called when running the operator.
        store_current_transforms()
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class WriteOverride(bpy.types.Operator, ExportHelper):
    bl_idname = "object.write_override"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Write Override"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    filename_ext = ".usda"

    def execute(self, context):        # execute() is called when running the operator.
        write_override(self.filepath)

        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

class SaveLoadPanel(bpy.types.Panel):
    bl_label = "Save/Load"
    bl_category = "USD"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.row().operator("object.store_current_transforms")
        box.row().operator("object.write_override")

bpy.utils.register_class(StoreCurrentTransforms)
bpy.utils.register_class(WriteOverride)
bpy.utils.register_class(SaveLoadPanel)
