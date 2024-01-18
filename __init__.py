# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "ProjectionStencil",
    "author": "BDFFZI",
    "description": "基于投影法移植贴图的便利小工具，请在贴图绘制模式下使用。",
    "blender": (3, 3, 10),
    "version": (1, 0, 0),
    "location": "",
    "warning": "",
    "category": "Generic",
}

from cgitb import text
import os
from typing import Set
import bpy
import tempfile


def get(prop: str):
    return getattr(bpy.context.scene.pstencil_props, prop, None)


def set(prop: str, value):
    setattr(bpy.context.scene.pstencil_props, prop, value)


class UpdatePStencil(bpy.types.Operator):
    bl_idname = "pstencil.init"
    bl_label = ""
    bl_description = """使用说明：
1. 将被参照物体的材质设置为“自发光”从而完美移植贴图颜色。
2. 将被参照物之外的物体设置为渲染不可见，以防不必要的物体出现在镂版上。
"""

    def execute(self, context):
        # 环境初始化
        camera = context.scene.camera
        if camera == None:
            self.report({"ERROR"}, "场景中没有可用的相机")
            return {"CANCELLED"}
        material = context.active_object.active_material
        if material == None:
            self.report({"ERROR"}, "当前绘制物体没有材质")
            return {"CANCELLED"}
        images = material.texture_paint_images
        image = images[material.paint_active_slot] if images else None
        if image == None:
            self.report({"ERROR"}, "材质上没有可绘制的贴图")
            return {"CANCELLED"}

        # 纹理初始化
        texture = get("texture")
        if texture == None:
            texture = bpy.data.textures.new(name="投影镂版", type="IMAGE")
            set("texture", texture)

        # 笔刷初始化
        brush = context.tool_settings.image_paint.brush
        brush.texture = texture
        brush.texture_slot.map_mode = "STENCIL"

        # 摄像机到视图视角
        camera.data.lens = context.area.spaces.active.lens / 2
        if context.area.spaces[0].region_3d.view_perspective != "CAMERA":
            bpy.ops.view3d.camera_to_view()

        # 渲染图片
        path = os.path.join(tempfile.gettempdir(), "pstencil.png")
        context.scene.render.image_settings.file_format = "PNG"
        context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        if texture.image == None:
            texture.image = bpy.data.images.load(path, check_existing=True)
        else:
            texture.image.reload()

        return {"FINISHED"}


def GetRegionSize():
    # 当前区域分辨率
    region = next(r for r in bpy.context.area.regions if r.type == "WINDOW")
    width = region.width
    height = region.height
    return [width, height]


def SetStencil(position, size=None):
    brush = bpy.context.tool_settings.image_paint.brush
    brush.stencil_pos = position
    brush.stencil_dimension = size


class AdaptionPStencil(bpy.types.Operator):
    bl_idname = "pstencil.adaption"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return bpy.ops.view3d.view_center_camera.poll()

    def execute(self, context):
        regionSize = GetRegionSize()

        # 相机视图全屏
        context.scene.render.resolution_x = regionSize[0] * 2
        context.scene.render.resolution_y = regionSize[1] * 2
        bpy.ops.view3d.view_center_camera()

        # 镂版全屏
        vector2 = (regionSize[0] / 2, regionSize[1] / 2)
        SetStencil(vector2, vector2)

        return {"FINISHED"}


class ResetPStencil(bpy.types.Operator):
    bl_idname = "pstencil.reset"
    bl_label = ""

    @classmethod
    def poll(cls, context):
        return (
            bpy.ops.brush.stencil_fit_image_aspect.poll()
            and bpy.ops.brush.stencil_reset_transform.poll()
        )

    def execute(self, context):
        # 相机重置
        context.area.spaces.active.region_3d.view_camera_offset = (0, 0)
        context.area.spaces.active.region_3d.view_camera_zoom = 0

        # 镂版重置
        bpy.ops.brush.stencil_reset_transform()
        bpy.ops.brush.stencil_fit_image_aspect()

        return {"FINISHED"}


class PStencilPanel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_category = "投影镂版"
    bl_region_type = "UI"
    bl_label = "投影镂版"

    @classmethod
    def poll(cls, context):
        return context.mode == "PAINT_TEXTURE"

    # 面板显示的内容
    def draw(self, context):
        layout = self.layout

        layout.operator(AdaptionPStencil.bl_idname, text="调整镂版至全屏状态")
        layout.operator(ResetPStencil.bl_idname, text="调整镂版至初始状态")

        column = layout.box().column(align=True)
        column.label(text="投影参数")
        column.prop(context.scene.render, "resolution_x")
        column.prop(context.scene.render, "resolution_y")
        column.prop(context.area.spaces.active, "lens")

        layout.operator(UpdatePStencil.bl_idname, text="投影并进入绘制模式")
        layout.label(text="鼠标悬停在上方按钮以查看说明")
        # layout.operator("view3d.view_center_camera", text="重置摄像机视图")


class Properties(bpy.types.PropertyGroup):
    texture: bpy.props.PointerProperty(type=bpy.types.Texture)
    render: bpy.props.PointerProperty(type=bpy.types.Image)


classes = [
    Properties,
    PStencilPanel,
    UpdatePStencil,
    AdaptionPStencil,
    ResetPStencil,
]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.pstencil_props = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.pstencil_props
    for c in classes:
        bpy.utils.unregister_class(c)
