# Fix for Garbled Japanese/Non-ASCII Text in Dropdowns

## Problem
Japanese, Korean, Chinese, and other non-ASCII characters were displaying as garbled/corrupted text in dropdown menus for:
- Armature selection in Quick Access panel
- Mesh selection in Visemes panel

This is a known issue with Blender's EnumProperty system when using dynamic callbacks that return Unicode strings.

## Root Cause
Blender's EnumProperty RNA system can have encoding issues when:
1. The enum items function is called multiple times with changing data
2. Unicode strings in display names aren't properly cached
3. The internal C API receives the same Python string object in different states

## Solution
Implemented proper caching with invalidation for EnumProperty items:

### Changes Made

1. **core/common.py** - Enhanced `get_armature_list()` function
   - Added cache key based on (name, pointer) tuples
   - Cache is invalidated only when actual objects change
   - Prevents Blender from re-encoding strings on every access
   - Added `clear_enum_caches()` helper function

2. **core/properties.py** - Enhanced `get_mesh_objects()` function  
   - Added same caching mechanism as armature list
   - Cache key based on mesh objects (name, pointer)
   - Stable cache prevents encoding corruption

3. **core/common.py** - `get_mesh_from_identifier()` helper
   - Converts safe identifier back to mesh object
   - Handles both new format (`MESH_{pointer}`) and legacy format
   - Returns None if mesh not found

4. **ui/visemes_panel.py** - Updated mesh retrieval
   - Uses `get_mesh_from_identifier()` instead of direct lookup

5. **functions/visemes.py** - Updated all mesh access points
   - All operators now use the helper function consistently

## Technical Details

### ASCII-Safe Identifiers
- Dropdown identifier: `ARM_{memory_pointer}` or `MESH_{memory_pointer}` (ASCII-safe, unique)
- Dropdown display: Original object name (preserves Unicode characters)
- Backwards compatibility: Falls back to direct name lookup

### Caching Strategy
The cache uses function attributes to store:
- `_cache_key`: Tuple of (name, pointer) for all relevant objects
- `_cached_items`: The actual list of enum items

Cache is invalidated when:
- Objects are added/removed
- Objects are renamed
- Object pointers change (object recreated)

This ensures Blender's RNA system receives the exact same Python string objects on subsequent calls, preventing encoding corruption.

## Testing

To verify the fix works:
1. Create armature/mesh objects with Japanese/Korean/Chinese names (e.g., "アバター", "아바타", "化身")
2. Open Quick Access panel - armature dropdown should display correctly
3. Open Visemes panel - mesh dropdown should display correctly
4. Select items - operations should work with the selected objects
5. Rename objects - dropdowns should update and still display correctly

## Related Files
- `core/properties.py` - Property definitions and mesh enumeration
- `core/common.py` - Common utility functions and armature enumeration
- `ui/visemes_panel.py` - Visemes UI panel
- `ui/quick_access_panel.py` - Quick Access UI panel
- `functions/visemes.py` - Viseme operators

## Note on prop_search
The `prop_search` widget used for shape key/bone selection inherently handles non-ASCII characters correctly since it searches Blender's internal data structures directly, not custom enum properties.
