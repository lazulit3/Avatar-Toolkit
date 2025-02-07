import bpy
from typing import Tuple, List, Dict, Set
from bpy.types import Object, Bone
from ..core.translations import t
from ..core.dictionaries import bone_names

def validate_armature(armature: Object) -> Tuple[bool, List[str]]:
    """Enhanced armature validation with multiple validation modes"""
    validation_mode = bpy.context.scene.avatar_toolkit.validation_mode
    messages: List[str] = []
    
    if validation_mode == 'NONE':
        return True, []
        
    if not armature or armature.type != 'ARMATURE' or not armature.data.bones:
        return False, [t("Armature.validation.basic_check_failed")]
        
    found_bones: Dict[str, Bone] = {bone.name.lower(): bone for bone in armature.data.bones}
    essential_bones: Set[str] = {'hips', 'spine', 'chest', 'neck', 'head'}
    
    missing_bones: List[str] = []
    for bone in essential_bones:
        if not any(alt_name in found_bones for alt_name in bone_names[bone]):
            missing_bones.append(bone)
    
    if missing_bones:
        messages.append(t("Armature.validation.missing_bones", bones=", ".join(missing_bones)))
    
    if validation_mode == 'STRICT':
        hierarchy: List[Tuple[str, str]] = [
            ('hips', 'spine'), ('spine', 'chest'), 
            ('chest', 'neck'), ('neck', 'head')
        ]
        for parent, child in hierarchy:
            if not validate_bone_hierarchy(found_bones, parent, child):
                messages.append(t("Armature.validation.invalid_hierarchy", 
                                parent=parent, child=child))
        
        symmetry_pairs: List[Tuple[str, str, str]] = [('arm', 'l', 'r'), ('leg', 'l', 'r')]
        for base, left, right in symmetry_pairs:
            if not validate_symmetry(found_bones, base, left, right):
                messages.append(t("Armature.validation.asymmetric_bones", bone=base))
                
        if (not validate_symmetry(found_bones, 'hand', 'l', 'r') and 
            not validate_symmetry(found_bones, 'wrist', 'l', 'r')):
            messages.append(t("Armature.validation.asymmetric_hand_wrist"))
    
    is_valid: bool = len(messages) == 0
    return is_valid, messages

def validate_bone_hierarchy(bones: Dict[str, Bone], parent_name: str, child_name: str) -> bool:
    """Validate if there is a valid parent-child relationship between bones"""
    parent_bone: Optional[Bone] = None
    child_bone: Optional[Bone] = None
    
    for alt_name in bone_names[parent_name]:
        if alt_name in bones:
            parent_bone = bones[alt_name]
            break
            
    for alt_name in bone_names[child_name]:
        if alt_name in bones:
            child_bone = bones[alt_name]
            break
    
    if not parent_bone or not child_bone:
        return False
        
    return child_bone.parent == parent_bone

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
