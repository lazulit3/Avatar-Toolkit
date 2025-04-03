# -*- coding: utf-8 -*-
# Copyright 2013 MMD Tools authors
# This file was originally part of the MMD Tools project, However Neoneko has added it to Avatar Toolkit.
# All credit goes to the original authors.
# Please note that some code was modified to fit the needs of Avatar Toolkit and some code may of been removed.
# MMD Tools is licensed under the terms of the GPL-3.0 license which Avatar Toolkit is also licensed under.
# You can find MMD Tools at: https://github.com/MMD-Blender/blender_mmd_tools/

import contextlib
from typing import Generator, List, Optional, TypeVar, Dict, Any, Set, Tuple, Type

import bpy
from bpy.types import Object, Material, Context
from mathutils import Vector, Matrix

from ...logging_setup import logger
from ...addon_preferences import get_preference, save_preference


class __EditMode:
    """Context manager for edit mode operations"""
    def __init__(self, obj: Object):
        if not isinstance(obj, bpy.types.Object):
            raise ValueError("Expected a Blender Object")
        self.__prevMode = obj.mode
        self.__obj = obj
        self.__obj_select = obj.select_get()
        with select_object(obj):
            if obj.mode != "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")

    def __enter__(self):
        return self.__obj.data

    def __exit__(self, type, value, traceback):
        if self.__prevMode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")  # update edited data
        bpy.ops.object.mode_set(mode=self.__prevMode)
        self.__obj.select_set(self.__obj_select)


class __SelectObjects:
    """Context manager for object selection operations"""
    def __init__(self, active_object: Object, selected_objects: Optional[List[Object]] = None):
        if not isinstance(active_object, bpy.types.Object):
            raise ValueError("Expected a Blender Object")
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
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

    def __exit__(self, type, value, traceback):
        for i, j in zip(self.__selected_objects, self.__hides):
            i.hide_set(j)


def setParent(obj: Object, parent: Object) -> None:
    """Set parent relationship between objects"""
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.parent_set(type="OBJECT", xmirror=False, keep_transform=False)


def setParentToBone(obj: Object, parent: Object, bone_name: str) -> None:
    """Set parent relationship to a specific bone"""
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.mode_set(mode="POSE")
        parent.data.bones.active = parent.data.bones[bone_name]
        bpy.ops.object.parent_set(type="BONE", xmirror=False, keep_transform=False)
        bpy.ops.object.mode_set(mode="OBJECT")


def edit_object(obj: Object):
    """Set the object interaction mode to 'EDIT'

    It is recommended to use 'edit_object' with 'with' statement like the following code.

       with edit_object:
           some functions...
    """
    return __EditMode(obj)


def select_object(obj: Object, objects: Optional[List[Object]] = None):
    """Select objects.

    It is recommended to use 'select_object' with 'with' statement like the following code.
    This function can select "hidden" objects safely.

       with select_object(obj):
           some functions...
    """
    return __SelectObjects(obj, objects)


def duplicateObject(obj: Object, total_len: int) -> List[Object]:
    """Duplicate an object multiple times"""
    return FnContext.duplicate_object(FnContext.ensure_context(), obj, total_len)


def createObject(name: str = "Object", object_data: Optional[Any] = None, target_scene: Optional[Any] = None) -> Object:
    """Create a new object and link it to the scene"""
    context = FnContext.ensure_context(target_scene)
    return FnContext.set_active_object(context, FnContext.new_and_link_object(context, name, object_data))


def makeSphere(segment: int = 8, ring_count: int = 5, radius: float = 1.0, target_object: Optional[Object] = None) -> Object:
    """Create a sphere mesh object"""
    import bmesh

    if target_object is None:
        target_object = createObject(name="Sphere")

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
    """Create a box mesh object"""
    import bmesh
    from mathutils import Matrix

    if target_object is None:
        target_object = createObject(name="Box")

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
    """Create a capsule mesh object"""
    import math
    import bmesh

    if target_object is None:
        target_object = createObject(name="Capsule")
    height = max(height, 1e-3)

    mesh = target_object.data
    bm = bmesh.new()
    verts = bm.verts
    top = (0, 0, height / 2 + radius)
    verts.new(top)

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
    """Helper class for transform constraints"""
    __MIN_MAX_MAP = {"ROTATION": "_rot", "SCALE": "_scale"}

    @staticmethod
    def create(constraints, name: str, map_type: str):
        """Create a transform constraint"""
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
        """Get min/max attribute names for a constraint type"""
        key = (map_type, name_id)
        ret = cls.__MIN_MAX_MAP.get(key, None)
        if ret is None:
            defaults = (i + j + k for i in ("from_", "to_") for j in ("min_", "max_") for k in "xyz")
            extension = cls.__MIN_MAX_MAP.get(map_type, "")
            ret = cls.__MIN_MAX_MAP[key] = tuple(n + extension for n in defaults if name_id in n)
        return ret

    @classmethod
    def update_min_max(cls, constraint, value: float, influence: Optional[float] = 1):
        """Update min/max values for a constraint"""
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
    """Function collection for object operations"""
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def mesh_remove_shape_key(mesh_object: Object, shape_key: bpy.types.ShapeKey) -> None:
        """Remove a shape key from a mesh object, cleaning up drivers"""
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        key: bpy.types.Key = shape_key.id_data
        assert key == mesh_object.data.shape_keys

        if mesh_object.animation_data is not None:
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


T = TypeVar("T")


class FnContext:
    """Function collection for context operations"""
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def ensure_context(context: Optional[Context] = None) -> Context:
        """Get a valid context, using bpy.context if none provided"""
        return context or bpy.context

    @staticmethod
    def get_active_object(context: Context) -> Optional[Object]:
        """Get the active object from context safely"""
        if context is None or not hasattr(context, 'active_object'):
            return None
        return context.active_object

    @staticmethod
    def set_active_object(context: Context, obj: Object) -> Object:
        """Set the active object in context"""
        context.view_layer.objects.active = obj
        return obj

    @staticmethod
    def set_active_and_select_single_object(context: Context, obj: Object) -> Object:
        """Set an object as active and the only selected object"""
        return FnContext.set_active_object(context, FnContext.select_single_object(context, obj))

    @staticmethod
    def get_scene_objects(context: Context) -> List[Object]:
        """Get all objects in the scene safely"""
        if context is None or not hasattr(context, 'scene') or not hasattr(context.scene, 'objects'):
            return []
        return context.scene.objects

    @staticmethod
    def ensure_selectable(context: Context, obj: Object) -> Object:
        """Make sure an object is selectable by unhiding it and its collections"""
        obj.hide_viewport = False
        obj.hide_select = False
        obj.hide_set(False)

        if obj not in context.selectable_objects:
            def __layer_check(layer_collection: bpy.types.LayerCollection) -> bool:
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
        """Select an object in the context"""
        FnContext.ensure_selectable(context, obj).select_set(True)
        return obj

    @staticmethod
    def select_objects(context: Context, *objects: Object) -> List[Object]:
        """Select multiple objects in the context"""
        return [FnContext.select_object(context, obj) for obj in objects]

    @staticmethod
    def select_single_object(context: Context, obj: Object) -> Object:
        """Select only the specified object, deselecting all others"""
        for i in context.selected_objects:
            if i != obj:
                i.select_set(False)
        return FnContext.select_object(context, obj)

    @staticmethod
    def link_object(context: Context, obj: Object) -> Object:
        """Link an object to the active collection"""
        context.collection.objects.link(obj)
        return obj

    @staticmethod
    def new_and_link_object(context: Context, name: str, object_data: Optional[Any]) -> Object:
        """Create a new object and link it to the active collection"""
        return FnContext.link_object(context, bpy.data.objects.new(name=name, object_data=object_data))

    @staticmethod
    def duplicate_object(context: Context, object_to_duplicate: Object, target_count: int) -> List[Object]:
        """
        Duplicate an object to reach the target count.
        
        Args:
            context: The context in which the duplication is performed
            object_to_duplicate: The object to be duplicated
            target_count: The desired count of duplicated objects
            
        Returns:
            A list of duplicated objects
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
        return result_objects

    @staticmethod
    def find_user_layer_collection_by_object(context: Context, target_object: Object) -> Optional[bpy.types.LayerCollection]:
        """
        Find the layer collection containing the target object.
        
        Args:
            context: The Blender context
            target_object: The target object to find the layer collection for
            
        Returns:
            The layer collection containing the target object, or None if not found
        """
        scene_layer_collection: bpy.types.LayerCollection = context.view_layer.layer_collection

        def find_layer_collection_by_name(layer_collection: bpy.types.LayerCollection, name: str) -> Optional[bpy.types.LayerCollection]:
            if layer_collection.name == name:
                return layer_collection

            for child_layer_collection in layer_collection.children:
                found = find_layer_collection_by_name(child_layer_collection, name)
                if found is not None:
                    return found

            return None

        for user_collection in target_object.users_collection:
            found = find_layer_collection_by_name(scene_layer_collection, user_collection.name)
            if found is not None:
                return found

        return None

    @staticmethod
    @contextlib.contextmanager
    def temp_override_active_layer_collection(context: Context, target_object: Object) -> Generator[Context, None, None]:
        """
        Temporarily override the active layer collection to the one containing the target object.
        
        Args:
            context: The context to modify
            target_object: The object whose collection should become active
            
        Yields:
            The modified context
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
    @contextlib.contextmanager
    def temp_override_objects(
        context: Context,
        active_object: Optional[Object] = None,
        selected_objects: Optional[List[Object]] = None,
        **keywords
    ) -> Generator[Context, None, None]:
        """Create a temporary context override for object operations using Blender 4.4+ temp_override."""
        override_dict = {}
            
        if active_object is not None:
            override_dict["active_object"] = active_object
            override_dict["object"] = active_object

        if selected_objects is not None:
            override_dict["selected_objects"] = selected_objects
            override_dict["selected_editable_objects"] = selected_objects
            
        override_dict.update(keywords)
        
        with context.temp_override(**override_dict) as override_context:
            yield override_context

    @staticmethod
    def get_preference(key: str, default: T = None) -> T:
        """
        Get a preference value using Avatar Toolkit's preference system."""
        return get_preference(key, default)

    @staticmethod
    def save_preference(key: str, value: Any) -> None:
        """Save a preference value using Avatar Toolkit's preference system."""
        save_preference(key, value)