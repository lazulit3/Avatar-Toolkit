# -*- coding: utf-8 -*-
# Copyright 2013 MMD Tools authors
# This file was originally part of the MMD Tools project, However Neoneko has added it to Avatar Toolkit.
# All credit goes to the original authors.
# Please note that some code was modified to fit the needs of Avatar Toolkit and some code may of been removed.
# MMD Tools is licensed under the terms of the GPL-3.0 license which Avatar Toolkit is also licensed under.
# You can find MMD Tools at: https://github.com/MMD-Blender/blender_mmd_tools/

import logging
import os
import re
from typing import Callable, Optional, Set, List, Dict, Any

import bpy
from bpy.types import Object, Context, Bone, PoseBone

from ...logging_setup import logger
from .bpyutils import FnContext


def selectAObject(obj: Object) -> None:
    """Select a single object and make it active"""
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        logger.debug(f"Failed to set object mode for {obj.name}")
    
    bpy.ops.object.select_all(action="DESELECT")
    FnContext.select_object(FnContext.ensure_context(), obj)
    FnContext.set_active_object(FnContext.ensure_context(), obj)


def enterEditMode(obj: Object) -> None:
    """Enter edit mode for the specified object"""
    selectAObject(obj)
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")


def setParentToBone(obj: Object, parent: Object, bone_name: str) -> None:
    """Set an object's parent to a specific bone"""
    selectAObject(obj)
    FnContext.set_active_object(FnContext.ensure_context(), parent)
    bpy.ops.object.mode_set(mode="POSE")
    parent.data.bones.active = parent.data.bones[bone_name]
    bpy.ops.object.parent_set(type="BONE", keep_transform=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def selectSingleBone(context: Context, armature: Object, bone_name: str, reset_pose: bool = False) -> None:
    """Select a single bone in an armature"""
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        logger.debug(f"Failed to set object mode for bone selection: {bone_name}")
    
    for i in context.selected_objects:
        i.select_set(False)
    
    FnContext.set_active_object(context, armature)
    bpy.ops.object.mode_set(mode="POSE")
    
    if reset_pose:
        for p_bone in armature.pose.bones:
            p_bone.matrix_basis.identity()
    
    armature_bones = armature.data.bones
    for bone in armature_bones:
        bone.select = bone.name == bone_name
        bone.select_head = bone.select_tail = bone.select
        if bone.select:
            armature_bones.active = bone
            bone.hide = False


# Regular expressions for name conversion
__CONVERT_NAME_TO_L_REGEXP = re.compile("^(.*)左(.*)$")
__CONVERT_NAME_TO_R_REGEXP = re.compile("^(.*)右(.*)$")


def convertNameToLR(name: str, use_underscore: bool = False) -> str:
    """Convert Japanese left/right naming to Blender's L/R convention"""
    m = __CONVERT_NAME_TO_L_REGEXP.match(name)
    delimiter = "_" if use_underscore else "."
    if m:
        name = m.group(1) + m.group(2) + delimiter + "L"
    m = __CONVERT_NAME_TO_R_REGEXP.match(name)
    if m:
        name = m.group(1) + m.group(2) + delimiter + "R"
    return name


__CONVERT_L_TO_NAME_REGEXP = re.compile(r"(?P<lr>(?P<separator>[._])[lL])(?P<after>($|(?P=separator)))")
__CONVERT_R_TO_NAME_REGEXP = re.compile(r"(?P<lr>(?P<separator>[._])[rR])(?P<after>($|(?P=separator)))")


def convertLRToName(name: str) -> str:
    """Convert Blender's L/R convention to Japanese left/right naming"""
    match = __CONVERT_L_TO_NAME_REGEXP.search(name)
    if match:
        return f"左{name[0:match.start()]}{match['after']}{name[match.end():]}"

    match = __CONVERT_R_TO_NAME_REGEXP.search(name)
    if match:
        return f"右{name[0:match.start()]}{match['after']}{name[match.end():]}"

    return name


def mergeVertexGroup(meshObj: Object, src_vertex_group_name: str, dest_vertex_group_name: str) -> None:
    """Merge weights from source vertex group to destination vertex group"""
    mesh = meshObj.data
    src_vertex_group = meshObj.vertex_groups[src_vertex_group_name]
    dest_vertex_group = meshObj.vertex_groups[dest_vertex_group_name]

    vtxIndex = src_vertex_group.index
    for v in mesh.vertices:
        try:
            gi = [i.group for i in v.groups].index(vtxIndex)
            dest_vertex_group.add([v.index], v.groups[gi].weight, "ADD")
        except ValueError:
            pass


def separateByMaterials(meshObj: Object) -> None:
    """Separate a mesh object by materials"""
    if len(meshObj.data.materials) < 2:
        selectAObject(meshObj)
        return
    
    matrix_parent_inverse = meshObj.matrix_parent_inverse.copy()
    prev_parent = meshObj.parent
    dummy_parent = bpy.data.objects.new(name="tmp", object_data=None)
    bpy.context.collection.objects.link(dummy_parent)
    
    meshObj.parent = dummy_parent
    meshObj.active_shape_key_index = 0
    
    try:
        enterEditMode(meshObj)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    
    for i in dummy_parent.children:
        materials = i.data.materials
        i.name = getattr(materials[0], "name", "None") if len(materials) else "None"
        i.parent = prev_parent
        i.matrix_parent_inverse = matrix_parent_inverse
    
    bpy.data.objects.remove(dummy_parent)


def clearUnusedMeshes() -> None:
    """Remove unused mesh data blocks"""
    meshes_to_delete = []
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            meshes_to_delete.append(mesh)

    for mesh in meshes_to_delete:
        bpy.data.meshes.remove(mesh)


def makePmxBoneMap(armObj: Object) -> Dict[str, PoseBone]:
    """Create a mapping from bone names to pose bones"""
    return {(i.mmd_bone.name_j or i.name): i for i in armObj.pose.bones}


__REMOVE_PREFIX_DIGITS_REGEXP = re.compile(r"\.\d{1,}$")


def unique_name(name: str, used_names: Set[str]) -> str:
    """Create a unique name that doesn't exist in the used_names set
    
    Args:
        name (str): The name to make unique
        used_names (Set[str]): A set of names that are already used
        
    Returns:
        str: The unique name, formatted as "{name}.{number:03d}"
    """
    if name not in used_names:
        return name
    
    count = 1
    new_name = orig_name = __REMOVE_PREFIX_DIGITS_REGEXP.sub("", name)
    
    while new_name in used_names:
        new_name = f"{orig_name}.{count:03d}"
        count += 1
    
    return new_name


def saferelpath(path: str, start: str, strategy: str = "inside") -> str:
    """Safely get a relative path, handling different drive issues on Windows
    
    Strategies:
    - inside: returns the basename of the path
    - outside: prepends '..' to the basename if on different drive
    - absolute: returns the absolute path
    """
    if strategy == "inside":
        return os.path.basename(path)

    if strategy == "absolute":
        return os.path.abspath(path)

    if strategy == "outside" and os.name == "nt":
        d1, _ = os.path.splitdrive(path)
        d2, _ = os.path.splitdrive(start)
        if d1 != d2:
            return ".." + os.sep + os.path.basename(path)

    return os.path.relpath(path, start)


class ItemOp:
    """Operations for managing collections of items"""
    
    @staticmethod
    def get_by_index(items: List[Any], index: int) -> Optional[Any]:
        """Get an item by index with bounds checking"""
        if 0 <= index < len(items):
            return items[index]
        return None

    @staticmethod
    def resize(items: bpy.types.bpy_prop_collection, length: int) -> None:
        """Resize a collection to the specified length"""
        count = length - len(items)
        if count > 0:
            for i in range(count):
                items.add()
        elif count < 0:
            for i in range(-count):
                items.remove(length)

    @staticmethod
    def add_after(items: bpy.types.bpy_prop_collection, index: int) -> tuple:
        """Add a new item after the specified index"""
        index_end = len(items)
        index = max(0, min(index_end, index + 1))
        items.add()
        items.move(index_end, index)
        return items[index], index


class ItemMoveOp:
    """Operations for moving items in collections"""
    
    @staticmethod
    def move(items: bpy.types.bpy_prop_collection, index: int, move_type: str, 
             index_min: int = 0, index_max: Optional[int] = None) -> int:
        """Move an item in a collection
        
        Args:
            items: The collection to modify
            index: Current index of the item
            move_type: Type of move ('UP', 'DOWN', 'TOP', 'BOTTOM')
            index_min: Minimum allowed index
            index_max: Maximum allowed index
            
        Returns:
            int: The new index after moving
        """
        if index_max is None:
            index_max = len(items) - 1
        else:
            index_max = min(index_max, len(items) - 1)
        
        index_min = min(index_min, index_max)

        if index < index_min:
            items.move(index, index_min)
            return index_min
        elif index > index_max:
            items.move(index, index_max)
            return index_max

        index_new = index
        if move_type == "UP":
            index_new = max(index_min, index - 1)
        elif move_type == "DOWN":
            index_new = min(index + 1, index_max)
        elif move_type == "TOP":
            index_new = index_min
        elif move_type == "BOTTOM":
            index_new = index_max

        if index_new != index:
            items.move(index, index_new)
        
        return index_new
