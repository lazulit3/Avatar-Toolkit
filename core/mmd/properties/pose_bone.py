# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools project, However Neoneko has added it to Avatar Toolkit.
# All credit goes to the original authors.
# Please note that some code was modified to fit the needs of Avatar Toolkit and some code may of been removed.
# MMD Tools is licensed under the terms of the GPL-3.0 license which Avatar Toolkit is also licensed under.
# You can find MMD Tools at: https://github.com/MMD-Blender/blender_mmd_tools/

import bpy
from bpy.types import PropertyGroup, Context, PoseBone
from bpy.props import (
    StringProperty, 
    IntProperty, 
    BoolProperty, 
    FloatProperty, 
    FloatVectorProperty
)

from ..logging_setup import logger
from ..bone import FnBone

def _mmd_bone_update_additional_transform(prop, context: Context):
    """Update handler for additional transform properties"""
    prop["is_additional_transform_dirty"] = True
    p_bone = context.active_pose_bone
    if p_bone and p_bone.mmd_bone.as_pointer() == prop.as_pointer():
        FnBone.apply_additional_transformation(prop.id_data)

def _mmd_bone_update_additional_transform_influence(prop, context: Context):
    """Update handler for additional transform influence"""
    pose_bone = context.active_pose_bone
    if pose_bone and pose_bone.mmd_bone.as_pointer() == prop.as_pointer():
        FnBone.update_additional_transform_influence(pose_bone)
    else:
        prop["is_additional_transform_dirty"] = True

def _mmd_bone_get_additional_transform_bone(prop):
    """Getter for additional transform bone property"""
    arm = prop.id_data
    bone_id = prop.get("additional_transform_bone_id", -1)
    if bone_id < 0:
        return ""
    pose_bone = FnBone.find_pose_bone_by_bone_id(arm, bone_id)
    if pose_bone is None:
        return ""
    return pose_bone.name

def _mmd_bone_set_additional_transform_bone(prop, value: str):
    """Setter for additional transform bone property"""
    arm = prop.id_data
    prop["is_additional_transform_dirty"] = True
    if value not in arm.pose.bones.keys():
        prop["additional_transform_bone_id"] = -1
        return
    pose_bone = arm.pose.bones[value]
    prop["additional_transform_bone_id"] = FnBone.get_or_assign_bone_id(pose_bone)

def _pose_bone_update_mmd_ik_toggle(prop: PoseBone, _context):
    """Update handler for IK toggle property"""
    v = prop.mmd_ik_toggle
    armature_object = prop.id_data
    for b in armature_object.pose.bones:
        for c in b.constraints:
            if c.type == "IK" and c.subtarget == prop.name:
                logger.debug('Updating IK constraint %s on bone %s', c.name, b.name)
                c.influence = v
                b_chain = b if c.use_tail else b.parent
                for chain_bone in ([b_chain] + b_chain.parent_recursive)[:c.chain_count]:
                    limit_c = next((c for c in chain_bone.constraints if c.type == "LIMIT_ROTATION" and not c.mute), None)
                    if limit_c:
                        limit_c.influence = v

class MMDBone(PropertyGroup):
    """Property group for MMD bone properties"""
    name_j: StringProperty(
        name="Name",
        description="Japanese Name",
        default="",
    )
    
    name_e: StringProperty(
        name="Name(Eng)",
        description="English Name",
        default="",
    )
    
    bone_id: IntProperty(
        name="Bone ID",
        description="Unique ID for the reference of bone morph and rotate+/move+",
        default=-1,
        min=-1,
    )
    
    transform_order: IntProperty(
        name="Transform Order",
        description="Deformation tier",
        min=0,
        max=100,
        soft_max=7,
    )
    
    is_controllable: BoolProperty(
        name="Controllable",
        description="Is controllable",
        default=True,
    )
    
    transform_after_dynamics: BoolProperty(
        name="After Dynamics",
        description="After physics",
        default=False,
    )
    
    enabled_fixed_axis: BoolProperty(
        name="Fixed Axis",
        description="Use fixed axis",
        default=False,
    )
    
    fixed_axis: FloatVectorProperty(
        name="Fixed Axis",
        description="Fixed axis",
        subtype="XYZ",
        size=3,
        precision=3,
        step=0.1,
        default=[0, 0, 0],
    )
    
    enabled_local_axes: BoolProperty(
        name="Local Axes",
        description="Use local axes",
        default=False,
    )
    
    local_axis_x: FloatVectorProperty(
        name="Local X-Axis",
        description="Local x-axis",
        subtype="XYZ",
        size=3,
        precision=3,
        step=0.1,
        default=[1, 0, 0],
    )
    
    local_axis_z: FloatVectorProperty(
        name="Local Z-Axis",
        description="Local z-axis",
        subtype="XYZ",
        size=3,
        precision=3,
        step=0.1,
        default=[0, 0, 1],
    )
    
    is_tip: BoolProperty(
        name="Tip Bone",
        description="Is zero length bone",
        default=False,
    )
    
    ik_rotation_constraint: FloatProperty(
        name="IK Rotation Constraint",
        description="The unit angle of IK",
        subtype="ANGLE",
        soft_min=0,
        soft_max=4,
        default=1,
    )
    
    has_additional_rotation: BoolProperty(
        name="Additional Rotation",
        description="Additional rotation",
        default=False,
        update=_mmd_bone_update_additional_transform,
    )
    
    has_additional_location: BoolProperty(
        name="Additional Location",
        description="Additional location",
        default=False,
        update=_mmd_bone_update_additional_transform,
    )
    
    additional_transform_bone: StringProperty(
        name="Additional Transform Bone",
        description="Additional transform bone",
        set=_mmd_bone_set_additional_transform_bone,
        get=_mmd_bone_get_additional_transform_bone,
        update=_mmd_bone_update_additional_transform,
    )
    
    additional_transform_bone_id: IntProperty(
        name="Additional Transform Bone ID",
        default=-1,
        update=_mmd_bone_update_additional_transform,
    )
    
    additional_transform_influence: FloatProperty(
        name="Additional Transform Influence",
        description="Additional transform influence",
        default=1,
        soft_min=-1,
        soft_max=1,
        update=_mmd_bone_update_additional_transform_influence,
    )
    
    is_additional_transform_dirty: BoolProperty(
        name="",
        default=True
    )
    
    def is_id_unique(self):
        """Check if the bone ID is unique"""
        return self.bone_id < 0 or not next((b for b in self.id_data.pose.bones if b.mmd_bone != self and b.mmd_bone.bone_id == self.bone_id), None)


def register():
    """Register MMD bone properties"""
    logger.info("Registering MMD bone properties")
    bpy.utils.register_class(MMDBone)
    
    # Add properties to PoseBone
    bpy.types.PoseBone.mmd_bone = bpy.props.PointerProperty(type=MMDBone)
    bpy.types.PoseBone.is_mmd_shadow_bone = bpy.props.BoolProperty(
        name="is_mmd_shadow_bone", 
        default=False
    )
    bpy.types.PoseBone.mmd_shadow_bone_type = bpy.props.StringProperty(
        name="mmd_shadow_bone_type"
    )
    bpy.types.PoseBone.mmd_ik_toggle = bpy.props.BoolProperty(
        name="MMD IK Toggle",
        description="MMD IK toggle is used to import/export animation of IK on-off",
        update=_pose_bone_update_mmd_ik_toggle,
        default=True,
    )


def unregister():
    """Unregister MMD bone properties"""
    logger.info("Unregistering MMD bone properties")
    
    # Remove properties from PoseBone
    del bpy.types.PoseBone.mmd_ik_toggle
    del bpy.types.PoseBone.mmd_shadow_bone_type
    del bpy.types.PoseBone.is_mmd_shadow_bone
    del bpy.types.PoseBone.mmd_bone
    
    bpy.utils.unregister_class(MMDBone)