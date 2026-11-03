"""Level navigability geometry tests.

Option-2 approach: for each hand-authored level, assert the critical geometric
relationships that make the goal reachable.  These tests do NOT do pathfinding
(that is option-1, parked in the roadmap backlog).  Instead they check:

  1. A player standing on at least one platform in at least one gravity
     orientation has their centre point inside the goal rect (i.e. there is a
     valid position from which the goal can be triggered).
  2. Level-specific assertions for named critical passages (wall gaps, zone
     coverage, etc.) that protect known design constraints.

Player physics rect sizes (from constants):
  DOWN / UP gravity  : PLAYER_PHYSICS_WIDTH_NORMAL  × PLAYER_PHYSICS_HEIGHT_NORMAL   (64 × 96)
  LEFT / RIGHT gravity: PLAYER_PHYSICS_WIDTH_HORIZONTAL × PLAYER_PHYSICS_HEIGHT_HORIZONTAL (96 × 64)
"""
from __future__ import annotations

import json
import unittest

import tests.conftest  # noqa: F401  — headless pygame

import constants as C
import main


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _goal_triggerable(
    platform: dict,
    goal: dict,
    gravity_dir: tuple[int, int],
) -> bool:
    """Return True if a player *standing* on *platform* in *gravity_dir* has
    their centre point inside *goal*.

    Standing means:
      DOWN  (0, 1)  – player rests on platform TOP  (platform.y)
      UP    (0, -1) – player rests on platform BOTTOM (platform.y + platform.h)
      RIGHT (1, 0)  – player rests on platform LEFT face (platform.x)
      LEFT  (-1, 0) – player rests on platform RIGHT face (platform.x + platform.w)
    """
    px, py = platform["x"], platform["y"]
    pw_p, ph_p = platform["w"], platform["h"]
    gx, gy, gw, gh = goal["x"], goal["y"], goal["w"], goal["h"]

    if gravity_dir in ((0, 1), (0, -1)):
        pw = C.PLAYER_PHYSICS_WIDTH_NORMAL
        ph = C.PLAYER_PHYSICS_HEIGHT_NORMAL
        # x: player must fit fully on platform surface
        cx_min = px + pw // 2
        cx_max = px + pw_p - pw // 2
        if cx_min > cx_max:
            return False
        x_ok = cx_min <= gx + gw and cx_max >= gx

        if gravity_dir == (0, 1):   # DOWN — stand on top
            cy = py - ph // 2
        else:                        # UP   — stand on bottom
            cy = py + ph_p + ph // 2
        y_ok = gy <= cy <= gy + gh
        return x_ok and y_ok

    else:  # horizontal gravity
        pw = C.PLAYER_PHYSICS_WIDTH_HORIZONTAL
        ph = C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL
        # y: player must fit fully on platform face
        cy_min = py + ph // 2
        cy_max = py + ph_p - ph // 2
        if cy_min > cy_max:
            return False
        y_ok = cy_min <= gy + gh and cy_max >= gy

        if gravity_dir == (1, 0):   # RIGHT — stand on left face
            cx = px - pw // 2
        else:                        # LEFT  — stand on right face
            cx = px + pw_p + pw // 2
        x_ok = gx <= cx <= gx + gw
        return x_ok and y_ok


def _load(level_index: int) -> dict:
    """Load level JSON by 1-based index."""
    with open(main.LEVELS[level_index - 1]) as f:
        return json.load(f)


def _all_platforms(data: dict) -> list[dict]:
    return data["static_platforms"] + data.get("moving_platforms", [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLevelNavigability(unittest.TestCase):
    """Each level has at least one valid player position that triggers the goal."""

    # -----------------------------------------------------------------------
    # Level 01 — The Dividing Wall
    # -----------------------------------------------------------------------

    def test_level_01_wall_gap_blocks_down_requires_rotation(self):
        """Gap between wall bottom and floor is < DOWN player height (rotation required)."""
        data = _load(1)
        gate = next(p for p in data["static_platforms"] if p["x"] == 540)
        floor = next(p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 820)
        gap = floor["y"] - (gate["y"] + gate["h"])
        self.assertLess(
            gap, C.PLAYER_PHYSICS_HEIGHT_NORMAL,
            f"Gap {gap}px must block DOWN player ({C.PLAYER_PHYSICS_HEIGHT_NORMAL}px)"
        )

    def test_level_01_wall_gap_passable_with_rotation(self):
        """Same gap is wider than the rotated player height (64px)."""
        data = _load(1)
        gate = next(p for p in data["static_platforms"] if p["x"] == 540)
        floor = next(p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 820)
        gap = floor["y"] - (gate["y"] + gate["h"])
        self.assertGreater(
            gap, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL,
            f"Gap {gap}px must pass rotated player ({C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL}px)"
        )

    def test_level_01_goal_reachable_in_down_gravity(self):
        """At least one static platform allows the player to trigger the goal in DOWN gravity."""
        data = _load(1)
        goal = data["goal"]
        reachable = any(
            _goal_triggerable(p, goal, (0, 1)) for p in data["static_platforms"]
        )
        self.assertTrue(
            reachable,
            "No static platform in DOWN gravity puts player centre in goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 02 — Flip Up
    # -----------------------------------------------------------------------

    def test_level_02_goal_unreachable_from_floor_in_down_gravity(self):
        """Goal sits near the ceiling; player on the starting floor cannot trigger it."""
        data = _load(2)
        floor = next(p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 860)
        self.assertFalse(
            _goal_triggerable(floor, data["goal"], (0, 1)),
            "Floor in DOWN gravity should NOT reach the goal (flip required)"
        )

    def test_level_02_goal_reachable_from_ceiling_in_up_gravity(self):
        """Ceiling acts as floor in UP gravity and spans the goal area."""
        data = _load(2)
        ceiling = next(p for p in data["static_platforms"] if p["y"] == 0 and p["w"] >= 2000)
        self.assertTrue(
            _goal_triggerable(ceiling, data["goal"], (0, -1)),
            "Ceiling in UP gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 03 — Side Step
    # -----------------------------------------------------------------------

    def test_level_03_right_gravity_zone_covers_goal(self):
        """RIGHT gravity zone must overlap the goal x and y ranges."""
        data = _load(3)
        zone = next(
            z for z in data["gravity_zones"] if z.get("gravity_dir") == [1, 0]
        )
        goal = data["goal"]
        self.assertLessEqual(zone["x"], goal["x"] + goal["w"],
                             "Zone must reach goal left edge")
        self.assertGreaterEqual(zone["x"] + zone["w"], goal["x"],
                                "Zone must reach goal right edge")
        self.assertLessEqual(zone["y"], goal["y"] + goal["h"],
                             "Zone must reach goal top")
        self.assertGreaterEqual(zone["y"] + zone["h"], goal["y"],
                                "Zone must reach goal bottom")

    def test_level_03_goal_reachable_via_right_wall_in_right_gravity(self):
        """Right boundary wall provides a valid standing surface in RIGHT gravity."""
        data = _load(3)
        right_wall = next(
            p for p in data["static_platforms"] if p["x"] >= 2300 and p["w"] <= 60
        )
        self.assertTrue(
            _goal_triggerable(right_wall, data["goal"], (1, 0)),
            "Right wall in RIGHT gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 04 — The Frozen Gate
    # -----------------------------------------------------------------------

    def test_level_04_goal_reachable_from_solid_block(self):
        """Large solid block below the goal allows DOWN-gravity trigger."""
        data = _load(4)
        block = next(
            p for p in data["static_platforms"] if p["x"] == 900 and p["y"] == 620
        )
        self.assertTrue(
            _goal_triggerable(block, data["goal"], (0, 1)),
            "Solid block in DOWN gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 05 — The Inverter
    # -----------------------------------------------------------------------

    def test_level_05_up_gravity_zone_covers_goal(self):
        """UP gravity zone spans the goal area."""
        data = _load(5)
        zone = next(
            z for z in data["gravity_zones"] if z.get("gravity_dir") == [0, -1]
        )
        goal = data["goal"]
        self.assertLessEqual(zone["x"], goal["x"],
                             "Zone left edge must be left of goal")
        self.assertGreaterEqual(zone["x"] + zone["w"], goal["x"] + goal["w"],
                                "Zone right edge must cover full goal width")

    def test_level_05_goal_reachable_from_ceiling_in_up_gravity(self):
        """Full ceiling spans goal x range and puts player centre inside goal in UP gravity."""
        data = _load(5)
        ceiling = next(
            p for p in data["static_platforms"] if p["y"] == 0 and p["w"] >= 1500
        )
        self.assertTrue(
            _goal_triggerable(ceiling, data["goal"], (0, -1)),
            "Ceiling in UP gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 06 — The Fault Line
    # -----------------------------------------------------------------------

    def test_level_06_right_gravity_zone_covers_goal(self):
        """RIGHT gravity zone overlaps goal position."""
        data = _load(6)
        zone = next(
            z for z in data["gravity_zones"] if z.get("gravity_dir") == [1, 0]
        )
        goal = data["goal"]
        self.assertLessEqual(zone["x"], goal["x"] + goal["w"],
                             "Zone must reach goal")
        self.assertGreaterEqual(zone["x"] + zone["w"], goal["x"],
                                "Zone must cover goal x start")

    def test_level_06_goal_reachable_via_right_wall_in_right_gravity(self):
        """Right boundary wall provides a valid standing surface in RIGHT gravity."""
        data = _load(6)
        right_wall = next(
            p for p in data["static_platforms"] if p["x"] >= 1900 and p["w"] <= 60
        )
        self.assertTrue(
            _goal_triggerable(right_wall, data["goal"], (1, 0)),
            "Right wall in RIGHT gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 07 — Convergence Point
    # -----------------------------------------------------------------------

    def test_level_07_goal_reachable_from_floor(self):
        """Floor extends into goal x range; player standing on floor triggers goal."""
        data = _load(7)
        floor = next(
            p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 820
        )
        self.assertTrue(
            _goal_triggerable(floor, data["goal"], (0, 1)),
            "Floor in DOWN gravity must reach the goal rect"
        )

    # -----------------------------------------------------------------------
    # Level 08 — The Threshold
    # -----------------------------------------------------------------------

    def test_level_08_up_gravity_zone_covers_goal(self):
        """UP gravity zone fully covers the goal x range and overlaps its y range."""
        data = _load(8)
        goal = data["goal"]
        zone = next(
            z for z in data["gravity_zones"] if z.get("gravity_dir") == [0, -1]
        )
        zone_right = zone["x"] + zone["w"]
        zone_bottom = zone["y"] + zone["h"]
        self.assertLessEqual(zone["x"], goal["x"],
                             "Zone left must be at or left of goal left")
        self.assertGreaterEqual(zone_right, goal["x"] + goal["w"],
                                "Zone right must reach goal right edge")
        self.assertLessEqual(zone["y"], goal["y"],
                             "Zone top must be above goal top")
        self.assertGreater(zone_bottom, goal["y"],
                           "Zone bottom must be below goal top (zone overlaps goal y)")

    def test_level_08_ceiling_spans_goal_column(self):
        """Ceiling x range covers goal x — player can drop through goal column from ceiling."""
        data = _load(8)
        goal = data["goal"]
        ceiling = next(
            p for p in data["static_platforms"] if p["y"] == 0 and p["w"] >= 1500
        )
        self.assertLessEqual(ceiling["x"], goal["x"],
                             "Ceiling must start at or left of goal")
        self.assertGreaterEqual(ceiling["x"] + ceiling["w"], goal["x"] + goal["w"],
                                "Ceiling must extend past goal right edge")

    # -----------------------------------------------------------------------
    # Generic — levels 01-07
    # -----------------------------------------------------------------------

    def test_all_levels_01_to_07_have_triggerable_goal(self):
        """Every level 01-07 has at least one platform/gravity combo that puts
        the player centre inside the goal rect."""
        all_gravities = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for idx in range(1, 8):
            data = _load(idx)
            goal = data["goal"]
            platforms = _all_platforms(data)
            found = any(
                _goal_triggerable(p, goal, g)
                for p in platforms
                for g in all_gravities
            )
            self.assertTrue(
                found,
                f"level_{idx:02d} ({data['name']}): no platform/gravity combination "
                f"places player centre in goal rect {goal}"
            )


if __name__ == "__main__":
    unittest.main()
