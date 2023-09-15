import bpy
import copy
import sys 
from pxr import Usd, UsdGeom, UsdShade, Sdf


filepath = sys.argv[4]

#help(bpy.ops.wm.usd_import)

bpy.ops.wm.usd_import(filepath = filepath, use_instancing = True)

base_transforms = {}

for object in bpy.data.objects:
    if "usd_path" in object:
        base_transforms[object["usd_path"]] = copy.copy(object.matrix_basis)
        print(object["usd_path"])
        
bpy.data.objects[-1].location.x += 1

stage = Usd.Stage.CreateNew("override.usda")
source_stage = Usd.Stage.Open(filepath)

up_axis = source_stage.GetMetadata("upAxis")
meters_per_unit = source_stage.GetMetadata("metersPerUnit")

stage.SetMetadata("upAxis", up_axis)
stage.SetMetadata("metersPerUnit", meters_per_unit)

root = stage.DefinePrim("/root", "Xform")

stage.SetDefaultPrim(root)

root.GetReferences().AddReference(filepath)



for object in bpy.data.objects:
    if "usd_path" in object:
        if object.matrix_basis != base_transforms[object["usd_path"]]:
            stage.OverridePrim(object["usd_path"])
            print(object["usd_path"] + "!!!")

stage.GetRootLayer.Save()
