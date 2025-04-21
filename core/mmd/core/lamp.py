# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import bpy
from typing import Optional, Union, Any, List, Tuple
from bpy.types import Object, Context

from ..bpyutils import FnContext, Props
from ....core.logging_setup import logger


class MMDLamp:
    def __init__(self, obj: Object) -> None:
        if MMDLamp.isLamp(obj):
            obj = obj.parent
        if obj and obj.type == "EMPTY" and obj.mmd_type == "LIGHT":
            self.__emptyObj: Object = obj
        else:
            error_msg = f"{str(obj)} is not MMDLamp"
            logger.error(error_msg)
            raise ValueError(error_msg)

    @staticmethod
    def isLamp(obj: Optional[Object]) -> bool:
        """Check if the object is a lamp/light object"""
        return obj is not None and obj.type in {"LIGHT", "LAMP"}

    @staticmethod
    def isMMDLamp(obj: Optional[Object]) -> bool:
        """Check if the object is an MMD lamp"""
        if MMDLamp.isLamp(obj):
            obj = obj.parent
        return obj is not None and obj.type == "EMPTY" and obj.mmd_type == "LIGHT"

    @staticmethod
    def convertToMMDLamp(lampObj: Object, scale: float = 1.0) -> 'MMDLamp':
        """Convert a regular lamp to an MMD lamp"""
        if MMDLamp.isMMDLamp(lampObj):
            logger.debug(f"Object {lampObj.name} is already an MMD lamp")
            return MMDLamp(lampObj)

        logger.info(f"Converting {lampObj.name} to MMD lamp with scale {scale}")
        
        empty: Object = bpy.data.objects.new(name="MMD_Light", object_data=None)
        context = FnContext.ensure_context()
        FnContext.link_object(context, empty)

        empty.rotation_mode = "XYZ"
        empty.lock_rotation = (True, True, True)
        setattr(empty, Props.empty_display_size, 0.4)
        empty.scale = [10 * scale] * 3
        empty.mmd_type = "LIGHT"
        empty.location = (0, 0, 11 * scale)

        lampObj.parent = empty
        lampObj.data.color = (0.602, 0.602, 0.602)
        lampObj.location = (0.5, -0.5, 1.0)
        lampObj.rotation_mode = "XYZ"
        lampObj.rotation_euler = (0, 0, 0)
        lampObj.lock_rotation = (True, True, True)

        constraint = lampObj.constraints.new(type="TRACK_TO")
        constraint.name = "mmd_lamp_track"
        constraint.target = empty
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"

        logger.debug(f"Successfully created MMD lamp from {lampObj.name}")
        return MMDLamp(empty)

    def object(self) -> Object:
        """Get the empty object that represents this MMD lamp"""
        return self.__emptyObj

    def lamp(self) -> Object:
        """Get the actual lamp/light object"""
        for i in self.__emptyObj.children:
            if MMDLamp.isLamp(i):
                return i
        error_msg = f"No lamp found in MMD lamp {self.__emptyObj.name}"
        logger.error(error_msg)
        raise KeyError(error_msg)
