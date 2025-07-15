# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

from typing import Set, Tuple

import bpy
from bpy.types import Operator, Context, Object

from ..core.model import FnModel
from ..core.sdef import FnSDEF
from ....core.logging_setup import logger


def _get_target_objects(context: Context) -> Tuple[Set[Object], Set[Object]]:
    root_objects: Set[Object] = set()
    selected_objects: Set[Object] = set()
    for i in context.selected_objects:
        if i.type == "MESH":
            selected_objects.add(i)
            continue

        root_object = FnModel.find_root_object(i)
        if root_object is None:
            continue
        if root_object in root_objects:
            continue

        root_objects.add(root_object)

        selected_objects |= set(FnModel.iterate_mesh_objects(root_object))
    return selected_objects, root_objects


class ResetSDEFCache(Operator):
    bl_idname = "mmd_tools.sdef_cache_reset"
    bl_label = "Reset MMD SDEF cache"
    bl_description = "Reset MMD SDEF cache of selected objects and clean unused cache"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: Context) -> Set[str]:
        target_meshes, _ = _get_target_objects(context)
        logger.info(f"Resetting SDEF cache for {len(target_meshes)} objects")
        for i in target_meshes:
            FnSDEF.clear_cache(i)
        FnSDEF.clear_cache(unused_only=True)
        logger.debug("SDEF cache reset completed")
        return {"FINISHED"}


class BindSDEF(Operator):
    bl_idname = "mmd_tools.sdef_bind"
    bl_label = "Bind SDEF Driver"
    bl_description = "Bind MMD SDEF data of selected objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Select mode",
        items=[
            ("2", "Bulk", "Speed up with numpy (may be slower in some cases)", 2),
            ("1", "Normal", "Normal mode", 1),
            ("0", "- Auto -", "Select best mode by benchmark result", 0),
        ],
        default="0",
    )
    use_skip: bpy.props.BoolProperty(
        name="Skip",
        description="Skip when the bones are not moving",
        default=True,
    )
    use_scale: bpy.props.BoolProperty(
        name="Scale",
        description="Support bone scaling (slow)",
        default=False,
    )

    def invoke(self, context: Context, event: bpy.types.Event) -> Set[str]:
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context: Context) -> Set[str]:
        target_meshes, root_objects = _get_target_objects(context)
        logger.info(f"Binding SDEF for {len(target_meshes)} objects with mode={self.mode}, skip={self.use_skip}, scale={self.use_scale}")

        for r in root_objects:
            r.mmd_root.use_sdef = True

        param = ((None, False, True)[int(self.mode)], self.use_skip, self.use_scale)
        count = sum(FnSDEF.bind(i, *param) for i in target_meshes)
        logger.info(f"Successfully bound SDEF for {count} of {len(target_meshes)} meshes")
        self.report({"INFO"}, f"Binded {count} of {len(target_meshes)} selected mesh(es)")
        return {"FINISHED"}


class UnbindSDEF(Operator):
    bl_idname = "mmd_tools.sdef_unbind"
    bl_label = "Unbind SDEF Driver"
    bl_description = "Unbind MMD SDEF data of selected objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: Context) -> Set[str]:
        target_meshes, root_objects = _get_target_objects(context)
        logger.info(f"Unbinding SDEF for {len(target_meshes)} objects")
        
        for i in target_meshes:
            FnSDEF.unbind(i)

        for r in root_objects:
            r.mmd_root.use_sdef = False

        logger.debug("SDEF unbinding completed")
        return {"FINISHED"}
