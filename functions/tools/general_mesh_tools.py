import bpy
import numpy as np
from bpy.types import Operator, Context
from typing import Set
from ...core.translations import t
from ...core.logging_setup import logger
from ...core.common import get_active_armature, get_all_meshes
from ...core.armature_validation import validate_armature

import bmesh


class MapItem():
    length: int
    current_node: bmesh.types.BMVert
    marched_paths: list[bmesh.types.BMEdge]

class AvatarToolkit_OT_SelectShortestSeamPath(Operator):
    """Find the shortest seam path between two vertices."""
    bl_idname = "avatar_toolkit.find_shortest_seam_path"
    bl_label = t("Tools.find_shortest_seam_path")
    bl_description = t("Tools.find_shortest_seam_path_desc")
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context: Context) -> bool:
        if context.mode != "EDIT_MESH":
            return False
        mesh_data: bpy.types.Mesh = context.active_object.data
        mesh = bmesh.from_edit_mesh(mesh_data)
        selected: int = 0
        for vert in mesh.verts:
            if vert.select == True:
                selected = selected+1
                if selected > 2:
                    return False
                found_seam: bool = False
                for edge in vert.link_edges:
                    if edge.seam:
                        found_seam = True
                if not found_seam:
                    return False
        if selected < 2:
            return False
        armature = get_active_armature(context)
        if not armature:
            return False
        valid, _, _ = validate_armature(armature)
        return valid
        
    def execute(self, context: Context) -> Set[str]:
        mesh_data: bpy.types.Mesh = context.active_object.data
        mesh = bmesh.from_edit_mesh(mesh_data)
        vert1: bmesh.types.BMVert = None
        vert2: bmesh.types.BMVert = None
        for vert in mesh.verts:
            if vert.select == True:
                if vert1 == None:
                    vert1 = vert
                else:
                    vert2 = vert
        
        current_verts: list[MapItem] = []

        first_item: MapItem  = MapItem()
        first_item.current_node = vert1
        first_item.length = 0
        first_item.marched_paths = []
        current_verts.append(first_item)

        def find_next_edge() -> list[bmesh.types.BMEdge]:
            if len(current_verts) == 0: #all paths have been exausted.
                return []
            for mapeditem in current_verts:
                current_verts.remove(mapeditem)
                for edge in mapeditem.current_node.link_edges:
                    if edge.seam and (edge not in mapeditem.marched_paths):
                        for vert_new in edge.verts:
                            if vert_new != mapeditem.current_node:
                                if vert_new == vert2:
                                    mapeditem.marched_paths.append(edge)
                                    return mapeditem.marched_paths
                                first_item: MapItem  = MapItem()
                                first_item.current_node = vert_new
                                first_item.length = mapeditem.length+1
                                first_item.marched_paths = []
                                first_item.marched_paths.extend(mapeditem.marched_paths)
                                first_item.marched_paths.append(edge)
                                current_verts.append(first_item)
            return find_next_edge()
            
        mesh.select_flush(False)
        path: list[bmesh.types.BMEdge] = find_next_edge()
        for edge in path:
            edge.select = True
            for vert in edge.verts:
                vert.select = True
        bpy.ops.mesh.select_mode(type='EDGE')
    
        return {'FINISHED'}

