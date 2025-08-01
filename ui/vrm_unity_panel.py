import bpy
from bpy.types import Panel, Context, UILayout
from .main_panel import AvatarToolKit_PT_AvatarToolkitPanel, CATEGORY_NAME
from ..core.translations import t
from ..core.common import get_active_armature
from ..core.vrm_unity_converter import detect_vrm_armature
from ..functions.tools.vrm_unity_conversion import AvatarToolkit_OT_ConvertVRMToUnity


class AvatarToolKit_PT_VRMUnityPanel(Panel):
    """Panel for VRM to Unity conversion tools"""
    bl_label = "VRM to Unity"
    bl_idname = "OBJECT_PT_avatar_toolkit_vrm_unity"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY_NAME
    bl_parent_id = AvatarToolKit_PT_AvatarToolkitPanel.bl_idname
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: Context) -> None:
        """Draw the VRM to Unity conversion panel interface"""
        layout: UILayout = self.layout
        
        # VRM Conversion Tools
        vrm_box: UILayout = layout.box()
        col: UILayout = vrm_box.column(align=True)
        col.label(text="VRM Converter", icon='ARMATURE_DATA')
        col.separator(factor=0.5)
        
        # Check if we have an active armature
        armature = get_active_armature(context)
        
        if not armature:
            col.label(text="No armature selected", icon='ERROR')
            col.label(text="Select an armature to convert")
            return
        
        # Check if the armature appears to be VRM
        is_vrm = detect_vrm_armature(armature)
        
        if is_vrm:
            col.label(text=f"Armature: {armature.name}", icon='CHECKMARK')
            col.label(text="VRM armature detected", icon='INFO')
            col.separator(factor=0.3)
            
            toolkit = context.scene.avatar_toolkit
            col.prop(toolkit, 'vrm_remove_colliders', text="Remove Colliders")
            col.separator(factor=0.2)
            
            col.operator(
                AvatarToolkit_OT_ConvertVRMToUnity.bl_idname,
                text="Convert to Unity Format",
                icon='EXPORT'
            )
            
            info_box = vrm_box.box()
            info_col = info_box.column(align=True)
            info_col.label(text="Conversion Info:", icon='INFO')
            info_col.label(text="• Renames VRM bones to Unity format")
            info_col.label(text="• Removes collider bones (optional)")
            info_col.label(text="• Maintains bone hierarchy")
            info_col.label(text="• Validates conversion results")
            info_col.label(text="• Preserves all animations")
            
        else:
            col.label(text=f"Armature: {armature.name}", icon='ERROR')
            col.label(text="No VRM bones detected", icon='CANCEL')
            col.separator(factor=0.3)
            
            row = col.row()
            row.enabled = False
            row.operator(
                AvatarToolkit_OT_ConvertVRMToUnity.bl_idname,
                text="Convert to Unity Format",
                icon='CANCEL'
            )
            
            help_box = vrm_box.box()
            help_col = help_box.column(align=True)
            help_col.label(text="VRM Detection Failed:", icon='QUESTION')
            help_col.label(text="• Selected armature is not VRM format")
            help_col.label(text="• VRM bones start with 'J_Bip_C_'")
            help_col.label(text="• Need at least 5 VRM bones detected")
            help_col.label(text="• Check armature bone names")