# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

from typing import List, Optional, Tuple, Union, Dict, Any, Set, cast

import bpy
from mathutils import Euler, Vector, Matrix

from ..bpyutils import FnContext, Props
from ....core.logging_setup import logger

SHAPE_SPHERE = 0
SHAPE_BOX = 1
SHAPE_CAPSULE = 2

MODE_STATIC = 0
MODE_DYNAMIC = 1
MODE_DYNAMIC_BONE = 2


def shapeType(collision_shape: str) -> int:
    """Convert collision shape name to type index"""
    return ("SPHERE", "BOX", "CAPSULE").index(collision_shape)


def collisionShape(shape_type: int) -> str:
    """Convert shape type index to collision shape name"""
    return ("SPHERE", "BOX", "CAPSULE")[shape_type]


def setRigidBodyWorldEnabled(enable: bool) -> bool:
    """Enable or disable the rigid body world and return previous state"""
    if bpy.ops.rigidbody.world_add.poll():
        logger.debug("Creating rigid body world")
        bpy.ops.rigidbody.world_add()
    rigidbody_world = bpy.context.scene.rigidbody_world
    enabled = rigidbody_world.enabled
    rigidbody_world.enabled = enable
    logger.debug(f"Rigid body world enabled: {enable} (was: {enabled})")
    return enabled


class RigidBodyMaterial:
    COLORS: List[int] = [
        0x7FDDD4,
        0xF0E68C,
        0xEE82EE,
        0xFFE4E1,
        0x8FEEEE,
        0xADFF2F,
        0xFA8072,
        0x9370DB,
        0x40E0D0,
        0x96514D,
        0x5A964E,
        0xE6BFAB,
        0xD3381C,
        0x165E83,
        0x701682,
        0x828216,
    ]

    @classmethod
    def getMaterial(cls, number: int) -> bpy.types.Material:
        """Get or create a material for rigid bodies with the specified number"""
        number = int(number)
        material_name = f"mmd_tools_rigid_{number}"
        if material_name not in bpy.data.materials:
            logger.debug(f"Creating rigid body material: {material_name}")
            mat = bpy.data.materials.new(material_name)
            color = cls.COLORS[number]
            mat.diffuse_color[:3] = [((0xFF0000 & color) >> 16) / float(255), ((0x00FF00 & color) >> 8) / float(255), (0x0000FF & color) / float(255)]
            mat.specular_intensity = 0
            if len(mat.diffuse_color) > 3:
                mat.diffuse_color[3] = 0.5
            mat.blend_method = "BLEND"
            if hasattr(mat, "shadow_method"):
                mat.shadow_method = "NONE"
            mat.use_backface_culling = True
            mat.show_transparent_back = False
            # Note: material.use_nodes is deprecated in Blender 5.0 - materials always use nodes
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            nodes.clear()
            node_color = nodes.new("ShaderNodeBackground")
            node_color.inputs["Color"].default_value = mat.diffuse_color
            node_output = nodes.new("ShaderNodeOutputMaterial")
            links.new(node_color.outputs[0], node_output.inputs["Surface"])
        else:
            mat = bpy.data.materials[material_name]
        return mat


class FnRigidBody:
    @staticmethod
    def new_rigid_body_objects(context: bpy.types.Context, parent_object: bpy.types.Object, count: int) -> List[bpy.types.Object]:
        """Create multiple rigid body objects parented to the specified object"""
        if count < 1:
            return []

        logger.debug(f"Creating {count} rigid body objects parented to {parent_object.name}")
        obj = FnRigidBody.new_rigid_body_object(context, parent_object)

        if count == 1:
            return [obj]

        return FnContext.duplicate_object(context, obj, count)

    @staticmethod
    def new_rigid_body_object(context: bpy.types.Context, parent_object: bpy.types.Object) -> bpy.types.Object:
        """Create a new rigid body object parented to the specified object"""
        logger.debug(f"Creating new rigid body object parented to {parent_object.name}")
        obj = FnContext.new_and_link_object(context, name="Rigidbody", object_data=bpy.data.meshes.new(name="Rigidbody"))
        obj.parent = parent_object
        obj.mmd_type = "RIGID_BODY"
        obj.rotation_mode = "YXZ"
        setattr(obj, Props.display_type, "SOLID")
        obj.show_transparent = True
        obj.hide_render = True
        obj.display.show_shadows = False

        with context.temp_override(object=obj):
            bpy.ops.rigidbody.object_add(type="ACTIVE")

        return obj

    @staticmethod
    def setup_rigid_body_object(
        obj: bpy.types.Object,
        shape_type: int,
        location: Vector,
        rotation: Euler,
        size: Vector,
        dynamics_type: int,
        collision_group_number: Optional[int] = None,
        collision_group_mask: Optional[List[bool]] = None,
        name: Optional[str] = None,
        name_e: Optional[str] = None,
        bone: Optional[str] = None,
        friction: Optional[float] = None,
        mass: Optional[float] = None,
        angular_damping: Optional[float] = None,
        linear_damping: Optional[float] = None,
        bounce: Optional[float] = None,
    ) -> bpy.types.Object:
        """Set up a rigid body object with the specified parameters"""
        logger.debug(f"Setting up rigid body object: {obj.name}")
        obj.location = location
        obj.rotation_euler = rotation

        obj.mmd_rigid.shape = collisionShape(shape_type)
        obj.mmd_rigid.size = size
        obj.mmd_rigid.type = str(dynamics_type) if dynamics_type in range(3) else "1"

        if collision_group_number is not None:
            obj.mmd_rigid.collision_group_number = collision_group_number

        if collision_group_mask is not None:
            obj.mmd_rigid.collision_group_mask = collision_group_mask

        if name is not None:
            obj.name = name
            obj.mmd_rigid.name_j = name
            obj.data.name = name

        if name_e is not None:
            obj.mmd_rigid.name_e = name_e

        if bone is not None:
            obj.mmd_rigid.bone = bone
        else:
            obj.mmd_rigid.bone = ""

        rb = obj.rigid_body
        if friction is not None:
            rb.friction = friction
        if mass is not None:
            rb.mass = mass
        if angular_damping is not None:
            rb.angular_damping = angular_damping
        if linear_damping is not None:
            rb.linear_damping = linear_damping
        if bounce is not None:
            rb.restitution = bounce

        return obj

    @staticmethod
    def get_rigid_body_size(obj: bpy.types.Object) -> Tuple[float, float, float]:
        """Get the size of a rigid body object based on its shape type"""
        assert obj.mmd_type == "RIGID_BODY"

        x0, y0, z0 = obj.bound_box[0]
        x1, y1, z1 = obj.bound_box[6]
        assert x1 >= x0 and y1 >= y0 and z1 >= z0

        shape = obj.mmd_rigid.shape
        if shape == "SPHERE":
            radius = (z1 - z0) / 2
            return (radius, 0.0, 0.0)
        elif shape == "BOX":
            x, y, z = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
            return (x, y, z)
        elif shape == "CAPSULE":
            diameter = x1 - x0
            radius = diameter / 2
            height = abs((z1 - z0) - diameter)
            return (radius, height, 0.0)
        else:
            error_msg = f"Invalid shape type: {shape}"
            logger.error(error_msg)
            raise ValueError(error_msg)

    @staticmethod
    def new_joint_object(context: bpy.types.Context, parent_object: bpy.types.Object, empty_display_size: float) -> bpy.types.Object:
        """Create a new joint object parented to the specified object"""
        logger.debug(f"Creating new joint object parented to {parent_object.name}")
        obj = FnContext.new_and_link_object(context, name="Joint", object_data=None)
        obj.parent = parent_object
        obj.mmd_type = "JOINT"
        obj.rotation_mode = "YXZ"
        setattr(obj, Props.empty_display_type, "ARROWS")
        setattr(obj, Props.empty_display_size, 0.1 * empty_display_size)
        obj.hide_render = True

        with context.temp_override():
            context.view_layer.objects.active = obj
            bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")

        rigid_body_constraint = obj.rigid_body_constraint
        rigid_body_constraint.disable_collisions = False
        rigid_body_constraint.use_limit_ang_x = True
        rigid_body_constraint.use_limit_ang_y = True
        rigid_body_constraint.use_limit_ang_z = True
        rigid_body_constraint.use_limit_lin_x = True
        rigid_body_constraint.use_limit_lin_y = True
        rigid_body_constraint.use_limit_lin_z = True
        rigid_body_constraint.use_spring_x = True
        rigid_body_constraint.use_spring_y = True
        rigid_body_constraint.use_spring_z = True
        rigid_body_constraint.use_spring_ang_x = True
        rigid_body_constraint.use_spring_ang_y = True
        rigid_body_constraint.use_spring_ang_z = True

        return obj

    @staticmethod
    def new_joint_objects(context: bpy.types.Context, parent_object: bpy.types.Object, count: int, empty_display_size: float) -> List[bpy.types.Object]:
        """Create multiple joint objects parented to the specified object"""
        if count < 1:
            return []

        logger.debug(f"Creating {count} joint objects parented to {parent_object.name}")
        obj = FnRigidBody.new_joint_object(context, parent_object, empty_display_size)

        if count == 1:
            return [obj]

        return FnContext.duplicate_object(context, obj, count)

    @staticmethod
    def setup_joint_object(
        obj: bpy.types.Object,
        location: Vector,
        rotation: Euler,
        rigid_a: bpy.types.Object,
        rigid_b: bpy.types.Object,
        maximum_location: Vector,
        minimum_location: Vector,
        maximum_rotation: Euler,
        minimum_rotation: Euler,
        spring_angular: Vector,
        spring_linear: Vector,
        name: str,
        name_e: Optional[str] = None,
    ) -> bpy.types.Object:
        """Set up a joint object with the specified parameters"""
        logger.debug(f"Setting up joint object: {obj.name} with name {name}")
        obj.name = f"J.{name}"

        obj.location = location
        obj.rotation_euler = rotation

        rigid_body_constraint = obj.rigid_body_constraint
        rigid_body_constraint.object1 = rigid_a
        rigid_body_constraint.object2 = rigid_b
        rigid_body_constraint.limit_lin_x_upper = maximum_location.x
        rigid_body_constraint.limit_lin_y_upper = maximum_location.y
        rigid_body_constraint.limit_lin_z_upper = maximum_location.z

        rigid_body_constraint.limit_lin_x_lower = minimum_location.x
        rigid_body_constraint.limit_lin_y_lower = minimum_location.y
        rigid_body_constraint.limit_lin_z_lower = minimum_location.z

        rigid_body_constraint.limit_ang_x_upper = maximum_rotation.x
        rigid_body_constraint.limit_ang_y_upper = maximum_rotation.y
        rigid_body_constraint.limit_ang_z_upper = maximum_rotation.z

        rigid_body_constraint.limit_ang_x_lower = minimum_rotation.x
        rigid_body_constraint.limit_ang_y_lower = minimum_rotation.y
        rigid_body_constraint.limit_ang_z_lower = minimum_rotation.z

        obj.mmd_joint.name_j = name
        if name_e is not None:
            obj.mmd_joint.name_e = name_e

        obj.mmd_joint.spring_linear = spring_linear
        obj.mmd_joint.spring_angular = spring_angular

        return obj
