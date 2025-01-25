import bpy
from bpy.types import Panel, Context, UILayout
from ..core.translations import t

class UVTools_PT_Tools(Panel):
    """UV Tools panel containing UV manipulation operators"""
    bl_label = t("Tools.label")
    bl_idname = "OBJECT_PT_avatar_toolkit_uv_tools"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Avatar Toolkit"
    bl_parent_id = "OBJECT_PT_avatar_toolkit_uv"
    bl_order = 3

    def draw(self, context: Context) -> None:
        layout: UILayout = self.layout

        row: UILayout = layout.row(align=True)
        row.operator("avatar_toolkit.align_uv_edges_to_target", 
                    text=t("UVTools.align_edges"), 
                    icon='GP_MULTIFRAME_EDITING')
