"""Render a still of a normalised product GLB (engine/product.py) in a studio light.

  blender -b --factory-startup -P product_still.py -- --glb product.glb --out still.png --size 1600x1200
          --view '{"yaw": -35, "pitch": 20, "zoom": 1, "explode": 0, "lens": 50, "low": false}'
          --samples 96 --hdri studio --shadow 1

Output: an RGBA PNG (transparent film, with a soft contact shadow caught on an invisible floor). The camera is
fitted to the product's (exploded) bounds and shifted so the product sits centred in the frame.

  --camera cam.json   also write the camera (matrix, lens, sensor, shift, floor) for a perspective-matched backdrop
  --env env.json      light it with an environment built from a backdrop ({"file", "ground", "sun", "sun_strength"})
                      instead of the studio
  --mask mask.png     also write the product's own alpha (no shadow), for compositing checks
"""
import argparse
import fnmatch
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--size", default="1600x1200")
ap.add_argument("--view", default="{}")
ap.add_argument("--samples", type=int, default=96)
ap.add_argument("--hdri", default="studio")
ap.add_argument("--shadow", type=int, default=1)
ap.add_argument("--camera", default=None)
ap.add_argument("--env", default=None)
ap.add_argument("--mask", default=None)
a = ap.parse_args(argv)
W, H = (int(v) for v in a.size.split("x"))
V = json.loads(a.view)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=a.glb)
meshes = [o for o in scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("the product GLB has no meshes")

# normalise to unit radius so the lights work for a watch or a car alike
bpy.context.view_layer.update()


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


lo, hi = bounds(meshes)
radius = max((hi - lo).length / 2, 1e-6)
root = bpy.data.objects.new("Root", None)
scene.collection.objects.link(root)
for o in list(scene.objects):
    if o.parent is None and o is not root:
        o.parent = root
root.matrix_world = Matrix.Scale(1 / radius, 4)
bpy.context.view_layer.update()

# explode: offsets come from the GLB (ss_explode, metres, glTF axes)
ex = float(V.get("explode", 0) or 0)
if ex:
    for o in meshes:
        off = o.get("ss_explode")
        if off is None:
            continue
        v = Vector((off[0], -off[2], off[1])) / radius * ex
        o.matrix_world = Matrix.Translation(v) @ o.matrix_world
    bpy.context.view_layer.update()
lo, hi = bounds(meshes)
floor_z = lo.z if not ex else min(lo.z, 0.0)


def names_of(o):
    out, p = [o.name, o.data.name], o.parent
    while p and p is not root:
        out.append(p.name)
        p = p.parent
    return [n.lower() for n in out]


focus = meshes
if V.get("part"):
    pat = V["part"].lower()
    focus = [o for o in meshes if any(fnmatch.fnmatchcase(n, pat) for n in names_of(o))]
    if not focus:
        raise SystemExit(f"no part matches {V['part']!r} (studio product <project> --parts lists the names)")


def sample_points(objs, cap=40000):
    """World positions of the objects' vertices (evenly thinned), for framing on the real silhouette."""
    deps = bpy.context.evaluated_depsgraph_get()
    total = sum(len(o.data.vertices) for o in objs) or 1
    step = max(1, total // cap)
    pts = []
    for o in objs:
        M = o.evaluated_get(deps).matrix_world
        vs = o.data.vertices
        pts += [M @ vs[i].co for i in range(0, len(vs), step)]
    return pts


FOCUS = bool(V.get("part") or V.get("region"))   # a detail: frame and aim at part of the product
normal_sum = Vector((0, 0, 0))
if V.get("region"):
    # a box in 0-1 of the product's bounds (as PartMaterial.region): the vertices inside it, and the faces' normals
    r = V["region"]
    size = Vector((max(hi.x - lo.x, 1e-9), max(hi.y - lo.y, 1e-9), max(hi.z - lo.z, 1e-9)))
    deps = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in focus:
        M = o.evaluated_get(deps).matrix_world
        N = M.to_3x3().inverted_safe().transposed()
        for poly in o.data.polygons:
            c = M @ poly.center
            u = [(c[i] - lo[i]) / size[i] for i in range(3)]
            if all(r[i] <= u[i] <= r[i + 3] for i in range(3)):
                pts += [M @ o.data.vertices[v].co for v in poly.vertices]
                normal_sum += (N @ poly.normal).normalized() * poly.area
    if not pts:
        raise SystemExit(f"no faces in region {r}")
else:
    pts = sample_points(focus)
    if FOCUS:
        deps = bpy.context.evaluated_depsgraph_get()
        for o in focus:
            M = o.evaluated_get(deps).matrix_world
            N = M.to_3x3().inverted_safe().transposed()
            for poly in o.data.polygons[::max(1, len(o.data.polygons) // 4000)]:
                normal_sum += (N @ poly.normal).normalized() * poly.area
flo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
fhi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))

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
scene.cycles.use_adaptive_sampling = True
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
try:   # Khronos PBR Neutral keeps product colours true (AgX washes saturated plastics out)
    scene.view_settings.view_transform = "Khronos PBR Neutral"
except TypeError:
    scene.view_settings.view_transform = "AgX"
scene.view_settings.exposure = float(V.get("exposure", 0) or 0)
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
ENV = None
if a.env:
    with open(a.env, encoding="utf-8") as f:
        ENV = json.load(f)
    env.image = bpy.data.images.load(ENV["file"])
# reflections see the studio HDRI; diffuse light from the world is an even grey, so the only shadows are the soft
# ones from the area lights (an HDRI's own sun throws long streaks across the shadow catcher)
path = nt.nodes.new("ShaderNodeLightPath")
mix = nt.nodes.new("ShaderNodeMixRGB")
mix.inputs["Color1"].default_value = (0.32, 0.32, 0.33, 1.0)
nt.links.new(path.outputs["Is Glossy Ray"], mix.inputs["Fac"])
nt.links.new(env.outputs["Color"], mix.inputs["Color2"])
nt.links.new(mix.outputs["Color"], nt.nodes["Background"].inputs["Color"])
nt.nodes["Background"].inputs["Strength"].default_value = 1.0
if ENV:      # the backdrop's own light, for every ray type
    nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = float(ENV.get("strength", 1.0))

if V.get("aim") and FOCUS:   # detail: look at the part from the way its surfaces face
    n = normal_sum.normalized() if normal_sum.length > 1e-9 else ((fhi + flo) / 2 - (hi + lo) / 2).normalized()
    if n.z > 0.8:          # facing up: from above and a little in front, so it keeps its perspective
        V.setdefault("yaw", -22)
        V.setdefault("pitch", 52)
    else:
        V.setdefault("yaw", math.degrees(math.atan2(n.x, -n.y)) + 18)
        V.setdefault("pitch", max(10.0, min(60.0, math.degrees(math.asin(max(-1.0, min(1.0, n.z)))) + 14)))
yaw = math.radians(float(V.get("yaw", -35)))
pitch = math.radians(float(V.get("pitch", 20)))
# the lights follow the camera's yaw, so every view is lit from its front-left like a product shoot
fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))
right = Vector((math.cos(yaw), math.sin(yaw), 0))


def area(name, loc, energy, size, shadow=True):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size = energy, size
    d.use_shadow = shadow     # only the key casts a shadow: one soft contact shadow, no streaks
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = ((hi + lo) / 2 - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


c = (hi + lo) / 2
if ENV:
    # the backdrop's brightest region becomes a sun, so the shadow falls the way the scene's light does
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = 0.6 + 0.45 * float(ENV.get("sun_strength", 2.0))   # overcast (low contrast): a soft, weak sun
    sd.angle = math.radians(6)
    sun = bpy.data.objects.new("Sun", sd)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (-Vector(ENV.get("sun", (0.3, -0.4, 0.8))).normalized()).to_track_quat("-Z", "Y").to_euler()
    area("Rim", c - fwd * 2.8 + right * 1.6 + Vector((0, 0, 2.2)), 60, 2.0, shadow=False)
else:
    area("Key", c + fwd * 2.2 - right * 2.0 + Vector((0, 0, 3.6)), 240, 3.0)
    area("Fill", c + fwd * 3.0 + right * 2.8 + Vector((0, 0, 0.8)), 70, 3.0, shadow=False)
    area("Rim", c - fwd * 2.8 + right * 1.6 + Vector((0, 0, 2.2)), 170, 2.0, shadow=False)

catcher = None
if a.shadow:
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, floor_z))
    catcher = bpy.context.active_object
    catcher.is_shadow_catcher = True
    if ENV and ENV.get("ground"):
        gm = bpy.data.materials.new("Ground")
        gm.use_nodes = True
        gb = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        gb.inputs["Base Color"].default_value = (*ENV["ground"], 1.0)
        gb.inputs["Roughness"].default_value = 0.8
        catcher.data.materials.append(gm)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = float(V.get("lens") or 50)
cam_data.sensor_fit = "AUTO"
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam_data.clip_start, cam_data.clip_end = 0.01, 100

target = (flo + fhi) / 2
if V.get("low"):
    target.z = flo.z + (fhi.z - flo.z) * 0.6
dirv = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
# the product's silhouette fills about two thirds of the frame (a detail view's part a little more)
fill = min(0.98, (0.74 if FOCUS else 0.68) * float(V.get("zoom", 1) or 1))


def exit_distance():
    """How far along the view ray the camera must be to stand outside the whole product's bounds."""
    t = 1e3      # the ray leaves the box through the first face it crosses
    for i in range(3):
        if abs(dirv[i]) > 1e-6:
            t = min(t, max((lo[i] - target[i]) / dirv[i], (hi[i] - target[i]) / dirv[i]))
    return max(t, 0.0) * 1.02 + 0.02


def place(dist):
    cam.location = target + dirv * dist
    if V.get("low"):
        cam.location.z = max(cam.location.z, floor_z + 0.03)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.shift_x = cam_data.shift_y = 0
    bpy.context.view_layer.update()


def extent():
    proj = [world_to_camera_view(scene, cam, p) for p in pts]
    if any(p.z <= 0 for p in proj):
        return None
    xs, ys = [p.x for p in proj], [p.y for p in proj]
    return min(xs), max(xs), min(ys), max(ys)


# the shortest distance at which the silhouette fits inside `fill` of the frame (binary search on distance)
if len(pts) > 4000:
    pts = pts[::len(pts) // 4000]
if len(focus) > 1:      # thinning must never lose a part's extremes: add every part's own bounds
    pts += [o.matrix_world @ Vector(c) for o in focus for c in o.bound_box]
near, far = (exit_distance() if FOCUS else 0.05), 60.0
for _ in range(36):
    mid = (near + far) / 2
    place(mid)
    e = extent()
    if e is None or (e[1] - e[0]) > fill or (e[3] - e[2]) > fill:
        near = mid
    else:
        far = mid
place(far)
x0, x1, y0, y1 = extent()
# centre the product with lens shift (keeps the perspective of the chosen angle)
k = max(W, H)
px, py = V.get("place") or (0.5, 0.5)    # where the product's centre sits in the frame (x right, y down)
cam_data.shift_x = ((x0 + x1) / 2 - float(px)) * W / k
cam_data.shift_y = ((y0 + y1) / 2 - (1 - float(py))) * H / k

fstop = V.get("fstop") or (8.0 if FOCUS and V.get("aim") else None)
if fstop:
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = (target - cam.location).length
    cam_data.dof.aperture_fstop = float(fstop) * radius   # the scene is scaled to unit radius: keep the real-size blur
if a.camera:
    m = cam.matrix_world
    with open(a.camera, "w", encoding="utf-8") as f:
        json.dump({"matrix": [list(r) for r in m], "lens": cam_data.lens, "sensor": cam_data.sensor_width,
                   "shift": [cam_data.shift_x, cam_data.shift_y], "size": [W, H], "floor": floor_z,
                   "radius": radius, "target": list(target)}, f)
scene.render.filepath = os.path.abspath(a.out)
bpy.ops.render.render(write_still=True)
if a.mask:     # the product's own alpha: no shadow catcher, a few samples
    if catcher is not None:
        catcher.hide_render = True
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
    scene.render.filepath = os.path.abspath(a.mask)
    bpy.ops.render.render(write_still=True)
print(f"STILL {a.out}", flush=True)
