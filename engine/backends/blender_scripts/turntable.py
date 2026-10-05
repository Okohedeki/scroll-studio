"""Render a 3D model as a scroll sequence: camera keys (yaw, pitch, zoom) and an explode amount over 0-1.

  blender -b --factory-startup -P turntable.py -- --model m.glb --out DIR --frames 120 --size 1920x1080
          --samples 96 --keys '[{"t":0,"yaw":-35,"pitch":18,"explode":0,"zoom":1}, ...]' --hdri studio

Output: DIR/frames/0001.png ... RGBA (transparent background, with a soft contact shadow).
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--frames", type=int, default=120)
ap.add_argument("--size", default="1920x1080")
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--keys", default="[]")
ap.add_argument("--hdri", default="studio")
ap.add_argument("--only", type=int, nargs="*", help="render just these frame numbers (previews)")
a = ap.parse_args(argv)
W, H = (int(v) for v in a.size.split("x"))
KEYS = sorted(json.loads(a.keys), key=lambda k: k["t"]) or [{"t": 0, "yaw": 0, "pitch": 15, "explode": 0, "zoom": 1}]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- import + normalise
ext = os.path.splitext(a.model)[1].lower()
if ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=a.model)
elif ext == ".obj":
    bpy.ops.wm.obj_import(filepath=a.model)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=a.model)
elif ext in (".stl",):
    bpy.ops.wm.stl_import(filepath=a.model)
else:
    raise SystemExit(f"unsupported model format {ext} (use glb, gltf, obj, fbx or stl)")

meshes = [o for o in scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("the model has no meshes")
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre, radius = (lo + hi) / 2, max((hi - lo).length / 2, 1e-6)
root = bpy.data.objects.new("Root", None)
scene.collection.objects.link(root)
for o in scene.objects:
    if o.parent is None and o is not root:
        o.parent = root
root.matrix_world = Matrix.Scale(1 / radius, 4) @ Matrix.Translation(-centre)
bpy.context.view_layer.update()

# explode: movable parts are meshes without a mesh ancestor; each moves away from the centre
def has_mesh_parent(o):
    p = o.parent
    while p:
        if p.type == "MESH":
            return True
        p = p.parent
    return False
parts = [o for o in meshes if not has_mesh_parent(o)]
base = {o.name: o.matrix_world.copy() for o in parts}
dirs = {}
def footprint(o):
    w = [o.matrix_world @ Vector(v) for v in o.bound_box]
    return (max(p.x for p in w) - min(p.x for p in w)) * (max(p.y for p in w) - min(p.y for p in w))
anchor = max(parts, key=footprint).name if len(parts) > 1 else None   # the base (board, chassis) stays put
for o in parts:
    c = sum((o.matrix_world @ Vector(v) for v in o.bound_box), Vector()) / 8
    lift = 0.22 + 0.3 * ((sum(map(ord, o.name)) * 2654435761) % 1000) / 1000   # staggered, deterministic
    dirs[o.name] = Vector((c.x * 0.35, c.y * 0.35, lift)) if o.name != anchor else Vector((0, 0, 0))

floor_z = min((o.matrix_world @ Vector(v)).z for o in meshes for v in o.bound_box)

# ---------------------------------------------------------------- look
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        if any(d.type == dev_type for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == dev_type
            scene.cycles.device = "GPU"
            break
    except TypeError:
        continue
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
nt = world.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment")
hdri = next((p for p in (os.path.join(bpy.utils.resource_path(k), "datafiles", "studiolights", "world", f"{a.hdri}.exr")
                          for k in ("LOCAL", "SYSTEM", "USER")) if os.path.exists(p)), None)
if hdri is None:
    raise SystemExit(f"studio light '{a.hdri}' not found in Blender's datafiles")
env.image = bpy.data.images.load(hdri)
bgn = nt.nodes["Background"]
bgn.inputs["Strength"].default_value = 1.0
nt.links.new(env.outputs["Color"], bgn.inputs["Color"])

def area(name, loc, energy, size):
    d = bpy.data.lights.new(name, "AREA"); d.energy = energy; d.size = size
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("Key", (2.6, -2.2, 3.0), 260, 2.5)
area("Rim", (-2.8, 2.4, 1.8), 160, 2.0)

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, floor_z))
floor = bpy.context.active_object
floor.is_shadow_catcher = True

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
fov = 2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens) * (min(W, H) / max(W, H) if W >= H else 1)
base_dist = 1.0 / math.sin(fov / 2) * 1.08

# ---------------------------------------------------------------- animation (evaluated per frame)
def at(t):
    if t <= KEYS[0]["t"]:
        return KEYS[0]
    for k0, k1 in zip(KEYS, KEYS[1:]):
        if t <= k1["t"]:
            u = (t - k0["t"]) / max(k1["t"] - k0["t"], 1e-6)
            u = u * u * (3 - 2 * u)
            return {f: k0.get(f, 0) + (k1.get(f, 0) - k0.get(f, 0)) * u for f in ("yaw", "pitch", "explode", "zoom")}
    return KEYS[-1]

os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
frames = a.only or range(1, a.frames + 1)
for f in frames:
    t = (f - 1) / max(a.frames - 1, 1)
    k = at(t)
    ex = k.get("explode", 0)
    for o in parts:
        v = dirs[o.name]
        o.matrix_world = Matrix.Translation(v * ex) @ base[o.name]
    yaw, pitch = math.radians(k.get("yaw", 0)), math.radians(k.get("pitch", 15))
    dist = base_dist * (1 + ex * 0.15) / max(k.get("zoom", 1), 0.05)
    cam.location = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * dist
    cam.rotation_euler = (-cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(a.out, "frames", f"{f:04d}.png")
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {f}/{a.frames}", flush=True)
