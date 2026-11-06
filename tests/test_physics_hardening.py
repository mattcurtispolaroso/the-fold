"""Engine Session 1 — physics hardening regression tests and engine fuzz harness.

Each TestBugN class reproduces a bug from docs/engine-audit-2026-11-05.md and
asserts the fixed behaviour. TestEngineFuzz drives the real physics functions
through 10k+ random steps (random geometry, inputs, gravity, rotations).
"""
from __future__ import annotations

import math
import os
import random
import tempfile
import unittest

import pygame

import constants as C
from src.levels.level_data import GoalDef, LevelData, MovingPlatformDef, PlatformDef
from src.levels.level_renderer import LevelRenderer, MovingPlatform
from src.physics import (
    apply_gravity, apply_jump_impulse, apply_lateral_movement, clamp_terminal_velocity,
    combined_gravity_mult, find_safe_position, push_out_of_movers, resolve_collisions,
    rotate_gravity_ccw, try_rotate, validate_player,
)
from src.physics.collision import collision_substeps
from src.physics.validation import overlaps_any

PW, PH = C.PLAYER_PHYSICS_WIDTH_NORMAL, C.PLAYER_PHYSICS_HEIGHT_NORMAL


def _fall_onto(mult: float, start_y: float, plat: pygame.Rect, gdir=(0, 1)) -> bool:
    """Drop a player at terminal velocity toward `plat`; True if it lands."""
    w, h = (PW, PH) if gdir[1] else (PH, PW)
    tv = C.TERMINAL_VELOCITY * mult
    if gdir[1]:
        px, py, vx, vy = plat.centerx, start_y, 0.0, tv
    else:
        px, py, vx, vy = start_y, plat.centery, tv, 0.0
    on = False
    for _ in range(80):
        vx, vy = apply_gravity(vx, vy, gdir, on, mult)
        vx, vy = clamp_terminal_velocity(vx, vy, gdir, mult)
        px, py, vx, vy, on = resolve_collisions(px, py, vx, vy, w, h, [plat], gdir)
        if on:
            return True
    return False


class TestBug1RotationSafety(unittest.TestCase):
    """Rotation never leaves the player inside geometry."""

    def setUp(self) -> None:
        """An 80px-wide shaft with a floor — narrower than the rotated 96px hitbox."""
        self.shaft = [pygame.Rect(0, 0, 100, 600), pygame.Rect(180, 0, 100, 600),
                      pygame.Rect(0, 500, 400, 40)]

    def test_rotation_refused_when_no_room(self) -> None:
        """In the shaft (was: rotated into a wall) the rotation is refused."""
        self.assertIsNone(try_rotate(140.0, 452.0, 0.0, 0.0, (1, 0), self.shaft,
                                     C.ROTATION_SAFE_SEARCH_PX))

    def test_rotation_nudges_into_room(self) -> None:
        """Standing close to a wall in open space: nudged out, never inside geometry."""
        rects = [pygame.Rect(0, 0, 100, 600), pygame.Rect(0, 500, 800, 40)]
        r = try_rotate(140.0, 452.0, 0.0, 0.0, (1, 0), rects, C.ROTATION_SAFE_SEARCH_PX)
        self.assertIsNotNone(r)
        self.assertFalse(overlaps_any(r.px, r.py, r.w, r.h, rects))

    def test_4000_rotations_near_geometry_stay_valid(self) -> None:
        """Rotation stress with real geometry (the old test only rotated a tuple)."""
        rng = random.Random(7)
        rects = [pygame.Rect(0, 0, 100, 600), pygame.Rect(260, 0, 40, 600),
                 pygame.Rect(0, 500, 400, 40), pygame.Rect(0, 0, 400, 40)]
        px, py, gdir = 180.0, 452.0, (0, 1)
        w, h = PW, PH
        for _ in range(4000):
            new_dir = rotate_gravity_ccw(gdir)
            r = try_rotate(px + rng.uniform(-3, 3), py + rng.uniform(-3, 3), 0.0, 0.0,
                           new_dir, rects, C.ROTATION_SAFE_SEARCH_PX)
            if r is not None:
                px, py, gdir, w, h = r.px, r.py, new_dir, r.w, r.h
            self.assertFalse(overlaps_any(px, py, w, h, rects))


class TestBug2PlatformPush(unittest.TestCase):
    """A platform moving into the player shoves them along its motion."""

    def test_side_push_moves_player_sideways(self) -> None:
        """Was: popped 80px up onto the platform. Now: pushed sideways, y unchanged."""
        floor = pygame.Rect(0, 500, 800, 40)
        mp = MovingPlatform(MovingPlatformDef(x=100, y=420, w=100, h=80, axis="x",
                                              min_val=100, max_val=400, speed=4))
        px, py, vx, vy, on = 260.0, 500 - PH / 2, 0.0, 0.0, True
        for _ in range(40):
            mp.update(1.0)
            px, py = push_out_of_movers(px, py, PW, PH, [(mp.rect, *mp.delta)])
            vx, vy = apply_gravity(vx, vy, (0, 1), on)
            px, py, vx, vy, on = resolve_collisions(px, py, vx, vy, PW, PH, [floor, mp.rect], (0, 1))
            self.assertFalse(overlaps_any(px, py, PW, PH, [floor, mp.rect]))
            self.assertAlmostEqual(py, 500 - PH / 2, delta=1.0)
        self.assertGreater(px, 300.0)  # carried along by the platform

    def test_push_ignores_platforms_not_touching(self) -> None:
        """No overlap → no movement."""
        self.assertEqual(push_out_of_movers(50.0, 50.0, PW, PH, [(pygame.Rect(500, 500, 10, 10), 4, 0)]),
                         (50.0, 50.0))


class TestBug3RidingTurnaround(unittest.TestCase):
    """The player stays locked to a platform through its turnarounds."""

    def test_offset_constant_through_turnarounds(self) -> None:
        """Was: slipped 8px at each turnaround."""
        p = MovingPlatform(MovingPlatformDef(x=100, y=500, w=200, h=20, axis="x",
                                             min_val=100, max_val=160, speed=4))
        lr = LevelRenderer()
        lr.moving_platforms = [p]
        px, py = 200.0, 500 - PH / 2
        offsets = set()
        for _ in range(60):
            lr.update(1.0)
            dx, dy = lr.riding_velocity(px, py, PW, PH, (0, 1), 1.0)
            px, py = px + dx, py + dy
            offsets.add(px - p.rect.x)
        self.assertEqual(offsets, {100.0})

    def test_vertical_platform_carries_player_down(self) -> None:
        """A platform moving down faster than the 2px probe still carries the player."""
        p = MovingPlatform(MovingPlatformDef(x=100, y=300, w=200, h=20, axis="y",
                                             min_val=300, max_val=500, speed=6))
        lr = LevelRenderer()
        lr.moving_platforms = [p]
        px, py = 200.0, 300 - PH / 2
        for _ in range(20):
            lr.update(1.0)
            dx, dy = lr.riding_velocity(px, py, PW, PH, (0, 1), 1.0)
            px, py = px + dx, py + dy
            self.assertEqual(py + PH / 2, p.rect.top)


class TestBug4GravityCapAndTunnelling(unittest.TestCase):
    """Gravity is capped at 5× and collision is safe at any speed."""

    def test_combined_multiplier_clamped(self) -> None:
        """level × zone × pressure never exceeds GRAVITY_MULT_MAX; clamping is reported."""
        mult, clamped = combined_gravity_mult(3.0, 4.0, 1.5)
        self.assertEqual(mult, C.GRAVITY_MULT_MAX)
        self.assertTrue(clamped)
        self.assertEqual(combined_gravity_mult(1.0, 0.4, 1.2), (0.48, False))

    def test_no_tunnelling_up_to_cap(self) -> None:
        """Was: fell through a 20px platform at 3×. Lands at every alignment up to 5×."""
        for mult in (1.0, 2.0, 3.0, 4.0, C.GRAVITY_MULT_MAX):
            for phase in range(0, 140, 7):
                self.assertTrue(_fall_onto(mult, 400.0 + phase, pygame.Rect(0, 1000, 400, 20)),
                                f"down x{mult} phase {phase}")
                self.assertTrue(_fall_onto(mult, 400.0 + phase, pygame.Rect(1000, 0, 20, 400), (1, 0)),
                                f"right x{mult} phase {phase}")

    def test_thin_platform_safe_at_extreme_speed(self) -> None:
        """Even a 2px platform at 10× terminal velocity is not skipped."""
        self.assertTrue(_fall_onto(10.0, 100.0, pygame.Rect(0, 1000, 400, 2)))

    def test_normal_speeds_use_a_single_pass(self) -> None:
        """Sub-stepping only kicks in for fast moves — normal play is unchanged."""
        self.assertEqual(collision_substeps(C.MAX_MOVE_SPEED, C.JUMP_SPEED, PW, PH), 1)
        self.assertGreater(collision_substeps(0.0, C.TERMINAL_VELOCITY * 5, PW, PH), 1)


class TestBug5Validation(unittest.TestCase):
    """Post-step validation corrects invalid states and reports them."""

    rects = [pygame.Rect(0, 500, 800, 40)]

    def test_valid_state_untouched(self) -> None:
        """A normal state passes through with no issues."""
        s = validate_player(100.0, 452.0, 2.0, 0.0, PW, PH, self.rects, (50.0, 452.0), 96.0)
        self.assertEqual((s.px, s.py, s.vx, s.vy, s.issues), (100.0, 452.0, 2.0, 0.0, []))

    def test_nan_position_restored(self) -> None:
        """NaN position → fallback, stopped, reported."""
        s = validate_player(float("nan"), 100.0, 1.0, 1.0, PW, PH, self.rects, (50.0, 452.0), 96.0)
        self.assertEqual((s.px, s.py, s.vx, s.vy), (50.0, 452.0, 0.0, 0.0))
        self.assertEqual(len(s.issues), 1)

    def test_inf_velocity_zeroed(self) -> None:
        """Infinite velocity → zeroed, position kept."""
        s = validate_player(100.0, 300.0, float("inf"), 0.0, PW, PH, self.rects, (50.0, 452.0), 96.0)
        self.assertEqual((s.px, s.py, s.vx, s.vy), (100.0, 300.0, 0.0, 0.0))

    def test_inside_geometry_ejected(self) -> None:
        """Slightly sunk into the floor → ejected to the nearest valid spot."""
        s = validate_player(100.0, 470.0, 0.0, 0.0, PW, PH, self.rects, (50.0, 100.0), 96.0)
        self.assertFalse(overlaps_any(s.px, s.py, PW, PH, self.rects))
        self.assertEqual((s.px, s.py), (100.0, 452.0))
        self.assertIn("ejected", s.issues[0])

    def test_crushed_goes_to_fallback(self) -> None:
        """No room anywhere nearby (crushed) → last safe position, no damage implied."""
        solid = [pygame.Rect(0, 0, 1000, 1000)]
        s = validate_player(500.0, 500.0, 3.0, 3.0, PW, PH, solid, (-200.0, -200.0), 96.0)
        self.assertEqual((s.px, s.py, s.vx, s.vy), (-200.0, -200.0, 0.0, 0.0))

    def test_violation_logged_to_crash_log(self) -> None:
        """LoggingManager.log_physics_violation writes a tagged line."""
        from src.systems.logging_manager import LoggingManager
        with tempfile.TemporaryDirectory() as d:
            log = LoggingManager(log_dir=d)
            log.log_physics_violation("player", "inside geometry")
            with open(log.crash_log_path) as f:
                self.assertIn("PHYSICS VIOLATION [player]: inside geometry", f.read())


class TestFindSafePosition(unittest.TestCase):
    """The nearest-valid-spot search used by rotation and validation."""

    def test_already_valid_returns_same(self) -> None:
        """No overlap → unchanged."""
        self.assertEqual(find_safe_position(50.0, 50.0, 10, 10, [], 10.0), (50.0, 50.0))

    def test_picks_nearest_side(self) -> None:
        """Overlapping a wall's left edge by 4px → moved 4px left, not across it."""
        wall = [pygame.Rect(100, 0, 50, 200)]
        self.assertEqual(find_safe_position(99.0, 100.0, 10, 10, wall, 50.0), (95.0, 100.0))


def _random_level(rng: random.Random, with_movers: bool) -> LevelRenderer:
    """A random enclosed room with scattered static (and optionally moving) platforms."""
    w, h = rng.choice([(800, 600), (1200, 900)])
    plats = [PlatformDef(x=rng.randrange(0, w - 200), y=rng.randrange(80, h - 40),
                         w=rng.randrange(20, 300), h=rng.choice([20, 30, 40, 80]))
             for _ in range(rng.randrange(4, 12))]
    movers = []
    if with_movers:
        for _ in range(rng.randrange(1, 3)):
            axis = rng.choice("xy")
            x, y = rng.randrange(100, w - 300), rng.randrange(150, h - 150)
            lo = x if axis == "x" else y
            movers.append(MovingPlatformDef(x=x, y=y, w=rng.randrange(60, 160), h=20, axis=axis,
                                            min_val=lo, max_val=lo + rng.randrange(40, 160),
                                            speed=rng.choice([1, 2, 4, 6])))
    level = LevelRenderer()
    level.load_from_data(LevelData(name="fuzz", gravity_start=(0, 1), spawn=(w / 2, h / 2),
                                   goal=GoalDef(x=0, y=0, w=1, h=1), static_platforms=plats,
                                   moving_platforms=movers, level_width=w, level_height=h))
    return level


class _FuzzPlayer:
    """Minimal player state for the fuzz harness."""

    def __init__(self, px: float, py: float) -> None:
        """Spawn at rest with DOWN gravity."""
        self.px, self.py, self.vx, self.vy = px, py, 0.0, 0.0
        self.gdir, self.w, self.h, self.on_ground = (0, 1), PW, PH, False
        self.safe = (px, py)


def _fuzz_step(p: _FuzzPlayer, level: LevelRenderer, rng: random.Random, mult: float) -> list[str]:
    """One physics step in main.py's order, with random input. Returns validation issues."""
    rects = level.collision_rects()
    p.vx, p.vy = apply_lateral_movement(p.vx, p.vy, rng.choice([-1, 0, 1]), p.gdir, p.on_ground)
    if p.on_ground and rng.random() < 0.05:
        p.vx, p.vy = apply_jump_impulse(p.vx, p.vy, p.gdir)
    if rng.random() < 0.02:  # simulate arriving from a long fall: full terminal velocity
        tv = C.TERMINAL_VELOCITY * mult
        p.vx, p.vy = p.vx + p.gdir[0] * tv, p.vy + p.gdir[1] * tv
    if not p.on_ground:
        p.vx, p.vy = apply_gravity(p.vx, p.vy, p.gdir, p.on_ground, mult)
        p.vx, p.vy = clamp_terminal_velocity(p.vx, p.vy, p.gdir, mult)
    level.update(1.0)
    if p.on_ground:
        dx, dy = level.riding_velocity(p.px, p.py, p.w, p.h, p.gdir, 1.0)
        p.px, p.py = p.px + dx, p.py + dy
    p.px, p.py = push_out_of_movers(p.px, p.py, p.w, p.h, level.movers())
    p.px, p.py, p.vx, p.vy, p.on_ground = resolve_collisions(p.px, p.py, p.vx, p.vy, p.w, p.h, rects, p.gdir)
    state = validate_player(p.px, p.py, p.vx, p.vy, p.w, p.h, rects, p.safe, C.VALIDATION_EJECT_SEARCH_PX)
    p.px, p.py, p.vx, p.vy = state.px, state.py, state.vx, state.vy
    if p.on_ground:
        p.safe = (p.px, p.py)
    if rng.random() < 0.03:
        new_dir = rotate_gravity_ccw(p.gdir) if rng.random() < 0.8 else (0, 1)
        r = try_rotate(p.px, p.py, p.vx, p.vy, new_dir, rects, C.ROTATION_SAFE_SEARCH_PX)
        if r is not None:
            p.px, p.py, p.vx, p.vy, p.w, p.h, p.on_ground = r.px, r.py, r.vx, r.vy, r.w, r.h, r.on_ground
            p.gdir = new_dir
    return state.issues


class TestEngineFuzz(unittest.TestCase):
    """CLAUDE.md fuzz test: 10k+ random steps through the real physics functions."""

    def _run(self, seed: int, with_movers: bool, levels: int, steps: int) -> tuple[int, int]:
        """Run the harness; returns (total steps, validation interventions)."""
        rng = random.Random(seed)
        total = interventions = 0
        for _ in range(levels):
            level = _random_level(rng, with_movers)
            rects = level.collision_rects()
            spot = find_safe_position(level.spawn[0], level.spawn[1], PW, PH, rects, 400.0)
            if spot is None:
                continue
            p = _FuzzPlayer(*spot)
            mult = rng.choice([0.4, 1.0, 1.5, 3.0, C.GRAVITY_MULT_MAX])
            for _ in range(steps):
                interventions += bool(_fuzz_step(p, level, rng, mult))
                total += 1
                self.assertTrue(all(math.isfinite(v) for v in (p.px, p.py, p.vx, p.vy)))
                self.assertFalse(overlaps_any(p.px, p.py, p.w, p.h, level.collision_rects()),
                                 f"inside geometry at step {total}")
        return total, interventions

    def test_static_geometry_needs_no_validation(self) -> None:
        """With only static solids, collision + safe rotation alone keep the player valid."""
        total, interventions = self._run(seed=101, with_movers=False, levels=20, steps=600)
        self.assertGreaterEqual(total, 10_000)
        self.assertEqual(interventions, 0, "collision/rotation produced an invalid state")

    def test_moving_geometry_always_valid(self) -> None:
        """With moving platforms (crush possible), every step still ends valid."""
        total, _ = self._run(seed=202, with_movers=True, levels=20, steps=600)
        self.assertGreaterEqual(total, 10_000)
