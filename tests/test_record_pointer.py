"""`studio record --pointer`: the mouse moves through waypoints while the page is recorded (for pictures that follow
the pointer), with a ring drawn where it is. The path, the parsing and the cursor; no browser needed."""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from engine.project import BuildError
from engine.record import WANDER, draw_cursor, parse_pointer, pointer_path


def test_parse_pointer_reads_wander_and_waypoints():
    assert parse_pointer(None) is None and parse_pointer("") is None
    assert parse_pointer("wander") == WANDER
    assert parse_pointer("0.2,0.5 0.8,0.4") == [(0.2, 0.5), (0.8, 0.4)]
    assert parse_pointer("0.2,0.5;0.8,0.4") == [(0.2, 0.5), (0.8, 0.4)]


@pytest.mark.parametrize("bad", ["0.2", "a,b", "1.5,0.2", "0.2,-0.1"])
def test_parse_pointer_refuses_what_is_not_a_point_in_the_viewport(bad):
    with pytest.raises(BuildError):
        parse_pointer(bad)


def test_path_passes_through_every_waypoint_and_stays_in_the_viewport():
    pts = [(0.1, 0.2), (0.9, 0.3), (0.5, 0.9)]
    path = pointer_path(pts, 101)
    assert len(path) == 101
    assert path[0] == pytest.approx(pts[0]) and path[50] == pytest.approx(pts[1]) and path[-1] == pytest.approx(pts[2])
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in path)


def test_path_is_smooth():
    path = np.array(pointer_path(WANDER, 400))
    step = np.linalg.norm(np.diff(path, axis=0), axis=1)
    assert step.max() < 0.02                                   # no jumps between frames
    turn = np.linalg.norm(np.diff(path, 2, axis=0), axis=1)
    assert turn.max() < 0.002                                  # no kinks at the waypoints


def test_one_waypoint_holds_and_no_frames_is_empty():
    assert pointer_path([(0.3, 0.4)], 5) == [(0.3, 0.4)] * 5
    assert pointer_path(WANDER, 0) == []


def test_cursor_is_a_ring_at_the_pointer():
    im = Image.new("RGB", (200, 120), (40, 40, 40))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = np.asarray(Image.open(io.BytesIO(draw_cursor(buf.getvalue(), (100, 60)))).convert("L")).astype(int)
    assert out[60, 100] > 180                                  # the dot in the middle
    assert out[60, 109] > 150 or out[60, 110] > 150            # the ring, 9 px out
    assert out[60, 104] < 90                                   # inside the ring the page shows through
    assert abs(out[10, 10] - 40) < 6                           # far away, nothing changes
