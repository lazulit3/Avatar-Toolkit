# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import re
from typing import List, Dict, Any, Set, Optional, Tuple, Union, Type

import bpy
from bpy.types import Context, Object, Operator, ShapeKey

from .. import utils
from ..bpyutils import FnContext, FnObject
from ..core.bone import FnBone
from ..core.model import FnModel, Model
from ..core.morph import FnMorph
from ....core.logging_setup import logger


class SelectObject(bpy.types.Operator):
    bl_idname = "mmd_tools.object_select"
    bl_label = "Select Object"
    bl_description = "Select the object"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    name: bpy.props.StringProperty(
        name="Name",
        description="The object name",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context: Context) -> Set[str]:
        logger.debug(f"Selecting object: {self.name}")
        utils.selectAObject(context.scene.objects[self.name])
        return {"FINISHED"}


class MoveObject(bpy.types.Operator, utils.ItemMoveOp):
    bl_idname = "mmd_tools.object_move"
    bl_label = "Move Object"
    bl_description = "Move active object up/down in the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    __PREFIX_REGEXP = re.compile(r"(?P<prefix>[0-9A-Z]{3}_)(?P<name>.*)")

    @classmethod
    def set_index(cls, obj: Object, index: int) -> None:
        m = cls.__PREFIX_REGEXP.match(obj.name)
        name = m.group("name") if m else obj.name
        obj.name = "%s_%s" % (utils.int2base(index, 36, 3), name)

    @classmethod
    def get_name(cls, obj: Object, prefix: Optional[str] = None) -> str:
        m = cls.__PREFIX_REGEXP.match(obj.name)
        name = m.group("name") if m else obj.name
        return name[len(prefix) :] if prefix and name.startswith(prefix) else name

    @classmethod
    def normalize_indices(cls, objects: List[Object]) -> None:
        for i, x in enumerate(objects):
            cls.set_index(x, i)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object is not None

    def execute(self, context: Context) -> Set[str]:
        obj = context.active_object
        objects = self.__get_objects(obj)
        if obj not in objects:
            logger.error(f'Cannot move object "{obj.name}"')
            self.report({"ERROR"}, f'Can not move object "{obj.name}"')
            return {"CANCELLED"}

        objects.sort(key=lambda x: x.name)
        logger.debug(f"Moving object {obj.name} {self.type}")
        self.move(objects, objects.index(obj), self.type)
        self.normalize_indices(objects)
        return {"FINISHED"}

    def __get_objects(self, obj: Object) -> Any:
        class __MovableList(list):
            def move(self, index_old: int, index_new: int) -> None:
                item = self[index_old]
                self.remove(item)
                self.insert(index_new, item)

        objects = []
        root = FnModel.find_root_object(obj)
        if root:
            rig = Model(root)
            if obj.mmd_type == "NONE" and obj.type == "MESH":
                objects = rig.meshes()
            elif obj.mmd_type == "RIGID_BODY":
                objects = rig.rigidBodies()
            elif obj.mmd_type == "JOINT":
                objects = rig.joints()
        return __MovableList(objects)


class CleanShapeKeys(bpy.types.Operator):
    bl_idname = "mmd_tools.clean_shape_keys"
    bl_label = "Clean Shape Keys"
    bl_description = "Remove unused shape keys of selected mesh objects"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return any(o.type == "MESH" for o in context.selected_objects)

    @staticmethod
    def __can_remove(key_block: ShapeKey) -> bool:
        if key_block.relative_key == key_block:
            return False  # Basis
        for v0, v1 in zip(key_block.relative_key.data, key_block.data):
            if v0.co != v1.co:
                return False
        return True

    def __shape_key_clean(self, obj: Object, key_blocks: List[ShapeKey]) -> None:
        for kb in key_blocks:
            if self.__can_remove(kb):
                logger.debug(f"Removing unused shape key: {kb.name} from {obj.name}")
                FnObject.mesh_remove_shape_key(obj, kb)
        if len(key_blocks) == 1:
            logger.debug(f"Removing single shape key: {key_blocks[0].name} from {obj.name}")
            FnObject.mesh_remove_shape_key(obj, key_blocks[0])

    def execute(self, context: Context) -> Set[str]:
        logger.info("Cleaning shape keys for selected objects")
        obj: Object
        for obj in context.selected_objects:
            if obj.type != "MESH" or obj.data.shape_keys is None:
                continue
            if not obj.data.shape_keys.use_relative:
                continue  # not be considered yet
            logger.debug(f"Processing shape keys for {obj.name}")
            self.__shape_key_clean(obj, obj.data.shape_keys.key_blocks)
        return {"FINISHED"}


class SeparateByMaterials(bpy.types.Operator):
    bl_idname = "mmd_tools.separate_by_materials"
    bl_label = "Separate By Materials"
    bl_options = {"REGISTER", "UNDO"}

    clean_shape_keys: bpy.props.BoolProperty(
        name="Clean Shape Keys",
        description="Remove unused shape keys of separated objects",
        default=True,
    )

    @classmethod
    def poll(cls, context: Context) -> bool:
        obj = context.active_object
        return obj and obj.type == "MESH"

    def __separate_by_materials(self, obj: Object) -> None:
        logger.info(f"Separating {obj.name} by materials")
        utils.separateByMaterials(obj)
        if self.clean_shape_keys:
            logger.debug("Cleaning shape keys after separation")
            bpy.ops.mmd_tools.clean_shape_keys()

    def execute(self, context: Context) -> Set[str]:
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        if root is None:
            logger.debug("No root object found, separating single object")
            self.__separate_by_materials(obj)
        else:
            logger.debug(f"Root object found: {root.name}, preparing for separation")
            bpy.ops.mmd_tools.clear_temp_materials()
            bpy.ops.mmd_tools.clear_uv_morph_view()

            # Store the current material names
            rig = Model(root)
            mat_names = [getattr(mat, "name", None) for mat in rig.materials()]
            self.__separate_by_materials(obj)
            for mesh in rig.meshes():
                FnMorph.clean_uv_morph_vertex_groups(mesh)
                if len(mesh.data.materials) > 0:
                    mat = mesh.data.materials[0]
                    idx = mat_names.index(getattr(mat, "name", None))
                    logger.debug(f"Setting index {idx} for mesh {mesh.name}")
                    MoveObject.set_index(mesh, idx)

            for morph in root.mmd_root.material_morphs:
                logger.debug(f"Updating material morph: {morph.name}")
                FnMorph(morph, rig).update_mat_related_mesh()
        utils.clearUnusedMeshes()
        return {"FINISHED"}


class JoinMeshes(bpy.types.Operator):
    bl_idname = "mmd_tools.join_meshes"
    bl_label = "Join Meshes"
    bl_description = "Join the Model meshes into a single one"
    bl_options = {"REGISTER", "UNDO"}

    sort_shape_keys: bpy.props.BoolProperty(
        name="Sort Shape Keys",
        description="Sort shape keys in the order of vertex morph",
        default=True,
    )

    def execute(self, context: Context) -> Set[str]:
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        if root is None:
            logger.error("No MMD model found")
            self.report({"ERROR"}, "Select a MMD model")
            return {"CANCELLED"}

        logger.info(f"Joining meshes for model: {root.name}")
        bpy.ops.mmd_tools.clear_temp_materials()
        bpy.ops.mmd_tools.clear_uv_morph_view()

        # Find all the meshes in mmd_root
        rig = Model(root)
        meshes_list = sorted(rig.meshes(), key=lambda x: x.name)
        if not meshes_list:
            logger.error("No meshes found in the model")
            self.report({"ERROR"}, "The model does not have any meshes")
            return {"CANCELLED"}
        active_mesh = meshes_list[0]
        logger.debug(f"Found {len(meshes_list)} meshes, using {active_mesh.name} as active")

        FnContext.select_objects(context, *meshes_list)
        FnContext.set_active_object(context, active_mesh)

        # Store the current order of the materials
        for m in meshes_list[1:]:
            for mat in m.data.materials:
                if mat not in active_mesh.data.materials[:]:
                    logger.debug(f"Adding material {mat.name} to active mesh")
                    active_mesh.data.materials.append(mat)

        # Join selected meshes
        logger.debug("Joining meshes")
        bpy.ops.object.join()

        if self.sort_shape_keys:
            logger.debug("Sorting shape keys")
            FnMorph.fixShapeKeyOrder(active_mesh, root.mmd_root.vertex_morphs.keys())
            active_mesh.active_shape_key_index = 0
        for morph in root.mmd_root.material_morphs:
            logger.debug(f"Updating material morph: {morph.name}")
            FnMorph(morph, rig).update_mat_related_mesh(active_mesh)
        utils.clearUnusedMeshes()
        return {"FINISHED"}


class AttachMeshesToMMD(bpy.types.Operator):
    bl_idname = "mmd_tools.attach_meshes"
    bl_label = "Attach Meshes to Model"
    bl_description = "Finds existing meshes and attaches them to the selected MMD model"
    bl_options = {"REGISTER", "UNDO"}

    add_armature_modifier: bpy.props.BoolProperty(default=True)

    def execute(self, context: Context) -> Set[str]:
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            logger.error("No MMD model found")
            self.report({"ERROR"}, "Select a MMD model")
            return {"CANCELLED"}

        armObj = FnModel.find_armature_object(root)
        if armObj is None:
            logger.error("Model armature not found")
            self.report({"ERROR"}, "Model Armature not found")
            return {"CANCELLED"}

        logger.info(f"Attaching meshes to model: {root.name}")
        FnModel.attach_mesh_objects(root, context.visible_objects, self.add_armature_modifier)
        return {"FINISHED"}


class ChangeMMDIKLoopFactor(bpy.types.Operator):
    bl_idname = "mmd_tools.change_mmd_ik_loop_factor"
    bl_label = "Change MMD IK Loop Factor"
    bl_description = "Multiplier for all bones' IK iterations in Blender"
    bl_options = {"REGISTER", "UNDO"}

    mmd_ik_loop_factor: bpy.props.IntProperty(
        name="MMD IK Loop Factor",
        description="Scaling factor of MMD IK loop",
        min=1,
        soft_max=10,
        max=100,
    )

    @classmethod
    def poll(cls, context: Context) -> bool:
        return FnModel.find_root_object(context.active_object) is not None

    def invoke(self, context: Context, event: Any) -> Set[str]:
        root_object = FnModel.find_root_object(context.active_object)
        self.mmd_ik_loop_factor = root_object.mmd_root.ik_loop_factor
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context: Context) -> Set[str]:
        root_object = FnModel.find_root_object(context.active_object)
        logger.info(f"Changing IK loop factor to {self.mmd_ik_loop_factor} for model: {root_object.name}")
        FnModel.change_mmd_ik_loop_factor(root_object, self.mmd_ik_loop_factor)
        return {"FINISHED"}


class RecalculateBoneRoll(bpy.types.Operator):
    bl_idname = "mmd_tools.recalculate_bone_roll"
    bl_label = "Recalculate bone roll"
    bl_description = "Recalculate bone roll for arm related bones"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: Context) -> bool:
        obj = context.active_object
        return obj and obj.type == "ARMATURE"

    def invoke(self, context: Context, event: Any) -> Set[str]:
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def draw(self, context: Context) -> None:
        layout = self.layout
        c = layout.column()
        c.label(text="This operation will break existing f-curve/action.", icon="QUESTION")
        c.label(text="Click [OK] to run the operation.")

    def execute(self, context: Context) -> Set[str]:
        arm = context.active_object
        logger.info(f"Recalculating bone roll for armature: {arm.name}")
        FnBone.apply_auto_bone_roll(arm)
        return {"FINISHED"}
