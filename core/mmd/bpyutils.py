# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import contextlib
from typing import Generator, List, Optional, TypeVar, Any, Set, Tuple, Dict, Union

import bpy
from bpy.types import Object, Context, ID, Key, ShapeKey, FCurve, LayerCollection, Collection
from bpy.types import AddonPreferences, Addon, WindowManager, Area, Region, Window

from ..logging_setup import logger


class Props:  # For API changes of only name changed properties
    show_in_front = "show_in_front"
    display_type = "display_type"
    display_size = "display_size"
    empty_display_type = "empty_display_type"
    empty_display_size = "empty_display_size"


class __EditMode:
    def __init__(self, obj: Object):
        if not isinstance(obj, bpy.types.Object):
            raise ValueError
        self.__prevMode = obj.mode
        self.__obj = obj
        self.__obj_select = obj.select_get()
        with select_object(obj):
            if obj.mode != "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")

    def __enter__(self) -> Any:
        return self.__obj.data

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        if self.__prevMode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")  # update edited data
        bpy.ops.object.mode_set(mode=self.__prevMode)
        self.__obj.select_set(self.__obj_select)


class __SelectObjects:
    def __init__(self, active_object: Object, selected_objects: Optional[List[Object]] = None):
        if not isinstance(active_object, bpy.types.Object):
            raise ValueError
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            logger.debug("Failed to set object mode")
            pass

        context = FnContext.ensure_context()

        for i in context.selected_objects:
            i.select_set(False)

        self.__active_object = active_object
        self.__selected_objects = tuple(set(selected_objects) | set([active_object])) if selected_objects else (active_object,)

        self.__hides: List[bool] = []
        for i in self.__selected_objects:
            self.__hides.append(i.hide_get())
            FnContext.select_object(context, i)
        FnContext.set_active_object(context, active_object)

    def __enter__(self) -> Object:
        return self.__active_object

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        for i, j in zip(self.__selected_objects, self.__hides):
            i.hide_set(j)


def setParent(obj: Object, parent: Object) -> None:
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.parent_set(type="OBJECT", xmirror=False, keep_transform=False)


def setParentToBone(obj: Object, parent: Object, bone_name: str) -> None:
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.mode_set(mode="POSE")
        parent.data.bones.active = parent.data.bones[bone_name]
        bpy.ops.object.parent_set(type="BONE", xmirror=False, keep_transform=False)
        bpy.ops.object.mode_set(mode="OBJECT")


def edit_object(obj: Object) -> __EditMode:
    """Set the object interaction mode to 'EDIT'

    It is recommended to use 'edit_object' with 'with' statement like the following code.

       with edit_object:
           some functions...
    """
    return __EditMode(obj)


def select_object(obj: Object, objects: Optional[List[Object]] = None) -> __SelectObjects:
    """Select objects.

    It is recommended to use 'select_object' with 'with' statement like the following code.
    This function can select "hidden" objects safely.

       with select_object(obj):
           some functions...
    """
    # TODO: Reimplement with bpy.context.temp_override (If it ain't broke, don't fix it.)
    return __SelectObjects(obj, objects)


def duplicateObject(obj: Object, total_len: int) -> List[Object]:
    return FnContext.duplicate_object(FnContext.ensure_context(), obj, total_len)


def createObject(name: str = "Object", object_data: Optional[ID] = None, target_scene: Optional[bpy.types.Scene] = None) -> Object:
    context = FnContext.ensure_context(target_scene)
    return FnContext.set_active_object(context, FnContext.new_and_link_object(context, name, object_data))


def makeSphere(segment: int = 8, ring_count: int = 5, radius: float = 1.0, target_object: Optional[Object] = None) -> Object:
    import bmesh

    if target_object is None:
        target_object = createObject(name="Sphere")
        logger.debug(f"Created new sphere object: {target_object.name}")
    else:
        logger.debug(f"Using existing object for sphere: {target_object.name}")

    mesh = target_object.data
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(
        bm,
        u_segments=segment,
        v_segments=ring_count,
        radius=radius,
    )
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    return target_object


def makeBox(size: Tuple[float, float, float] = (1, 1, 1), target_object: Optional[Object] = None) -> Object:
    import bmesh
    from mathutils import Matrix

    if target_object is None:
        target_object = createObject(name="Box")
        logger.debug(f"Created new box object: {target_object.name}")
    else:
        logger.debug(f"Using existing object for box: {target_object.name}")

    mesh = target_object.data
    bm = bmesh.new()
    bmesh.ops.create_cube(
        bm,
        size=2,
        matrix=Matrix([[size[0], 0, 0, 0], [0, size[1], 0, 0], [0, 0, size[2], 0], [0, 0, 0, 1]]),
    )
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    return target_object


def makeCapsule(segment: int = 8, ring_count: int = 2, radius: float = 1.0, height: float = 1.0, target_object: Optional[Object] = None) -> Object:
    import math
    import bmesh

    if target_object is None:
        target_object = createObject(name="Capsule")
        logger.debug(f"Created new capsule object: {target_object.name}")
    else:
        logger.debug(f"Using existing object for capsule: {target_object.name}")
        
    height = max(height, 1e-3)

    mesh = target_object.data
    bm = bmesh.new()
    verts = bm.verts
    top = (0, 0, height / 2 + radius)
    verts.new(top)

    # f = lambda i: radius*i/ring_count
    f = lambda i: radius * math.sin(0.5 * math.pi * i / ring_count)
    for i in range(ring_count, 0, -1):
        z = f(i - 1)
        t = math.sqrt(radius**2 - z**2)
        for j in range(segment):
            theta = 2 * math.pi / segment * j
            x = t * math.sin(-theta)
            y = t * math.cos(-theta)
            verts.new((x, y, z + height / 2))

    for i in range(ring_count):
        z = -f(i)
        t = math.sqrt(radius**2 - z**2)
        for j in range(segment):
            theta = 2 * math.pi / segment * j
            x = t * math.sin(-theta)
            y = t * math.cos(-theta)
            verts.new((x, y, z - height / 2))

    bottom = (0, 0, -(height / 2 + radius))
    verts.new(bottom)
    if hasattr(verts, "ensure_lookup_table"):
        verts.ensure_lookup_table()

    faces = bm.faces
    for i in range(1, segment):
        faces.new([verts[x] for x in (0, i, i + 1)])
    faces.new([verts[x] for x in (0, segment, 1)])
    offset = segment + 1
    for i in range(ring_count * 2 - 1):
        for j in range(segment - 1):
            t = offset + j
            faces.new([verts[x] for x in (t - segment, t, t + 1, t - segment + 1)])
        faces.new([verts[x] for x in (offset - 1, offset + segment - 1, offset, offset - segment)])
        offset += segment
    for i in range(segment - 1):
        t = offset + i
        faces.new([verts[x] for x in (t - segment, offset, t - segment + 1)])
    faces.new([verts[x] for x in (offset - 1, offset, offset - segment)])

    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return target_object


class TransformConstraintOp:
    __MIN_MAX_MAP: Dict[Union[str, Tuple[str, str]], Union[str, Tuple[str, ...]]] = {"ROTATION": "_rot", "SCALE": "_scale"}

    @staticmethod
    def create(constraints: bpy.types.ObjectConstraints, name: str, map_type: str) -> bpy.types.TransformConstraint:
        c = constraints.get(name, None)
        if c and c.type != "TRANSFORM":
            constraints.remove(c)
            c = None
        if c is None:
            c = constraints.new("TRANSFORM")
            c.name = name
        c.use_motion_extrapolate = True
        c.target_space = c.owner_space = "LOCAL"
        c.map_from = c.map_to = map_type
        c.map_to_x_from = "X"
        c.map_to_y_from = "Y"
        c.map_to_z_from = "Z"
        c.influence = 1
        return c

    @classmethod
    def min_max_attributes(cls, map_type: str, name_id: str = "") -> Tuple[str, ...]:
        key = (map_type, name_id)
        ret = cls.__MIN_MAX_MAP.get(key, None)
        if ret is None:
            defaults = (i + j + k for i in ("from_", "to_") for j in ("min_", "max_") for k in "xyz")
            extension = cls.__MIN_MAX_MAP.get(map_type, "")
            ret = cls.__MIN_MAX_MAP[key] = tuple(n + extension for n in defaults if name_id in n)
        return ret

    @classmethod
    def update_min_max(cls, constraint: bpy.types.TransformConstraint, value: float, influence: Optional[float] = 1) -> None:
        c = constraint
        if not c or c.type != "TRANSFORM":
            return

        for attr in cls.min_max_attributes(c.map_from, "from_min"):
            setattr(c, attr, -value)
        for attr in cls.min_max_attributes(c.map_from, "from_max"):
            setattr(c, attr, value)

        if influence is None:
            return

        for attr in cls.min_max_attributes(c.map_to, "to_min"):
            setattr(c, attr, -value * influence)
        for attr in cls.min_max_attributes(c.map_to, "to_max"):
            setattr(c, attr, value * influence)


class FnObject:
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def mesh_remove_shape_key(mesh_object: Object, shape_key: ShapeKey) -> None:
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        key: Key = shape_key.id_data
        assert key == mesh_object.data.shape_keys

        if mesh_object.animation_data is not None:
            fc_curve: FCurve
            for fc_curve in mesh_object.animation_data.drivers:
                if not fc_curve.data_path.startswith(shape_key.path_from_id()):
                    continue
                mesh_object.driver_remove(fc_curve.data_path)

        key_blocks = key.key_blocks

        last_index = mesh_object.active_shape_key_index or 0
        if last_index >= key_blocks.find(shape_key.name):
            last_index = max(0, last_index - 1)

        mesh_object.shape_key_remove(shape_key)
        mesh_object.active_shape_key_index = min(last_index, len(key_blocks) - 1)


ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE = TypeVar("ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE")


class FnContext:
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def ensure_context(context: Optional[Context] = None) -> Context:
        return context or bpy.context

    @staticmethod
    def get_active_object(context: Context) -> Optional[Object]:
        return context.active_object

    @staticmethod
    def set_active_object(context: Context, obj: Object) -> Object:
        context.view_layer.objects.active = obj
        return obj

    @staticmethod
    def set_active_and_select_single_object(context: Context, obj: Object) -> Object:
        return FnContext.set_active_object(context, FnContext.select_single_object(context, obj))

    @staticmethod
    def get_scene_objects(context: Context) -> bpy.types.SceneObjects:
        return context.scene.objects

    @staticmethod
    def ensure_selectable(context: Context, obj: Object) -> Object:
        obj.hide_viewport = False
        obj.hide_select = False
        obj.hide_set(False)

        if obj not in context.selectable_objects:

            def __layer_check(layer_collection: LayerCollection) -> bool:
                for lc in layer_collection.children:
                    if __layer_check(lc):
                        lc.hide_viewport = False
                        lc.collection.hide_viewport = False
                        lc.collection.hide_select = False
                        return True
                if obj in layer_collection.collection.objects.values():
                    if layer_collection.exclude:
                        layer_collection.exclude = False
                    return True
                return False

            selected_objects = set(context.selected_objects)
            __layer_check(context.view_layer.layer_collection)
            if len(context.selected_objects) != len(selected_objects):
                for i in context.selected_objects:
                    if i not in selected_objects:
                        i.select_set(False)
        return obj

    @staticmethod
    def select_object(context: Context, obj: Object) -> Object:
        FnContext.ensure_selectable(context, obj).select_set(True)
        return obj

    @staticmethod
    def select_objects(context: Context, *objects: Object) -> List[Object]:
        return [FnContext.select_object(context, obj) for obj in objects]

    @staticmethod
    def select_single_object(context: Context, obj: Object) -> Object:
        for i in context.selected_objects:
            if i != obj:
                i.select_set(False)
        return FnContext.select_object(context, obj)

    @staticmethod
    def link_object(context: Context, obj: Object) -> Object:
        context.collection.objects.link(obj)
        return obj

    @staticmethod
    def new_and_link_object(context: Context, name: str, object_data: Optional[ID]) -> Object:
        return FnContext.link_object(context, bpy.data.objects.new(name=name, object_data=object_data))

    @staticmethod
    def duplicate_object(context: Context, object_to_duplicate: Object, target_count: int) -> List[Object]:
        """
        Duplicate object.

        This function duplicates the given object and returns a list of duplicated objects.

        Args:
            context (Context): The context in which the duplication is performed.
            object_to_duplicate (Object): The object to be duplicated.
            target_count (int): The desired count of duplicated objects.

        Returns:
            List[Object]: A list of duplicated objects.

        Raises:
            AssertionError: If the number of selected objects in the context is not equal to 1 or if the selected object is not the same as the object to be duplicated.
        """
        for o in context.selected_objects:
            o.select_set(False)
        object_to_duplicate.select_set(True)
        assert len(context.selected_objects) == 1
        assert context.selected_objects[0] == object_to_duplicate
        last_selected_objects = result_objects = [object_to_duplicate]
        while len(result_objects) < target_count:
            bpy.ops.object.duplicate()
            result_objects.extend(context.selected_objects)
            remain = target_count - len(result_objects) - len(context.selected_objects)
            if remain < 0:
                last_selected_objects = context.selected_objects
                for i in range(-remain):
                    last_selected_objects[i].select_set(False)
            else:
                for i in range(min(remain, len(last_selected_objects))):
                    last_selected_objects[i].select_set(True)
                last_selected_objects = context.selected_objects
        assert len(result_objects) == target_count
        logger.debug(f"Duplicated object {object_to_duplicate.name} to create {target_count} objects")
        return result_objects

    @staticmethod
    def find_user_layer_collection_by_object(context: Context, target_object: Object) -> Optional[LayerCollection]:
        """
        Finds the layer collection that contains the given target_object in the user's collections.

        Args:
            context (Context): The Blender context.
            target_object (Object): The target object to find the layer collection for.

        Returns:
            Optional[LayerCollection]: The layer collection that contains the target_object, or None if not found.
        """
        scene_layer_collection: LayerCollection = context.view_layer.layer_collection

        def find_layer_collection_by_name(layer_collection: LayerCollection, name: str) -> Optional[LayerCollection]:
            if layer_collection.name == name:
                return layer_collection

            child_layer_collection: LayerCollection
            for child_layer_collection in layer_collection.children:
                found = find_layer_collection_by_name(child_layer_collection, name)
                if found is not None:
                    return found

            return None

        user_collection: Collection
        for user_collection in target_object.users_collection:
            found = find_layer_collection_by_name(scene_layer_collection, user_collection.name)
            if found is not None:
                return found

        return None

    @staticmethod
    @contextlib.contextmanager
    def temp_override_active_layer_collection(context: Context, target_object: Object) -> Generator[Context, None, None]:
        """
        Context manager to temporarily override the active_layer_collection that contains the target object.

        This context manager allows you to temporarily change the active_layer_collection in the given context to the one that contains the target object.
        It ensures that the original active_layer_collection is restored after the context is exited.

        Args:
            context (Context): The context in which the active_layer_collection will be overridden.
            target_object (Object): The target object whose layer collection will be set as the active_layer_collection.

        Yields:
            Context: The modified context with the active_layer_collection overridden.

        Example:
            with FnContext.temp_override_active_layer_collection(context, target_object):
                # Perform operations with the modified context
                bpy.ops.object.select_all(action='DESELECT')
                target_object.select_set(True)
                bpy.ops.object.delete()

        """
        original_layer_collection = context.view_layer.active_layer_collection
        target_layer_collection = FnContext.find_user_layer_collection_by_object(context, target_object)
        if target_layer_collection is not None:
            context.view_layer.active_layer_collection = target_layer_collection
        try:
            yield context
        finally:
            if context.view_layer.active_layer_collection.name != original_layer_collection.name:
                context.view_layer.active_layer_collection = original_layer_collection

    @staticmethod
    def __get_addon_preferences(context: Context) -> Optional[AddonPreferences]:
        addon: Addon = context.preferences.addons.get(__package__, None)
        return addon.preferences if addon else None

    @staticmethod
    def get_addon_preferences_attribute(context: Context, attribute_name: str, default_value: ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE = None) -> ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE:
        return getattr(FnContext.__get_addon_preferences(context), attribute_name, default_value)

    @staticmethod
    def temp_override_objects(
        context: Context,
        window: Optional[Window] = None,
        area: Optional[Area] = None,
        region: Optional[Region] = None,
        active_object: Optional[Object] = None,
        selected_objects: Optional[List[Object]] = None,
        **keywords: Any,
    ) -> Generator[Context, None, None]:
        if active_object is not None:
            keywords["active_object"] = active_object
            keywords["object"] = active_object

        if selected_objects is not None:
            keywords["selected_objects"] = selected_objects
            keywords["selected_editable_objects"] = selected_objects

        return context.temp_override(window=window, area=area, region=region, **keywords)
