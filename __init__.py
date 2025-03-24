modules = None
ordered_classes = None

def register():
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
    
    # Make sure to initialize logging first
    from .core.logging_setup import configure_logging
    configure_logging(False)
    
    # Then initialize the addon
    auto_load.init()
    
    # Register classes in proper order
    auto_load.register()
    
    # Verify property registration
    import bpy
    if not hasattr(bpy.types.Scene, "avatar_toolkit"):
        from .core.properties import register as register_properties
        register_properties()
    
    print("Registration complete")

def unregister():
    from .core import auto_load
    auto_load.unregister()