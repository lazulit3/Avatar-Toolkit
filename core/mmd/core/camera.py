# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import math
from typing import Optional, List, Tuple, Callable, Any, Union

import bpy
from bpy.types import Object, ID, Camera, Context
from bpy_extras import anim_utils
from mathutils import Vector, Matrix, Euler
import traceback

from ..bpyutils import FnContext, Props
from ....core.logging_setup import logger

class FnCamera:
    @staticmethod
    def find_root(obj: Optional[Object]) -> Optional[Object]:
        """Find the root object of an MMD camera setup."""
        if obj is None:
            return None
        if FnCamera.is_mmd_camera_root(obj):
            return obj
        if obj.parent is not None and FnCamera.is_mmd_camera_root(obj.parent):
            return obj.parent
        return None

    @staticmethod
    def is_mmd_camera(obj: Object) -> bool:
        """Check if an object is an MMD camera."""
        return obj.type == "CAMERA" and FnCamera.find_root(obj.parent) is not None

    @staticmethod
    def is_mmd_camera_root(obj: Object) -> bool:
        """Check if an object is an MMD camera root."""
        return obj.type == "EMPTY" and obj.mmd_type == "CAMERA"

    @staticmethod
    def add_drivers(camera_object: Object) -> None:
        """Add drivers to the camera object for MMD camera functionality."""
        logger.debug(f"Adding drivers to camera: {camera_object.name}")
        
        def __add_driver(id_data: ID, data_path: str, expression: str, index: int = -1) -> None:
            """Add a driver to the specified ID data."""
            d = id_data.driver_add(data_path, index).driver
            d.type = "SCRIPTED"
            if "$empty_distance" in expression:
                v = d.variables.new()
                v.name = "empty_distance"
                v.type = "TRANSFORMS"
                v.targets[0].id = camera_object
                v.targets[0].transform_type = "LOC_Y"
                v.targets[0].transform_space = "LOCAL_SPACE"
                expression = expression.replace("$empty_distance", v.name)
            if "$is_perspective" in expression:
                v = d.variables.new()
                v.name = "is_perspective"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.is_perspective"
                expression = expression.replace("$is_perspective", v.name)
            if "$angle" in expression:
                v = d.variables.new()
                v.name = "angle"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.angle"
                expression = expression.replace("$angle", v.name)
            if "$sensor_height" in expression:
                v = d.variables.new()
                v.name = "sensor_height"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "CAMERA"
                v.targets[0].id = camera_object.data
                v.targets[0].data_path = "sensor_height"
                expression = expression.replace("$sensor_height", v.name)

            d.expression = expression

        try:
            __add_driver(camera_object.data, "ortho_scale", "25*abs($empty_distance)/45")
            __add_driver(camera_object, "rotation_euler", "pi if $is_perspective == False and $empty_distance > 1e-5 else 0", index=1)
            __add_driver(camera_object.data, "type", "not $is_perspective")
            __add_driver(camera_object.data, "lens", "$sensor_height/tan($angle/2)/2")
            logger.debug(f"Successfully added drivers to camera: {camera_object.name}")
        except Exception:
            logger.error(f"Failed to add drivers to camera {camera_object.name}: {traceback.format_exc()}")

    @staticmethod
    def remove_drivers(camera_object: Object) -> None:
        """Remove drivers from the camera object."""
        logger.debug(f"Removing drivers from camera: {camera_object.name}")
        try:
            camera_object.data.driver_remove("ortho_scale")
            camera_object.driver_remove("rotation_euler")
            camera_object.data.driver_remove("ortho_scale")
            camera_object.data.driver_remove("lens")
            logger.debug(f"Successfully removed drivers from camera: {camera_object.name}")
        except Exception:
            logger.error(f"Failed to remove drivers from camera {camera_object.name}: {traceback.format_exc()}")


class MigrationFnCamera:
    @staticmethod
    def update_mmd_camera() -> None:
        """Update all MMD cameras in the scene."""
        logger.info("Updating all MMD cameras in the scene")
        updated_count = 0
        
        for camera_object in bpy.data.objects:
            if camera_object.type != "CAMERA":
                continue

            root_object = FnCamera.find_root(camera_object)
            if root_object is None:
                # It's not a MMD Camera
                continue

            try:
                FnCamera.remove_drivers(camera_object)
                FnCamera.add_drivers(camera_object)
                updated_count += 1
            except Exception:
                logger.error(f"Failed to update MMD camera {camera_object.name}: {traceback.format_exc()}")
                
        logger.info(f"Updated {updated_count} MMD cameras")


class MMDCamera:
    def __init__(self, obj: Object):
        """Initialize an MMD camera."""
        root_object = FnCamera.find_root(obj)
        if root_object is None:
            logger.error(f"Object {obj.name} is not an MMD camera")
            raise ValueError(f"{obj.name} is not an MMD camera")

        self.__emptyObj = getattr(root_object, "original", obj)
        logger.debug(f"Initialized MMD camera with root: {self.__emptyObj.name}")

    @staticmethod
    def isMMDCamera(obj: Object) -> bool:
        """Check if an object is an MMD camera."""
        return FnCamera.find_root(obj) is not None

    @staticmethod
    def addDrivers(cameraObj: Object) -> None:
        """Add drivers to the camera object."""
        FnCamera.add_drivers(cameraObj)

    @staticmethod
    def removeDrivers(cameraObj: Object) -> None:
        """Remove drivers from the camera object. """
        if cameraObj.type != "CAMERA":
            return
        FnCamera.remove_drivers(cameraObj)

    @staticmethod
    def convertToMMDCamera(cameraObj: Object, scale: float = 1.0) -> 'MMDCamera':
        """Convert a camera to an MMD camera."""
        logger.info(f"Converting camera {cameraObj.name} to MMD camera with scale {scale}")
        
        if FnCamera.is_mmd_camera(cameraObj):
            logger.debug(f"Camera {cameraObj.name} is already an MMD camera")
            return MMDCamera(cameraObj)

        try:
            empty = bpy.data.objects.new(name="MMD_Camera", object_data=None)
            context = FnContext.ensure_context()
            FnContext.link_object(context, empty)

            cameraObj.parent = empty
            cameraObj.data.sensor_fit = "VERTICAL"
            cameraObj.data.lens_unit = "MILLIMETERS"  # MILLIMETERS, FOV
            cameraObj.data.ortho_scale = 25 * scale
            cameraObj.data.clip_end = 500 * scale
            setattr(cameraObj.data, Props.display_size, 5 * scale)
            cameraObj.location = (0, -45 * scale, 0)
            cameraObj.rotation_mode = "XYZ"
            cameraObj.rotation_euler = (math.radians(90), 0, 0)
            cameraObj.lock_location = (True, False, True)
            cameraObj.lock_rotation = (True, True, True)
            cameraObj.lock_scale = (True, True, True)
            cameraObj.data.dof.focus_object = empty
            FnCamera.add_drivers(cameraObj)

            empty.location = (0, 0, 10 * scale)
            empty.rotation_mode = "YXZ"
            setattr(empty, Props.empty_display_size, 5 * scale)
            empty.lock_scale = (True, True, True)
            empty.mmd_type = "CAMERA"
            empty.mmd_camera.angle = math.radians(30)
            empty.mmd_camera.persp = True
            
            logger.info(f"Successfully converted {cameraObj.name} to MMD camera")
            return MMDCamera(empty)
        except Exception:
            logger.error(f"Failed to convert camera {cameraObj.name} to MMD camera: {traceback.format_exc()}")
            raise

    @staticmethod
    def newMMDCameraAnimation(
        cameraObj: Optional[Object], 
        cameraTarget: Optional[Object] = None, 
        scale: float = 1.0, 
        min_distance: float = 0.1
    ) -> 'MMDCamera':
        """Create a new MMD camera animation."""
        logger.info(f"Creating new MMD camera animation with scale {scale}")
        
        try:
            scene = bpy.context.scene
            mmd_cam = bpy.data.objects.new(name="Camera", object_data=bpy.data.cameras.new("Camera"))
            FnContext.link_object(FnContext.ensure_context(), mmd_cam)
            MMDCamera.convertToMMDCamera(mmd_cam, scale=scale)
            mmd_cam_root = mmd_cam.parent

            _camera_override_func: Optional[Callable[[], Object]] = None
            if cameraObj is None:
                if scene.camera is None:
                    scene.camera = mmd_cam
                    logger.debug("Set scene camera to new MMD camera")
                    return MMDCamera(mmd_cam_root)
                _camera_override_func = lambda: scene.camera

            _target_override_func: Optional[Callable[[Object], Object]] = None
            if cameraTarget is None:
                _target_override_func = lambda camObj: camObj.data.dof.focus_object or camObj

            action_name = mmd_cam_root.name
            parent_action = bpy.data.actions.new(name=action_name)
            distance_action = bpy.data.actions.new(name=action_name + "_dis")
            FnCamera.remove_drivers(mmd_cam)

            from math import atan
            from mathutils import Matrix, Vector

            render = scene.render
            factor = (render.resolution_y * render.pixel_aspect_y) / (render.resolution_x * render.pixel_aspect_x)
            matrix_rotation = Matrix(([1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]))
            neg_z_vector = Vector((0, 0, -1))
            frame_start, frame_end, frame_current = scene.frame_start, scene.frame_end + 1, scene.frame_current
            frame_count = frame_end - frame_start
            frames = range(frame_start, frame_end)

            # Get channelbags for camera actions using Blender 5.0 API
            if not parent_action.slots:
                parent_slot = parent_action.slots.new(for_id=mmd_cam_root)
            else:
                parent_slot = parent_action.slots[0]
            parent_channelbag = anim_utils.action_ensure_channelbag_for_slot(parent_action, parent_slot)
            
            if not distance_action.slots:
                distance_slot = distance_action.slots.new(for_id=mmd_cam)
            else:
                distance_slot = distance_action.slots[0]
            distance_channelbag = anim_utils.action_ensure_channelbag_for_slot(distance_action, distance_slot)

            fcurves = []
            for i in range(3):
                fcurves.append(parent_channelbag.fcurves.new(data_path="location", index=i))  # x, y, z
            for i in range(3):
                fcurves.append(parent_channelbag.fcurves.new(data_path="rotation_euler", index=i))  # rx, ry, rz
            fcurves.append(parent_channelbag.fcurves.new(data_path="mmd_camera.angle"))  # fov
            fcurves.append(parent_channelbag.fcurves.new(data_path="mmd_camera.is_perspective"))  # persp
            fcurves.append(distance_channelbag.fcurves.new(data_path="location", index=1))  # dis
            for c in fcurves:
                c.keyframe_points.add(frame_count)

            logger.debug(f"Processing {frame_count} frames for camera animation")
            for f, x, y, z, rx, ry, rz, fov, persp, dis in zip(frames, *(c.keyframe_points for c in fcurves)):
                scene.frame_set(f)
                if _camera_override_func:
                    cameraObj = _camera_override_func()
                if _target_override_func:
                    cameraTarget = _target_override_func(cameraObj)
                cam_matrix_world = cameraObj.matrix_world
                cam_target_loc = cameraTarget.matrix_world.translation
                cam_rotation = (cam_matrix_world @ matrix_rotation).to_euler(mmd_cam_root.rotation_mode)
                cam_vec = cam_matrix_world.to_3x3() @ neg_z_vector
                if cameraObj.data.type == "ORTHO":
                    cam_dis = -(9 / 5) * cameraObj.data.ortho_scale
                    if cameraObj.data.sensor_fit != "VERTICAL":
                        if cameraObj.data.sensor_fit == "HORIZONTAL":
                            cam_dis *= factor
                        else:
                            cam_dis *= min(1, factor)
                else:
                    target_vec = cam_target_loc - cam_matrix_world.translation
                    cam_dis = -max(target_vec.length * cam_vec.dot(target_vec.normalized()), min_distance)
                cam_target_loc = cam_matrix_world.translation - cam_vec * cam_dis

                tan_val = cameraObj.data.sensor_height / cameraObj.data.lens / 2
                if cameraObj.data.sensor_fit != "VERTICAL":
                    ratio = cameraObj.data.sensor_width / cameraObj.data.sensor_height
                    if cameraObj.data.sensor_fit == "HORIZONTAL":
                        tan_val *= factor * ratio
                    else:  # cameraObj.data.sensor_fit == 'AUTO'
                        tan_val *= min(ratio, factor * ratio)

                x.co, y.co, z.co = ((f, i) for i in cam_target_loc)
                rx.co, ry.co, rz.co = ((f, i) for i in cam_rotation)
                dis.co = (f, cam_dis)
                fov.co = (f, 2 * atan(tan_val))
                persp.co = (f, cameraObj.data.type != "ORTHO")
                persp.interpolation = "CONSTANT"
                for kp in (x, y, z, rx, ry, rz, fov, dis):
                    kp.interpolation = "LINEAR"

            FnCamera.add_drivers(mmd_cam)
            mmd_cam_root.animation_data_create().action = parent_action
            mmd_cam.animation_data_create().action = distance_action
            scene.frame_set(frame_current)
            
            logger.info(f"Successfully created MMD camera animation with {frame_count} frames")
            return MMDCamera(mmd_cam_root)
            
        except Exception:
            logger.error(f"Failed to create MMD camera animation: {traceback.format_exc()}")
            raise

    def object(self) -> Object:
        """Get the root object of the MMD camera."""
        return self.__emptyObj

    def camera(self) -> Object:
        """Get the camera object of the MMD camera."""
        for i in self.__emptyObj.children:
            if i.type == "CAMERA":
                return i
        logger.error(f"No camera found for MMD camera root {self.__emptyObj.name}")
        raise KeyError(f"No camera found for MMD camera root {self.__emptyObj.name}")
