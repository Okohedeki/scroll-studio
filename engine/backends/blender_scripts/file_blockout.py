"""Blockout from the user's own .blend: render its active camera's animation plus the depth pass.

  blender -b scene.blend --python file_blockout.py -- --out DIR --fps 24 --duration 18 --res 1280x720

The scene can be as rough as you like (grey boxes); only camera motion, layout and depth matter.
Put clouds, smoke and other soft things in a collection named "Soft" to keep them out of the depth pass.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blockout_lib import parse_args, setup_depth_output  # noqa: E402

args = parse_args()
scene = bpy.context.scene
if scene.camera is None:
    raise SystemExit("the .blend has no active camera; add one and animate it")
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.view_settings.view_transform = "Standard"
scene.render.fps = args.fps
scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
scene.render.resolution_percentage = 100
scene.frame_end = scene.frame_start + args.frames - 1
os.makedirs(args.out, exist_ok=True)
setup_depth_output(os.path.join(args.out, "depth", ""), far_clip=float(os.environ.get("DEPTH_FAR", 400)))
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = os.path.join(args.out, "frames", "")
bpy.ops.render.render(animation=True)
