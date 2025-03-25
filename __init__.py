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
    # Check Blender version first
    version = bpy.app.version
    if version[0] > 4 or (version[0] == 4 and version[1] > 3):
        show_version_error_popup()
        return
    
    # Add wheel installation check
    try:
        import lz4
    except ImportError:
        import sys
        import os
        import site
        import pip
        wheels_dir = os.path.join(os.path.dirname(__file__), "wheels")
        for wheel in os.listdir(wheels_dir):
            if wheel.endswith(".whl"):
                pip.main(['install', os.path.join(wheels_dir, wheel)])
                site.addsitedir(site.getsitepackages()[0])
    
    from .core import auto_load
    print("Starting registration")
    auto_load.init()
    auto_load.register()
    print("Registration complete")

def unregister():
    from .core import auto_load
    auto_load.unregister()
