# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

import logging
import os
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Tuple, cast, Dict, List, Any, Union, Set

import bpy
from mathutils import Vector

from ..bpyutils import FnContext
from .exceptions import MaterialNotFoundError
from .shader import _NodeGroupUtils
from ....core.logging_setup import logger

if TYPE_CHECKING:
    from ..properties.material import MMDMaterial

# TODO: use enum instead of constants
SPHERE_MODE_OFF = 0
SPHERE_MODE_MULT = 1
SPHERE_MODE_ADD = 2
SPHERE_MODE_SUBTEX = 3


class _DummyTexture:
    def __init__(self, image: bpy.types.Image):
        self.type: str = "IMAGE"
        self.image: bpy.types.Image = image
        self.use_mipmap: bool = True


class _DummyTextureSlot:
    def __init__(self, image: bpy.types.Image):
        self.diffuse_color_factor: float = 1
        self.uv_layer: str = ""
        self.texture: _DummyTexture = _DummyTexture(image)


class FnMaterial:
    __NODES_ARE_READONLY: bool = False

    def __init__(self, material: bpy.types.Material):
        self.__material: bpy.types.Material = material
        self._nodes_are_readonly: bool = FnMaterial.__NODES_ARE_READONLY

    @staticmethod
    def set_nodes_are_readonly(nodes_are_readonly: bool) -> None:
        FnMaterial.__NODES_ARE_READONLY = nodes_are_readonly

    @classmethod
    def from_material_id(cls, material_id: str) -> Optional['FnMaterial']:
        for material in bpy.data.materials:
            if material.mmd_material.material_id == material_id:
                return cls(material)
        return None

    @staticmethod
    def clean_materials(obj: bpy.types.Object, can_remove: Callable[[bpy.types.Material], bool]) -> None:
        materials = obj.data.materials
        materials_pop = materials.pop
        removed_count = 0
        for i in sorted((x for x, m in enumerate(materials) if can_remove(m)), reverse=True):
            m = materials_pop(index=i)
            removed_count += 1
            if m.users < 1:
                bpy.data.materials.remove(m)
        
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} materials from {obj.name}")

    @staticmethod
    def swap_materials(mesh_object: bpy.types.Object, mat1_ref: Union[str, int], mat2_ref: Union[str, int], reverse: bool = False, swap_slots: bool = False) -> Tuple[bpy.types.Material, bpy.types.Material]:
        """
        This method will assign the polygons of mat1 to mat2.
        If reverse is True it will also swap the polygons assigned to mat2 to mat1.
        The reference to materials can be indexes or names
        Finally it will also swap the material slots if the option is given.

        Args:
            mesh_object (bpy.types.Object): The mesh object
            mat1_ref (str | int): The reference to the first material
            mat2_ref (str | int): The reference to the second material
            reverse (bool, optional): If true it will also swap the polygons assigned to mat2 to mat1. Defaults to False.
            swap_slots (bool, optional): If true it will also swap the material slots. Defaults to False.

        Retruns:
            Tuple[bpy.types.Material, bpy.types.Material]: The swapped materials

        Raises:
            MaterialNotFoundError: If one of the materials is not found
        """
        mesh = cast(bpy.types.Mesh, mesh_object.data)
        try:
            # Try to find the materials
            mat1 = mesh.materials[mat1_ref]
            mat2 = mesh.materials[mat2_ref]
            if None in (mat1, mat2):
                raise MaterialNotFoundError()
        except (KeyError, IndexError) as exc:
            # Wrap exceptions within our custom ones
            raise MaterialNotFoundError() from exc
        
        mat1_idx = mesh.materials.find(mat1.name)
        mat2_idx = mesh.materials.find(mat2.name)
        
        logger.debug(f"Swapping materials: {mat1.name} (idx:{mat1_idx}) <-> {mat2.name} (idx:{mat2_idx}) in {mesh_object.name}")
        
        # Swap polygons
        for poly in mesh.polygons:
            if poly.material_index == mat1_idx:
                poly.material_index = mat2_idx
            elif reverse and poly.material_index == mat2_idx:
                poly.material_index = mat1_idx
        # Swap slots if specified
        if swap_slots:
            mesh_object.material_slots[mat1_idx].material = mat2
            mesh_object.material_slots[mat2_idx].material = mat1
        return mat1, mat2

    @staticmethod
    def fixMaterialOrder(meshObj: bpy.types.Object, material_names: Iterable[str]) -> None:
        """
        This method will fix the material order. Which is lost after joining meshes.
        """
        materials = cast(bpy.types.Mesh, meshObj.data).materials
        logger.debug(f"Fixing material order for {meshObj.name}")
        
        for new_idx, mat in enumerate(material_names):
            # Get the material that is currently on this index
            other_mat = materials[new_idx]
            if other_mat.name == mat:
                continue  # This is already in place
            logger.debug(f"Moving material {mat} to index {new_idx}")
            FnMaterial.swap_materials(meshObj, mat, new_idx, reverse=True, swap_slots=True)

    @property
    def material_id(self) -> int:
        mmd_mat: 'MMDMaterial' = self.__material.mmd_material
        if mmd_mat.material_id < 0:
            max_id = -1
            for mat in bpy.data.materials:
                max_id = max(max_id, mat.mmd_material.material_id)
            mmd_mat.material_id = max_id + 1
            logger.debug(f"Assigned new material ID {mmd_mat.material_id} to {self.__material.name}")
        return mmd_mat.material_id

    @property
    def material(self) -> bpy.types.Material:
        return self.__material

    def __same_image_file(self, image: Optional[bpy.types.Image], filepath: str) -> bool:
        if image and image.source == "FILE":
            # pylint: disable=assignment-from-no-return
            img_filepath = bpy.path.abspath(image.filepath)  # image.filepath_from_user()
            if img_filepath == filepath:
                return True
            # pylint: disable=bare-except
            try:
                return os.path.samefile(img_filepath, filepath)
            except:
                pass
        return False

    def _load_image(self, filepath: str) -> bpy.types.Image:
        img = next((i for i in bpy.data.images if self.__same_image_file(i, filepath)), None)
        if img is None:
            # pylint: disable=bare-except
            try:
                logger.debug(f"Loading image: {filepath}")
                img = bpy.data.images.load(filepath)
            except:
                logger.warning(f"Cannot create a texture for {filepath}. No such file.")
                img = bpy.data.images.new(os.path.basename(filepath), 1, 1)
                img.source = "FILE"
                img.filepath = filepath
            use_alpha = img.depth == 32 and img.file_format != "BMP"
            if hasattr(img, "use_alpha"):
                img.use_alpha = use_alpha
            elif not use_alpha:
                img.alpha_mode = "NONE"
        return img

    def update_toon_texture(self) -> None:
        if self._nodes_are_readonly:
            return
        mmd_mat: 'MMDMaterial' = self.__material.mmd_material
        if mmd_mat.is_shared_toon_texture:
            shared_toon_folder = FnContext.get_addon_preferences_attribute(FnContext.ensure_context(), "shared_toon_folder", "")
            toon_path = os.path.join(shared_toon_folder, "toon%02d.bmp" % (mmd_mat.shared_toon_texture + 1))
            logger.debug(f"Using shared toon texture: {toon_path}")
            self.create_toon_texture(bpy.path.resolve_ncase(path=toon_path))
        elif mmd_mat.toon_texture != "":
            logger.debug(f"Using custom toon texture: {mmd_mat.toon_texture}")
            self.create_toon_texture(mmd_mat.toon_texture)
        else:
            logger.debug(f"Removing toon texture from {self.__material.name}")
            self.remove_toon_texture()

    def _mix_diffuse_and_ambient(self, mmd_mat: 'MMDMaterial') -> List[float]:
        r, g, b = mmd_mat.diffuse_color
        ar, ag, ab = mmd_mat.ambient_color
        return [min(1.0, 0.5 * r + ar), min(1.0, 0.5 * g + ag), min(1.0, 0.5 * b + ab)]

    def update_drop_shadow(self) -> None:
        pass

    def update_enabled_toon_edge(self) -> None:
        if self._nodes_are_readonly:
            return
        self.update_edge_color()

    def update_edge_color(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.__material
        mmd_mat: 'MMDMaterial' = mat.mmd_material
        color, alpha = mmd_mat.edge_color[:3], mmd_mat.edge_color[3]
        line_color = color + (min(alpha, int(mmd_mat.enabled_toon_edge)),)
        if hasattr(mat, "line_color"):  # freestyle line color
            mat.line_color = line_color

        mat_edge: Optional[bpy.types.Material] = bpy.data.materials.get("mmd_edge." + mat.name, None)
        if mat_edge:
            mat_edge.mmd_material.edge_color = line_color

        if mat.name.startswith("mmd_edge.") and mat.node_tree:
            mmd_mat.ambient_color, mmd_mat.alpha = color, alpha
            node_shader = mat.node_tree.nodes.get("mmd_edge_preview", None)
            if node_shader and "Color" in node_shader.inputs:
                node_shader.inputs["Color"].default_value = mmd_mat.edge_color
            if node_shader and "Alpha" in node_shader.inputs:
                node_shader.inputs["Alpha"].default_value = alpha
        
        logger.debug(f"Updated edge color for {mat.name}")

    def update_edge_weight(self) -> None:
        pass

    def get_texture(self) -> Optional[_DummyTexture]:
        return self.__get_texture_node("mmd_base_tex", use_dummy=True)

    def create_texture(self, filepath: str) -> _DummyTextureSlot:
        texture = self.__create_texture_node("mmd_base_tex", filepath, (-4, -1))
        logger.debug(f"Created base texture for {self.__material.name}: {filepath}")
        return _DummyTextureSlot(texture.image)

    def remove_texture(self) -> None:
        if self._nodes_are_readonly:
            return
        logger.debug(f"Removing base texture from {self.__material.name}")
        self.__remove_texture_node("mmd_base_tex")

    def get_sphere_texture(self) -> Optional[_DummyTexture]:
        return self.__get_texture_node("mmd_sphere_tex", use_dummy=True)

    def use_sphere_texture(self, use_sphere: bool, obj: Optional[bpy.types.Object] = None) -> None:
        if self._nodes_are_readonly:
            return
        if use_sphere:
            logger.debug(f"Enabling sphere texture for {self.__material.name}")
            self.update_sphere_texture_type(obj)
        else:
            logger.debug(f"Disabling sphere texture for {self.__material.name}")
            self.__update_shader_input("Sphere Tex Fac", 0)

    def create_sphere_texture(self, filepath: str, obj: Optional[bpy.types.Object] = None) -> _DummyTextureSlot:
        texture = self.__create_texture_node("mmd_sphere_tex", filepath, (-2, -2))
        logger.debug(f"Created sphere texture for {self.__material.name}: {filepath}")
        self.update_sphere_texture_type(obj)
        return _DummyTextureSlot(texture.image)

    def update_sphere_texture_type(self, obj: Optional[bpy.types.Object] = None) -> None:
        if self._nodes_are_readonly:
            return
        sphere_texture_type = int(self.material.mmd_material.sphere_texture_type)
        is_sph_add = sphere_texture_type == 2

        if sphere_texture_type not in (1, 2, 3):
            self.__update_shader_input("Sphere Tex Fac", 0)
        else:
            self.__update_shader_input("Sphere Tex Fac", 1)
            self.__update_shader_input("Sphere Mul/Add", is_sph_add)
            self.__update_shader_input("Sphere Tex", (0, 0, 0, 1) if is_sph_add else (1, 1, 1, 1))

            texture = self.__get_texture_node("mmd_sphere_tex")
            if texture and (not texture.inputs["Vector"].is_linked or texture.inputs["Vector"].links[0].from_node.name == "mmd_tex_uv"):
                if hasattr(texture, "color_space"):
                    texture.color_space = "NONE" if is_sph_add else "COLOR"
                elif hasattr(texture.image, "colorspace_settings"):
                    texture.image.colorspace_settings.name = "Linear Rec.709" if is_sph_add else "sRGB"

                mat = self.material
                nodes, links = mat.node_tree.nodes, mat.node_tree.links
                if sphere_texture_type == 3:
                    if obj and obj.type == "MESH" and mat in tuple(obj.data.materials):
                        uv_layers = (l for l in obj.data.uv_layers if not l.name.startswith("_"))
                        next(uv_layers, None)  # skip base UV
                        subtex_uv = getattr(next(uv_layers, None), "name", "")
                        if subtex_uv != "UV1":
                            logger.info(f'Material({mat.name}): object "{obj.name}" use UV "{subtex_uv}" for SubTex')
                    links.new(nodes["mmd_tex_uv"].outputs["SubTex UV"], texture.inputs["Vector"])
                else:
                    links.new(nodes["mmd_tex_uv"].outputs["Sphere UV"], texture.inputs["Vector"])
        
        logger.debug(f"Updated sphere texture type for {self.material.name}: {sphere_texture_type}")

    def remove_sphere_texture(self) -> None:
        if self._nodes_are_readonly:
            return
        logger.debug(f"Removing sphere texture from {self.__material.name}")
        self.__remove_texture_node("mmd_sphere_tex")

    def get_toon_texture(self) -> Optional[_DummyTexture]:
        return self.__get_texture_node("mmd_toon_tex", use_dummy=True)

    def use_toon_texture(self, use_toon: bool) -> None:
        if self._nodes_are_readonly:
            return
        logger.debug(f"{'Enabling' if use_toon else 'Disabling'} toon texture for {self.__material.name}")
        self.__update_shader_input("Toon Tex Fac", use_toon)

    def create_toon_texture(self, filepath: str) -> _DummyTextureSlot:
        texture = self.__create_texture_node("mmd_toon_tex", filepath, (-3, -1.5))
        logger.debug(f"Created toon texture for {self.__material.name}: {filepath}")
        return _DummyTextureSlot(texture.image)

    def remove_toon_texture(self) -> None:
        if self._nodes_are_readonly:
            return
        logger.debug(f"Removing toon texture from {self.__material.name}")
        self.__remove_texture_node("mmd_toon_tex")

    def __get_texture_node(self, node_name: str, use_dummy: bool = False) -> Optional[Union[bpy.types.ShaderNodeTexImage, _DummyTexture]]:
        mat = self.material
        texture = getattr(mat.node_tree, "nodes", {}).get(node_name, None)
        if isinstance(texture, bpy.types.ShaderNodeTexImage):
            return _DummyTexture(texture.image) if use_dummy else texture
        return None

    def __remove_texture_node(self, node_name: str) -> None:
        mat = self.material
        texture = getattr(mat.node_tree, "nodes", {}).get(node_name, None)
        if isinstance(texture, bpy.types.ShaderNodeTexImage):
            mat.node_tree.nodes.remove(texture)
            mat.update_tag()

    def __create_texture_node(self, node_name: str, filepath: str, pos: Tuple[float, float]) -> bpy.types.ShaderNodeTexImage:
        texture = self.__get_texture_node(node_name)
        if texture is None:
            from mathutils import Vector

            self.__update_shader_nodes()
            nodes = self.material.node_tree.nodes
            texture = nodes.new("ShaderNodeTexImage")
            # pylint: disable=assignment-from-no-return
            texture.label = bpy.path.display_name(node_name)
            texture.name = node_name
            texture.location = nodes["mmd_shader"].location + Vector((pos[0] * 210, pos[1] * 220))
        texture.image = self._load_image(filepath)
        self.__update_shader_nodes()
        return texture

    def update_ambient_color(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        mat.diffuse_color[:3] = self._mix_diffuse_and_ambient(mmd_mat)
        self.__update_shader_input("Ambient Color", mmd_mat.ambient_color[:] + (1,))
        logger.debug(f"Updated ambient color for {mat.name}")

    def update_diffuse_color(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        mat.diffuse_color[:3] = self._mix_diffuse_and_ambient(mmd_mat)
        self.__update_shader_input("Diffuse Color", mmd_mat.diffuse_color[:] + (1,))
        logger.debug(f"Updated diffuse color for {mat.name}")

    def update_alpha(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        if hasattr(mat, "blend_method"):
            mat.blend_method = "HASHED"  # 'BLEND'
            # mat.show_transparent_back = False
        elif hasattr(mat, "transparency_method"):
            mat.use_transparency = True
            mat.transparency_method = "Z_TRANSPARENCY"
            mat.game_settings.alpha_blend = "ALPHA"
        if hasattr(mat, "alpha"):
            mat.alpha = mmd_mat.alpha
        elif len(mat.diffuse_color) > 3:
            mat.diffuse_color[3] = mmd_mat.alpha
        self.__update_shader_input("Alpha", mmd_mat.alpha)
        self.update_self_shadow_map()
        logger.debug(f"Updated alpha for {mat.name}: {mmd_mat.alpha}")

    def update_specular_color(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        mat.specular_color = mmd_mat.specular_color
        self.__update_shader_input("Specular Color", mmd_mat.specular_color[:] + (1,))
        logger.debug(f"Updated specular color for {mat.name}")

    def update_shininess(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        mat.roughness = 1 / pow(max(mmd_mat.shininess, 1), 0.37)
        if hasattr(mat, "metallic"):
            mat.metallic = pow(1 - mat.roughness, 2.7)
        if hasattr(mat, "specular_hardness"):
            mat.specular_hardness = mmd_mat.shininess
        self.__update_shader_input("Reflect", mmd_mat.shininess)
        logger.debug(f"Updated shininess for {mat.name}: {mmd_mat.shininess}")

    def update_is_double_sided(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        if hasattr(mat, "game_settings"):
            mat.game_settings.use_backface_culling = not mmd_mat.is_double_sided
        elif hasattr(mat, "use_backface_culling"):
            mat.use_backface_culling = not mmd_mat.is_double_sided
        self.__update_shader_input("Double Sided", mmd_mat.is_double_sided)
        logger.debug(f"Updated double-sided setting for {mat.name}: {mmd_mat.is_double_sided}")

    def update_self_shadow_map(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        cast_shadows = mmd_mat.enabled_self_shadow_map if mmd_mat.alpha > 1e-3 else False
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "HASHED" if cast_shadows else "NONE"
        logger.debug(f"Updated self shadow map for {mat.name}: {cast_shadows}")

    def update_self_shadow(self) -> None:
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        self.__update_shader_input("Self Shadow", mmd_mat.enabled_self_shadow)
        logger.debug(f"Updated self shadow for {mat.name}: {mmd_mat.enabled_self_shadow}")

    @staticmethod
    def convert_to_mmd_material(material: bpy.types.Material, context: bpy.types.Context = bpy.context) -> None:
        m, mmd_material = material, material.mmd_material
        logger.debug(f"Converting material to MMD material: {material.name}")

        if m.use_nodes and next((n for n in m.node_tree.nodes if n.name.startswith("mmd_")), None) is None:

            def search_tex_image_node(node: bpy.types.ShaderNode) -> Optional[bpy.types.ShaderNodeTexImage]:
                if node.type == "TEX_IMAGE":
                    return node
                for node_input in node.inputs:
                    if not node_input.is_linked:
                        continue
                    child = search_tex_image_node(node_input.links[0].from_node)
                    if child is not None:
                        return child
                return None

            if hasattr(context, "engine"):
                active_render_engine = context.engine
            else:
                # use ALL anyway
                active_render_engine = "ALL"

            preferred_output_node_target = {
                "CYCLES": "CYCLES",
                "BLENDER_EEVEE": "EEVEE",
            }.get(active_render_engine, "ALL")

            tex_node = None
            for target in [preferred_output_node_target, "ALL"]:
                output_node = m.node_tree.get_output_node(target)
                if output_node is None:
                    continue

                if not output_node.inputs[0].is_linked:
                    continue

                tex_node = search_tex_image_node(output_node.inputs[0].links[0].from_node)
                break

            if tex_node is None:
                tex_node = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"), None)
            if tex_node:
                logger.debug(f"Found texture node for {material.name}: {tex_node.name}")
                tex_node.name = "mmd_base_tex"
            else:
                # Take the Base Color from BSDF if there's no texture
                bsdf_node = next((n for n in m.node_tree.nodes if n.type.startswith('BSDF_')), None)
                if bsdf_node:
                    base_color_input = bsdf_node.inputs.get('Base Color') or bsdf_node.inputs.get('Color')
                    if base_color_input:
                        logger.debug(f"Using BSDF base color for {material.name}")
                        mmd_material.diffuse_color = base_color_input.default_value[:3]
                        # ambient should be half the diffuse
                        mmd_material.ambient_color = [x * 0.5 for x in mmd_material.diffuse_color]

        shadow_method = getattr(m, "shadow_method", None)

        if mmd_material.diffuse_color is None:
            mmd_material.diffuse_color = m.diffuse_color[:3]
        if hasattr(m, "alpha"):
            mmd_material.alpha = m.alpha
        elif len(m.diffuse_color) > 3:
            mmd_material.alpha = m.diffuse_color[3]

        mmd_material.specular_color = m.specular_color
        if hasattr(m, "specular_hardness"):
            mmd_material.shininess = m.specular_hardness
        else:
            mmd_material.shininess = pow(1 / max(m.roughness, 0.099), 1 / 0.37)

        if hasattr(m, "game_settings"):
            mmd_material.is_double_sided = not m.game_settings.use_backface_culling
        elif hasattr(m, "use_backface_culling"):
            mmd_material.is_double_sided = not m.use_backface_culling

        if shadow_method:
            mmd_material.enabled_self_shadow_map = (shadow_method != "NONE") and mmd_material.alpha > 1e-3
            mmd_material.enabled_self_shadow = shadow_method != "NONE"

        # delete bsdf node if it's there
        if m.use_nodes:
            nodes_to_remove = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED' or n.type.startswith('BSDF_')]
            for n in nodes_to_remove:
                logger.debug(f"Removing BSDF node from {material.name}: {n.name}")
                m.node_tree.nodes.remove(n)

    def __update_shader_input(self, name: str, val: Any) -> None:
        mat = self.material
        if mat.name.startswith("mmd_"):  # skip mmd_edge.*
            return
        self.__update_shader_nodes()
        shader = mat.node_tree.nodes.get("mmd_shader", None)
        if shader and name in shader.inputs:
            interface_socket = shader.node_tree.interface.items_tree[name]
            if hasattr(interface_socket, "min_value"):
                val = min(max(val, interface_socket.min_value), interface_socket.max_value)
            shader.inputs[name].default_value = val

    def __update_shader_nodes(self) -> None:
        mat = self.material
        if mat.node_tree is None:
            logger.debug(f"Creating node tree for {mat.name}")
            # Note: material.use_nodes is deprecated in Blender 5.0 - materials always use nodes
            # Creating a new material automatically creates a node tree
            if mat.node_tree is None:
                # Fallback: node tree should exist, but if not, log warning
                logger.warning(f"Node tree is None for material {mat.name} - this should not happen")
                return
            mat.node_tree.nodes.clear()

        nodes, links = mat.node_tree.nodes, mat.node_tree.links

        class _Dummy:
            default_value: Any = None
            is_linked: bool = True

        node_shader = nodes.get("mmd_shader", None)
        if node_shader is None:
            logger.debug(f"Creating MMD shader node for {mat.name}")
            node_shader: bpy.types.ShaderNodeGroup = nodes.new("ShaderNodeGroup")
            node_shader.name = "mmd_shader"
            node_shader.location = (0, 1500)
            node_shader.width = 200
            node_shader.node_tree = self.__get_shader()

            mmd_mat: 'MMDMaterial' = mat.mmd_material
            node_shader.inputs.get("Ambient Color", _Dummy).default_value = mmd_mat.ambient_color[:] + (1,)
            node_shader.inputs.get("Diffuse Color", _Dummy).default_value = mmd_mat.diffuse_color[:] + (1,)
            node_shader.inputs.get("Specular Color", _Dummy).default_value = mmd_mat.specular_color[:] + (1,)
            node_shader.inputs.get("Reflect", _Dummy).default_value = mmd_mat.shininess
            node_shader.inputs.get("Alpha", _Dummy).default_value = mmd_mat.alpha
            node_shader.inputs.get("Double Sided", _Dummy).default_value = mmd_mat.is_double_sided
            node_shader.inputs.get("Self Shadow", _Dummy).default_value = mmd_mat.enabled_self_shadow
            self.update_sphere_texture_type()

        node_uv = nodes.get("mmd_tex_uv", None)
        if node_uv is None:
            logger.debug(f"Creating MMD UV node for {mat.name}")
            node_uv: bpy.types.ShaderNodeGroup = nodes.new("ShaderNodeGroup")
            node_uv.name = "mmd_tex_uv"
            node_uv.location = node_shader.location + Vector((-5 * 210, -2.5 * 220))
            node_uv.node_tree = self.__get_shader_uv()

        if not (node_shader.outputs["Shader"].is_linked or node_shader.outputs["Color"].is_linked or node_shader.outputs["Alpha"].is_linked):
            node_output = next((n for n in nodes if isinstance(n, bpy.types.ShaderNodeOutputMaterial) and n.is_active_output), None)
            if node_output is None:
                node_output: bpy.types.ShaderNodeOutputMaterial = nodes.new("ShaderNodeOutputMaterial")
                node_output.is_active_output = True
            node_output.location = node_shader.location + Vector((400, 0))
            links.new(node_shader.outputs["Shader"], node_output.inputs["Surface"])

        for name_id in ("Base", "Toon", "Sphere"):
            texture = self.__get_texture_node("mmd_%s_tex" % name_id.lower())
            if texture:
                name_tex_in, name_alpha_in, name_uv_out = (name_id + x for x in (" Tex", " Alpha", " UV"))
                if not node_shader.inputs.get(name_tex_in, _Dummy).is_linked:
                    links.new(texture.outputs["Color"], node_shader.inputs[name_tex_in])
                if not node_shader.inputs.get(name_alpha_in, _Dummy).is_linked:
                    links.new(texture.outputs["Alpha"], node_shader.inputs[name_alpha_in])
                if not texture.inputs["Vector"].is_linked:
                    links.new(node_uv.outputs[name_uv_out], texture.inputs["Vector"])

    def __get_shader_uv(self) -> bpy.types.ShaderNodeTree:
        group_name = "MMDTexUV"
        shader: bpy.types.ShaderNodeTree = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        logger.debug(f"Creating MMD UV shader node group")
        ng = _NodeGroupUtils(shader)

        ############################################################################
        _node_output: bpy.types.NodeGroupOutput = ng.new_node("NodeGroupOutput", (6, 0))

        tex_coord: bpy.types.ShaderNodeTexCoord = ng.new_node("ShaderNodeTexCoord", (0, 0))

        tex_coord1: bpy.types.ShaderNodeUVMap = ng.new_node("ShaderNodeUVMap", (4, -2))
        tex_coord1.uv_map = "UV1"

        vec_trans: bpy.types.ShaderNodeVectorTransform = ng.new_node("ShaderNodeVectorTransform", (1, -1))
        vec_trans.vector_type = "NORMAL"
        vec_trans.convert_from = "OBJECT"
        vec_trans.convert_to = "CAMERA"

        node_vector: bpy.types.ShaderNodeMapping = ng.new_node("ShaderNodeMapping", (2, -1))
        node_vector.vector_type = "POINT"
        node_vector.inputs["Location"].default_value = (0.5, 0.5, 0.0)
        node_vector.inputs["Scale"].default_value = (0.5, 0.5, 1.0)

        links = ng.links
        links.new(tex_coord.outputs["Normal"], vec_trans.inputs["Vector"])
        links.new(vec_trans.outputs["Vector"], node_vector.inputs["Vector"])

        ng.new_output_socket("Base UV", tex_coord.outputs["UV"])
        ng.new_output_socket("Toon UV", node_vector.outputs["Vector"])
        ng.new_output_socket("Sphere UV", node_vector.outputs["Vector"])
        ng.new_output_socket("SubTex UV", tex_coord1.outputs["UV"])

        return shader

    def __get_shader(self) -> bpy.types.ShaderNodeTree:
        group_name = "MMDShaderDev"
        shader: bpy.types.ShaderNodeTree = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        logger.debug(f"Creating MMD shader node group")
        ng = _NodeGroupUtils(shader)

        ############################################################################
        node_input: bpy.types.NodeGroupInput = ng.new_node("NodeGroupInput", (-5, -1))
        _node_output: bpy.types.NodeGroupOutput = ng.new_node("NodeGroupOutput", (11, 1))

        node_diffuse: bpy.types.ShaderNodeMath = ng.new_mix_node("ADD", (-3, 4), fac=0.6)
        node_diffuse.use_clamp = True

        node_tex: bpy.types.ShaderNodeMath = ng.new_mix_node("MULTIPLY", (-2, 3.5))
        node_toon: bpy.types.ShaderNodeMath = ng.new_mix_node("MULTIPLY", (-1, 3))
        node_sph: bpy.types.ShaderNodeMath = ng.new_mix_node("MULTIPLY", (0, 2.5))
        node_spa: bpy.types.ShaderNodeMath = ng.new_mix_node("ADD", (0, 1.5))
        node_sphere: bpy.types.ShaderNodeMath = ng.new_mix_node("MIX", (1, 1))

        node_geo: bpy.types.ShaderNodeNewGeometry = ng.new_node("ShaderNodeNewGeometry", (6, 3.5))
        node_invert: bpy.types.ShaderNodeMath = ng.new_math_node("LESS_THAN", (7, 3))
        node_cull: bpy.types.ShaderNodeMath = ng.new_math_node("MAXIMUM", (8, 2.5))
        node_alpha: bpy.types.ShaderNodeMath = ng.new_math_node("MINIMUM", (9, 2))
        node_alpha.use_clamp = True
        node_alpha_tex: bpy.types.ShaderNodeMath = ng.new_math_node("MULTIPLY", (-1, -2))
        node_alpha_toon: bpy.types.ShaderNodeMath = ng.new_math_node("MULTIPLY", (0, -2.5))
        node_alpha_sph: bpy.types.ShaderNodeMath = ng.new_math_node("MULTIPLY", (1, -3))

        node_reflect: bpy.types.ShaderNodeMath = ng.new_math_node("DIVIDE", (7, -1.5), value1=1)
        node_reflect.use_clamp = True

        shader_diffuse: bpy.types.ShaderNodeBsdfDiffuse = ng.new_node("ShaderNodeBsdfDiffuse", (8, 0))
        shader_glossy: bpy.types.ShaderNodeBsdfAnisotropic = ng.new_node("ShaderNodeBsdfAnisotropic", (8, -1))
        shader_base_mix: bpy.types.ShaderNodeMixShader = ng.new_node("ShaderNodeMixShader", (9, 0))
        shader_base_mix.inputs["Fac"].default_value = 0.02
        shader_trans: bpy.types.ShaderNodeBsdfTransparent = ng.new_node("ShaderNodeBsdfTransparent", (9, 1))
        shader_alpha_mix: bpy.types.ShaderNodeMixShader = ng.new_node("ShaderNodeMixShader", (10, 1))

        links = ng.links
        links.new(node_reflect.outputs["Value"], shader_glossy.inputs["Roughness"])
        links.new(shader_diffuse.outputs["BSDF"], shader_base_mix.inputs[1])
        links.new(shader_glossy.outputs["BSDF"], shader_base_mix.inputs[2])

        links.new(node_diffuse.outputs["Color"], node_tex.inputs["Color1"])
        links.new(node_tex.outputs["Color"], node_toon.inputs["Color1"])
        links.new(node_toon.outputs["Color"], node_sph.inputs["Color1"])
        links.new(node_toon.outputs["Color"], node_spa.inputs["Color1"])
        links.new(node_sph.outputs["Color"], node_sphere.inputs["Color1"])
        links.new(node_spa.outputs["Color"], node_sphere.inputs["Color2"])
        links.new(node_sphere.outputs["Color"], shader_diffuse.inputs["Color"])

        links.new(node_geo.outputs["Backfacing"], node_invert.inputs[0])
        links.new(node_invert.outputs["Value"], node_cull.inputs[0])
        links.new(node_cull.outputs["Value"], node_alpha.inputs[0])
        links.new(node_alpha_tex.outputs["Value"], node_alpha_toon.inputs[0])
        links.new(node_alpha_toon.outputs["Value"], node_alpha_sph.inputs[0])
        links.new(node_alpha_sph.outputs["Value"], node_alpha.inputs[1])

        links.new(node_alpha.outputs["Value"], shader_alpha_mix.inputs["Fac"])
        links.new(shader_trans.outputs["BSDF"], shader_alpha_mix.inputs[1])
        links.new(shader_base_mix.outputs["Shader"], shader_alpha_mix.inputs[2])

        ############################################################################
        ng.new_input_socket("Ambient Color", node_diffuse.inputs["Color1"], (0.4, 0.4, 0.4, 1))
        ng.new_input_socket("Diffuse Color", node_diffuse.inputs["Color2"], (0.8, 0.8, 0.8, 1))
        # ↓ specular should be disabled by default
        ng.new_input_socket("Specular Color", shader_glossy.inputs["Color"], (0.0, 0.0, 0.0, 1))
        ng.new_input_socket("Reflect", node_reflect.inputs[1], 50, min_max=(1, 512))
        ng.new_input_socket("Base Tex Fac", node_tex.inputs["Fac"], 1)
        ng.new_input_socket("Base Tex", node_tex.inputs["Color2"], (1, 1, 1, 1))
        ng.new_input_socket("Toon Tex Fac", node_toon.inputs["Fac"], 1)
        ng.new_input_socket("Toon Tex", node_toon.inputs["Color2"], (1, 1, 1, 1))
        ng.new_input_socket("Sphere Tex Fac", node_sph.inputs["Fac"], 1)
        ng.new_input_socket("Sphere Tex", node_sph.inputs["Color2"], (1, 1, 1, 1))
        ng.new_input_socket("Sphere Mul/Add", node_sphere.inputs["Fac"], 0)
        ng.new_input_socket("Double Sided", node_cull.inputs[1], 0, min_max=(0, 1))
        ng.new_input_socket("Alpha", node_alpha_tex.inputs[0], 1, min_max=(0, 1))
        ng.new_input_socket("Base Alpha", node_alpha_tex.inputs[1], 1, min_max=(0, 1))
        ng.new_input_socket("Toon Alpha", node_alpha_toon.inputs[1], 1, min_max=(0, 1))
        ng.new_input_socket("Sphere Alpha", node_alpha_sph.inputs[1], 1, min_max=(0, 1))

        links.new(node_input.outputs["Sphere Tex Fac"], node_spa.inputs["Fac"])
        links.new(node_input.outputs["Sphere Tex"], node_spa.inputs["Color2"])

        ng.new_output_socket("Shader", shader_alpha_mix.outputs["Shader"])
        ng.new_output_socket("Color", node_sphere.outputs["Color"])
        ng.new_output_socket("Alpha", node_alpha.outputs["Value"])

        return shader


class MigrationFnMaterial:
    @staticmethod
    def update_mmd_shader() -> None:
        mmd_shader_node_tree: Optional[bpy.types.NodeTree] = bpy.data.node_groups.get("MMDShaderDev")
        if mmd_shader_node_tree is None:
            logger.debug("No MMD shader node tree found, skipping update")
            return

        ng = _NodeGroupUtils(mmd_shader_node_tree)
        if "Color" in ng.node_output.inputs:
            logger.debug("MMD shader already has Color output, skipping update")
            return

        logger.info("Updating MMD shader node tree")
        shader_diffuse: bpy.types.ShaderNodeBsdfDiffuse = [n for n in mmd_shader_node_tree.nodes if n.type == "BSDF_DIFFUSE"][0]
        node_sphere: bpy.types.ShaderNodeMixRGB = shader_diffuse.inputs["Color"].links[0].from_node
        node_output: bpy.types.NodeGroupOutput = ng.node_output
        shader_alpha_mix: bpy.types.ShaderNodeMixShader = node_output.inputs["Shader"].links[0].from_node
        node_alpha: bpy.types.ShaderNodeMath = shader_alpha_mix.inputs["Fac"].links[0].from_node

        ng.new_output_socket("Color", node_sphere.outputs["Color"])
        ng.new_output_socket("Alpha", node_alpha.outputs["Value"])
        logger.info("MMD shader node tree updated successfully")
        
        # Add Self Shadow input if it doesn't exist
        if "Self Shadow" not in ng.node_input.outputs:
            logger.info("Adding Self Shadow input to MMD shader")
            # Find shader_base_mix node to connect Self Shadow
            shader_base_mix = shader_alpha_mix.inputs[2].links[0].from_node
            ng.new_input_socket("Self Shadow", shader_base_mix.inputs["Fac"], 0, min_max=(0, 1))
