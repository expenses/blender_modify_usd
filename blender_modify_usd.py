# coding: utf-8
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Tf
import sys
import bpy
import os
import copy

stage = None
object_to_prim = {}

def load(filename):
    global stage
    stage = Usd.Stage.Open(filename)
    cache = UsdGeom.XformCache()
    stack = [(stage.GetDefaultPrim(), None)]

    # Todo: we can probably just traverse the stage normally but
    # this makes setting the parent object slightly easier.
    while len(stack) > 0:
        (prim, parent_obj) = stack.pop()

        object = bpy.data.objects.new(str(prim.GetPath()), None)
        object.matrix_basis = list(cache.GetLocalTransformation(prim)[0])

        if parent_obj is not None:
            object.parent = parent_obj
        bpy.context.scene.collection.objects.link(object)

        object_to_prim[object] = [prim, copy.copy(object.matrix_basis)]

        for child in prim.GetChildren():
            stack.append((child, object))

def modify():
    for object in bpy.data.objects:
        object.location.x += 1

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
                xform_ops[2].Set(Gf.Vec3d(list(scale)))
        elif types == ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]:
            if pos_modifed:
                xform_ops[0].Set(Gf.Vec3d(list(pos)))
            # Todo: quaternion to xyz.
            if rot_modified:
                assert False
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

            prim.ClearXformOpOrder()
            prim.AddXformOp(UsdGeom.XformOp.TypeTranslate).Set(Gf.Vec3d(list(pos)))
            prim.AddXformOp(UsdGeom.XformOp.TypeOrient).Set(Gf.Quatd(*list(rot)))
            prim.AddXformOp(UsdGeom.XformOp.TypeScale).Set(Gf.Vec3d(list(scale)))

        stage.GetRootLayer().Save()


load(sys.argv[1])
modify()
save()

bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath("test.blend"))
