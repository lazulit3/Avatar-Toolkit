import bpy
from typing import Set
from bpy.types import Panel, Context, UILayout, Operator, UIList
from .main_panel import AvatarToolKit_PT_AvatarToolkitPanel, CATEGORY_NAME
from ..core.translations import t

from ..core.resonite_utils import AvatarToolkit_OT_ConvertResonite
from ..functions.tools.mesh_separation import AvatarToolKit_OT_SeparateByLooseParts, AvatarToolKit_OT_SeparateByMaterials
from ..functions.tools.additional_tools import AvatarToolkit_OT_ApplyTransforms, AvatarToolkit_OT_CleanShapekeys
from ..functions.tools.bone_tools import AvatarToolKit_OT_CreateDigitigradeLegs, AvatarToolKit_OT_DeleteBoneConstraints, AvatarToolKit_OT_RemoveSelectedBones, AvatarToolKit_OT_RemoveZeroWeightBones, AvatarToolKit_OT_RemoveZeroWeightVertexGroups
from ..functions.tools.standardize_armature import AvatarToolkit_OT_StandardizeArmature
from ..functions.tools.merge_tools import AvatarToolkit_OT_MergeToActive, AvatarToolkit_OT_MergeToParent, AvatarToolkit_OT_ConnectBones
from ..functions.tools.rigify_converter import AvatarToolkit_OT_ConvertRigifyToUnity


class AVATAR_TOOLKIT_UL_ZeroWeightBones(UIList):
    """UI List for displaying zero weight bones with selection options"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            row.label(text=item.name)
            if item.has_children:
                row.label(text="", icon='OUTLINER_OB_ARMATURE')
            if item.is_deform:
                row.label(text="", icon='MOD_ARMATURE')

class AvatarToolKit_PT_ToolsPanel(Panel):
    """Panel containing various tools for avatar customization and optimization"""
    bl_label: str = t("Tools.label")
    bl_idname: str = "OBJECT_PT_avatar_toolkit_tools"
    bl_space_type: str = 'VIEW_3D'
    bl_region_type: str = 'UI'
    bl_category: str = CATEGORY_NAME
    bl_parent_id: str = AvatarToolKit_PT_AvatarToolkitPanel.bl_idname
    bl_order: int = 2
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: Context) -> None:
        """Draw the tools panel interface"""
        layout: UILayout = self.layout
        toolkit = context.scene.avatar_toolkit
        
        # General Tools
        tools_box: UILayout = layout.box()
        col: UILayout = tools_box.column(align=True)
        col.label(text=t("Tools.general_title"), icon='TOOL_SETTINGS')
        col.separator(factor=0.5)
        col.operator(AvatarToolkit_OT_ConvertResonite.bl_idname, text=t("Tools.convert_resonite"), icon='EXPORT')
        
        # Separation Tools
        sep_box: UILayout = layout.box()
        col = sep_box.column(align=True)
        col.label(text=t("Tools.separate_title"), icon='MOD_EXPLODE')
        col.separator(factor=0.5)
        row: UILayout = col.row(align=True)
        row.operator(AvatarToolKit_OT_SeparateByMaterials.bl_idname, text=t("Tools.separate_materials"), icon='MATERIAL')
        row.operator(AvatarToolKit_OT_SeparateByLooseParts.bl_idname, text=t("Tools.separate_loose"), icon='MESH_DATA')
        
        # Bone Tools
        bone_box: UILayout = layout.box()
        col = bone_box.column(align=True)
        col.label(text=t("Tools.bone_title"), icon='BONE_DATA')
        col.separator(factor=0.5)
        col.operator(AvatarToolKit_OT_CreateDigitigradeLegs.bl_idname, text=t("Tools.create_digitigrade"), icon='BONE_DATA')
        
        # Standardization Tools
        standardize_box: UILayout = bone_box.box()
        col = standardize_box.column(align=True)
        col.label(text=t("Tools.standardize_title"), icon='OUTLINER_OB_ARMATURE')
        col.separator(factor=0.5)
        col.operator(AvatarToolkit_OT_StandardizeArmature.bl_idname, icon='CHECKMARK')

        # Weight Tools
        weight_box: UILayout = bone_box.box()
        col = weight_box.column(align=True)
        col.prop(toolkit, "merge_twist_bones", text=t("Tools.merge_twist_bones"))
        col.prop(toolkit, "preserve_parent_bones")
        col.prop(toolkit, "target_bone_type")
        col.prop(toolkit, "list_only_mode")
        
        if toolkit.list_only_mode and len(toolkit.zero_weight_bones) > 0:
            box = weight_box.box()
            row = box.row()
            row.template_list("AVATAR_TOOLKIT_UL_ZeroWeightBones", "", 
                            toolkit, "zero_weight_bones",
                            toolkit, "zero_weight_bones_index")
            
            col = box.column(align=True)
            col.operator(AvatarToolKit_OT_RemoveSelectedBones.bl_idname, 
                        text=t("Tools.remove_selected_bones"))
        
        row = col.row(align=True)
        row.operator(AvatarToolKit_OT_RemoveZeroWeightBones.bl_idname, text=t("Tools.clean_weights"), icon='GROUP_BONE')
        row.operator(AvatarToolKit_OT_DeleteBoneConstraints.bl_idname, text=t("Tools.clean_constraints"), icon='CONSTRAINT_BONE')
        
        # Merge Tools
        merge_box: UILayout = layout.box()
        col = merge_box.column(align=True)
        col.label(text=t("Tools.merge_title"), icon='AUTOMERGE_ON')
        col.separator(factor=0.5)
        row = col.row(align=True)
        row.operator(AvatarToolkit_OT_MergeToActive.bl_idname, text=t("Tools.merge_to_active"), icon='BONE_DATA')
        row.operator(AvatarToolkit_OT_MergeToParent.bl_idname, text=t("Tools.merge_to_parent"), icon='BONE_DATA')
        col.operator(AvatarToolkit_OT_ConnectBones.bl_idname, text=t("Tools.connect_bones"), icon='BONE_DATA')
        
        # Additional Tools
        extra_box: UILayout = layout.box()
        col = extra_box.column(align=True)
        col.label(text=t("Tools.additional_title"), icon='TOOL_SETTINGS')
        col.separator(factor=0.5)
        col.operator(AvatarToolkit_OT_ApplyTransforms.bl_idname, text=t("Tools.apply_transforms"), icon='OBJECT_DATA')
        col.operator(AvatarToolkit_OT_CleanShapekeys.bl_idname, text=t("Tools.clean_shapekeys"), icon='SHAPEKEY_DATA')

        # Rigify Tools
        rigify_box: UILayout = layout.box()
        col = rigify_box.column(align=True)
        col.label(text=t("Tools.rigify_title"), icon='ARMATURE_DATA')
        col.separator(factor=0.5)
        col.operator(AvatarToolkit_OT_ConvertRigifyToUnity.bl_idname, icon='ARMATURE_DATA')
        col.prop(context.scene.avatar_toolkit, "merge_twist_bones")
