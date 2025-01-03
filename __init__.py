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
    auto_load.init()
    auto_load.register()
    print("Registration complete")

def unregister():
    from .core import auto_load
    auto_load.unregister()
