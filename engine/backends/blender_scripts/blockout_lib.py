"""Shared helpers for headless Blender blockout scripts.

Run a shot script with:
  blender -b --factory-startup -P blender/<shot>.py -- --out <dir> --fps 24 --duration 10 --res 1280x720
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--duration", type=float, default=10)
    p.add_argument("--res", default="1280x720")
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--stills", type=float, nargs="*", help="render only these seconds as PNG stills")
    a = p.parse_args(argv)
    a.out = os.path.abspath(a.out)
    a.width, a.height = (int(v) for v in a.res.split("x"))
    a.frames = int(round(a.fps * a.duration))
    return a


def reset_scene(args, sky=(0.55, 0.68, 0.85)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.fps = args.fps
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.frame_start = 1
    scene.frame_end = args.frames
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "OBJECT"
    shading.show_shadows = True
    shading.shadow_intensity = 0.6
    shading.show_cavity = True
    scene.display.light_direction = (0.4, -0.3, 0.85)
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("World")
    world.color = sky
    scene.world = world
    return scene


def _finish(obj, name, color):
    obj.name = name
    obj.color = (*color, 1.0)
    return obj


def box(name, loc, size, color):
    """Axis-aligned box; size is full width/depth/height."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.scale = size
    return _finish(obj, name, color)


def cylinder(name, loc, radius, depth, color, rotation=(0, 0, 0), vertices=32, scale=(1, 1, 1),
             capped=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                        location=loc, rotation=rotation,
                                        end_fill_type="NGON" if capped else "NOTHING")
    obj = bpy.context.active_object
    obj.scale = scale
    return _finish(obj, name, color)


def cone(name, loc, radius, depth, color, vertices=4):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, depth=depth, location=loc)
    return _finish(bpy.context.active_object, name, color)


def blob(name, loc, scale, color, soft=False):
    """soft=True: visible in the preview but left out of the depth guide (clouds, smoke, haze),
    so the video model paints them from the prompt instead of treating them as solid shapes."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, location=loc)
    obj = bpy.context.active_object
    obj.scale = scale
    if soft:
        coll = bpy.data.collections.get("Soft") or bpy.data.collections.new("Soft")
        if coll.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(coll)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
    return _finish(obj, name, color)


def plane(name, loc, size, color):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.scale = (size[0], size[1], 1)
    return _finish(obj, name, color)


def shell(obj, thickness):
    """Turn an open surface into a thin solid wall (so booleans cut holes, not pockets)."""
    mod = obj.modifiers.new("shell", "SOLIDIFY")
    mod.thickness = thickness
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cut(target, cutter):
    """Boolean-subtract cutter from target, then delete the cutter."""
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def camera_rig(keys, lens=28, clip_end=2000):
    """keys: list of (seconds, camera_location, look_at_target). Bezier-eased between keys."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = lens
    cam_data.clip_start = 0.1
    cam_data.clip_end = clip_end
    cam = bpy.data.objects.new("Camera", cam_data)
    target = bpy.data.objects.new("CameraTarget", None)
    scene.collection.objects.link(cam)
    scene.collection.objects.link(target)
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    for sec, loc, look in keys:
        frame = 1 + round(sec * scene.render.fps)
        cam.location = loc
        target.location = look
        cam.keyframe_insert("location", frame=frame)
        target.keyframe_insert("location", frame=frame)
    scene.camera = cam
    return cam, target


def export_camera_json(cam, target, args, path):
    """Per-half-second camera samples, used to write the motion prompt from real numbers."""
    scene = bpy.context.scene
    samples = []
    steps = int(args.duration * 2)
    for i in range(steps + 1):
        sec = i / 2
        scene.frame_set(min(args.frames, 1 + round(sec * args.fps)))
        m = cam.matrix_world
        fwd = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
        samples.append({
            "t": sec,
            "position": [round(v, 2) for v in m.translation],
            "look_at": [round(v, 2) for v in target.matrix_world.translation],
            "pitch_deg": round(math.degrees(math.asin(max(-1, min(1, fwd.z)))), 1),
            "heading_deg": round(math.degrees(math.atan2(fwd.x, fwd.y)), 1),
        })
    with open(path, "w") as f:
        json.dump({"fps": args.fps, "lens_mm": cam.data.lens, "samples": samples}, f, indent=2)


def setup_depth_output(out_dir, far_clip=400.0):
    """Write a per-frame depth map (near = white) next to every beauty frame.

    Log depth, normalised per frame and inverted: keeps structure readable both
    in the cabin (z ~ 1) and over the city (z ~ 100) even when a wing or cloud
    passes close to the lens. Sky is clamped to the far plane -> black.
    """
    scene = bpy.context.scene
    beauty_layer = bpy.context.view_layer
    depth_layer = scene.view_layers.new("Depth")
    depth_layer.use_pass_z = True
    soft = depth_layer.layer_collection.children.get("Soft")
    if soft:
        soft.exclude = True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    beauty = tree.nodes.new("CompositorNodeRLayers")
    beauty.layer = beauty_layer.name
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.layer = depth_layer.name
    comp = tree.nodes.new("CompositorNodeComposite")
    tree.links.new(beauty.outputs["Image"], comp.inputs["Image"])

    def math(op, a, b=None, value=None):
        node = tree.nodes.new("CompositorNodeMath")
        node.operation = op
        tree.links.new(a, node.inputs[0])
        if b is not None:
            tree.links.new(b, node.inputs[1])
        elif value is not None:
            node.inputs[1].default_value = value
        return node.outputs[0]

    far = math("MINIMUM", rl.outputs["Depth"], value=far_clip)
    logz = math("LOGARITHM", math("MAXIMUM", far, value=0.05), value=2.718281828)
    norm = tree.nodes.new("CompositorNodeNormalize")
    tree.links.new(logz, norm.inputs[0])
    invert = tree.nodes.new("CompositorNodeMath")
    invert.operation = "SUBTRACT"
    invert.inputs[0].default_value = 1.0
    tree.links.new(norm.outputs[0], invert.inputs[1])
    fout = tree.nodes.new("CompositorNodeOutputFile")
    fout.base_path = out_dir
    fout.format.file_format = "PNG"
    fout.format.color_mode = "BW"
    fout.file_slots[0].path = "####"
    tree.links.new(invert.outputs[0], fout.inputs[0])


def render(args, cam, target, depth_far=400.0):
    os.makedirs(args.out, exist_ok=True)
    export_camera_json(cam, target, args, os.path.join(args.out, "camera.json"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(args.out, "blockout.blend"))
    if args.no_render:
        return
    scene = bpy.context.scene
    setup_depth_output(os.path.join(args.out, "depth", ""), far_clip=depth_far)
    scene.render.image_settings.file_format = "PNG"
    if args.stills:
        for sec in args.stills:
            scene.frame_set(min(args.frames, 1 + round(sec * args.fps)))
            scene.render.filepath = os.path.join(args.out, "stills", f"t{sec:05.2f}.png")
            bpy.ops.render.render(write_still=True)
        return
    scene.render.filepath = os.path.join(args.out, "frames", "")
    bpy.ops.render.render(animation=True)
