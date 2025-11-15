# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import re
from typing import Optional, Tuple, List, Set, Dict, Any, Generator, Callable, Union, Type, Iterator

from bpy.types import Operator, Context
from mathutils import Matrix, Vector, Quaternion

from ...logging_setup import logger


class _SetShadingBase:
    bl_options: Set[str] = {"REGISTER", "UNDO"}

    @staticmethod
    def _get_view3d_spaces(context: Context) -> Iterator[Any]:
        if getattr(context.area, "type", None) == "VIEW_3D":
            return (context.area.spaces[0],)
        return (area.spaces[0] for area in getattr(context.screen, "areas", ()) if area.type == "VIEW_3D")

    @staticmethod
    def _reset_color_management(context: Context, use_display_device: bool = True) -> None:
        try:
            context.scene.display_settings.display_device = ("None", "sRGB")[use_display_device]
        except TypeError:
            pass

    @staticmethod
    def _reset_material_shading(context: Context, use_shadeless: bool = False) -> None:
        # Note: material.use_nodes and material.use_shadeless are deprecated in Blender 5.0
        # Materials always use nodes now, and shadeless is handled differently
        # This method is kept for compatibility but no longer modifies materials
        pass

    def execute(self, context: Context) -> Dict[str, str]:
        context.scene.render.engine = "BLENDER_EEVEE"
        logger.debug(f"Setting render engine to BLENDER_EEVEE")

        shading_mode: Optional[str] = getattr(self, "_shading_mode", None)
        for space in self._get_view3d_spaces(context):
            shading = space.shading
            shading.type = "SOLID"
            shading.light = "FLAT" if shading_mode == "SHADELESS" else "STUDIO"
            shading.color_type = "TEXTURE" if shading_mode else "MATERIAL"
            shading.show_object_outline = False
            shading.show_backface_culling = False
        logger.debug(f"Applied shading mode: {shading_mode or 'DEFAULT'}")
        return {"FINISHED"}


class SetGLSLShading(Operator, _SetShadingBase):
    bl_idname: str = "mmd_tools.set_glsl_shading"
    bl_label: str = "GLSL View"
    bl_description: str = "Use GLSL shading with additional lighting"

    _shading_mode: str = "GLSL"


class SetShadelessGLSLShading(Operator, _SetShadingBase):
    bl_idname: str = "mmd_tools.set_shadeless_glsl_shading"
    bl_label: str = "Shadeless GLSL View"
    bl_description: str = "Use only toon shading"

    _shading_mode: str = "SHADELESS"


class ResetShading(Operator, _SetShadingBase):
    bl_idname: str = "mmd_tools.reset_shading"
    bl_label: str = "Reset View"
    bl_description: str = "Reset to default Blender shading"


class FlipPose(Operator):
    bl_idname: str = "mmd_tools.flip_pose"
    bl_label: str = "Flip Pose"
    bl_description: str = "Apply the current pose of selected bones to matching bone on opposite side of X-Axis."
    bl_options: Set[str] = {"REGISTER", "UNDO"}

    # https://docs.blender.org/manual/en/dev/rigging/armatures/bones/editing/naming.html
    __LR_REGEX: List[Dict[str, Any]] = [
        {"re": re.compile(r"^(.+)(RIGHT|LEFT)(\.\d+)?$", re.IGNORECASE), "lr": 1},
        {"re": re.compile(r"^(.+)([\.\- _])(L|R)(\.\d+)?$", re.IGNORECASE), "lr": 2},
        {"re": re.compile(r"^(LEFT|RIGHT)(.+)$", re.IGNORECASE), "lr": 0},
        {"re": re.compile(r"^(L|R)([\.\- _])(.+)$", re.IGNORECASE), "lr": 0},
        {"re": re.compile(r"^(.+)(左|右)(\.\d+)?$"), "lr": 1},
        {"re": re.compile(r"^(左|右)(.+)$"), "lr": 0},
    ]
    __LR_MAP: Dict[str, str] = {
        "RIGHT": "LEFT",
        "Right": "Left",
        "right": "left",
        "LEFT": "RIGHT",
        "Left": "Right",
        "left": "right",
        "L": "R",
        "l": "r",
        "R": "L",
        "r": "l",
        "左": "右",
        "右": "左",
    }

    @classmethod
    def flip_name(cls, name: str) -> str:
        for regex in cls.__LR_REGEX:
            match = regex["re"].match(name)
            if match:
                groups = match.groups()
                lr = groups[regex["lr"]]
                if lr in cls.__LR_MAP:
                    flip_lr = cls.__LR_MAP[lr]
                    name = ""
                    for i, s in enumerate(groups):
                        if i == regex["lr"]:
                            name += flip_lr
                        elif s:
                            name += s
                    return name
        return ""

    @staticmethod
    def __cmul(vec1: Union[Vector, Quaternion], vec2: Tuple[float, float, float, float]) -> Union[Vector, Quaternion]:
        return type(vec1)([x * y for x, y in zip(vec1, vec2)])

    @staticmethod
    def __matrix_compose(loc: Vector, rot: Quaternion, scale: Vector) -> Matrix:
        return (Matrix.Translation(loc) @ rot.to_matrix().to_4x4()) @ Matrix([(scale[0], 0, 0, 0), (0, scale[1], 0, 0), (0, 0, scale[2], 0), (0, 0, 0, 1)])

    @classmethod
    def __flip_pose(cls, matrix_basis: Matrix, bone_src: Any, bone_dest: Any) -> None:
        m = bone_dest.bone.matrix_local.to_3x3().transposed()
        mi = bone_src.bone.matrix_local.to_3x3().transposed().inverted() if bone_src != bone_dest else m.inverted()
        loc, rot, scale = matrix_basis.decompose()
        loc = cls.__cmul(mi @ loc, (-1, 1, 1))
        rot = cls.__cmul(Quaternion(mi @ rot.axis, rot.angle).normalized(), (1, 1, -1, -1))
        bone_dest.matrix_basis = cls.__matrix_compose(m @ loc, Quaternion(m @ rot.axis, rot.angle).normalized(), scale)

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object and context.active_object.type == "ARMATURE" and context.active_object.mode == "POSE"

    def execute(self, context: Context) -> Dict[str, str]:
        logger.info("Executing flip pose operation")
        pose_bones = context.active_object.pose.bones
        for b, mat in [(x, x.matrix_basis.copy()) for x in context.selected_pose_bones]:
            flip_name = self.flip_name(b.name)
            target_bone = pose_bones.get(flip_name, b)
            logger.debug(f"Flipping pose from {b.name} to {target_bone.name}")
            self.__flip_pose(mat, b, target_bone)
        logger.info("Flip pose operation completed")
        return {"FINISHED"}
