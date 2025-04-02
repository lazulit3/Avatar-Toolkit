import bpy
from bpy.app.handlers import persistent

modules = None
ordered_classes = None

def show_version_error_popup():
    def draw(self, context):
        self.layout.label(text="Sorry, this version of Avatar Toolkit does not work on this version of Blender.")
        self.layout.label(text="Please check the GitHub repository for the correct version for your Blender.")
        self.layout.operator("wm.url_open", text="Open GitHub Repository").url = "https://github.com/teamneoneko/Avatar-Toolkit"
   
    bpy.context.window_manager.popup_menu(draw, title="Avatar Toolkit Version Error", icon='ERROR')

def register():
    import bpy
    version = bpy.app.version
    if version[0] > 4 or (version[0] == 4 and version[1] >= 5): 
        show_version_error_popup()
        return
        
    print("Starting registration")
    
    # Import modules using relative imports
    from . import core
    from .core import auto_load
    from .core.logging_setup import configure_logging
    
    # Initialize logging
    configure_logging(False)
    
    auto_load.init()
    auto_load.register()
    
    # Verify property registration
    if not hasattr(bpy.types.Scene, "avatar_toolkit"):
        from .core.properties import register as register_properties
        register_properties()
    
    print("Registration complete")

def unregister():
    from .core import auto_load
    auto_load.unregister()
