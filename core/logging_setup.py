import logging
import traceback
from typing import Optional, Any
from bpy.types import Context

logger = logging.getLogger('avatar_toolkit')

def configure_logging(enabled: bool = False) -> None:
    """Configure logging for Avatar Toolkit"""
    logger.setLevel(logging.DEBUG if enabled else logging.WARNING)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    if enabled:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s' if enabled else '%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Override error logging to include traceback
        def error_with_traceback(msg, *args, **kwargs):
            if kwargs.get('exc_info', False):
                msg = f"{msg}\n{traceback.format_exc()}"
            logger.error(msg, *args, **kwargs)
            
        logger.error = error_with_traceback

def update_logging_state(self: Any, context: Context) -> None:
    """Update logging state based on user preference"""
    from .addon_preferences import save_preference
    enabled = self.enable_logging
    save_preference("enable_logging", enabled)
    configure_logging(enabled)
