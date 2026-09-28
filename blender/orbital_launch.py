"""Blockout: launch pad -> lift-off -> through the cloud deck -> orbit -> stage + fairing separation -> satellite.

Units are roughly metres. The rocket rides an animated rig; stages, fairing halves and the satellite are
children with their own local animation for the separation beats.
"""
import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blockout_lib import (parse_args, reset_scene, box, cylinder, cone, blob, cut, camera_rig, render)

LIFTOFF = 1.5          # s
ACCEL = 61.5           # m/s^2 (toy value so the rocket clears the clouds around t = 8 s)
CLOUD_BASE, CLOUD_TOP = 1150, 1350
EARTH_R = 9000
STAGE_SEP, FAIRING_SEP, PANELS = 12.0, 13.5, 15.2

args = parse_args()
scene = reset_scene(args, sky=(0.32, 0.42, 0.6))
fps = args.fps


def rocket_z(t):
    if t <= LIFTOFF:
        return 1.0
    if t <= 10:
        return 1.0 + 0.5 * ACCEL * (t - LIFTOFF) ** 2
    return rocket_z(10) + ACCEL * (10 - LIFTOFF) * (t - 10)


def frame(t):
    return 1 + round(t * fps)


def key_loc(obj, t, loc):
    obj.location = loc
    obj.keyframe_insert("location", frame=frame(t))


def key_rot(obj, t, rot):
    obj.rotation_euler = rot
    obj.keyframe_insert("rotation_euler", frame=frame(t))


def key_scale(obj, t, s):
    obj.scale = s
    obj.keyframe_insert("scale", frame=frame(t))


def attach(child, parent):
    bpy.context.view_layer.update()  # parent.matrix_world must reflect its latest location
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    return child


# ---------------- Ground: Earth, pad, tower, site buildings ----------------
bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=EARTH_R, location=(0, 0, -EARTH_R))
earth = bpy.context.active_object
earth.name, earth.color = "Earth", (0.2, 0.34, 0.3, 1)

box("Pad", (0, 0, 0.5), (46, 46, 1), (0.62, 0.62, 0.6))
box("FlameTrench", (0, -30, 0.3), (10, 18, 0.6), (0.35, 0.35, 0.35))
box("ServiceTower", (9.5, 0, 30), (5, 5, 60), (0.45, 0.2, 0.15))
box("CrewArm", (5.5, 0, 44), (4, 1.2, 1.2), (0.45, 0.2, 0.15))
for sx in (-26, 26):
    for sy in (-26, 26):
        cylinder(f"Mast_{sx}_{sy}", (sx, sy, 38), 0.6, 76, (0.5, 0.5, 0.5), vertices=8)
cylinder("WaterTower", (70, 40, 22), 5, 12, (0.7, 0.7, 0.68))
cylinder("WaterTowerLeg", (70, 40, 8), 1.2, 16, (0.5, 0.5, 0.5), vertices=8)
rng = random.Random(3)
# Only the hangar near the camera. Flat boxes sitting on the far horizon behind the pad were rendered by LTX
# at full HD as translucent pink panels floating in the sky, so they are left out.
box("Hangar0", (300, -200, 13), (70, 40, 26), (0.7, 0.7, 0.72))
box("Road", (0, 200, 0.05), (8, 400, 0.1), (0.3, 0.3, 0.3))

# ---------------- Rocket (children of an animated rig) ----------------
rig = bpy.data.objects.new("RocketRig", None)
scene.collection.objects.link(rig)
white, dark = (0.93, 0.93, 0.92), (0.15, 0.15, 0.17)

stage1 = bpy.data.objects.new("Stage1", None)
scene.collection.objects.link(stage1)
attach(stage1, rig)
for i in range(3):
    a = i * 2 * math.pi / 3
    attach(cylinder(f"Engine{i}", (0.8 * math.cos(a), 0.8 * math.sin(a), -0.4), 0.55, 1.6, dark, vertices=16), stage1)
attach(cylinder("Stage1Body", (0, 0, 15), 1.8, 30, white, vertices=48), stage1)
attach(cylinder("Stage1Band", (0, 0, 29.5), 1.82, 1.0, dark, vertices=48), stage1)
for i in range(4):
    a = i * math.pi / 2 + math.pi / 4
    fin = box(f"Fin{i}", (2.2 * math.cos(a), 2.2 * math.sin(a), 2.5), (1.4, 0.15, 4), dark)
    fin.rotation_euler = (0, 0, a)
    attach(fin, stage1)

stage2 = bpy.data.objects.new("Stage2", None)
scene.collection.objects.link(stage2)
attach(stage2, rig)
attach(cylinder("Interstage", (0, 0, 31), 1.8, 2, dark, vertices=48), stage2)
attach(cylinder("Stage2Body", (0, 0, 36), 1.8, 8, white, vertices=48), stage2)
attach(cylinder("Stage2Nozzle", (0, 0, 29.6), 0.9, 1.2, dark, vertices=24), stage2)

# Fairing: cylinder + ogive-ish cone, split into two halves along X.
halves = []
for side in (1, -1):
    body = cylinder(f"FairingBody{side}", (0, 0, 43.5), 2.2, 7, white, vertices=48)
    body_cut = box(f"cutA{side}", (-side * 3, 0, 43.5), (6, 8, 8), (1, 0, 0))
    cut(body, body_cut)
    nose = cone(f"FairingNose{side}", (0, 0, 49.5), 2.2, 5, white, vertices=48)
    nose_cut = box(f"cutB{side}", (-side * 3, 0, 49.5), (6, 8, 6), (1, 0, 0))
    cut(nose, nose_cut)
    half = bpy.data.objects.new(f"FairingHalf{side}", None)
    half.location = (0, 0, 40)  # hinge at the fairing base
    scene.collection.objects.link(half)
    attach(half, stage2)
    attach(body, half)
    attach(nose, half)
    halves.append((side, half))

# Satellite inside the fairing.
sat = bpy.data.objects.new("Satellite", None)
sat.location = (0, 0, 43.5)
scene.collection.objects.link(sat)
attach(sat, stage2)
attach(box("SatBus", (0, 0, 43.5), (2.2, 2.2, 3.0), (0.8, 0.62, 0.22)), sat)
attach(cone("SatDish", (0, 0, 45.6), 0.9, 1.0, (0.85, 0.85, 0.85), vertices=24), sat)
panels = []
for side in (1, -1):
    p = box(f"Panel{side}", (side * 1.2, 0, 43.5), (0.12, 1.8, 2.8), (0.1, 0.14, 0.35))
    attach(p, sat)
    panels.append((side, p))

# Exhaust plume + ground steam: soft (preview only, not in the depth guide).
plume = blob("Plume", (0, 0, -18), (2.5, 2.5, 18), (1.0, 0.8, 0.45), soft=True)
attach(plume, stage1)
steam = blob("Steam", (0, -32, 6), (30, 18, 8), (0.95, 0.95, 0.95), soft=True)

# Cloud deck the rocket punches through (soft).
for i in range(160):
    r, a = 1500 * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
    x, y = r * math.cos(a), r * math.sin(a)
    if math.hypot(x, y) < 25:
        continue
    s = rng.uniform(40, 110)
    blob(f"Cloud{i}", (x, y, rng.uniform(CLOUD_BASE, CLOUD_TOP)), (s * 1.6, s * 1.3, s * 0.45),
         (0.97, 0.97, 0.97), soft=True)

# ---------------- Animation ----------------
t = 0.0
while t <= args.duration + 1e-6:
    key_loc(rig, t, (0, 0, rocket_z(t)))
    t += 0.25
for fc in rig.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# Plume / steam grow at ignition.
# The plume hangs below the engines: its centre sits one half-length under the nozzles.
for t_, sc in ((0, 0.01), (1.0, 0.01), (2.0, 18), (9, 60), (STAGE_SEP - 0.1, 60), (STAGE_SEP, 0.01)):
    w_ = 0.01 if sc == 0.01 else (2.5 if sc == 18 else 4)
    key_scale(plume, t_, (w_, w_, sc))
    key_loc(plume, t_, (0, 0, -1 - sc))
key_scale(steam, 0, (0.01, 0.01, 0.01)); key_scale(steam, 1.0, (4, 4, 2)); key_scale(steam, 4, (60, 40, 18))

# Stage separation: stage 1 falls back and tumbles.
key_loc(stage1, STAGE_SEP, (0, 0, 0)); key_rot(stage1, STAGE_SEP, (0, 0, 0))
key_loc(stage1, STAGE_SEP + 3, (-4, 3, -90)); key_rot(stage1, STAGE_SEP + 3, (0.5, 0.3, 0))
key_loc(stage1, args.duration, (-8, 6, -170)); key_rot(stage1, args.duration, (0.9, 0.5, 0))

# Fairing halves hinge open and drift away.
for side, half in halves:
    key_loc(half, FAIRING_SEP, (0, 0, 40)); key_rot(half, FAIRING_SEP, (0, 0, 0))
    key_loc(half, FAIRING_SEP + 1.2, (side * 3, 0, 41)); key_rot(half, FAIRING_SEP + 1.2, (0, side * 0.6, 0))
    key_loc(half, args.duration, (side * 22, -2, 38)); key_rot(half, args.duration, (0.3, side * 1.9, 0))

# Satellite rises clear, panels unfold into long wings.
key_loc(sat, FAIRING_SEP + 1.0, (0, 0, 43.5)); key_loc(sat, args.duration, (0, 0, 49))
for side, p in panels:
    key_loc(p, PANELS, (side * 1.2, 0, 43.5)); key_scale(p, PANELS, (0.12, 1.8, 2.8))
    key_loc(p, PANELS + 1.3, (side * 5.2, 0, 43.5)); key_scale(p, PANELS + 1.3, (8.0, 1.8, 0.1))

# ---------------- Camera ----------------
def rz(t):
    return rocket_z(t)


keys = [
    (0.0, (0, -260, 6), (0, 0, 28)),
    (1.5, (0, -250, 8), (0, 0, 30)),
    (2.5, (20, -235, 14), (0, 0, rz(2.5) + 30)),
    (3.5, (45, -205, 40), (0, 0, rz(3.5) + 28)),
    (4.5, (60, -175, 140), (0, 0, rz(4.5) + 26)),
    (6.0, (70, -150, 520), (0, 0, rz(6.0) + 25)),
    (7.0, (65, -120, 860), (0, 0, rz(7.0) + 25)),
    (8.0, (55, -95, 1250), (0, 0, rz(8.0) + 28)),
    (9.0, (45, -80, 1690), (0, 0, rz(9.0) + 30)),
    (10.0, (38, -72, rz(10.0) - 32), (0, 0, rz(10.0) + 30)),
    # Orbit: the camera rises above the rocket and looks down so Earth's limb fills the background
    # (horizon dip at ~3000 m on this 9 km planet is ~40 deg).
    (11.5, (42, -62, rz(11.5) + 40), (0, 0, rz(11.5) + 22)),
    (12.5, (35, -55, rz(12.5) + 72), (0, 0, rz(12.5) + 30)),
    (13.7, (28, -40, rz(13.7) + 80), (0, 0, rz(13.7) + 44)),
    (15.5, (12, -38, rz(15.5) + 84), (0, 0, rz(15.5) + 46)),
    (17.0, (-12, -34, rz(17.0) + 86), (0, 0, rz(17.0) + 48)),
    (18.0, (-22, -28, rz(18.0) + 88), (0, 0, rz(18.0) + 49)),
]

# The rocket moves at up to ~500 m/s, so sparse eased camera keys would drift off it between keys.
# Store each key as an offset from the rocket, ease the offsets, and re-add the exact rocket height at
# every sample (12 per second, linear in between).
def offset_at(t, idx):
    for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)  # smoothstep
            p0 = [a[idx][k] - (rz(t0) if k == 2 else 0) for k in range(3)]
            p1 = [b[idx][k] - (rz(t1) if k == 2 else 0) for k in range(3)]
            return [p0[k] + (p1[k] - p0[k]) * u for k in range(3)]
    last = keys[-1]
    return [last[1 + idx][k] - (rz(last[0]) if k == 2 else 0) for k in range(3)]


dense = []
t = 0.0
while t <= args.duration + 1e-6:
    c, l = offset_at(t, 0), offset_at(t, 1)
    dense.append((t, (c[0], c[1], c[2] + rz(t)), (l[0], l[1], l[2] + rz(t))))
    t += 1 / 12
cam, target = camera_rig(dense, lens=30, clip_end=60000)
for obj in (cam, target):
    for fc in obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

render(args, cam, target, depth_far=30000.0)
