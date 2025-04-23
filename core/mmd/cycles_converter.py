# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file was originally part of the MMD Tools add-on for Blender
# You can find MMD Tools here: https://github.com/MMD-Blender/blender_mmd_tools
# Neoneko has modified this file to work with Avatar Toolkit and may of made changes or improvements.
# MMD Tools is licensed under the terms of the GNU General Public License version 3 (GPLv3) same as Avatar Toolkit.

from typing import Iterable, Optional, Any, List, Tuple, Union

import bpy
from bpy.types import Material, NodeTree, Node, NodeSocket, ShaderNodeGroup, ShaderNodeOutputMaterial, NodeLink

from ..logging_setup import logger
from .core.shader import _NodeGroupUtils
from .core.material import FnMaterial


def __switchToCyclesRenderEngine() -> None:
    if bpy.context.scene.render.engine != "CYCLES":
        logger.debug("Switching render engine to Cycles")
        bpy.context.scene.render.engine = "CYCLES"


def __exposeNodeTreeInput(in_socket: NodeSocket, name: str, default_value: Any, node_input: Node, shader: NodeTree) -> None:
    _NodeGroupUtils(shader).new_input_socket(name, in_socket, default_value)


def __exposeNodeTreeOutput(out_socket: NodeSocket, name: str, node_output: Node, shader: NodeTree) -> None:
    _NodeGroupUtils(shader).new_output_socket(name, out_socket)


def __getMaterialOutput(nodes: bpy.types.Nodes, bl_idname: str) -> Node:
    o = next((n for n in nodes if n.bl_idname == bl_idname and n.is_active_output), None) or nodes.new(bl_idname)
    o.is_active_output = True
    return o


def create_MMDAlphaShader() -> NodeTree:
    __switchToCyclesRenderEngine()

    if "MMDAlphaShader" in bpy.data.node_groups:
        logger.debug("Using existing MMDAlphaShader node group")
        return bpy.data.node_groups["MMDAlphaShader"]

    logger.info("Creating new MMDAlphaShader node group")
    shader = bpy.data.node_groups.new(name="MMDAlphaShader", type="ShaderNodeTree")

    node_input = shader.nodes.new("NodeGroupInput")
    node_output = shader.nodes.new("NodeGroupOutput")
    node_output.location.x += 250
    node_input.location.x -= 500

    trans = shader.nodes.new("ShaderNodeBsdfTransparent")
    trans.location.x -= 250
    trans.location.y += 150
    mix = shader.nodes.new("ShaderNodeMixShader")

    shader.links.new(mix.inputs[1], trans.outputs["BSDF"])

    __exposeNodeTreeInput(mix.inputs[2], "Shader", None, node_input, shader)
    __exposeNodeTreeInput(mix.inputs["Fac"], "Alpha", 1.0, node_input, shader)
    __exposeNodeTreeOutput(mix.outputs["Shader"], "Shader", node_output, shader)

    return shader


def create_MMDBasicShader() -> NodeTree:
    __switchToCyclesRenderEngine()

    if "MMDBasicShader" in bpy.data.node_groups:
        logger.debug("Using existing MMDBasicShader node group")
        return bpy.data.node_groups["MMDBasicShader"]

    logger.info("Creating new MMDBasicShader node group")
    shader: NodeTree = bpy.data.node_groups.new(name="MMDBasicShader", type="ShaderNodeTree")

    node_input: Node = shader.nodes.new("NodeGroupInput")
    node_output: Node = shader.nodes.new("NodeGroupOutput")
    node_output.location.x += 250
    node_input.location.x -= 500

    dif: Node = shader.nodes.new("ShaderNodeBsdfDiffuse")
    dif.location.x -= 250
    dif.location.y += 150
    glo: Node = shader.nodes.new("ShaderNodeBsdfAnisotropic")
    glo.location.x -= 250
    glo.location.y -= 150
    mix: Node = shader.nodes.new("ShaderNodeMixShader")
    shader.links.new(mix.inputs[1], dif.outputs["BSDF"])
    shader.links.new(mix.inputs[2], glo.outputs["BSDF"])

    __exposeNodeTreeInput(dif.inputs["Color"], "diffuse", [1.0, 1.0, 1.0, 1.0], node_input, shader)
    __exposeNodeTreeInput(glo.inputs["Color"], "glossy", [1.0, 1.0, 1.0, 1.0], node_input, shader)
    __exposeNodeTreeInput(glo.inputs["Roughness"], "glossy_rough", 0.0, node_input, shader)
    __exposeNodeTreeInput(mix.inputs["Fac"], "reflection", 0.02, node_input, shader)
    __exposeNodeTreeOutput(mix.outputs["Shader"], "shader", node_output, shader)

    return shader


def __enum_linked_nodes(node: Node) -> Iterable[Node]:
    yield node
    if node.parent:
        yield node.parent
    for n in set(l.from_node for i in node.inputs for l in i.links):
        yield from __enum_linked_nodes(n)


def __cleanNodeTree(material: Material) -> None:
    logger.debug(f"Cleaning node tree for material: {material.name}")
    nodes = material.node_tree.nodes
    node_names = set(n.name for n in nodes)
    for o in (n for n in nodes if n.bl_idname in {"ShaderNodeOutput", "ShaderNodeOutputMaterial"}):
        if any(i.is_linked for i in o.inputs):
            node_names -= set(linked.name for linked in __enum_linked_nodes(o))
    for name in node_names:
        nodes.remove(nodes[name])


def convertToCyclesShader(obj: bpy.types.Object, use_principled: bool = False, clean_nodes: bool = False, subsurface: float = 0.001) -> None:
    logger.info(f"Converting {obj.name} to Cycles shader (use_principled={use_principled}, clean_nodes={clean_nodes})")
    __switchToCyclesRenderEngine()
    convertToBlenderShader(obj, use_principled, clean_nodes, subsurface)


def convertToBlenderShader(obj: bpy.types.Object, use_principled: bool = False, clean_nodes: bool = False, subsurface: float = 0.001) -> None:
    for i in obj.material_slots:
        if not i.material:
            continue
        if not i.material.use_nodes:
            logger.debug(f"Enabling nodes for material: {i.material.name}")
            i.material.use_nodes = True
            __convertToMMDBasicShader(i.material)
        if use_principled:
            logger.debug(f"Converting material to Principled BSDF: {i.material.name}")
            __convertToPrincipledBsdf(i.material, subsurface)
        if clean_nodes:
            __cleanNodeTree(i.material)

def convertToMMDShader(obj: bpy.types.Object) -> None:
    """BSDF -> MMDShaderDev conversion."""
    logger.info(f"Converting {obj.name} to MMD shader")
    for i in obj.material_slots:
        if not i.material:
            continue
        if not i.material.use_nodes:
            logger.debug(f"Enabling nodes for material: {i.material.name}")
            i.material.use_nodes = True
        FnMaterial.convert_to_mmd_material(i.material)

def __convertToMMDBasicShader(material: Material) -> None:
    logger.debug(f"Converting material to MMD Basic Shader: {material.name}")
    # TODO: test me
    mmd_basic_shader_grp = create_MMDBasicShader()
    mmd_alpha_shader_grp = create_MMDAlphaShader()

    if not any(filter(lambda x: isinstance(x, ShaderNodeGroup) and x.node_tree.name in {"MMDBasicShader", "MMDAlphaShader"}, material.node_tree.nodes)):
        # Add nodes for Cycles Render
        shader: ShaderNodeGroup = material.node_tree.nodes.new("ShaderNodeGroup")
        shader.node_tree = mmd_basic_shader_grp
        shader.inputs[0].default_value[:3] = material.diffuse_color[:3]
        shader.inputs[1].default_value[:3] = material.specular_color[:3]
        shader.inputs["glossy_rough"].default_value = 1.0 / getattr(material, "specular_hardness", 50)
        outplug = shader.outputs[0]

        location = shader.location.copy()
        location.x -= 1000

        alpha_value = 1.0
        if len(material.diffuse_color) > 3:
            alpha_value = material.diffuse_color[3]

        if alpha_value < 1.0:
            logger.debug(f"Material has alpha: {material.name}, alpha={alpha_value}")
            alpha_shader: ShaderNodeGroup = material.node_tree.nodes.new("ShaderNodeGroup")
            alpha_shader.location.x = shader.location.x + 250
            alpha_shader.location.y = shader.location.y - 150
            alpha_shader.node_tree = mmd_alpha_shader_grp
            alpha_shader.inputs[1].default_value = alpha_value
            material.node_tree.links.new(alpha_shader.inputs[0], outplug)
            outplug = alpha_shader.outputs[0]

        material_output: ShaderNodeOutputMaterial = __getMaterialOutput(material.node_tree.nodes, "ShaderNodeOutputMaterial")
        material.node_tree.links.new(material_output.inputs["Surface"], outplug)
        material_output.location.x = shader.location.x + 500
        material_output.location.y = shader.location.y - 150


def __convertToPrincipledBsdf(material: Material, subsurface: float) -> None:
    logger.debug(f"Converting material to Principled BSDF: {material.name}")
    node_names = set()
    for s in (n for n in material.node_tree.nodes if isinstance(n, ShaderNodeGroup)):
        if s.node_tree.name == "MMDBasicShader":
            l: NodeLink
            for l in s.outputs[0].links:
                to_node = l.to_node
                # assuming there is no bpy.types.NodeReroute between MMDBasicShader and MMDAlphaShader
                if isinstance(to_node, ShaderNodeGroup) and to_node.node_tree.name == "MMDAlphaShader":
                    __switchToPrincipledBsdf(material.node_tree, s, subsurface, node_alpha=to_node)
                    node_names.add(to_node.name)
                else:
                    __switchToPrincipledBsdf(material.node_tree, s, subsurface)
            node_names.add(s.name)
        elif s.node_tree.name == "MMDShaderDev":
            __switchToPrincipledBsdf(material.node_tree, s, subsurface)
            node_names.add(s.name)
    # remove MMD shader nodes
    nodes = material.node_tree.nodes
    for name in node_names:
        nodes.remove(nodes[name])


def __switchToPrincipledBsdf(node_tree: NodeTree, node_basic: ShaderNodeGroup, subsurface: float, node_alpha: Optional[ShaderNodeGroup] = None) -> None:
    logger.debug(f"Switching to Principled BSDF: {node_basic.name}")
    shader: Node = node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    shader.parent = node_basic.parent
    shader.location.x = node_basic.location.x
    shader.location.y = node_basic.location.y

    alpha_socket_name = "Alpha"
    if node_basic.node_tree.name == "MMDShaderDev":
        node_alpha, alpha_socket_name = node_basic, "Base Alpha"
        if "Base Tex" in node_basic.inputs and node_basic.inputs["Base Tex"].is_linked:
            node_tree.links.new(node_basic.inputs["Base Tex"].links[0].from_socket, shader.inputs["Base Color"])
        elif "Diffuse Color" in node_basic.inputs:
            shader.inputs["Base Color"].default_value[:3] = node_basic.inputs["Diffuse Color"].default_value[:3]
    elif "diffuse" in node_basic.inputs:
        shader.inputs["Base Color"].default_value[:3] = node_basic.inputs["diffuse"].default_value[:3]
        if node_basic.inputs["diffuse"].is_linked:
            node_tree.links.new(node_basic.inputs["diffuse"].links[0].from_socket, shader.inputs["Base Color"])

    shader.inputs["IOR"].default_value = 1.0
    shader.inputs["Subsurface Weight"].default_value = subsurface

    output_links = node_basic.outputs[0].links
    if node_alpha:
        output_links = node_alpha.outputs[0].links
        shader.parent = node_alpha.parent or shader.parent
        shader.location.x = node_alpha.location.x

        if alpha_socket_name in node_alpha.inputs:
            if "Alpha" in shader.inputs:
                shader.inputs["Alpha"].default_value = node_alpha.inputs[alpha_socket_name].default_value
                if node_alpha.inputs[alpha_socket_name].is_linked:
                    node_tree.links.new(node_alpha.inputs[alpha_socket_name].links[0].from_socket, shader.inputs["Alpha"])
            else:
                shader.inputs["Transmission"].default_value = 1 - node_alpha.inputs[alpha_socket_name].default_value
                if node_alpha.inputs[alpha_socket_name].is_linked:
                    node_invert = node_tree.nodes.new("ShaderNodeMath")
                    node_invert.parent = shader.parent
                    node_invert.location.x = node_alpha.location.x - 250
                    node_invert.location.y = node_alpha.location.y - 300
                    node_invert.operation = "SUBTRACT"
                    node_invert.use_clamp = True
                    node_invert.inputs[0].default_value = 1
                    node_tree.links.new(node_alpha.inputs[alpha_socket_name].links[0].from_socket, node_invert.inputs[1])
                    node_tree.links.new(node_invert.outputs[0], shader.inputs["Transmission"])

    for l in output_links:
        node_tree.links.new(shader.outputs[0], l.to_socket)
