"""Blockout: camera exits a private-jet window and descends over London to the clock tower."""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blockout_lib import (parse_args, reset_scene, box, cylinder, cone, blob, plane, cut, shell,
                          camera_rig, render)

GROUND_Z = -50
TOWER = (0, -82)

args = parse_args()
reset_scene(args, sky=(0.36, 0.52, 0.8))

# Jet: fuselage along X with an oval window on the -Y side.
fuselage = shell(cylinder("Fuselage", (0, 0, 0), 1.5, 24, (0.86, 0.86, 0.84),
                          rotation=(0, math.pi / 2, 0), capped=False), 0.12)
window = cylinder("WindowCutter", (0, -1.4, 0.3), 0.36, 1.2, (1, 0, 0),
                  rotation=(math.pi / 2, 0, 0), scale=(0.8, 1.15, 1))
cut(fuselage, window)
box("WingL", (4.2, -6.2, -0.9), (2.6, 9.6, 0.1), (0.8, 0.8, 0.8))
box("WingR", (4.2, 6.2, -0.9), (2.6, 9.6, 0.1), (0.8, 0.8, 0.8))
box("TailFin", (11, 0, 2.2), (1.8, 0.1, 3), (0.8, 0.8, 0.8))
cone("Nose", (-13, 0, 0), 1.5, 3, (0.86, 0.86, 0.84), vertices=32).rotation_euler = (0, -math.pi / 2, 0)

# City
plane("Ground", (0, -100, GROUND_Z), (420, 320), (0.3, 0.38, 0.28))
plane("Thames", (0, -74, GROUND_Z + 0.05), (420, 7), (0.18, 0.3, 0.45))
box("Bridge", (-14, -74, GROUND_Z + 0.4), (3, 9, 0.6), (0.55, 0.5, 0.45))

rng = random.Random(7)
for x in range(-84, 85, 6):
    for y in range(-170, -25, 6):
        if -79 <= y <= -69:  # river
            continue
        if abs(x - TOWER[0]) < 10 and -92 < y < -66:  # keep tower clear
            continue
        if 6 < x < 32 and -90 < y < -76:  # parliament footprint
            continue
        h = rng.uniform(2, 11) if y < -90 else rng.uniform(1.5, 6)
        shade = rng.uniform(0.55, 0.75)
        box(f"B_{x}_{y}", (x + rng.uniform(-0.8, 0.8), y + rng.uniform(-0.8, 0.8), GROUND_Z + h / 2),
            (4, 4, h), (shade, shade * 0.97, shade * 0.9))

box("Parliament", (19, -83, GROUND_Z + 2.5), (26, 5, 5), (0.78, 0.7, 0.52))
box("VictoriaTower", (33, -83, GROUND_Z + 7), (4, 4, 14), (0.78, 0.7, 0.52))

# Clock tower: shaft, clock stage, faces, spire
tx, ty = TOWER
box("TowerShaft", (tx, ty, GROUND_Z + 9), (2.4, 2.4, 18), (0.8, 0.72, 0.52))
box("ClockStage", (tx, ty, GROUND_Z + 19.5), (3, 3, 3), (0.8, 0.72, 0.52))
for name, loc, rot in [("ClockN", (tx, ty + 1.52, GROUND_Z + 19.5), (math.pi / 2, 0, 0)),
                       ("ClockS", (tx, ty - 1.52, GROUND_Z + 19.5), (math.pi / 2, 0, 0)),
                       ("ClockE", (tx + 1.52, ty, GROUND_Z + 19.5), (0, math.pi / 2, 0)),
                       ("ClockW", (tx - 1.52, ty, GROUND_Z + 19.5), (0, math.pi / 2, 0))]:
    cylinder(name, loc, 1.1, 0.08, (1.0, 0.9, 0.55), rotation=rot)
cone("Spire", (tx, ty, GROUND_Z + 23.5), 1.8, 5, (0.35, 0.37, 0.4)).rotation_euler = (0, 0, math.pi / 4)

# Clouds between the jet and the city, kept out of the final sightline.
for i in range(26):
    x, y = rng.uniform(-70, 70), rng.uniform(-130, -10)
    if abs(x) < 16 and y < -38:
        continue
    z = rng.uniform(-24, -12)
    for j in range(rng.randint(4, 7)):  # puffy cluster of blobs
        s = rng.uniform(2.2, 4.5)
        blob(f"Cloud{i}_{j}", (x + rng.uniform(-6, 6), y + rng.uniform(-4, 4), z + rng.uniform(0, 1.5)),
             (s * 1.4, s, s * 0.7), (0.98, 0.97, 0.95), soft=True)

# Camera: inside cabin -> through window -> pull away and tilt down -> arc to the tower.
cam, target = camera_rig([
    (0.0, (0, 0.3, 0.3), (0, -10, 0.15)),
    (3.0, (0, -3.2, 0.2), (0, -30, -7)),
    (6.0, (-4, -15, -4), (0, -65, -38)),
    (10.0, (5, -62, GROUND_Z + 19), (tx, ty, GROUND_Z + 18.5)),
], lens=28)

render(args, cam, target)
