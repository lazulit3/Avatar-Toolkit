# -*- coding: utf-8 -*-
# Copyright 2013 MMD Tools authors
# This file was originally part of the MMD Tools project, However Neoneko has added it to Avatar Toolkit.
# All credit goes to the original authors.
# Please note that some code was modified to fit the needs of Avatar Toolkit and some code may of been removed.
# MMD Tools is licensed under the terms of the GPL-3.0 license which Avatar Toolkit is also licensed under.
# You can find MMD Tools at: https://github.com/MMD-Blender/blender_mmd_tools/

import logging
import os
from typing import TYPE_CHECKING, Callable, Iterable, Optional, Tuple, cast

import bpy
from mathutils import Vector

from ..logging_setup import logger
from .exceptions import MaterialNotFoundError
from .shader import _NodeGroupUtils

if TYPE_CHECKING:
    from ..properties.material import MMDMaterial

# Constants for sphere modes
SPHERE_MODE_OFF = 0
SPHERE_MODE_MULT = 1
SPHERE_MODE_ADD = 2
SPHERE_MODE_SUBTEX = 3


class FnMaterial:
    __NODES_ARE_READONLY: bool = False

    def __init__(self, material: bpy.types.Material):
        self.__material = material
        self._nodes_are_readonly = FnMaterial.__NODES_ARE_READONLY
        logger.debug(f"Initializing FnMaterial for {material.name}")

    @staticmethod
    def set_nodes_are_readonly(nodes_are_readonly: bool):
        FnMaterial.__NODES_ARE_READONLY = nodes_are_readonly

    @classmethod
    def from_material_id(cls, material_id: str):
        for material in bpy.data.materials:
            if material.mmd_material.material_id == material_id:
                return cls(material)
        return None

    @staticmethod
    def clean_materials(obj, can_remove: Callable[[bpy.types.Material], bool]):
        materials = obj.data.materials
        materials_pop = materials.pop
        for i in sorted((x for x, m in enumerate(materials) if can_remove(m)), reverse=True):
            m = materials_pop(index=i)
            if m.users < 1:
                bpy.data.materials.remove(m)

    @staticmethod
    def swap_materials(mesh_object: bpy.types.Object, mat1_ref: str | int, mat2_ref: str | int, reverse=False, swap_slots=False) -> Tuple[bpy.types.Material, bpy.types.Material]:
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
    def fixMaterialOrder(meshObj: bpy.types.Object, material_names: Iterable[str]):
        """
        This method will fix the material order. Which is lost after joining meshes.
        """
        materials = cast(bpy.types.Mesh, meshObj.data).materials
        for new_idx, mat in enumerate(material_names):
            # Get the material that is currently on this index
            other_mat = materials[new_idx]
            if other_mat.name == mat:
                continue  # This is already in place
            FnMaterial.swap_materials(meshObj, mat, new_idx, reverse=True, swap_slots=True)

    @property
    def material_id(self):
        mmd_mat = self.__material.mmd_material
        if mmd_mat.material_id < 0:
            max_id = -1
            for mat in bpy.data.materials:
                max_id = max(max_id, mat.mmd_material.material_id)
            mmd_mat.material_id = max_id + 1
        return mmd_mat.material_id

    @property
    def material(self):
        return self.__material

    def __same_image_file(self, image, filepath):
        if image and image.source == "FILE":
            img_filepath = bpy.path.abspath(image.filepath)
            if img_filepath == filepath:
                return True
            try:
                return os.path.samefile(img_filepath, filepath)
            except:
                pass
        return False

    def _load_image(self, filepath):
        img = next((i for i in bpy.data.images if self.__same_image_file(i, filepath)), None)
        if img is None:
            try:
                img = bpy.data.images.load(filepath)
                logger.debug(f"Loaded image from {filepath}")
            except:
                logger.warning(f"Cannot create a texture for {filepath}. No such file.")
                img = bpy.data.images.new(os.path.basename(filepath), 1, 1)
                img.source = "FILE"
                img.filepath = filepath
            # For Blender 4.4+
            if img.depth == 32 and img.file_format != "BMP":
                img.alpha_mode = "CHANNEL_PACKED"
            else:
                img.alpha_mode = "NONE"
        return img

    def update_toon_texture(self):
        if self._nodes_are_readonly:
            return
        mmd_mat = self.__material.mmd_material
        if mmd_mat.is_shared_toon_texture:
            # Get shared toon folder from preferences
            context = bpy.context
            addon_prefs = context.preferences.addons.get("avatar_toolkit", None)
            if addon_prefs:
                shared_toon_folder = addon_prefs.preferences.shared_toon_folder
            else:
                shared_toon_folder = ""
            toon_path = os.path.join(shared_toon_folder, f"toon{mmd_mat.shared_toon_texture + 1:02d}.bmp")
            self.create_toon_texture(bpy.path.resolve_ncase(path=toon_path))
        elif mmd_mat.toon_texture != "":
            self.create_toon_texture(mmd_mat.toon_texture)
        else:
            self.remove_toon_texture()

    def _mix_diffuse_and_ambient(self, mmd_mat):
        r, g, b = mmd_mat.diffuse_color
        ar, ag, ab = mmd_mat.ambient_color
        return [min(1.0, 0.5 * r + ar), min(1.0, 0.5 * g + ag), min(1.0, 0.5 * b + ab)]

    def update_drop_shadow(self):
        pass

    def update_enabled_toon_edge(self):
        if self._nodes_are_readonly:
            return
        self.update_edge_color()

    def update_edge_color(self):
        if self._nodes_are_readonly:
            return
        mat = self.__material
        mmd_mat = mat.mmd_material
        color, alpha = mmd_mat.edge_color[:3], mmd_mat.edge_color[3]
        line_color = color + (min(alpha, int(mmd_mat.enabled_toon_edge)),)
        
        # For Blender 4.4+
        if hasattr(mat, "line_color"):  # freestyle line color
            mat.line_color = line_color

        mat_edge = bpy.data.materials.get("mmd_edge." + mat.name, None)
        if mat_edge:
            mat_edge.mmd_material.edge_color = line_color

        if mat.name.startswith("mmd_edge.") and mat.node_tree:
            mmd_mat.ambient_color, mmd_mat.alpha = color, alpha
            node_shader = mat.node_tree.nodes.get("mmd_edge_preview", None)
            if node_shader and "Color" in node_shader.inputs:
                node_shader.inputs["Color"].default_value = mmd_mat.edge_color
            if node_shader and "Alpha" in node_shader.inputs:
                node_shader.inputs["Alpha"].default_value = alpha

    def update_edge_weight(self):
        pass

    def get_texture(self):
        return self.__get_texture_node("mmd_base_tex")

    def create_texture(self, filepath):
        texture = self.__create_texture_node("mmd_base_tex", filepath, (-4, -1))
        return texture

    def remove_texture(self):
        if self._nodes_are_readonly:
            return
        self.__remove_texture_node("mmd_base_tex")

    def get_sphere_texture(self):
        return self.__get_texture_node("mmd_sphere_tex")

    def use_sphere_texture(self, use_sphere, obj=None):
        if self._nodes_are_readonly:
            return
        if use_sphere:
            self.update_sphere_texture_type(obj)
        else:
            self.__update_shader_input("Sphere Tex Fac", 0)

    def create_sphere_texture(self, filepath, obj=None):
        texture = self.__create_texture_node("mmd_sphere_tex", filepath, (-2, -2))
        self.update_sphere_texture_type(obj)
        return texture

    def update_sphere_texture_type(self, obj=None):
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
                # For Blender 4.4+
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

    def remove_sphere_texture(self):
        if self._nodes_are_readonly:
            return
        self.__remove_texture_node("mmd_sphere_tex")

    def get_toon_texture(self):
        return self.__get_texture_node("mmd_toon_tex")

    def use_toon_texture(self, use_toon):
        if self._nodes_are_readonly:
            return
        self.__update_shader_input("Toon Tex Fac", use_toon)

    def create_toon_texture(self, filepath):
        texture = self.__create_texture_node("mmd_toon_tex", filepath, (-3, -1.5))
        return texture

    def remove_toon_texture(self):
        if self._nodes_are_readonly:
            return
        self.__remove_texture_node("mmd_toon_tex")

    def __get_texture_node(self, node_name):
        mat = self.material
        texture = getattr(mat.node_tree, "nodes", {}).get(node_name, None)
        if isinstance(texture, bpy.types.ShaderNodeTexImage):
            return texture
        return None

    def __remove_texture_node(self, node_name):
        mat = self.material
        texture = getattr(mat.node_tree, "nodes", {}).get(node_name, None)
        if isinstance(texture, bpy.types.ShaderNodeTexImage):
            mat.node_tree.nodes.remove(texture)
            mat.update_tag()

    def __create_texture_node(self, node_name, filepath, pos):
        texture = self.__get_texture_node(node_name)
        if texture is None:
            from mathutils import Vector

            self.__update_shader_nodes()
            nodes = self.material.node_tree.nodes
            texture = nodes.new("ShaderNodeTexImage")
            texture.label = bpy.path.display_name(node_name)
            texture.name = node_name
            texture.location = nodes["mmd_shader"].location + Vector((pos[0] * 210, pos[1] * 220))
        texture.image = self._load_image(filepath)
        self.__update_shader_nodes()
        return texture

    def update_ambient_color(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        # For Blender 4.4+
        mat.diffuse_color[:3] = self._mix_diffuse_and_ambient(mmd_mat)
        self.__update_shader_input("Ambient Color", mmd_mat.ambient_color[:] + (1,))

    def update_diffuse_color(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        # For Blender 4.4+
        mat.diffuse_color[:3] = self._mix_diffuse_and_ambient(mmd_mat)
        self.__update_shader_input("Diffuse Color", mmd_mat.diffuse_color[:] + (1,))

    def update_alpha(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        
        # For Blender 4.4+
        mat.blend_method = "HASHED"
        
        # Update alpha in diffuse_color
        if len(mat.diffuse_color) > 3:
            mat.diffuse_color[3] = mmd_mat.alpha
            
        self.__update_shader_input("Alpha", mmd_mat.alpha)
        self.update_self_shadow_map()

    def update_specular_color(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        mat.specular_color = mmd_mat.specular_color
        self.__update_shader_input("Specular Color", mmd_mat.specular_color[:] + (1,))

    def update_shininess(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        
        # For Blender 4.4+
        mat.roughness = 1 / pow(max(mmd_mat.shininess, 1), 0.37)
        mat.metallic = pow(1 - mat.roughness, 2.7)
        
        self.__update_shader_input("Reflect", mmd_mat.shininess)

    def update_is_double_sided(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        
        # For Blender 4.4+
        mat.use_backface_culling = not mmd_mat.is_double_sided
        
        self.__update_shader_input("Double Sided", mmd_mat.is_double_sided)

    def update_self_shadow_map(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        cast_shadows = mmd_mat.enabled_self_shadow_map if mmd_mat.alpha > 1e-3 else False
        
        # For Blender 4.4+
        mat.shadow_method = "HASHED" if cast_shadows else "NONE"

    def update_self_shadow(self):
        if self._nodes_are_readonly:
            return
        mat = self.material
        mmd_mat = mat.mmd_material
        self.__update_shader_input("Self Shadow", mmd_mat.enabled_self_shadow)

    @staticmethod
    def convert_to_mmd_material(material, context=bpy.context):
        m, mmd_material = material, material.mmd_material

        if m.use_nodes and next((n for n in m.node_tree.nodes if n.name.startswith("mmd_")), None) is None:

            def search_tex_image_node(node: bpy.types.ShaderNode):
                if node.type == "TEX_IMAGE":
                    return node
                for node_input in node.inputs:
                    if not node_input.is_linked:
                        continue
                    child = search_tex_image_node(node_input.links[0].from_node)
                    if child is not None:
                        return child
                return None

            # For Blender 4.4+
            preferred_output_node_target = "EEVEE"

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
                tex_node.name = "mmd_base_tex"
            else:
                # Take the Base Color from BSDF if there's no texture
                bsdf_node = next((n for n in m.node_tree.nodes if n.type.startswith('BSDF_')), None)
                if bsdf_node:
                    base_color_input = bsdf_node.inputs.get('Base Color') or bsdf_node.inputs.get('Color')
                    if base_color_input:
                        mmd_material.diffuse_color = base_color_input.default_value[:3]
                        # ambient should be half the diffuse
                        mmd_material.ambient_color = [x * 0.5 for x in mmd_material.diffuse_color]

        # For Blender 4.4+
        shadow_method = getattr(m, "shadow_method", None)

        if mmd_material.diffuse_color is None:
            mmd_material.diffuse_color = m.diffuse_color[:3]
            
        # For Blender 4.4+
        if len(m.diffuse_color) > 3:
            mmd_material.alpha = m.diffuse_color[3]

        mmd_material.specular_color = m.specular_color
        
        # For Blender 4.4+
        mmd_material.shininess = pow(1 / max(m.roughness, 0.099), 1 / 0.37)
        mmd_material.is_double_sided = not m.use_backface_culling

        if shadow_method:
            mmd_material.enabled_self_shadow_map = (shadow_method != "NONE") and mmd_material.alpha > 1e-3
            mmd_material.enabled_self_shadow = shadow_method != "NONE"

        # delete bsdf node if it's there
        if m.use_nodes:
            nodes_to_remove = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED' or n.type.startswith('BSDF_')]
            for n in nodes_to_remove:
                m.node_tree.nodes.remove(n)

    def __update_shader_input(self, name, val):
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

    def __update_shader_nodes(self):
        mat = self.material
        if mat.node_tree is None:
            mat.use_nodes = True
            mat.node_tree.nodes.clear()

        nodes, links = mat.node_tree.nodes, mat.node_tree.links

        class _Dummy:
            default_value, is_linked = None, True

        node_shader = nodes.get("mmd_shader", None)
        if node_shader is None:
            node_shader = nodes.new("ShaderNodeGroup")
            node_shader.name = "mmd_shader"
            node_shader.location = (0, 1500)
            node_shader.width = 200
            node_shader.node_tree = self.__get_shader()

            mmd_mat = mat.mmd_material
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
            node_uv = nodes.new("ShaderNodeGroup")
            node_uv.name = "mmd_tex_uv"
            node_uv.location = node_shader.location + Vector((-5 * 210, -2.5 * 220))
            node_uv.node_tree = self.__get_shader_uv()

        if not (node_shader.outputs["Shader"].is_linked or node_shader.outputs["Color"].is_linked or node_shader.outputs["Alpha"].is_linked):
            node_output = next((n for n in nodes if isinstance(n, bpy.types.ShaderNodeOutputMaterial) and n.is_active_output), None)
            if node_output is None:
                node_output = nodes.new("ShaderNodeOutputMaterial")
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

    def __get_shader_uv(self):
        group_name = "MMDTexUV"
        shader = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        ng = _NodeGroupUtils(shader)

        ############################################################################
        _node_output = ng.new_node("NodeGroupOutput", (6, 0))

        tex_coord = ng.new_node("ShaderNodeTexCoord", (0, 0))

        tex_coord1 = ng.new_node("ShaderNodeUVMap", (4, -2))
        tex_coord1.uv_map = "UV1"

        vec_trans = ng.new_node("ShaderNodeVectorTransform", (1, -1))
        vec_trans.vector_type = "NORMAL"
        vec_trans.convert_from = "OBJECT"
        vec_trans.convert_to = "CAMERA"

        node_vector = ng.new_node("ShaderNodeMapping", (2, -1))
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

    def __get_shader(self):
        group_name = "MMDShaderDev"
        shader = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        ng = _NodeGroupUtils(shader)

        ############################################################################
        node_input = ng.new_node("NodeGroupInput", (-5, -1))
        _node_output = ng.new_node("NodeGroupOutput", (11, 1))

        node_diffuse = ng.new_mix_node("ADD", (-3, 4), fac=0.6)
        node_diffuse.use_clamp = True

        node_tex = ng.new_mix_node("MULTIPLY", (-2, 3.5))
        node_toon = ng.new_mix_node("MULTIPLY", (-1, 3))
        node_sph = ng.new_mix_node("MULTIPLY", (0, 2.5))
        node_spa = ng.new_mix_node("ADD", (0, 1.5))
        node_sphere = ng.new_mix_node("MIX", (1, 1))

        node_geo = ng.new_node("ShaderNodeNewGeometry", (6, 3.5))
        node_invert = ng.new_math_node("LESS_THAN", (7, 3))
        node_cull = ng.new_math_node("MAXIMUM", (8, 2.5))
        node_alpha = ng.new_math_node("MINIMUM", (9, 2))
        node_alpha.use_clamp = True
        node_alpha_tex = ng.new_math_node("MULTIPLY", (-1, -2))
        node_alpha_toon = ng.new_math_node("MULTIPLY", (0, -2.5))
        node_alpha_sph = ng.new_math_node("MULTIPLY", (1, -3))

        node_reflect = ng.new_math_node("DIVIDE", (7, -1.5), value1=1)
        node_reflect.use_clamp = True

        shader_diffuse = ng.new_node("ShaderNodeBsdfDiffuse", (8, 0))
        shader_glossy = ng.new_node("ShaderNodeBsdfAnisotropic", (8, -1))
        shader_base_mix = ng.new_node("ShaderNodeMixShader", (9, 0))
        shader_base_mix.inputs["Fac"].default_value = 0.02
        shader_trans = ng.new_node("ShaderNodeBsdfTransparent", (9, 1))
        shader_alpha_mix = ng.new_node("ShaderNodeMixShader", (10, 1))

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
    def update_mmd_shader():
        mmd_shader_node_tree = bpy.data.node_groups.get("MMDShaderDev")
        if mmd_shader_node_tree is None:
            return

        ng = _NodeGroupUtils(mmd_shader_node_tree)
        if "Color" in ng.node_output.inputs:
            return

        shader_diffuse = [n for n in mmd_shader_node_tree.nodes if n.type == "BSDF_DIFFUSE"][0]
        node_sphere = shader_diffuse.inputs["Color"].links[0].from_node
        node_output = ng.node_output
        shader_alpha_mix = node_output.inputs["Shader"].links[0].from_node
        node_alpha = shader_alpha_mix.inputs["Fac"].links[0].from_node

        ng.new_output_socket("Color", node_sphere.outputs["Color"])
        ng.new_output_socket("Alpha", node_alpha.outputs["Value"])
