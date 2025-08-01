import bpy
from typing import Dict, List, Optional, Tuple, Set
from bpy.types import Object, Bone
from .common import get_active_armature
from .dictionaries import simplify_bonename, standard_bones, bone_hierarchy
from .logging_setup import logger


def detect_vrm_armature(armature: Object) -> bool:
    """
    Detect if armature uses VRM bone naming conventions
    """
    if not armature or armature.type != 'ARMATURE':
        return False
    
    vrm_patterns = [
        'jbipchips', 'jbipcspine', 'jbipcchest', 'jbipcneck', 'jbipchead',
        'jbiprlshoulder', 'jbiprrupperarm', 'jbiprrforearm', 'jbiprrhand',
        'jbipllshoulder', 'jbiplupperarm', 'jbipllforearm', 'jbipllhand',
        'jbiprrupperleg', 'jbiprrlowerleg', 'jbiprrfoot', 'jbiprrtoe',
        'jbiplupperleg', 'jbipllowerleg', 'jbipllfoot', 'jbiplltoe',
        'jbipc', 'jbipr', 'jbipl'  
    ]
    
    found_vrm_bones = 0
    for bone_name in armature.data.bones.keys():
        simplified_name = simplify_bonename(bone_name)
        if simplified_name.startswith('jbip') or any(pattern in simplified_name for pattern in vrm_patterns):
            found_vrm_bones += 1
    
    # Consider it VRM if we find at least 5 VRM bones
    logger.debug(f"Found {found_vrm_bones} VRM bones in armature {armature.name}")
    return found_vrm_bones >= 5


def get_vrm_to_unity_mapping() -> Dict[str, str]:
    """
    Get mapping from VRM bone names to Unity humanoid bone names
    """
    return {
        # Core structure
        'jbipchips': standard_bones['hips'],
        'jbipcspine': standard_bones['spine'],
        'jbipcchest': standard_bones['chest'],
        'jbipcupperchest': standard_bones.get('upper_chest', 'UpperChest'),
        'jbipcneck': standard_bones['neck'],
        'jbipchead': standard_bones['head'],
        
        # Left arm
        'jbipllshoulder': standard_bones.get('left_shoulder', 'LeftShoulder'),
        'jbiplupperarm': standard_bones['left_arm'],
        'jbipllforearm': standard_bones['left_elbow'],
        'jbipllhand': standard_bones['left_wrist'],
        
        # Right arm
        'jbiprlshoulder': standard_bones.get('right_shoulder', 'RightShoulder'),
        'jbiprrupperarm': standard_bones['right_arm'],
        'jbiprrforearm': standard_bones['right_elbow'],
        'jbiprrhand': standard_bones['right_wrist'],
        
        # Left leg
        'jbiplupperleg': standard_bones['left_leg'],
        'jbipllowerleg': standard_bones['left_knee'],
        'jbipllfoot': standard_bones['left_ankle'],
        'jbiplltoe': standard_bones['left_toe'],
        
        # Right leg
        'jbiprrupperleg': standard_bones['right_leg'],
        'jbiprrlowerleg': standard_bones['right_knee'],
        'jbiprrfoot': standard_bones['right_ankle'],
        'jbiprrtoe': standard_bones['right_toe'],
        
        # Eyes
        'jbipcleye': standard_bones.get('left_eye', 'Eye.L'),
        'jbipcreye': standard_bones.get('right_eye', 'Eye.R'),
        
        # Fingers - Left thumb
        'jbipllthumb1': standard_bones.get('thumb_1_l', 'Thumb1.L'),
        'jbipllthumb2': standard_bones.get('thumb_2_l', 'Thumb2.L'),
        'jbipllthumb3': standard_bones.get('thumb_3_l', 'Thumb3.L'),
        
        # Fingers - Left index
        'jbipllindex1': standard_bones.get('index_1_l', 'Index1.L'),
        'jbipllindex2': standard_bones.get('index_2_l', 'Index2.L'),
        'jbipllindex3': standard_bones.get('index_3_l', 'Index3.L'),
        
        # Fingers - Left middle
        'jbipllmiddle1': standard_bones.get('middle_1_l', 'Middle1.L'),
        'jbipllmiddle2': standard_bones.get('middle_2_l', 'Middle2.L'),
        'jbipllmiddle3': standard_bones.get('middle_3_l', 'Middle3.L'),
        
        # Fingers - Left ring
        'jbipllring1': standard_bones.get('ring_1_l', 'Ring1.L'),
        'jbipllring2': standard_bones.get('ring_2_l', 'Ring2.L'),
        'jbipllring3': standard_bones.get('ring_3_l', 'Ring3.L'),
        
        # Fingers - Left pinky
        'jbipllpinky1': standard_bones.get('pinkie_1_l', 'Pinky1.L'),
        'jbipllpinky2': standard_bones.get('pinkie_2_l', 'Pinky2.L'),
        'jbipllpinky3': standard_bones.get('pinkie_3_l', 'Pinky3.L'),
        
        # Fingers - Right thumb
        'jbiprthumb1': standard_bones.get('thumb_1_r', 'Thumb1.R'),
        'jbiprthumb2': standard_bones.get('thumb_2_r', 'Thumb2.R'),
        'jbiprthumb3': standard_bones.get('thumb_3_r', 'Thumb3.R'),
        
        # Fingers - Right index
        'jbiprindex1': standard_bones.get('index_1_r', 'Index1.R'),
        'jbiprindex2': standard_bones.get('index_2_r', 'Index2.R'),
        'jbiprindex3': standard_bones.get('index_3_r', 'Index3.R'),
        
        # Fingers - Right middle
        'jbiprmiddle1': standard_bones.get('middle_1_r', 'Middle1.R'),
        'jbiprmiddle2': standard_bones.get('middle_2_r', 'Middle2.R'),
        'jbiprmiddle3': standard_bones.get('middle_3_r', 'Middle3.R'),
        
        # Fingers - Right ring
        'jbiprring1': standard_bones.get('ring_1_r', 'Ring1.R'),
        'jbiprring2': standard_bones.get('ring_2_r', 'Ring2.R'),
        'jbiprring3': standard_bones.get('ring_3_r', 'Ring3.R'),
        
        # Fingers - Right pinky
        'jbiprpinky1': standard_bones.get('pinkie_1_r', 'Pinky1.R'),
        'jbiprpinky2': standard_bones.get('pinkie_2_r', 'Pinky2.R'),
        'jbiprpinky3': standard_bones.get('pinkie_3_r', 'Pinky3.R'),
    }


def find_vrm_bones_in_armature(armature: Object) -> Dict[str, str]:
    """
    Find VRM bones in armature and return mapping to their actual names
    """
    vrm_mapping = get_vrm_to_unity_mapping()
    found_bones = {}
    
    for bone_name in armature.data.bones.keys():
        simplified_name = simplify_bonename(bone_name)
        
        # Check if this bone matches any VRM pattern
        for vrm_pattern, unity_name in vrm_mapping.items():
            if simplified_name == vrm_pattern:
                found_bones[bone_name] = unity_name
                logger.debug(f"Found VRM bone: {bone_name} -> {unity_name}")
                break
        
        if simplified_name.startswith('jbip') and bone_name not in found_bones:
            unity_equivalent = guess_unity_name_from_vrm(simplified_name)
            if unity_equivalent:
                found_bones[bone_name] = unity_equivalent
                logger.debug(f"Guessed VRM bone mapping: {bone_name} -> {unity_equivalent}")
    
    return found_bones


def guess_unity_name_from_vrm(vrm_simplified: str) -> Optional[str]:
    """
    Attempt to guess Unity bone name from VRM simplified name
    """
    # Map common VRM patterns to Unity equivalents
    pattern_mappings = {
        'jbipcupperchest': 'UpperChest',
        'jbipcchest': 'Chest', 
        'jbipcspine': 'Spine',
        'jbipchips': 'Hips',
        'jbipcneck': 'Neck',
        'jbipchead': 'Head',
        
        # Left arm
        'jbipllclavicle': 'LeftShoulder',
        'jbipllshoulder': 'LeftShoulder', 
        'jbiplupperarm': 'LeftUpperArm',
        'jbipllforearm': 'LeftLowerArm',
        'jbipllhand': 'LeftHand',
        
        # Right arm  
        'jbiprrclavicle': 'RightShoulder',
        'jbiprlshoulder': 'RightShoulder',
        'jbiprrupperarm': 'RightUpperArm', 
        'jbiprrforearm': 'RightLowerArm',
        'jbiprrhand': 'RightHand',
        
        # Left leg
        'jbiplupperleg': 'LeftUpperLeg',
        'jbipllowerleg': 'LeftLowerLeg', 
        'jbipllfoot': 'LeftFoot',
        'jbiplltoe': 'LeftToes',
        
        # Right leg
        'jbiprrupperleg': 'RightUpperLeg',
        'jbiprrlowerleg': 'RightLowerLeg',
        'jbiprrfoot': 'RightFoot', 
        'jbiprrtoe': 'RightToes',
        
        # Eyes
        'jbipcleye': 'LeftEye',
        'jbipcreye': 'RightEye'
    }
    
    return pattern_mappings.get(vrm_simplified)


def is_vrm_collider_object(obj_name: str) -> bool:
    """
    Test if an object name represents a VRM collider
    """
    obj_name_lower = obj_name.lower()
    collider_patterns = ['collider', 'collision', 'dynamic', 'spring', 'physics', 'secondary']
    
    # Must contain a collider pattern
    contains_collider = any(pattern in obj_name_lower for pattern in collider_patterns)
    if not contains_collider:
        return False
    
    # Must be VRM-related (multiple detection methods)
    is_vrm = (
        'j_bip' in obj_name_lower or
        'jbip' in simplify_bonename(obj_name) or
        any(vrm_part in obj_name_lower for vrm_part in ['j_bip_c_', 'j_bip_l_', 'j_bip_r_'])
    )
    
    return is_vrm


def remove_vrm_colliders(armature: Object = None) -> Tuple[int, List[str]]:
    """
    Simple approach: Remove ALL objects with 'collider' in their name and clean up empty collections
    Returns tuple of (removed_count, removed_object_names)
    """
    objects_to_remove = []
    removed_names = []
    collections_to_check = set()
    
    # Store the current mode and active object
    current_mode = bpy.context.mode
    original_active = bpy.context.view_layer.objects.active
    
    if current_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    try:
        logger.info("Starting simple collider removal - removing ALL objects with 'collider' in name")
        
        collider_object_names = []
        for obj in bpy.data.objects:
            if 'collider' in obj.name.lower():
                collider_object_names.append(obj.name)
                # Track collections this object is in
                for collection in obj.users_collection:
                    collections_to_check.add(collection)
                logger.info(f"Found collider object: {obj.name}")
        
        logger.info(f"Found {len(collider_object_names)} collider objects to remove")
        
        # Remove collider objects by name
        removed_count = 0
        for obj_name in collider_object_names:
            try:
                # Check if object still exists
                if obj_name in bpy.data.objects:
                    obj = bpy.data.objects[obj_name]
                    logger.info(f"Removing collider object: {obj_name}")
                    
                    # Remove from all collections first
                    for collection in list(obj.users_collection):
                        collection.objects.unlink(obj)
                        logger.debug(f"  Unlinked from collection: {collection.name}")
                    
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed_count += 1
                    removed_names.append(obj_name)
                    logger.info(f"  Successfully removed: {obj_name}")
                else:
                    logger.debug(f"Object {obj_name} already removed")
                
            except Exception as e:
                logger.error(f"Failed to remove collider object {obj_name}: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        logger.info(f"Successfully removed {removed_count} collider objects")
        
        # Clean up empty collections
        empty_collections_removed = 0
        for collection in list(collections_to_check):
            try:
                # Check if collection is now empty and not the master collection
                if (len(collection.objects) == 0 and 
                    len(collection.children) == 0 and 
                    collection.name != "Collection" and
                    collection.name != "Master Collection"):
                    
                    logger.info(f"Removing empty collection: {collection.name}")
                    
                    if collection in bpy.context.scene.collection.children:
                        bpy.context.scene.collection.children.unlink(collection)
                    
                    bpy.data.collections.remove(collection)
                    empty_collections_removed += 1
                    logger.info(f"  Successfully removed collection: {collection.name}")
                    
            except Exception as e:
                logger.warning(f"Failed to remove empty collection {collection.name}: {str(e)}")
        
        if empty_collections_removed > 0:
            logger.info(f"Cleaned up {empty_collections_removed} empty collections")
        
    except Exception as e:
        logger.error(f"Error during collider removal: {str(e)}")
        return 0, []
    
    finally:
        if original_active and original_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = original_active
        
        if current_mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode=current_mode)
            except:
                pass
    
    logger.info(f"Collider removal complete. Removed {len(removed_names)} objects")
    return len(removed_names), removed_names


def convert_vrm_to_unity(armature: Object, remove_colliders: bool = True) -> Tuple[bool, List[str], int]:
    """
    Convert VRM armature bone names to Unity humanoid format
    
    Returns:
        Tuple of (success, messages, converted_count)
    """
    if not armature or armature.type != 'ARMATURE':
        return False, ["No valid armature selected"], 0
    
    logger.info(f"Starting VRM to Unity conversion for armature: {armature.name}")
    
    # Check if this is a VRM armature
    if not detect_vrm_armature(armature):
        return False, ["Selected armature does not appear to be a VRM armature"], 0
    
    messages = []
    converted_count = 0
    failed_conversions = []
    collider_count = 0
    
    current_mode = bpy.context.mode
    if current_mode != 'EDIT':
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')
    
    try:
        # First, remove collider objects and bones if requested
        if remove_colliders:
            collider_count, removed_colliders = remove_vrm_colliders(armature)
            if collider_count > 0:
                messages.append(f"Removed {collider_count} VRM collider objects/bones")
                logger.info(f"Removed {collider_count} VRM colliders: {removed_colliders}")
        
        vrm_bones = find_vrm_bones_in_armature(armature)
        
        if not vrm_bones:
            if remove_colliders and collider_count > 0:
                messages.append("No VRM bones found to convert (colliders were removed)")
                return True, messages, 0  
            else:
                return False, ["No VRM bones found in armature"], 0
        
        if bpy.context.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Rename bones
        for vrm_bone_name, unity_name in vrm_bones.items():
            if vrm_bone_name in armature.data.edit_bones:
                bone = armature.data.edit_bones[vrm_bone_name]
                
                # Check if target name already exists
                if unity_name in armature.data.edit_bones and unity_name != vrm_bone_name:
                    failed_conversions.append(f"{vrm_bone_name} -> {unity_name} (name conflict)")
                    continue
                
                # Rename the bone
                bone.name = unity_name
                converted_count += 1
                logger.debug(f"Renamed bone: {vrm_bone_name} -> {unity_name}")
        
        messages.append(f"Successfully converted {converted_count} VRM bones to Unity format")
        
        if failed_conversions:
            messages.append("Failed conversions due to name conflicts:")
            messages.extend(failed_conversions)
        
        logger.info(f"VRM to Unity conversion completed. Converted {converted_count} bones")
        
    except Exception as e:
        logger.error(f"Error during VRM conversion: {str(e)}")
        messages.append(f"Error during conversion: {str(e)}")
        return False, messages, converted_count
    
    finally:
        # Restore original mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')
    
    return converted_count > 0 or (remove_colliders and collider_count > 0), messages, converted_count


def validate_unity_hierarchy(armature: Object) -> Tuple[bool, List[str]]:
    """
    Validate that the converted armature has proper Unity humanoid hierarchy
    """
    if not armature or armature.type != 'ARMATURE':
        return False, ["No valid armature to validate"]
    
    messages = []
    is_valid = True
    
    # Check for essential Unity bones
    essential_unity_bones = [
        standard_bones['hips'],
        standard_bones['spine'],
        standard_bones['chest'],
        standard_bones['neck'],
        standard_bones['head']
    ]
    
    missing_bones = []
    for bone_name in essential_unity_bones:
        if bone_name not in armature.data.bones:
            missing_bones.append(bone_name)
    
    if missing_bones:
        is_valid = False
        messages.append("Missing essential Unity bones:")
        messages.extend([f"- {bone}" for bone in missing_bones])
    
    # Validate basic hierarchy
    hierarchy_issues = []
    for parent_name, child_name in bone_hierarchy:
        if parent_name in armature.data.bones and child_name in armature.data.bones:
            parent_bone = armature.data.bones[parent_name]
            child_bone = armature.data.bones[child_name]
            
            if child_bone.parent != parent_bone:
                hierarchy_issues.append(f"{parent_name} -> {child_name}")
    
    if hierarchy_issues:
        is_valid = False
        messages.append("Hierarchy issues found:")
        messages.extend([f"- {issue}" for issue in hierarchy_issues])
    
    if is_valid:
        messages.append("Unity hierarchy validation passed")
    
    return is_valid, messages