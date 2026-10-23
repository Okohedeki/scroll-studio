"""A take: the world blockout and the product pass, rendered through one and the same camera.

  blender -b --factory-startup -P take.py -- --take take.json --pass world   --out DIR --res 1280x720
  blender -b --factory-startup -P take.py -- --take take.json --pass product --out DIR --res 1920x1080 --samples 64 [--env env.json]
  blender -b --factory-startup -P take.py -- --take take.json --pass track   --out DIR --res 1920x1080

take.json is the spec's `take` mapping (see engine/spec.py Take) plus "product_file", the resolved model path.

world:    Workbench beauty frames + the depth guide for the video model (depth/####.png), camera.json. The product
          mesh is in this pass too, so the guide tells the model something solid stands there.
product:  Cycles, transparent film: only the product, lit by a studio HDRI and a sun along the take's light
          direction, with its shadow caught on an invisible ground at its base. frames/####.png, RGBA.
          With --env (engine/scenes/film_build.py stage_plate_env) the light is the plate itself: environments
          built from the generated frames, blended over time, and the ground the shadow falls on takes the plate's
          colour. Depth of field focuses where the camera looks; motion blur follows the camera.
track:    no render: per frame, the camera and the product's place on screen -> track.json (normalised 0-1, y down).

Both passes build the camera from the same keys with the same fps, so frame i of one pass is frame i of the other.
"""
import argparse
import json
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blockout_lib import blob, box, camera_rig, cone, cylinder, plane, render, reset_scene  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--take", required=True)
ap.add_argument("--pass", dest="which", choices=["world", "product", "track"], required=True)
ap.add_argument("--env", default=None, help="product: env.json of plate environments (else the studio light `hdri`)")
ap.add_argument("--out", required=True)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=64)
ap.add_argument("--only", type=int, nargs="*", help="product: render just these frame numbers")
a = ap.parse_args(argv)
with open(a.take, encoding="utf-8") as f:
    T = json.load(f)
a.out = os.path.abspath(a.out)
a.fps = int(T.get("fps", 24))
a.duration = float(T["duration"])
a.width, a.height = (int(v) for v in a.res.split("x"))
a.frames = int(round(a.fps * a.duration))
a.no_render = False
a.stills = None


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rad(deg):
    return tuple(math.radians(v) for v in deg)


# ---------------------------------------------------------------- world shapes
def build_world():
    g = T.get("ground") or {"kind": "plane", "at": [0, 0, 0], "size": [400, 400, 1], "color": "#55604a"}
    plane("Ground", tuple(g["at"]), (g["size"][0], g["size"][1]), hexrgb(g["color"]))
    for i, o in enumerate(T.get("objects", [])):
        name = o.get("name") or f"{o['kind']}{i}"
        at, col = tuple(o["at"]), hexrgb(o["color"])
        rot = rad(o.get("rotation", (0, 0, 0)))
        if o["kind"] == "box":
            box(name, at, tuple(o["size"]), col).rotation_euler = rot
        elif o["kind"] == "plane":
            plane(name, at, (o["size"][0], o["size"][1]), col).rotation_euler = rot
        elif o["kind"] == "cylinder":
            cylinder(name, at, o["radius"], o["depth"], col, rotation=rot)
        elif o["kind"] == "cone":
            cone(name, at, o["radius"], o["depth"], col, vertices=32).rotation_euler = rot
        elif o["kind"] == "blob":
            blob(name, at, tuple(o["size"]), col, soft=o.get("soft", False))
        elif o["kind"] == "scatter":
            rng = random.Random(o.get("seed", 1))
            x0, y0, x1, y1 = o["area"]
            h0, h1 = o["height"]
            f0, f1 = o["footprint"]
            clear = o.get("clear")
            for j in range(o.get("count", 40)):
                x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
                if clear and math.hypot(x - clear[0], y - clear[1]) < clear[2]:
                    continue
                h, w, d = rng.uniform(h0, h1), rng.uniform(f0, f1), rng.uniform(f0, f1)
                shade = rng.uniform(0.8, 1.1)
                c = tuple(min(1, c * shade) for c in col)
                if o.get("shape", "box") == "cone":   # trees: a cone reads as a pine to the video model
                    cone(f"{name}_{j}", (x, y, at[2] + h / 2), (w + d) / 4, h, c, vertices=12)
                else:
                    box(f"{name}_{j}", (x, y, at[2] + h / 2), (w, d, h), c)


# ---------------------------------------------------------------- the product
def import_model(path):
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    else:
        raise SystemExit(f"unsupported product model {ext} (glb, gltf, obj, fbx, stl, ply)")
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise SystemExit("the product model has no meshes")
    if ext == ".ply":
        # vertex-coloured meshes (e.g. TRELLIS.2 output) get a material that shows the colours
        for o in meshes:
            mat = bpy.data.materials.new("VertexColour")
            mat.use_nodes = True
            nt = mat.node_tree
            attr = nt.nodes.new("ShaderNodeVertexColor")
            attr.layer_name = o.data.color_attributes[0].name if o.data.color_attributes else "Col"
            bsdf = nt.nodes["Principled BSDF"]
            bsdf.inputs["Roughness"].default_value = 0.6
            nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
            o.data.materials.clear()
            o.data.materials.append(mat)
    return new, meshes


def place_product(p):
    """Import, scale to `height`, stand the base centre on `at`, apply rotation and the slow spin."""
    new, meshes = import_model(T["product_file"])
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
    hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
    scale = float(p.get("height") or 1.0) / max(hi.z - lo.z, 1e-6)
    root = bpy.data.objects.new("Product", None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
    # inner pivot: centre the base on the origin, then scale; the root carries placement and spin
    pivot = Matrix.Scale(scale, 4) @ Matrix.Translation(-Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)))
    for o in new:
        if o.parent is root:
            o.matrix_parent_inverse = pivot
    root.location = Vector(p["at"])
    rx, ry, rz = rad(p.get("rotation", (0, 0, 0)))
    root.rotation_euler = (rx, ry, rz)
    root.keyframe_insert("rotation_euler", frame=1)
    root.rotation_euler = (rx, ry, rz + math.radians(p.get("spin", 0)))
    root.keyframe_insert("rotation_euler", frame=a.frames)
    for fc in root.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return root, meshes


# ---------------------------------------------------------------- passes
P = T.get("product")
if a.which == "world":
    reset_scene(a, sky=hexrgb(T.get("sky", "#8fb4d8")))
    bpy.context.scene.display.light_direction = tuple(T.get("light", (0.4, -0.3, 0.85)))
    build_world()
    if P and T.get("product_in_guide"):
        _, meshes = place_product(P)
        for o in meshes:
            o.color = (0.62, 0.62, 0.6, 1.0)
    keys = [(k["t"], tuple(k["at"]), tuple(k["look"])) for k in T["camera"]]
    cam, target = camera_rig(keys, lens=T.get("lens", 32))
    render(a, cam, target, depth_far=float(T.get("depth_far", 400)))
    print(f"WORLD {a.frames} frames -> {a.out}", flush=True)
    raise SystemExit(0)

# product pass
if not P:
    raise SystemExit("this take has no product")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = a.fps
scene.frame_start, scene.frame_end = 1, a.frames
scene.render.resolution_x, scene.render.resolution_y = a.width, a.height
scene.render.resolution_percentage = 100
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
scene.cycles.use_adaptive_sampling = True
scene.render.use_persistent_data = True   # keep the scene on the GPU between frames
scene.render.film_transparent = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

root, meshes = place_product(P)

if a.which == "track":
    from bpy_extras.object_utils import world_to_camera_view
    keys = [(k["t"], tuple(k["at"]), tuple(k["look"])) for k in T["camera"]]
    cam, target = camera_rig(keys, lens=T.get("lens", 32))
    out = []
    for fi in range(1, a.frames + 1):
        scene.frame_set(fi)
        deps = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in meshes:
            ev = o.evaluated_get(deps)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        proj = [world_to_camera_view(scene, cam, q) for q in pts]
        front = [q for q in proj if q.z > 0]
        base = world_to_camera_view(scene, cam, Vector(P["at"]))
        lo_ = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi_ = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        centre = world_to_camera_view(scene, cam, (lo_ + hi_) / 2)
        rec = {"f": fi, "t": round((fi - 1) / a.fps, 4), "visible": False,
               "camera": [list(r) for r in cam.matrix_world],
               "distance": round((cam.matrix_world.translation - (lo_ + hi_) / 2).length, 4)}
        if front and centre.z > 0:
            x0, x1 = min(q.x for q in front), max(q.x for q in front)
            y0, y1 = 1 - max(q.y for q in front), 1 - min(q.y for q in front)
            rec.update({"visible": x1 > 0 and x0 < 1 and y1 > 0 and y0 < 1,
                        "centre": [round(centre.x, 5), round(1 - centre.y, 5)],
                        "base": [round(base.x, 5), round(1 - base.y, 5)],
                        "box": [round(v, 5) for v in (x0, y0, x1, y1)]})
        out.append(rec)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "track.json"), "w", encoding="utf-8") as f:
        json.dump({"fps": a.fps, "size": [a.width, a.height], "lens": cam.data.lens, "sensor": cam.data.sensor_width,
                   "sensor_fit": cam.data.sensor_fit, "frames": out}, f)
    print(f"TRACK {len(out)} frames -> {a.out}", flush=True)
    raise SystemExit(0)

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
nt = world.node_tree
ENV = None
if a.env:
    with open(a.env, encoding="utf-8") as f:
        ENV = json.load(f)
env = nt.nodes.new("ShaderNodeTexEnvironment")
hdri = next((q for q in (os.path.join(bpy.utils.resource_path(k), "datafiles", "studiolights", "world", f"{P.get('hdri') or 'sunrise'}.exr")
                        for k in ("LOCAL", "SYSTEM", "USER")) if os.path.exists(q)), None)
if hdri is None:
    raise SystemExit(f"studio light '{P.get('hdri')}' not found in Blender's datafiles")
env.image = bpy.data.images.load(hdri)
# turn the HDRI so its own sun sits at the take's light azimuth: one shadow direction, matching the world
img = env.image
w, h = img.size
px = list(img.pixels[:])   # RGBA floats, bottom row first
best, bi = -1.0, 0
acc, cnt = [0.0, 0.0, 0.0], 0
for i in range(0, len(px), 4 * 3):   # every third pixel is plenty to find the sun
    lum = px[i] * 0.2126 + px[i + 1] * 0.7152 + px[i + 2] * 0.0722
    if lum > best:
        best, bi = lum, i // 4
    for c in range(3):
        acc[c] += min(px[i + c], 2.0)   # the sun disc would swamp the average
    cnt += 1
sky = tuple(v / max(cnt, 1) for v in acc)
u = (bi % w + 0.5) / w
sun_az = (u - 0.5) * 2 * math.pi                       # equirect: u = atan2(y, -x) / 2pi + 0.5
Lw = Vector(T.get("light", (0.4, -0.3, 0.85)))
light_az = math.atan2(Lw.y, -Lw.x)
coord = nt.nodes.new("ShaderNodeTexCoord")
mapping = nt.nodes.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (0.0, 0.0, light_az - sun_az + math.pi)
nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
# reflections see the HDRI; diffuse light and shadows come from its average colour, so the product gets a soft
# contact shadow and the sun lamp's crisp one, not a second long shadow from the HDRI's own (low) sun
path = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixRGB")
mix.inputs["Color1"].default_value = (*sky, 1.0)
nt.links.new(path.outputs["Is Glossy Ray"], mix.inputs["Fac"])
nt.links.new(env.outputs["Color"], mix.inputs["Color2"])
cam_mix = nt.nodes.new("ShaderNodeMixRGB")   # the camera never sees the world (transparent film), but keep it exact
nt.links.new(path.outputs["Is Camera Ray"], cam_mix.inputs["Fac"])
nt.links.new(mix.outputs["Color"], cam_mix.inputs["Color1"])
nt.links.new(env.outputs["Color"], cam_mix.inputs["Color2"])
nt.links.new(cam_mix.outputs["Color"], nt.nodes["Background"].inputs["Color"])
nt.nodes["Background"].inputs["Strength"].default_value = 1.0
if ENV:
    # plate-matched light: one environment per key time (built from the generated frame at that moment, in world
    # axes), cross-faded over the take, lighting and reflecting on the product for every ray type
    for n in list(nt.nodes):
        if n.type not in ("BACKGROUND", "OUTPUT_WORLD"):
            nt.nodes.remove(n)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    last = None
    keys_env = ENV["keys"]
    for i, k in enumerate(keys_env):
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(k["file"])
        tex.interpolation = "Cubic"
        nt.links.new(coord.outputs["Generated"], tex.inputs["Vector"])
        if last is None:
            last = tex.outputs["Color"]
            continue
        mixn = nt.nodes.new("ShaderNodeMixRGB")
        nt.links.new(last, mixn.inputs["Color1"])
        nt.links.new(tex.outputs["Color"], mixn.inputs["Color2"])
        f0 = 1 + round(keys_env[i - 1]["t"] * a.fps)
        f1 = 1 + round(k["t"] * a.fps)
        mixn.inputs["Fac"].default_value = 0.0
        mixn.inputs["Fac"].keyframe_insert("default_value", frame=f0)
        mixn.inputs["Fac"].default_value = 1.0
        mixn.inputs["Fac"].keyframe_insert("default_value", frame=f1)
        last = mixn.outputs["Color"]
    nt.links.new(last, nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = float(ENV.get("strength", 1.0))
if P.get("sun_strength", 3.0) > 0:
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = float(P["sun_strength"])
    sun_data.angle = math.radians(2.5)
    sun = bpy.data.objects.new("Sun", sun_data)
    scene.collection.objects.link(sun)
    d = Vector(T.get("light", (0.4, -0.3, 0.85))).normalized()
    sun.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()   # a sun lamp points along its -Z

SHADOW = float(P.get("shadow_size") or P["height"] * 3)
if P.get("shadow", True):
    # the catcher is the surface the product stands on (default 3x its height): shadows end at its edge
    # instead of streaking across the world
    bpy.ops.mesh.primitive_plane_add(size=SHADOW, location=(P["at"][0], P["at"][1], P["at"][2]))
    floor = bpy.context.active_object
    floor.is_shadow_catcher = True
    if ENV and ENV.get("ground"):
        # the surface it stands on takes the plate's colour, so bounce light and occlusion match the ground
        gm = bpy.data.materials.new("Ground")
        gm.use_nodes = True
        b = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (*ENV["ground"], 1.0)
        b.inputs["Roughness"].default_value = 0.8
        floor.data.materials.append(gm)

keys = [(k["t"], tuple(k["at"]), tuple(k["look"])) for k in T["camera"]]
cam, target = camera_rig(keys, lens=T.get("lens", 32))
if P.get("fstop"):            # focus where the camera looks, as the generated world does
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = target
    cam.data.dof.aperture_fstop = float(P["fstop"])
if float(P.get("motion_blur", 0) or 0) > 0:
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = float(P["motion_blur"])

from bpy_extras.object_utils import world_to_camera_view  # noqa: E402

FLOOR_Z = P["at"][2]

def on_screen_box():
    """The product's screen box (normalised, y up) including its shadow on the floor, or None when it is
    behind the camera, off-frame or under 3 px. Frames are rendered only inside this box."""
    deps = bpy.context.evaluated_depsgraph_get()
    world_pts = []
    for o in meshes:
        ev = o.evaluated_get(deps)
        world_pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    body = [world_to_camera_view(scene, cam, q) for q in world_pts]
    if all(p.z <= 0 for p in body):
        return None
    xs, ys = [p.x for p in body if p.z > 0], [p.y for p in body if p.z > 0]
    if max(xs) < 0 or min(xs) > 1 or max(ys) < 0 or min(ys) > 1:
        return None
    if max(max(xs) - min(xs), max(ys) - min(ys)) * max(a.width, a.height) < 3:
        return None
    if P.get("shadow", True):   # the shadow can fall anywhere on the catcher
        h = SHADOW / 2
        for dx, dy in ((-h, -h), (h, -h), (-h, h), (h, h)):
            v = world_to_camera_view(scene, cam, Vector((P["at"][0] + dx, P["at"][1] + dy, FLOOR_Z)))
            if v.z <= 0:
                return (0.0, 0.0, 1.0, 1.0)
            xs.append(v.x)
            ys.append(v.y)
    pad = 0.02
    box = (max(0.0, min(xs) - pad), max(0.0, min(ys) - pad), min(1.0, max(xs) + pad), min(1.0, max(ys) + pad))
    return box if box[2] > box[0] and box[3] > box[1] else None

os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
blank = None
frames = a.only or range(1, a.frames + 1)
for fi in frames:
    scene.frame_set(fi)
    path = os.path.join(a.out, "frames", f"{fi:04d}.png")
    screen_box = on_screen_box()
    if screen_box is None:   # too small or off-screen: an empty frame, no render
        if blank is None:
            blank = bpy.data.images.new("blank", a.width, a.height, alpha=True)
            blank.pixels[:] = [0.0] * (a.width * a.height * 4)
            blank.file_format = "PNG"
        blank.filepath_raw = path
        blank.save()
        print(f"FRAME {fi}/{a.frames} skipped", flush=True)
        continue
    # render only the product's region; the rest of the full-size frame stays transparent
    scene.render.use_border, scene.render.use_crop_to_border = True, False
    scene.render.border_min_x, scene.render.border_min_y, scene.render.border_max_x, scene.render.border_max_y = screen_box
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"FRAME {fi}/{a.frames}", flush=True)
