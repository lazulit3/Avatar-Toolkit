import bpy
from typing import Tuple, List, Dict, Set, Optional
from bpy.types import Object, Bone
from ..core.translations import t
from ..core.dictionaries import (
    standard_bones,
    bone_hierarchy,
    finger_hierarchy,
    acceptable_bone_hierarchy,
    acceptable_bone_names
)

def validate_armature(armature: Object) -> Tuple[bool, List[str], bool]:
    """
    Validates armature and returns (is_valid, messages, is_acceptable_standard)
    """
    validation_mode = bpy.context.scene.avatar_toolkit.validation_mode
    messages: List[str] = []
    
    if validation_mode == 'NONE':
        return True, [], False
        
    if not armature or armature.type != 'ARMATURE' or not armature.data.bones:
        return False, [t("Armature.validation.basic_check_failed")], False
        
    found_bones: Dict[str, Bone] = {bone.name: bone for bone in armature.data.bones}
    
    # Check if armature matches acceptable standards
    is_acceptable = check_acceptable_standards(found_bones)
    
    # List all bones in armature
    bone_list = "\n".join([f"- {bone}" for bone in found_bones.keys()])
    messages.append(t("Armature.validation.found_bones", bones=bone_list))
    
    # Check each bone against our standard
    non_standard_bones = []
    required_patterns = [
        'Hips', 'Spine', 'Chest', 'Neck', 'Head',
        'Upper', 'Lower', 'Hand', 'Foot', 'Toe',
        'Thumb', 'Index', 'Middle', 'Ring', 'Pinky',
        'Eye'
    ]
    
    for bone_name in found_bones:
        if any(pattern in bone_name for pattern in required_patterns):
            if bone_name not in standard_bones.values():
                non_standard_bones.append(bone_name)
    
    if non_standard_bones:
        non_standard_list = "\n".join([f"- {bone}" for bone in non_standard_bones])
        messages.append(t("Armature.validation.non_standard_bones", bones=non_standard_list))
    
    # Check for missing required bones
    essential_bones = {standard_bones[key] for key in ['hips', 'spine', 'chest', 'neck', 'head']}
    missing_bones = [bone for bone in essential_bones if bone not in found_bones]
    
    if missing_bones:
        missing_list = "\n".join([f"- {bone}" for bone in missing_bones])
        messages.append(t("Armature.validation.missing_bones", bones=missing_list))
    
    if validation_mode == 'STRICT':
        # Validate bone hierarchy
        for parent, child in bone_hierarchy:
            if parent in found_bones and child in found_bones:
                if not validate_bone_hierarchy(found_bones, parent, child):
                    messages.append(t("Armature.validation.invalid_hierarchy", 
                                    parent=parent, child=child))
        
        # Validate symmetry
        symmetry_pairs = [('arm', 'l', 'r'), ('leg', 'l', 'r')]
        for base, left, right in symmetry_pairs:
            if not validate_symmetry(found_bones, base, left, right):
                messages.append(t("Armature.validation.asymmetric_bones", bone=base))
                
        if (not validate_symmetry(found_bones, 'hand', 'l', 'r') and 
            not validate_symmetry(found_bones, 'wrist', 'l', 'r')):
            messages.append(t("Armature.validation.asymmetric_hand_wrist"))
        
        # Validate finger hierarchies
        for side in ['left', 'right']:
            for finger_chain in finger_hierarchy[side]:
                if all(bone in found_bones for bone in finger_chain):
                    if not validate_finger_chain(found_bones, finger_chain):
                        messages.append(t("Armature.validation.invalid_finger", finger=finger_chain[0]))
    
    is_valid = len(messages) == 0
    
    if not is_valid and is_acceptable:
        messages = [
            t("Armature.validation.acceptable_standard.success"),
            t("Armature.validation.acceptable_standard.note"),
            t("Armature.validation.acceptable_standard.option")
        ]
        return True, messages, True
        
    return is_valid, messages, False

def validate_bone_hierarchy(bones: Dict[str, Bone], parent_name: str, child_name: str) -> bool:
    """Validate if there is a valid parent-child relationship between bones"""
    if parent_name not in bones or child_name not in bones:
        return False
    return bones[child_name].parent == bones[parent_name]

def validate_symmetry(bones: Dict[str, Bone], base: str, left: str, right: str) -> bool:
    """Validate if matching left and right bones exist for a given base bone name"""
    left_patterns: List[str] = [
        f"{base}.{left}",
        f"{base}_{left}",
        f"{left}_{base}"
    ]
    
    right_patterns: List[str] = [
        f"{base}.{right}",
        f"{base}_{right}", 
        f"{right}_{base}"
    ]
    
    left_exists: bool = any(pattern in bones for pattern in left_patterns)
    right_exists: bool = any(pattern in bones for pattern in right_patterns)
    
    return left_exists and right_exists

def validate_finger_chain(bones: Dict[str, Bone], chain: Tuple[str, ...]) -> bool:
    """Validate if a finger bone chain has correct hierarchy"""
    for i in range(len(chain) - 1):
        if not validate_bone_hierarchy(bones, chain[i], chain[i + 1]):
            return False
    return True

def check_acceptable_standards(bones: Dict[str, Bone]) -> bool:
    """Check if armature matches acceptable non-standard hierarchy"""
    # Check if bones exist in acceptable list
    for bone_category, acceptable_names in acceptable_bone_names.items():
        found = False
        for name in acceptable_names:
            if name in bones:
                found = True
                break
        if not found:
            return False
    
    # Validate acceptable hierarchy
    for parent, child in acceptable_bone_hierarchy:
        if parent in bones and child in bones:
            if not validate_bone_hierarchy(bones, parent, child):
                return False
                
    return True
