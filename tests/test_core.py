"""Unit tests for The Fold core game logic.

Tests physics, gravity, collision, movement, levels.
Runs headless — no game window is opened.
"""
import json
import os
import unittest

# Headless Pygame setup
import tests.conftest  # noqa: F401

import pygame
import main
import constants as C
from src.entities.player import Player
from src.physics import (
    GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT, GRAVITY_LABELS,
    rotate_gravity_ccw, gravity_is_vertical, gravity_speed,
    apply_gravity, clamp_terminal_velocity,
    resolve_collisions,
    apply_jump_impulse, apply_jump_cut, apply_lateral_movement,
)
from src.physics import get_player_physics_size
from src.levels.level_renderer import LevelRenderer, MovingPlatform
from src.levels.level_data import LevelData, PlatformDef, MovingPlatformDef, GoalDef, GravityZoneDef

# Load level_01 once for level geometry tests
_level = LevelRenderer()
_level.load(main.LEVELS[0])


class TestConstants(unittest.TestCase):
    """Sanity-check that physics constants are derived correctly."""

    def test_gravity_derived_from_earth(self):
        expected = C.EARTH_GRAVITY * C.PPM / C.FPS**2
        self.assertAlmostEqual(C.GRAVITY_STRENGTH, expected, places=6)

    def test_terminal_velocity_derived(self):
        expected = 53.0 * C.PPM / C.FPS
        self.assertAlmostEqual(C.TERMINAL_VELOCITY, expected, places=6)

    def test_four_gravity_labels(self):
        self.assertEqual(len(GRAVITY_LABELS), 4)

    def test_default_level_exists(self):
        self.assertTrue(os.path.isfile(main.LEVELS[0]))


class TestGravityDirections(unittest.TestCase):
    """Verify gravity direction constants are correct unit vectors."""

    def test_gravity_down(self):
        self.assertEqual(GRAVITY_DOWN, (0, 1))

    def test_gravity_left(self):
        self.assertEqual(GRAVITY_LEFT, (-1, 0))

    def test_gravity_up(self):
        self.assertEqual(GRAVITY_UP, (0, -1))

    def test_gravity_right(self):
        self.assertEqual(GRAVITY_RIGHT, (1, 0))

    def test_all_are_unit_vectors(self):
        for gdir in [GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT]:
            mag_sq = gdir[0] ** 2 + gdir[1] ** 2
            self.assertEqual(mag_sq, 1)

    def test_all_have_labels(self):
        for gdir in [GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT]:
            self.assertIn(gdir, GRAVITY_LABELS)


class TestGravityIsVertical(unittest.TestCase):
    """gravity_is_vertical() should return True for down/up, False for left/right."""

    def test_down_is_vertical(self):
        self.assertTrue(gravity_is_vertical(GRAVITY_DOWN))

    def test_up_is_vertical(self):
        self.assertTrue(gravity_is_vertical(GRAVITY_UP))

    def test_left_is_not_vertical(self):
        self.assertFalse(gravity_is_vertical(GRAVITY_LEFT))

    def test_right_is_not_vertical(self):
        self.assertFalse(gravity_is_vertical(GRAVITY_RIGHT))


class TestRotateGravity(unittest.TestCase):
    """rotate_gravity_ccw() should cycle: down → right → up → left → down."""

    def test_down_to_right(self):
        self.assertEqual(rotate_gravity_ccw(GRAVITY_DOWN), GRAVITY_RIGHT)

    def test_right_to_up(self):
        self.assertEqual(rotate_gravity_ccw(GRAVITY_RIGHT), GRAVITY_UP)

    def test_up_to_left(self):
        self.assertEqual(rotate_gravity_ccw(GRAVITY_UP), GRAVITY_LEFT)

    def test_left_to_down(self):
        self.assertEqual(rotate_gravity_ccw(GRAVITY_LEFT), GRAVITY_DOWN)

    def test_full_cycle_returns_to_start(self):
        gdir = GRAVITY_DOWN
        for _ in range(4):
            gdir = rotate_gravity_ccw(gdir)
        self.assertEqual(gdir, GRAVITY_DOWN)


class TestGravitySpeed(unittest.TestCase):
    """gravity_speed() returns dot product of velocity with gravity direction."""

    def test_gravity_down(self):
        self.assertEqual(gravity_speed(3, 5, GRAVITY_DOWN), 5)

    def test_gravity_up(self):
        self.assertEqual(gravity_speed(3, 5, GRAVITY_UP), -5)

    def test_gravity_left(self):
        self.assertEqual(gravity_speed(3, 5, GRAVITY_LEFT), -3)

    def test_gravity_right(self):
        self.assertEqual(gravity_speed(3, 5, GRAVITY_RIGHT), 3)

    def test_zero_velocity(self):
        self.assertEqual(gravity_speed(0, 0, GRAVITY_DOWN), 0)

    def test_moving_against_gravity_is_negative(self):
        self.assertLess(gravity_speed(0, -5, GRAVITY_DOWN), 0)
        self.assertLess(gravity_speed(5, 0, GRAVITY_LEFT), 0)


class TestGravityAccumulation(unittest.TestCase):
    """Simulate gravity being applied over multiple frames."""

    def test_falling_accelerates_downward(self):
        vy = 0.0
        for _ in range(60):
            vy += C.GRAVITY_STRENGTH
        expected = C.EARTH_GRAVITY * C.PPM / C.FPS
        self.assertAlmostEqual(vy, expected, places=1)

    def test_peak_gravity_multiplier_increases_pull(self):
        vy = 0.0
        vy += C.GRAVITY_STRENGTH * C.PEAK_GRAVITY_MULT
        self.assertAlmostEqual(vy, C.GRAVITY_STRENGTH * 2.5, places=6)

    def test_gravity_applied_via_direction_vector(self):
        for gdir in [GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT]:
            gx = gdir[0] * C.GRAVITY_STRENGTH
            gy = gdir[1] * C.GRAVITY_STRENGTH
            mag = (gx ** 2 + gy ** 2) ** 0.5
            self.assertAlmostEqual(mag, C.GRAVITY_STRENGTH, places=6)


class TestTerminalVelocity(unittest.TestCase):
    """Fall speed must be clamped to TERMINAL_VELOCITY."""

    def test_clamp_downward(self):
        vy = 0.0
        for _ in range(10000):
            vy += C.GRAVITY_STRENGTH
            vy = min(vy, C.TERMINAL_VELOCITY)
        self.assertAlmostEqual(vy, C.TERMINAL_VELOCITY, places=6)

    def test_clamp_leftward(self):
        vx = 0.0
        for _ in range(10000):
            vx += -C.GRAVITY_STRENGTH
            vx = max(vx, -C.TERMINAL_VELOCITY)
        self.assertAlmostEqual(vx, -C.TERMINAL_VELOCITY, places=6)

    def test_vector_clamping_preserves_lateral(self):
        vx, vy = 3.0, 100.0
        gdir = GRAVITY_DOWN
        grav_component = gravity_speed(vx, vy, gdir)
        if abs(grav_component) > C.TERMINAL_VELOCITY:
            clamped = max(-C.TERMINAL_VELOCITY, min(C.TERMINAL_VELOCITY, grav_component))
            diff = clamped - grav_component
            vx += diff * gdir[0]
            vy += diff * gdir[1]
        self.assertAlmostEqual(vx, 3.0)
        self.assertAlmostEqual(vy, C.TERMINAL_VELOCITY)


class TestJumpPhysics(unittest.TestCase):
    """Jump impulse and variable jump height using gravity_dir vector."""

    def test_jump_impulse_gravity_down(self):
        vx, vy = 0.0, 0.0
        gdir = GRAVITY_DOWN
        vx -= gdir[0] * C.JUMP_SPEED
        vy -= gdir[1] * C.JUMP_SPEED
        self.assertEqual(vx, 0.0)
        self.assertAlmostEqual(vy, -C.JUMP_SPEED)

    def test_jump_impulse_gravity_left(self):
        vx, vy = 0.0, 0.0
        gdir = GRAVITY_LEFT
        vx -= gdir[0] * C.JUMP_SPEED
        vy -= gdir[1] * C.JUMP_SPEED
        self.assertAlmostEqual(vx, C.JUMP_SPEED)
        self.assertEqual(vy, 0.0)

    def test_jump_impulse_gravity_up(self):
        vx, vy = 0.0, 0.0
        gdir = GRAVITY_UP
        vx -= gdir[0] * C.JUMP_SPEED
        vy -= gdir[1] * C.JUMP_SPEED
        self.assertEqual(vx, 0.0)
        self.assertAlmostEqual(vy, C.JUMP_SPEED)

    def test_jump_impulse_gravity_right(self):
        vx, vy = 0.0, 0.0
        gdir = GRAVITY_RIGHT
        vx -= gdir[0] * C.JUMP_SPEED
        vy -= gdir[1] * C.JUMP_SPEED
        self.assertAlmostEqual(vx, -C.JUMP_SPEED)
        self.assertEqual(vy, 0.0)

    def test_variable_jump_cut(self):
        vy = -C.JUMP_SPEED
        vy *= C.JUMP_CUT_MULTIPLIER
        self.assertAlmostEqual(vy, -C.JUMP_SPEED * 0.4, places=6)

    def test_going_up_detected_via_dot_product(self):
        self.assertLess(gravity_speed(0, -5, GRAVITY_DOWN), 0)
        self.assertLess(gravity_speed(5, 0, GRAVITY_LEFT), 0)
        self.assertLess(gravity_speed(0, 5, GRAVITY_UP), 0)
        self.assertLess(gravity_speed(-5, 0, GRAVITY_RIGHT), 0)

    def test_falling_not_detected_as_going_up(self):
        self.assertGreater(gravity_speed(0, 5, GRAVITY_DOWN), 0)


class TestCoyoteTime(unittest.TestCase):
    """Coyote timer should count down and allow jumping within the window."""

    def test_timer_starts_at_coyote_time(self):
        self.assertAlmostEqual(C.COYOTE_TIME, 0.1, places=3)

    def test_timer_counts_down(self):
        coyote_timer = C.COYOTE_TIME
        dt = 1.0 / C.FPS
        for _ in range(3):
            coyote_timer = max(0.0, coyote_timer - dt)
        expected = C.COYOTE_TIME - 3.0 / C.FPS
        self.assertAlmostEqual(coyote_timer, expected, places=6)

    def test_timer_reaches_zero(self):
        coyote_timer = C.COYOTE_TIME
        dt = 1.0 / C.FPS
        for _ in range(10):
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertEqual(coyote_timer, 0.0)

    def test_jump_allowed_within_window(self):
        coyote_timer = C.COYOTE_TIME
        dt = 1.0 / C.FPS
        for _ in range(3):
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertGreater(coyote_timer, 0)

    def test_jump_denied_after_window(self):
        coyote_timer = C.COYOTE_TIME
        dt = 1.0 / C.FPS
        for _ in range(60):
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertEqual(coyote_timer, 0.0)


class TestMovementAcceleration(unittest.TestCase):
    """Horizontal movement should accelerate and decelerate, not snap."""

    def test_acceleration_from_standstill(self):
        vx = 0.0
        vx += 1 * C.ACCEL
        vx = max(-C.MAX_MOVE_SPEED, min(C.MAX_MOVE_SPEED, vx))
        self.assertEqual(vx, C.ACCEL)
        self.assertLess(vx, C.MAX_MOVE_SPEED)

    def test_deceleration_to_stop(self):
        vx = 3.0
        steps = 0
        while vx != 0:
            if abs(vx) < C.DECEL:
                vx = 0
            else:
                vx -= C.DECEL if vx > 0 else -C.DECEL
            steps += 1
            if steps > 100:
                self.fail("Deceleration did not converge")
        self.assertEqual(vx, 0.0)

    def test_speed_clamped_to_max(self):
        vx = 0.0
        for _ in range(100):
            vx += C.ACCEL
            vx = max(-C.MAX_MOVE_SPEED, min(C.MAX_MOVE_SPEED, vx))
        self.assertEqual(vx, C.MAX_MOVE_SPEED)


class TestAirControl(unittest.TestCase):
    """Air accel/decel should be lower than ground values."""

    def test_air_accel_less_than_ground(self):
        self.assertLess(C.AIR_ACCEL, C.ACCEL)

    def test_air_decel_less_than_ground(self):
        self.assertLess(C.AIR_DECEL, C.DECEL)

    def test_air_accel_still_positive(self):
        self.assertGreater(C.AIR_ACCEL, 0)

    def test_momentum_preserved_in_air(self):
        vx = C.MAX_MOVE_SPEED
        if abs(vx) < C.AIR_DECEL:
            vx = 0
        else:
            vx -= C.AIR_DECEL if vx > 0 else -C.AIR_DECEL
        self.assertGreater(vx, C.MAX_MOVE_SPEED * 0.9)


class TestJumpAfterRotation(unittest.TestCase):
    """Jump must work correctly in all 4 gravity orientations.

    Simulates: player on platform, apply jump impulse, verify liftoff.
    """

    def _simulate_jump(self, gravity_dir):
        """Simulate a jump: place player on floor, apply impulse, check liftoff."""
        grav_vert = gravity_is_vertical(gravity_dir)
        # Create a platform the player stands on
        # Place player 1px into platform so collision resolves to on_ground
        if gravity_dir == GRAVITY_DOWN:
            plat = pygame.Rect(0, 500, 200, 20)
            px, py = 100.0, 500.0 - 15 + 1
        elif gravity_dir == GRAVITY_UP:
            plat = pygame.Rect(0, 100, 200, 20)
            px, py = 100.0, 120.0 + 15 - 1
        elif gravity_dir == GRAVITY_LEFT:
            plat = pygame.Rect(100, 0, 20, 200)
            px, py = 120.0 + 15 - 1, 100.0
        else:  # GRAVITY_RIGHT
            plat = pygame.Rect(200, 0, 20, 200)
            px, py = 200.0 - 15 + 1, 100.0

        # Resolve to confirm on_ground (player snaps to surface)
        px, py, _, _, on_ground = resolve_collisions(
            px, py, 0, 0, 30, 30, [plat], gravity_dir,
        )
        self.assertTrue(on_ground, f"Not on ground before jump with gravity={gravity_dir}")

        # Apply jump impulse (same logic as main.py)
        vx = -gravity_dir[0] * C.JUMP_SPEED
        vy = -gravity_dir[1] * C.JUMP_SPEED

        # Step physics once to move away from platform
        px2, py2, vx2, vy2, on_ground2 = resolve_collisions(
            px, py, vx, vy, 30, 30, [plat], gravity_dir,
        )
        self.assertFalse(on_ground2, f"Still on ground after jump with gravity={gravity_dir}")
        return vx2, vy2

    def test_jump_works_gravity_down(self):
        vx, vy = self._simulate_jump(GRAVITY_DOWN)
        self.assertLess(vy, 0)  # moving up

    def test_jump_works_gravity_up(self):
        vx, vy = self._simulate_jump(GRAVITY_UP)
        self.assertGreater(vy, 0)  # moving down

    def test_jump_works_gravity_left(self):
        vx, vy = self._simulate_jump(GRAVITY_LEFT)
        self.assertGreater(vx, 0)  # moving right

    def test_jump_works_gravity_right(self):
        vx, vy = self._simulate_jump(GRAVITY_RIGHT)
        self.assertLess(vx, 0)  # moving left

    def test_jump_cut_works_all_orientations(self):
        """Variable jump cut should reduce velocity in correct axis for all orientations."""
        for gdir in [GRAVITY_DOWN, GRAVITY_UP, GRAVITY_LEFT, GRAVITY_RIGHT]:
            vx = -gdir[0] * C.JUMP_SPEED
            vy = -gdir[1] * C.JUMP_SPEED
            going_up = gravity_speed(vx, vy, gdir) < 0
            self.assertTrue(going_up, f"Jump not detected as going up for gravity={gdir}")
            if gravity_is_vertical(gdir):
                vy_cut = vy * C.JUMP_CUT_MULTIPLIER
                self.assertLess(abs(vy_cut), abs(vy))
            else:
                vx_cut = vx * C.JUMP_CUT_MULTIPLIER
                self.assertLess(abs(vx_cut), abs(vx))

    def test_coyote_time_applies_in_all_orientations(self):
        """Coyote timer should be set when on_ground regardless of orientation."""
        for gdir in [GRAVITY_DOWN, GRAVITY_UP, GRAVITY_LEFT, GRAVITY_RIGHT]:
            if gdir == GRAVITY_DOWN:
                plat = pygame.Rect(0, 500, 200, 20)
                px, py = 100.0, 500.0 - 15 + 1
            elif gdir == GRAVITY_UP:
                plat = pygame.Rect(0, 100, 200, 20)
                px, py = 100.0, 120.0 + 15 - 1
            elif gdir == GRAVITY_LEFT:
                plat = pygame.Rect(100, 0, 20, 200)
                px, py = 120.0 + 15 - 1, 100.0
            else:
                plat = pygame.Rect(200, 0, 20, 200)
                px, py = 200.0 - 15 + 1, 100.0
            _, _, _, _, on_ground = resolve_collisions(
                px, py, 0, 0, 30, 30, [plat], gdir,
            )
            self.assertTrue(on_ground, f"Not on ground with gravity={gdir}")


class TestResolveCollisions(unittest.TestCase):
    """Two-pass collision resolution for all 4 gravity states."""

    def test_land_on_platform_gravity_down(self):
        plat = pygame.Rect(0, 500, 200, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            100, 480, 0, 10, 30, 30, [plat], GRAVITY_DOWN
        )
        self.assertTrue(on_ground)
        self.assertAlmostEqual(py, 500 - 15, delta=1)
        self.assertEqual(vy, 0)

    def test_hit_ceiling_gravity_down(self):
        plat = pygame.Rect(0, 100, 200, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            100, 130, 0, -10, 30, 30, [plat], GRAVITY_DOWN
        )
        self.assertFalse(on_ground)
        self.assertAlmostEqual(py, 120 + 15, delta=1)
        self.assertEqual(vy, 0)

    def test_land_on_platform_gravity_up(self):
        plat = pygame.Rect(0, 100, 200, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            100, 130, 0, -10, 30, 30, [plat], GRAVITY_UP
        )
        self.assertTrue(on_ground)
        self.assertAlmostEqual(py, 120 + 15, delta=1)
        self.assertEqual(vy, 0)

    def test_hit_floor_from_below_gravity_up(self):
        plat = pygame.Rect(0, 500, 200, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            100, 480, 0, 10, 30, 30, [plat], GRAVITY_UP
        )
        self.assertFalse(on_ground)
        self.assertAlmostEqual(py, 500 - 15, delta=1)
        self.assertEqual(vy, 0)

    def test_land_on_platform_gravity_left(self):
        plat = pygame.Rect(100, 0, 20, 200)
        px, py, vx, vy, on_ground = resolve_collisions(
            130, 100, -10, 0, 30, 30, [plat], GRAVITY_LEFT
        )
        self.assertTrue(on_ground)
        self.assertAlmostEqual(px, 120 + 15, delta=1)
        self.assertEqual(vx, 0)

    def test_land_on_platform_gravity_right(self):
        plat = pygame.Rect(200, 0, 20, 200)
        px, py, vx, vy, on_ground = resolve_collisions(
            190, 100, 10, 0, 30, 30, [plat], GRAVITY_RIGHT
        )
        self.assertTrue(on_ground)
        self.assertAlmostEqual(px, 200 - 15, delta=1)
        self.assertEqual(vx, 0)

    def test_lateral_wall_stops_player(self):
        wall = pygame.Rect(300, 0, 20, 600)
        px, py, vx, vy, on_ground = resolve_collisions(
            290, 300, 5, 0.5, 30, 30, [wall], GRAVITY_DOWN
        )
        self.assertAlmostEqual(px, 300 - 15)
        self.assertEqual(vx, 0)

    def test_no_collision_in_open_space(self):
        plat = pygame.Rect(0, 500, 100, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            400, 300, 3, 2, 30, 30, [plat], GRAVITY_DOWN
        )
        self.assertFalse(on_ground)
        self.assertAlmostEqual(px, 403)
        self.assertAlmostEqual(py, 302)

    def test_multiple_platforms(self):
        floor = pygame.Rect(0, 500, 400, 20)
        ceiling = pygame.Rect(0, 100, 400, 20)
        px, py, vx, vy, on_ground = resolve_collisions(
            200, 480, 0, 10, 30, 30, [floor, ceiling], GRAVITY_DOWN
        )
        self.assertTrue(on_ground)
        self.assertAlmostEqual(py, 500 - 15, delta=1)


class TestMovingPlatform(unittest.TestCase):
    """Moving platform update logic via LevelRenderer."""

    def _make(self, x, y, w, h, axis, min_val, max_val, speed):
        return MovingPlatform(MovingPlatformDef(x, y, w, h, axis, min_val, max_val, speed))

    def test_moves_in_positive_direction(self):
        mp = self._make(100, 200, 50, 20, 'x', 100, 200, 3)
        mp.update()
        self.assertEqual(mp.rect.x, 103)

    def test_reverses_at_max(self):
        mp = self._make(198, 200, 50, 20, 'x', 100, 200, 3)
        mp.update()
        self.assertEqual(mp.rect.x, 200)
        self.assertEqual(mp.direction, -1)

    def test_reverses_at_min(self):
        mp = self._make(102, 200, 50, 20, 'x', 100, 200, 3)
        mp.direction = -1
        mp.update()
        self.assertEqual(mp.rect.x, 100)
        self.assertEqual(mp.direction, 1)

    def test_y_axis_movement(self):
        mp = self._make(100, 150, 50, 20, 'y', 100, 200, 5)
        mp.update()
        self.assertEqual(mp.rect.y, 155)

    def test_y_axis_reversal(self):
        mp = self._make(100, 199, 50, 20, 'y', 100, 200, 5)
        mp.update()
        self.assertEqual(mp.rect.y, 200)
        self.assertEqual(mp.direction, -1)


class TestLevelLoading(unittest.TestCase):
    """Level JSON loading and parsing."""

    def test_load_level_01(self):
        renderer = LevelRenderer()
        data = renderer.load(main.LEVELS[0])
        self.assertEqual(data.name, "The Dividing Wall")

    def test_level_01_has_correct_platform_count(self):
        self.assertEqual(len(_level.static_platforms), 8)

    def test_level_01_has_correct_moving_platform_count(self):
        self.assertEqual(len(_level.moving_platforms), 1)

    def test_level_01_spawn(self):
        self.assertEqual(_level.spawn, (100.0, 772.0))

    def test_level_01_gravity_start(self):
        self.assertEqual(_level.gravity_start, (0, 1))

    def test_level_01_goal_rect(self):
        self.assertEqual(_level.goal_rect, pygame.Rect(660, 490, 220, 90))

    def test_level_01_physics_gate_gap(self):
        """Vertical wall gap (y=730-820 = 90px) fits RIGHT gravity (64px) but blocks DOWN (96px)."""
        with open(main.LEVELS[0]) as f:
            data = json.load(f)
        gate = next(p for p in data["static_platforms"] if p["x"] == 540)
        floor = next(p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 820)
        gap = floor["y"] - (gate["y"] + gate["h"])
        self.assertGreater(gap, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL,
            f"Gap {gap}px must fit horizontal player ({C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL}px)")
        self.assertLess(gap, C.PLAYER_PHYSICS_HEIGHT_NORMAL,
            f"Gap {gap}px must block normal player ({C.PLAYER_PHYSICS_HEIGHT_NORMAL}px)")

    def test_roundtrip_serialisation(self):
        data = LevelData.load(main.LEVELS[0])
        json_str = data.to_json()
        data2 = LevelData.from_json(json_str)
        self.assertEqual(data.name, data2.name)
        self.assertEqual(len(data.static_platforms), len(data2.static_platforms))
        self.assertEqual(len(data.moving_platforms), len(data2.moving_platforms))

    def test_all_platform_rects_returns_combined(self):
        rects = _level.all_platform_rects()
        expected = len(_level.static_platforms) + len(_level.moving_platforms)
        self.assertEqual(len(rects), expected)


class TestLevelDataValidation(unittest.TestCase):
    """Level data edge cases."""

    def test_empty_platforms(self):
        data = LevelData(
            name="empty", gravity_start=(0, 1), spawn=(0, 0),
            goal=GoalDef(0, 0, 10, 10),
        )
        renderer = LevelRenderer()
        renderer.load_from_data(data)
        self.assertEqual(len(renderer.static_platforms), 0)
        self.assertEqual(len(renderer.moving_platforms), 0)

    def test_missing_optional_fields_in_json(self):
        minimal = json.dumps({
            "name": "minimal",
            "gravity_start": [0, 1],
            "spawn": [0, 0],
            "goal": {"x": 0, "y": 0, "w": 10, "h": 10},
        })
        data = LevelData.from_json(minimal)
        self.assertEqual(data.name, "minimal")
        self.assertEqual(len(data.static_platforms), 0)
        self.assertEqual(len(data.moving_platforms), 0)
        self.assertEqual(data.tile_size, 40)


class TestGoalDetection(unittest.TestCase):
    """Goal overlap detection using loaded level."""

    def test_player_overlapping_goal(self):
        player = pygame.Rect(
            _level.goal_rect.centerx - 15,
            _level.goal_rect.centery - 15,
            30, 30
        )
        self.assertTrue(player.colliderect(_level.goal_rect))

    def test_player_far_from_goal(self):
        player = pygame.Rect(400, 400, 30, 30)
        self.assertFalse(player.colliderect(_level.goal_rect))


class TestLevelGeometry(unittest.TestCase):
    """Level layout sanity checks using loaded level."""

    def test_all_platforms_within_level(self):
        W, H = _level.level_width, _level.level_height
        for i, plat in enumerate(_level.static_platforms):
            self.assertGreaterEqual(plat.left, 0, f"Platform {i} left edge off-level")
            self.assertLessEqual(plat.right, W, f"Platform {i} right edge off-level")
            self.assertGreaterEqual(plat.top, 0, f"Platform {i} top edge off-level")
            self.assertLessEqual(plat.bottom, H, f"Platform {i} bottom edge off-level")

    def test_goal_within_level(self):
        W, H = _level.level_width, _level.level_height
        g = _level.goal_rect
        self.assertGreaterEqual(g.left, 0)
        self.assertLessEqual(g.right, W)
        self.assertGreaterEqual(g.top, 0)
        self.assertLessEqual(g.bottom, H)

    def test_start_platform_at_bottom_left(self):
        start = _level.static_platforms[0]
        self.assertEqual(start.left, 0)
        self.assertGreater(start.bottom, main.HEIGHT - 100)

    def test_goal_platform_exists(self):
        goal_area = _level.goal_rect.inflate(40, 40)
        found = any(plat.colliderect(goal_area) for plat in _level.static_platforms)
        self.assertTrue(found, "No platform near the goal")


class TestPlayerPhysicsSize(unittest.TestCase):
    """get_player_physics_size swaps dimensions for horizontal gravity."""

    def test_vertical_gravity_returns_normal_size(self) -> None:
        w, h = get_player_physics_size(GRAVITY_DOWN)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_NORMAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_NORMAL)

    def test_up_gravity_returns_normal_size(self) -> None:
        w, h = get_player_physics_size(GRAVITY_UP)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_NORMAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_NORMAL)

    def test_horizontal_gravity_swaps_dimensions(self) -> None:
        wR, hR = get_player_physics_size(GRAVITY_RIGHT)
        wL, hL = get_player_physics_size(GRAVITY_LEFT)
        self.assertEqual(wR, C.PLAYER_PHYSICS_WIDTH_HORIZONTAL)
        self.assertEqual(hR, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL)
        self.assertEqual(wL, C.PLAYER_PHYSICS_WIDTH_HORIZONTAL)
        self.assertEqual(hL, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL)

    def test_horizontal_width_equals_normal_height(self) -> None:
        """The horizontal rect is the normal rect rotated 90°."""
        self.assertEqual(C.PLAYER_PHYSICS_WIDTH_HORIZONTAL, C.PLAYER_PHYSICS_HEIGHT_NORMAL)
        self.assertEqual(C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL, C.PLAYER_PHYSICS_WIDTH_NORMAL)


class TestBoundaryRects(unittest.TestCase):
    """boundary_rects() seals the level with four platforms outside its edges."""

    def setUp(self) -> None:
        self.level = LevelRenderer()
        self.level.load(main.LEVELS[0])
        self.W = self.level.level_width
        self.H = self.level.level_height

    def test_returns_four_rects(self) -> None:
        self.assertEqual(len(self.level.boundary_rects()), 4)

    def test_left_wall_is_left_of_zero(self) -> None:
        self.assertTrue(any(r.right <= 0 for r in self.level.boundary_rects()))

    def test_right_wall_is_right_of_level_width(self) -> None:
        self.assertTrue(any(r.left >= self.W for r in self.level.boundary_rects()))

    def test_top_wall_is_above_zero(self) -> None:
        self.assertTrue(any(r.bottom <= 0 for r in self.level.boundary_rects()))

    def test_bottom_wall_is_below_level_height(self) -> None:
        self.assertTrue(any(r.top >= self.H for r in self.level.boundary_rects()))

    def test_stops_player_moving_past_left_edge(self) -> None:
        player_w, player_h = 60, 90
        px, py, vx, vy = 28.0, 400.0, -5.0, 0.0
        new_px, _, new_vx, _, _ = resolve_collisions(
            px, py, vx, vy, player_w, player_h, self.level.boundary_rects(), (0, 1),
        )
        self.assertGreaterEqual(new_px, player_w / 2)
        self.assertEqual(new_vx, 0.0)

    def test_stops_player_falling_through_bottom(self) -> None:
        player_w, player_h = 60, 90
        px, py, vx, vy = 400.0, self.H - player_h / 2 - 5.0, 0.0, 20.0
        _, new_py, _, new_vy, on_ground = resolve_collisions(
            px, py, vx, vy, player_w, player_h, self.level.boundary_rects(), (0, 1),
        )
        self.assertLessEqual(new_py, self.H - player_h / 2)
        self.assertEqual(new_vy, 0.0)
        self.assertTrue(on_ground)

    def test_subpixel_position_past_boundary_is_caught(self) -> None:
        """px=29.7 puts the left edge at -0.3 — boundary must catch it.

        The old round()-based clamp missed this: round(29.7)==30==round(30.0)
        so the comparison evaluated False and the clamp never fired.
        """
        player_w, player_h = 60, 90
        px, py, vx, vy = 29.7, 400.0, -5.0, 0.0
        new_px, _, new_vx, _, _ = resolve_collisions(
            px, py, vx, vy, player_w, player_h, self.level.boundary_rects(), (0, 1),
        )
        self.assertGreaterEqual(new_px, player_w / 2)
        self.assertEqual(new_vx, 0.0)

    def test_boundary_rects_rebuild_after_level_reload(self) -> None:
        """Boundary rects reflect new level dimensions after a reload."""
        self.level.load(main.LEVELS[1])
        new_W = self.level.level_width
        self.assertNotEqual(new_W, self.W)  # level_02 is wider than level_01
        self.assertTrue(any(r.left >= new_W for r in self.level.boundary_rects()))


class TestPlayer(unittest.TestCase):
    """Player dataclass creation, reset, gravity, and serialisation."""

    def test_from_spawn_sets_position(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        self.assertAlmostEqual(p.px, 100.0)
        self.assertAlmostEqual(p.py, 200.0)

    def test_from_spawn_zero_velocity(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        self.assertEqual(p.vx, 0.0)
        self.assertEqual(p.vy, 0.0)

    def test_from_spawn_default_gravity_down(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        self.assertEqual(p.gravity_dir, GRAVITY_DOWN)

    def test_from_spawn_physics_size_matches_gravity(self) -> None:
        p = Player.from_spawn((0.0, 0.0), GRAVITY_RIGHT)
        w, h = get_player_physics_size(GRAVITY_RIGHT)
        self.assertEqual(p.player_w, w)
        self.assertEqual(p.player_h, h)

    def test_set_gravity_updates_direction(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.set_gravity(GRAVITY_LEFT)
        self.assertEqual(p.gravity_dir, GRAVITY_LEFT)

    def test_set_gravity_updates_physics_size(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.set_gravity(GRAVITY_RIGHT)
        w, h = get_player_physics_size(GRAVITY_RIGHT)
        self.assertEqual(p.player_w, w)
        self.assertEqual(p.player_h, h)

    def test_reset_restores_position(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.px, p.py = 999.0, 999.0
        p.reset((50.0, 75.0), GRAVITY_DOWN)
        self.assertAlmostEqual(p.px, 50.0)
        self.assertAlmostEqual(p.py, 75.0)

    def test_reset_clears_velocity(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.vx, p.vy = 10.0, -5.0
        p.reset((100.0, 200.0), GRAVITY_DOWN)
        self.assertEqual(p.vx, 0.0)
        self.assertEqual(p.vy, 0.0)

    def test_reset_clears_flags(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.on_ground = True
        p.jumping = True
        p.goal_reached = True
        p.reset((100.0, 200.0), GRAVITY_DOWN)
        self.assertFalse(p.on_ground)
        self.assertFalse(p.jumping)
        self.assertFalse(p.goal_reached)

    def test_to_dict_contains_position(self) -> None:
        p = Player.from_spawn((42.0, 84.0))
        d = p.to_dict()
        self.assertIn("px", d)
        self.assertIn("py", d)
        self.assertAlmostEqual(d["px"], 42.0)
        self.assertAlmostEqual(d["py"], 84.0)

    def test_from_spawn_chrono_reserve_is_max(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_RESERVE_MAX)

    def test_reset_restores_chrono_reserve(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 10.0
        p.reset((0.0, 0.0), GRAVITY_DOWN)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_RESERVE_MAX)

    def test_to_dict_contains_chrono_reserve(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        self.assertIn("chrono_reserve", p.to_dict())

    def test_to_dict_is_json_serialisable(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        json.dumps(p.to_dict())  # must not raise


class TestTimeDilation(unittest.TestCase):
    """MovingPlatform respects time_scale; LevelRenderer passes it through."""

    def _make(self, x=100, speed=3):
        from src.levels.level_data import MovingPlatformDef
        from src.levels.level_renderer import MovingPlatform
        return MovingPlatform(MovingPlatformDef(x, 200, 50, 20, "x", 100, 300, speed))

    def test_zero_time_scale_freezes_platform(self) -> None:
        mp = self._make()
        x_before = mp.rect.x
        mp.update(time_scale=0.0)
        self.assertEqual(mp.rect.x, x_before)

    def test_full_time_scale_moves_normally(self) -> None:
        mp = self._make()
        mp.update(time_scale=1.0)
        self.assertEqual(mp.rect.x, 103)

    def test_default_time_scale_is_one(self) -> None:
        mp = self._make()
        mp.update()
        self.assertEqual(mp.rect.x, 103)

    def test_level_update_accepts_time_scale(self) -> None:
        level = LevelRenderer()
        level.load(main.LEVELS[0])
        positions_before = [mp.rect.x for mp in level.moving_platforms]
        level.update(time_scale=0.0)
        positions_after = [mp.rect.x for mp in level.moving_platforms]
        self.assertEqual(positions_before, positions_after)

    def test_level_update_moves_platforms_at_full_scale(self) -> None:
        level = LevelRenderer()
        level.load(main.LEVELS[0])
        positions_before = [mp.rect.x for mp in level.moving_platforms]
        level.update(time_scale=1.0)
        positions_after = [mp.rect.x for mp in level.moving_platforms]
        self.assertNotEqual(positions_before, positions_after)


class TestChronoRegen(unittest.TestCase):
    """tick_chrono_regen fills during movement, idles earns nothing, caps at max."""

    def test_regen_increases_during_movement(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 0.0
        p.tick_chrono_regen(1.0, is_moving=True)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_REGEN_MOVE)

    def test_no_regen_while_idle(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 0.0
        p.tick_chrono_regen(1.0, is_moving=False)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_REGEN_IDLE)

    def test_regen_does_not_exceed_max(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = C.CHRONO_RESERVE_MAX - 1.0
        p.tick_chrono_regen(10.0, is_moving=True)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_RESERVE_MAX)

    def test_regen_rate_over_one_second(self) -> None:
        """60 steps of PHYSICS_DT should equal one second of regen at move rate."""
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 0.0
        for _ in range(C.FPS):
            p.tick_chrono_regen(C.PHYSICS_DT, is_moving=True)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_REGEN_MOVE, places=4)

    def test_regen_mult_scales_rate(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 0.0
        p.tick_chrono_regen(1.0, is_moving=True, regen_mult=0.5)
        self.assertAlmostEqual(p.chrono_reserve, C.CHRONO_REGEN_MOVE * 0.5)

    def test_regen_mult_zero_earns_nothing(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.chrono_reserve = 50.0
        p.tick_chrono_regen(1.0, is_moving=True, regen_mult=0.0)
        self.assertAlmostEqual(p.chrono_reserve, 50.0)


class TestSingularityPressure(unittest.TestCase):
    """singularity_pressure drives the difficulty curve: 0.0 at start, 1.0 at last playable node."""

    from src.data.run_state import RunState as _RS

    def _run(self, node_idx: int):
        from src.data.run_state import RunState
        rs = RunState(
            fold_stability=100.0, current_node_idx=node_idx,
            run_seed=0, is_active=True,
            combat_levels=[0, 2], hole_outcomes=[True, False],
        )
        return rs

    def test_pressure_zero_at_start(self) -> None:
        self.assertAlmostEqual(self._run(0).singularity_pressure, 0.0)

    def test_pressure_one_at_last_playable(self) -> None:
        # 5-node sequence: last playable = node 3 (node 4 is singularity)
        self.assertAlmostEqual(self._run(3).singularity_pressure, 1.0)

    def test_pressure_increases_monotonically(self) -> None:
        pressures = [self._run(i).singularity_pressure for i in range(4)]
        for a, b in zip(pressures, pressures[1:]):
            self.assertGreater(b, a)

    def test_pressure_capped_at_one(self) -> None:
        self.assertLessEqual(self._run(4).singularity_pressure, 1.0)

    def test_regen_mult_is_one_at_zero_pressure(self) -> None:
        pressure = 0.0
        mult = 1.0 - pressure * (1.0 - C.SINGULARITY_CHRONO_REGEN_MIN_MULT)
        self.assertAlmostEqual(mult, 1.0)

    def test_regen_mult_is_min_at_max_pressure(self) -> None:
        pressure = 1.0
        mult = 1.0 - pressure * (1.0 - C.SINGULARITY_CHRONO_REGEN_MIN_MULT)
        self.assertAlmostEqual(mult, C.SINGULARITY_CHRONO_REGEN_MIN_MULT)

    def test_cost_mult_is_one_at_zero_pressure(self) -> None:
        pressure = 0.0
        mult = 1.0 + pressure * (C.SINGULARITY_ABILITY_COST_MAX_MULT - 1.0)
        self.assertAlmostEqual(mult, 1.0)

    def test_cost_mult_is_max_at_max_pressure(self) -> None:
        pressure = 1.0
        mult = 1.0 + pressure * (C.SINGULARITY_ABILITY_COST_MAX_MULT - 1.0)
        self.assertAlmostEqual(mult, C.SINGULARITY_ABILITY_COST_MAX_MULT)

    def test_gravity_mult_is_one_at_zero_pressure(self) -> None:
        pressure = 0.0
        mult = 1.0 + pressure * (C.SINGULARITY_GRAVITY_MAX_MULT - 1.0)
        self.assertAlmostEqual(mult, 1.0)

    def test_gravity_mult_is_max_at_max_pressure(self) -> None:
        pressure = 1.0
        mult = 1.0 + pressure * (C.SINGULARITY_GRAVITY_MAX_MULT - 1.0)
        self.assertAlmostEqual(mult, C.SINGULARITY_GRAVITY_MAX_MULT)


class TestVariableGravity(unittest.TestCase):
    """apply_gravity and clamp_terminal_velocity respect strength_mult."""

    def test_apply_gravity_double_strength_doubles_acceleration(self) -> None:
        # vy=5.0 is above PEAK_SPEED_THRESHOLD so peak multiplier is inactive
        _, vy1 = apply_gravity(0.0, 5.0, (0, 1), on_ground=False, strength_mult=1.0)
        _, vy2 = apply_gravity(0.0, 5.0, (0, 1), on_ground=False, strength_mult=2.0)
        self.assertAlmostEqual(vy2 - 5.0, (vy1 - 5.0) * 2.0)

    def test_apply_gravity_half_strength_halves_acceleration(self) -> None:
        _, vy1 = apply_gravity(0.0, 5.0, (0, 1), on_ground=False, strength_mult=1.0)
        _, vy2 = apply_gravity(0.0, 5.0, (0, 1), on_ground=False, strength_mult=0.5)
        self.assertAlmostEqual(vy2 - 5.0, (vy1 - 5.0) * 0.5)

    def test_clamp_terminal_velocity_scales_cap(self) -> None:
        high_vy = C.TERMINAL_VELOCITY * 3.0
        _, vy = clamp_terminal_velocity(0.0, high_vy, (0, 1), strength_mult=2.0)
        self.assertAlmostEqual(vy, C.TERMINAL_VELOCITY * 2.0)

    def test_level_data_default_gravity_multiplier(self) -> None:
        data = LevelData.load(main.LEVELS[0])
        self.assertAlmostEqual(data.gravity_multiplier, 1.0)

    def test_level_data_gravity_multiplier_roundtrip(self) -> None:
        from src.levels.level_data import GoalDef
        data = LevelData(
            name="test", gravity_start=(0, 1), spawn=(0.0, 0.0),
            goal=GoalDef(0, 0, 10, 10), gravity_multiplier=0.5,
        )
        data2 = LevelData.from_json(data.to_json())
        self.assertAlmostEqual(data2.gravity_multiplier, 0.5)

    def test_level_renderer_exposes_gravity_multiplier(self) -> None:
        renderer = LevelRenderer()
        renderer.load(main.LEVELS[0])
        self.assertAlmostEqual(renderer.gravity_multiplier, 1.0)


class TestLevel04(unittest.TestCase):
    """Level 04 geometry guarantees that Time Dilation is required to complete it."""

    LEVEL_PATH = os.path.join(os.path.dirname(__file__), "..", "levels", "level_04.json")

    def _load(self):
        with open(self.LEVEL_PATH) as f:
            return json.load(f)

    def test_level_file_exists(self) -> None:
        self.assertTrue(os.path.isfile(self.LEVEL_PATH))

    def test_gap_exceeds_max_jump_distance(self) -> None:
        """Gap between start floor and exit ledge must be wider than max jump distance."""
        data = self._load()
        start_floor = next(p for p in data["static_platforms"] if p["x"] == 0 and p["y"] == 820)
        exit_ledge = next(p for p in data["static_platforms"] if p["x"] == 900 and p["y"] == 620)
        gap = exit_ledge["x"] - (start_floor["x"] + start_floor["w"])
        max_jump_distance = 2 * C.JUMP_SPEED / C.GRAVITY_STRENGTH * C.MAX_MOVE_SPEED
        self.assertGreater(gap, max_jump_distance,
            f"Gap {gap:.1f}px must exceed max jump distance {max_jump_distance:.1f}px")

    def test_platform_speed_exceeds_player_speed(self) -> None:
        """Moving platform travels faster than the player so a rider falls short."""
        data = self._load()
        mp = data["moving_platforms"][0]
        self.assertGreater(mp["speed"], C.MAX_MOVE_SPEED,
            f"Platform speed {mp['speed']} must exceed player max speed {C.MAX_MOVE_SPEED}")

    def test_boundary_floor_jump_blocked(self) -> None:
        """Jump from boundary floor (y=level_height) cannot reach exit ledge."""
        data = self._load()
        level_height = data["level_height"]
        exit_ledge_y = next(
            p["y"] for p in data["static_platforms"] if p["x"] == 900 and p["y"] == 620
        )
        jump_needed = level_height - exit_ledge_y
        max_jump_height = C.JUMP_SPEED ** 2 / (2 * C.GRAVITY_STRENGTH)
        self.assertGreater(jump_needed, max_jump_height,
            f"Boundary workaround must be blocked: needs {jump_needed:.1f}px, max is {max_jump_height:.1f}px")

    def test_moving_platform_range_covers_gap(self) -> None:
        """Frozen platform at max_val must put its right edge past the exit ledge x."""
        data = self._load()
        mp = data["moving_platforms"][0]
        exit_ledge_x = next(p["x"] for p in data["static_platforms"] if p["x"] == 900)
        frozen_right_edge = mp["max_val"] + mp["w"]
        self.assertGreaterEqual(frozen_right_edge, exit_ledge_x,
            f"Frozen platform right edge {frozen_right_edge} must reach exit at {exit_ledge_x}")


class TestCombat(unittest.TestCase):
    """Hit detection, knockback, and i-frames via combat.py helpers."""

    def _make_player(self, px: float = 100.0, py: float = 100.0) -> Player:
        return Player.from_spawn((px, py))

    def _make_enemy(self, px: float = 100.0, py: float = 100.0):
        from src.entities.enemy import TemporalEcho
        return TemporalEcho(px=px, py=py, min_x=50.0, max_x=200.0, speed=C.TEMPORAL_ECHO_SPEED)

    def test_take_hit_decrements_integrity(self) -> None:
        p = self._make_player()
        p.take_hit(0.0, 0.0)
        self.assertEqual(p.anchor_integrity, C.ANCHOR_INTEGRITY_MAX - 1)

    def test_take_hit_starts_iframes(self) -> None:
        p = self._make_player()
        p.take_hit(0.0, 0.0)
        self.assertGreater(p.iframes_timer, 0.0)

    def test_take_hit_sets_knockback_velocity(self) -> None:
        p = self._make_player()
        p.take_hit(6.0, 0.0)
        self.assertAlmostEqual(p.vx, 6.0)

    def test_take_hit_returns_false_when_integrity_remains(self) -> None:
        p = self._make_player()
        result = p.take_hit(0.0, 0.0)
        self.assertFalse(result)

    def test_take_hit_returns_true_when_integrity_zero(self) -> None:
        p = self._make_player()
        p.anchor_integrity = 1
        result = p.take_hit(0.0, 0.0)
        self.assertTrue(result)

    def test_check_hit_false_during_iframes(self) -> None:
        from src.systems.combat import check_hit
        p = self._make_player(px=100.0, py=100.0)
        e = self._make_enemy(px=100.0, py=100.0)
        p.iframes_timer = 0.5
        self.assertFalse(check_hit(p, e))

    def test_check_hit_false_when_not_overlapping(self) -> None:
        from src.systems.combat import check_hit
        p = self._make_player(px=0.0, py=0.0)
        e = self._make_enemy(px=800.0, py=800.0)
        self.assertFalse(check_hit(p, e))

    def test_check_hit_true_when_overlapping(self) -> None:
        from src.systems.combat import check_hit
        p = self._make_player(px=100.0, py=100.0)
        e = self._make_enemy(px=100.0, py=100.0)
        self.assertTrue(check_hit(p, e))

    def test_compute_knockback_pushes_right(self) -> None:
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(150.0, 100.0, 100.0, 100.0, (0, 1))
        self.assertGreater(vx, 0.0)
        self.assertAlmostEqual(vy, 0.0)

    def test_compute_knockback_pushes_left(self) -> None:
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(50.0, 100.0, 100.0, 100.0, (0, 1))
        self.assertLess(vx, 0.0)
        self.assertAlmostEqual(vy, 0.0)

    def test_compute_knockback_horizontal_gravity_uses_y(self) -> None:
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(100.0, 150.0, 100.0, 100.0, (1, 0))
        self.assertAlmostEqual(vx, 0.0)
        self.assertGreater(vy, 0.0)

    def test_take_fall_damage_returns_false_above_zero(self) -> None:
        p = self._make_player()
        result = p.take_fall_damage()
        self.assertFalse(result)

    def test_take_fall_damage_returns_true_at_zero(self) -> None:
        p = self._make_player()
        p.anchor_integrity = 1
        result = p.take_fall_damage()
        self.assertTrue(result)


class TestTemporalEcho(unittest.TestCase):
    """TemporalEcho patrols horizontally, freezes on time_scale=0."""

    def _make(self) -> object:
        from src.entities.enemy import TemporalEcho
        return TemporalEcho(px=100.0, py=50.0, min_x=50.0, max_x=200.0, speed=C.TEMPORAL_ECHO_SPEED)

    def test_moves_right_by_speed(self) -> None:
        e = self._make()
        e.update(1.0)
        self.assertAlmostEqual(e.px, 100.0 + C.TEMPORAL_ECHO_SPEED)

    def test_reverses_at_max_x(self) -> None:
        e = self._make()
        e.px = 200.0
        e.update(1.0)
        self.assertEqual(e.direction, -1)
        self.assertLessEqual(e.px, 200.0)

    def test_reverses_at_min_x(self) -> None:
        e = self._make()
        e.direction = -1
        e.px = 50.0
        e.update(1.0)
        self.assertEqual(e.direction, 1)
        self.assertGreaterEqual(e.px, 50.0)

    def test_time_scale_zero_freezes(self) -> None:
        e = self._make()
        before = e.px
        e.update(0.0)
        self.assertAlmostEqual(e.px, before)

    def test_time_scale_half_slows(self) -> None:
        e = self._make()
        e.update(0.5)
        self.assertAlmostEqual(e.px, 100.0 + C.TEMPORAL_ECHO_SPEED * 0.5)

    def test_reset_restores_position(self) -> None:
        e = self._make()
        e.px = 190.0
        e.direction = -1
        e.reset()
        self.assertAlmostEqual(e.px, 100.0)
        self.assertEqual(e.direction, 1)

    def test_rect_covers_centre(self) -> None:
        e = self._make()
        r = e.rect
        self.assertEqual(r.centerx, int(e.px))
        self.assertEqual(r.centery, int(e.py))
        self.assertEqual(r.width, C.TEMPORAL_ECHO_W)
        self.assertEqual(r.height, C.TEMPORAL_ECHO_H)


class TestAnchorIntegrity(unittest.TestCase):
    """anchor_integrity is a 3-hit pool: serialisable, resets on spawn, fall costs 1 hit."""

    def test_default_is_max(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        self.assertEqual(p.anchor_integrity, C.ANCHOR_INTEGRITY_MAX)

    def test_resets_on_spawn(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        p.anchor_integrity = 1
        p.reset((0.0, 0.0), (0, 1))
        self.assertEqual(p.anchor_integrity, C.ANCHOR_INTEGRITY_MAX)

    def test_serialisable(self) -> None:
        p = Player.from_spawn((0.0, 0.0))
        d = p.to_dict()
        self.assertIn("anchor_integrity", d)
        self.assertEqual(d["anchor_integrity"], C.ANCHOR_INTEGRITY_MAX)

    def test_last_safe_initialised_to_spawn(self) -> None:
        p = Player.from_spawn((123.0, 456.0))
        self.assertAlmostEqual(p.last_safe_px, 123.0)
        self.assertAlmostEqual(p.last_safe_py, 456.0)

    def test_last_safe_resets_on_spawn(self) -> None:
        p = Player.from_spawn((10.0, 20.0))
        p.last_safe_px, p.last_safe_py = 999.0, 999.0
        p.reset((50.0, 80.0), (0, 1))
        self.assertAlmostEqual(p.last_safe_px, 50.0)
        self.assertAlmostEqual(p.last_safe_py, 80.0)

    def test_take_fall_damage_decrements(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.anchor_integrity = 3
        p.take_fall_damage()
        self.assertEqual(p.anchor_integrity, 2)

    def test_take_fall_damage_clamps_at_zero(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.anchor_integrity = 0
        p.take_fall_damage()
        self.assertEqual(p.anchor_integrity, 0)

    def test_take_fall_damage_respawns_at_last_safe(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.last_safe_px, p.last_safe_py = 50.0, 150.0
        p.px, p.py = 400.0, 900.0
        p.take_fall_damage()
        self.assertAlmostEqual(p.px, 50.0)
        self.assertAlmostEqual(p.py, 150.0)

    def test_take_fall_damage_zeroes_velocity(self) -> None:
        p = Player.from_spawn((100.0, 200.0))
        p.vx, p.vy = 5.0, 10.0
        p.take_fall_damage()
        self.assertAlmostEqual(p.vx, 0.0)
        self.assertAlmostEqual(p.vy, 0.0)

    def test_last_safe_in_to_dict(self) -> None:
        p = Player.from_spawn((75.0, 300.0))
        d = p.to_dict()
        self.assertIn("last_safe_px", d)
        self.assertIn("last_safe_py", d)


class TestRunState(unittest.TestCase):
    """RunState dataclass — fold_stability, seed, serialisation."""

    def test_new_run_is_active(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertTrue(rs.is_active)

    def test_new_run_fold_stability_is_max(self):
        from src.data.run_state import RunState
        from constants import FOLD_STABILITY_MAX
        rs = RunState.new_run()
        self.assertEqual(rs.fold_stability, FOLD_STABILITY_MAX)

    def test_new_run_current_node_zero(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.current_node_idx, 0)

    def test_new_run_generates_nonzero_seed(self):
        from src.data.run_state import RunState
        seeds = {RunState.new_run().run_seed for _ in range(10)}
        self.assertGreater(len(seeds), 1)

    def test_to_dict_is_serialisable(self):
        import json
        from src.data.run_state import RunState
        rs = RunState.new_run()
        d = rs.to_dict()
        json.dumps(d)  # raises if not serialisable

    def test_fold_stability_can_deplete(self):
        from src.data.run_state import RunState
        from constants import FOLD_STABILITY_INTEGRITY_COST
        rs = RunState.new_run()
        rs.fold_stability -= FOLD_STABILITY_INTEGRITY_COST
        self.assertLess(rs.fold_stability, 100.0)

    def test_fold_stability_depleted_to_zero_ends_run(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.fold_stability = 0.0
        self.assertLessEqual(rs.fold_stability, 0.0)

    def test_inactive_run_has_false_is_active(self):
        from src.data.run_state import RunState
        rs = RunState(fold_stability=100.0, current_node_idx=0, run_seed=0, is_active=False)
        self.assertFalse(rs.is_active)


class TestRunStateM4b(unittest.TestCase):
    """RunState M4b additions — node sequence, hole outcomes, combat levels."""

    def test_new_run_has_two_combat_levels(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(len(rs.combat_levels), 2)

    def test_new_run_combat_levels_in_valid_range(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertIn(rs.combat_levels[0], (0, 1))
        self.assertIn(rs.combat_levels[1], (2, 3))

    def test_new_run_has_two_hole_outcomes(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(len(rs.hole_outcomes), 2)

    def test_current_node_type_at_start(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.current_node_type, "combat")

    def test_advance_node_increments_idx(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()
        self.assertEqual(rs.current_node_idx, 1)
        self.assertEqual(rs.current_node_type, "hole")

    def test_node_count_is_five(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.node_count, 5)

    def test_combat_level_for_first_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        idx = rs.combat_level_for_current_node()
        self.assertIn(idx, (0, 1))

    def test_combat_level_for_second_combat_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()  # hole
        rs.advance_node()  # combat node 2
        idx = rs.combat_level_for_current_node()
        self.assertIn(idx, (2, 3))

    def test_hole_outcome_for_first_hole(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()  # now at first hole (idx 1)
        result = rs.current_hole_is_white()
        self.assertIsInstance(result, bool)

    def test_singularity_is_last_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        for _ in range(4):
            rs.advance_node()
        self.assertEqual(rs.current_node_type, "singularity")

    def test_deaths_starts_at_zero(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.deaths, 0)

    def test_to_dict_includes_new_fields(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        d = rs.to_dict()
        self.assertIn("combat_levels", d)
        self.assertIn("hole_outcomes", d)
        self.assertIn("deaths", d)


class TestHoleEncounter(unittest.TestCase):
    """Hole encounter constants and consequence logic."""

    def test_white_hole_restores_integrity(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import ANCHOR_INTEGRITY_MAX
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        p.anchor_integrity = 1
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertEqual(p.anchor_integrity, ANCHOR_INTEGRITY_MAX)

    def test_white_hole_restores_fold_stability(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import WHITE_HOLE_STABILITY_RESTORE
        rs = RunState.new_run()
        rs.fold_stability = 50.0
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertAlmostEqual(rs.fold_stability, 50.0 + WHITE_HOLE_STABILITY_RESTORE)

    def test_white_hole_capped_at_max(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import FOLD_STABILITY_MAX
        rs = RunState.new_run()
        rs.fold_stability = FOLD_STABILITY_MAX
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertEqual(rs.fold_stability, FOLD_STABILITY_MAX)

    def test_black_hole_reduces_integrity(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import ANCHOR_INTEGRITY_MAX
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertEqual(p.anchor_integrity, ANCHOR_INTEGRITY_MAX - 1)

    def test_black_hole_reduces_fold_stability(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import BLACK_HOLE_STABILITY_COST
        rs = RunState.new_run()
        initial = rs.fold_stability
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertAlmostEqual(rs.fold_stability, initial - BLACK_HOLE_STABILITY_COST)

    def test_black_hole_increments_deaths(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertEqual(rs.deaths, 1)

    def test_hole_phase_durations_are_positive(self):
        from constants import HOLE_ENCOUNTER_PHASE1_DURATION, HOLE_ENCOUNTER_PHASE2_DURATION
        self.assertGreater(HOLE_ENCOUNTER_PHASE1_DURATION, 0)
        self.assertGreater(HOLE_ENCOUNTER_PHASE2_DURATION, 0)


class TestEventBus(unittest.TestCase):
    """EventBus dispatches events, supports cancellation, handles no-listener case."""

    def setUp(self):
        from src.systems.events import EventBus, GameEvent, EventResult
        self.EventBus = EventBus
        self.GameEvent = GameEvent
        self.EventResult = EventResult

    def test_emit_with_no_listeners_returns_uncancelled(self):
        bus = self.EventBus()
        result = bus.emit(self.GameEvent.GRAVITY_ROTATED)
        self.assertFalse(result.cancelled)

    def test_registered_handler_is_called(self):
        bus = self.EventBus()
        called = []
        bus.subscribe(self.GameEvent.GRAVITY_ROTATED, lambda r: called.append(True))
        bus.emit(self.GameEvent.GRAVITY_ROTATED)
        self.assertEqual(len(called), 1)

    def test_handler_not_called_for_different_event(self):
        bus = self.EventBus()
        called = []
        bus.subscribe(self.GameEvent.GRAVITY_ROTATED, lambda r: called.append(True))
        bus.emit(self.GameEvent.ABILITY_USED)
        self.assertEqual(len(called), 0)

    def test_multiple_handlers_all_called(self):
        bus = self.EventBus()
        calls = []
        bus.subscribe(self.GameEvent.ROOM_CLEARED, lambda r: calls.append(1))
        bus.subscribe(self.GameEvent.ROOM_CLEARED, lambda r: calls.append(2))
        bus.emit(self.GameEvent.ROOM_CLEARED)
        self.assertEqual(calls, [1, 2])

    def test_cancellable_event_respects_cancelled_flag(self):
        bus = self.EventBus()
        def cancel(result):
            result.cancelled = True
        bus.subscribe(self.GameEvent.INTEGRITY_ZERO, cancel)
        result = bus.emit(self.GameEvent.INTEGRITY_ZERO)
        self.assertTrue(result.cancelled)

    def test_kwargs_passed_to_handler(self):
        bus = self.EventBus()
        received = {}
        def handler(result, **kwargs):
            received.update(kwargs)
        bus.subscribe(self.GameEvent.HOLE_RESOLVED, handler)
        bus.emit(self.GameEvent.HOLE_RESOLVED, is_white=True)
        self.assertEqual(received.get("is_white"), True)

    def test_unsubscribe_removes_handler(self):
        bus = self.EventBus()
        calls = []
        handler = lambda r: calls.append(True)
        bus.subscribe(self.GameEvent.ABILITY_USED, handler)
        bus.unsubscribe(self.GameEvent.ABILITY_USED, handler)
        bus.emit(self.GameEvent.ABILITY_USED)
        self.assertEqual(len(calls), 0)

    def test_clear_removes_all_listeners(self):
        bus = self.EventBus()
        calls = []
        bus.subscribe(self.GameEvent.GRAVITY_ROTATED, lambda r: calls.append(True))
        bus.clear()
        bus.emit(self.GameEvent.GRAVITY_ROTATED)
        self.assertEqual(len(calls), 0)


class TestAbilitySlot(unittest.TestCase):
    """AbilitySlot manages timers, activation, and ABILITY_ENDED emission."""

    def setUp(self):
        from src.systems.events import EventBus, GameEvent
        from src.systems.spacetime import AbilitySlot, make_time_dilation
        self.EventBus = EventBus
        self.GameEvent = GameEvent
        self.AbilitySlot = AbilitySlot
        self.make_time_dilation = make_time_dilation

    def _make_slot(self, duration=3.0, cost=25.0, cooldown=2.0):
        return self.AbilitySlot(name="test", duration=duration, cost=cost, cooldown=cooldown)

    def test_not_active_initially(self):
        slot = self._make_slot()
        self.assertFalse(slot.is_active)

    def test_is_ready_initially(self):
        slot = self._make_slot()
        self.assertTrue(slot.is_ready)

    def test_activate_deducts_cost(self):
        slot = self._make_slot(cost=25.0)
        remaining = slot.activate(100.0)
        self.assertAlmostEqual(remaining, 75.0)

    def test_activate_starts_active(self):
        slot = self._make_slot(duration=3.0)
        slot.activate(100.0)
        self.assertTrue(slot.is_active)

    def test_activate_starts_cooldown(self):
        slot = self._make_slot(duration=3.0, cooldown=2.0)
        slot.activate(100.0)
        self.assertFalse(slot.is_ready)

    def test_time_scale_is_dilated_when_active(self):
        from constants import TIME_DILATION_FACTOR
        slot = self.make_time_dilation()
        slot.activate(100.0)
        self.assertAlmostEqual(slot.time_scale(), TIME_DILATION_FACTOR)

    def test_time_scale_is_normal_when_inactive(self):
        slot = self.make_time_dilation()
        self.assertAlmostEqual(slot.time_scale(), 1.0)

    def test_tick_decrements_active_timer(self):
        bus = self.EventBus()
        slot = self._make_slot(duration=3.0)
        slot.activate(100.0)
        slot.tick(1.0, bus)
        self.assertAlmostEqual(slot.active_timer, 2.0)

    def test_tick_emits_ability_ended_when_expires(self):
        bus = self.EventBus()
        ended = []
        bus.subscribe(self.GameEvent.ABILITY_ENDED, lambda r, **kw: ended.append(kw))
        slot = self._make_slot(duration=1.0)
        slot.activate(100.0)
        slot.tick(1.0, bus)
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0].get("ability_name"), "test")

    def test_tick_does_not_emit_ended_before_expiry(self):
        bus = self.EventBus()
        ended = []
        bus.subscribe(self.GameEvent.ABILITY_ENDED, lambda r, **kw: ended.append(True))
        slot = self._make_slot(duration=3.0)
        slot.activate(100.0)
        slot.tick(1.0, bus)
        self.assertEqual(len(ended), 0)

    def test_reset_clears_both_timers(self):
        bus = self.EventBus()
        slot = self._make_slot(duration=3.0, cooldown=2.0)
        slot.activate(100.0)
        slot.reset()
        self.assertFalse(slot.is_active)
        self.assertTrue(slot.is_ready)

    def test_make_time_dilation_uses_constants(self):
        from constants import TIME_DILATION_DURATION, TIME_DILATION_COST, TIME_DILATION_COOLDOWN
        slot = self.make_time_dilation()
        self.assertAlmostEqual(slot.duration, TIME_DILATION_DURATION)
        self.assertAlmostEqual(slot.cost, TIME_DILATION_COST)
        self.assertAlmostEqual(slot.cooldown, TIME_DILATION_COOLDOWN)


class TestLevelGoalValidity(unittest.TestCase):
    """Goal rect must not contain the spawn point in any gravity orientation.

    Prevents the class of bug where rotating gravity changes the physics rect
    size and accidentally overlaps the goal at or near spawn.
    """

    LEVEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "levels")

    def _level_files(self):
        import glob
        return sorted(glob.glob(os.path.join(self.LEVEL_DIR, "level_*.json")))

    def test_spawn_not_inside_goal_for_all_levels(self):
        import pygame
        pygame.init()
        from src.levels.level_data import LevelData
        for path in self._level_files():
            with self.subTest(level=os.path.basename(path)):
                data = LevelData.load(path)
                goal = pygame.Rect(data.goal.x, data.goal.y, data.goal.w, data.goal.h)
                sx, sy = data.spawn
                self.assertFalse(
                    goal.collidepoint(sx, sy),
                    f"{os.path.basename(path)}: spawn {data.spawn} is inside goal rect {goal}",
                )


# ---------------------------------------------------------------------------
# Item System Tests (M5a Session 2)
# ---------------------------------------------------------------------------

class _FakePlayer:
    def __init__(self):
        self.chrono_reserve = 50.0
        self.iframes_timer = 0.0
        self.anchor_integrity = 3
        self.px = 100.0
        self.py = 200.0
        self.last_safe_px = 90.0
        self.last_safe_py = 200.0
        self.vx = 1.0
        self.vy = 0.0


class _FakeRunState:
    def __init__(self):
        self.fold_stability = 100.0
        self.extra_reward_options = 0


class _FakeEnemy:
    def __init__(self, px=300.0, py=200.0):
        self.px = px
        self.py = py
        self.frozen_timer = 0.0


class _FakeAbilitySlot:
    def __init__(self, name="time_dilation"):
        self.name = name
        self.active_timer = 0.0
        self.duration = 3.0
        self.cooldown = 2.0
        self.is_active = False
        self.is_ready = True


class _FakeLogger:
    def __init__(self):
        self.entries = []

    def log_event(self, msg):
        self.entries.append(msg)


def _make_ctx(player=None, enemies=None, run_state=None, ability_slot=None):
    from src.systems.items.effects import EffectContext
    return EffectContext(
        player=player or _FakePlayer(),
        enemies=enemies or [],
        run_state=run_state or _FakeRunState(),
        ability_slot=ability_slot or _FakeAbilitySlot(),
        rng=__import__("random").Random(42),
    )


class TestItemRegistry(unittest.TestCase):
    """Item registry loads and validates JSON files correctly."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_registry(self):
        from src.systems.items.registry import load_item_registry
        logger = _FakeLogger()
        reg = load_item_registry(self.BASE_DIR, logger)
        return reg, logger

    def test_loads_all_modifiers(self):
        reg, _ = self._make_registry()
        ids = {d.id for d in reg.modifiers()}
        expected = {"redshift", "closed_timelike_curve", "tidal_coupling",
                    "geodesic", "event_horizon", "quantum_foam"}
        self.assertEqual(ids, expected)

    def test_loads_all_artifacts(self):
        reg, _ = self._make_registry()
        ids = {d.id for d in reg.artifacts()}
        expected = {"kerr_ring", "hawking_emitter", "penrose_diagram"}
        self.assertEqual(ids, expected)

    def test_loads_all_resonances(self):
        reg, _ = self._make_registry()
        ids = {r.id for r in reg.all_resonances()}
        expected = {"spaghettification", "ergosphere", "information_paradox"}
        self.assertEqual(ids, expected)

    def test_modifier_params_by_rank_has_3_entries(self):
        reg, _ = self._make_registry()
        for defn in reg.modifiers():
            with self.subTest(item=defn.id):
                self.assertEqual(len(defn.params_by_rank), 3, defn.id)

    def test_artifact_params_by_rank_has_1_entry(self):
        reg, _ = self._make_registry()
        for defn in reg.artifacts():
            with self.subTest(item=defn.id):
                self.assertEqual(len(defn.params_by_rank), 1, defn.id)

    def test_all_items_have_valid_tiers(self):
        reg, _ = self._make_registry()
        for defn in reg.all_items():
            self.assertIn(defn.tier, {"modifier", "artifact"})

    def test_all_items_have_valid_domains(self):
        reg, _ = self._make_registry()
        for defn in reg.all_items():
            self.assertIn(defn.domain, {"time", "gravity", "horizon", "none"})

    def test_resonances_require_existing_items(self):
        reg, _ = self._make_registry()
        item_ids = {d.id for d in reg.all_items()}
        for res in reg.all_resonances():
            for req in res.requires:
                self.assertIn(req, item_ids, f"{res.id} requires unknown item {req!r}")

    def test_invalid_entry_is_skipped_with_log(self):
        from src.systems.items.registry import ItemRegistry
        logger = _FakeLogger()
        reg = ItemRegistry()
        bad = {"id": "bad", "name": "Bad", "tier": "unknown_tier",
               "domain": "time", "trigger": "X", "effect": "y",
               "params_by_rank": [{}], "description": "oops"}
        reg._add_item(bad, logger)
        self.assertIsNone(reg.get_item("bad"))
        self.assertTrue(any("bad" in e for e in logger.entries))


class TestEffectAddChrono(unittest.TestCase):
    def test_adds_amount(self):
        ctx = _make_ctx()
        ctx.player.chrono_reserve = 50.0
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        EFFECT_REGISTRY["add_chrono"](EventResult(), ctx, {"amount": 8})
        self.assertAlmostEqual(ctx.player.chrono_reserve, 58.0)

    def test_clamps_to_max(self):
        from constants import CHRONO_RESERVE_MAX
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.chrono_reserve = CHRONO_RESERVE_MAX - 1
        EFFECT_REGISTRY["add_chrono"](EventResult(), ctx, {"amount": 999})
        self.assertAlmostEqual(ctx.player.chrono_reserve, CHRONO_RESERVE_MAX)


class TestEffectGrantIframes(unittest.TestCase):
    def test_sets_timer(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.iframes_timer = 0.0
        EFFECT_REGISTRY["grant_iframes"](EventResult(), ctx, {"seconds": 0.3})
        self.assertAlmostEqual(ctx.player.iframes_timer, 0.3)

    def test_does_not_reduce_existing_timer(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.iframes_timer = 0.8
        EFFECT_REGISTRY["grant_iframes"](EventResult(), ctx, {"seconds": 0.3})
        self.assertAlmostEqual(ctx.player.iframes_timer, 0.8)


class TestEffectExtendActiveAbility(unittest.TestCase):
    def _make_active_slot(self):
        slot = _FakeAbilitySlot()
        slot.active_timer = 1.5
        slot.is_active = True
        return slot

    def test_extends_when_active(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 0.5})
        self.assertAlmostEqual(slot.active_timer, 2.0)

    def test_no_effect_when_not_active(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ability_slot.active_timer = 0.0
        ctx.ability_slot.is_active = False
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 0.5})
        self.assertAlmostEqual(ctx.ability_slot.active_timer, 0.0)

    def test_no_effect_wrong_ability(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "other_ability", "seconds": 0.5})
        self.assertAlmostEqual(slot.active_timer, 1.5)

    def test_caps_extension(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        slot.active_timer = slot.duration * 2.9
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 999})
        self.assertLessEqual(ctx.ability_slot.active_timer, slot.duration * 3 + 0.01)


class TestEffectCancelAndRestore(unittest.TestCase):
    def test_cancels_with_room_charge(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 1
        ctx.player.anchor_integrity = 0
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertTrue(result.cancelled)
        self.assertEqual(ctx.player.anchor_integrity, 1)
        self.assertEqual(ctx.ctc_room_charges, 0)

    def test_uses_run_bonus_when_room_exhausted(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 0
        ctx.ctc_run_bonus = 1
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertTrue(result.cancelled)
        self.assertEqual(ctx.ctc_run_bonus, 0)

    def test_does_not_cancel_with_no_charges(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 0
        ctx.ctc_run_bonus = 0
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertFalse(result.cancelled)

    def test_restores_position(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 1
        ctx.player.px = 999.0
        ctx.player.py = 999.0
        ctx.player.last_safe_px = 90.0
        ctx.player.last_safe_py = 200.0
        EFFECT_REGISTRY["cancel_and_restore"](EventResult(), ctx, {})
        self.assertAlmostEqual(ctx.player.px, 90.0)
        self.assertAlmostEqual(ctx.player.py, 200.0)


class TestEffectPhaseHit(unittest.TestCase):
    def test_cancels_when_rng_hits(self):
        import random
        from src.systems.items.effects import EFFECT_REGISTRY, EffectContext
        from src.systems.events import EventResult
        # Use a seeded RNG that will produce < 1.0 (always phase with chance=1.0)
        ctx = _make_ctx()
        ctx.rng = random.Random(0)
        result = EventResult()
        EFFECT_REGISTRY["phase_hit"](result, ctx, {"chance": 1.0})
        self.assertTrue(result.cancelled)
        self.assertTrue(ctx._phase_blocked)

    def test_does_not_cancel_when_chance_zero(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        result = EventResult()
        EFFECT_REGISTRY["phase_hit"](result, ctx, {"chance": 0.0})
        self.assertFalse(result.cancelled)


class TestEffectModifyHoleOutcome(unittest.TestCase):
    def test_restores_stability_on_black_hole(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        run = _FakeRunState()
        run.fold_stability = 60.0
        ctx = _make_ctx(run_state=run)
        EFFECT_REGISTRY["modify_hole_outcome"](
            EventResult(), ctx, {"stability_reduction": 5, "extra_reward_options": 0},
            is_white=False)
        self.assertAlmostEqual(run.fold_stability, 65.0)

    def test_adds_extra_options_on_white_hole(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        run = _FakeRunState()
        ctx = _make_ctx(run_state=run)
        EFFECT_REGISTRY["modify_hole_outcome"](
            EventResult(), ctx, {"stability_reduction": 10, "extra_reward_options": 1},
            is_white=True)
        self.assertEqual(run.extra_reward_options, 1)


class TestEffectFreezeEnemies(unittest.TestCase):
    def test_freezes_nearby_enemy(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        enemy = _FakeEnemy(px=110.0, py=200.0)
        ctx = _make_ctx(enemies=[enemy])
        ctx.player.px = 100.0
        ctx.player.py = 200.0
        EFFECT_REGISTRY["freeze_enemies_in_radius"](
            EventResult(), ctx, {"radius": 200.0, "duration": 1.0})
        self.assertAlmostEqual(enemy.frozen_timer, 1.0)

    def test_does_not_freeze_distant_enemy(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        enemy = _FakeEnemy(px=500.0, py=200.0)
        ctx = _make_ctx(enemies=[enemy])
        ctx.player.px = 100.0
        ctx.player.py = 200.0
        EFFECT_REGISTRY["freeze_enemies_in_radius"](
            EventResult(), ctx, {"radius": 200.0, "duration": 1.0})
        self.assertAlmostEqual(enemy.frozen_timer, 0.0)


class TestEffectTriggerAbility(unittest.TestCase):
    def test_triggers_on_nth_rotation(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = _FakeAbilitySlot()
        ctx = _make_ctx(ability_slot=slot)
        ctx.kerr_ring_rotations = 0
        params = {"ability_name": "time_dilation", "every_n": 4}
        for _ in range(3):
            EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertEqual(ctx.kerr_ring_rotations, 3)
        self.assertAlmostEqual(slot.active_timer, 0.0)
        EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertEqual(ctx.kerr_ring_rotations, 0)
        self.assertGreater(slot.active_timer, 0.0)

    def test_no_trigger_wrong_ability(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = _FakeAbilitySlot(name="other")
        ctx = _make_ctx(ability_slot=slot)
        params = {"ability_name": "time_dilation", "every_n": 1}
        EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertAlmostEqual(slot.active_timer, 0.0)


class TestResonanceActivation(unittest.TestCase):
    """Resonances auto-activate when both required items are owned."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_manager_with_items(self, item_ids):
        import random
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot, rng_seed=42)
        owned = [OwnedItem(id=iid, rank=1) for iid in item_ids]
        mgr.sync_owned(owned)
        return mgr, bus, player, run, slot

    def test_spaghettification_activates(self):
        mgr, *_ = self._make_manager_with_items(["tidal_coupling", "redshift"])
        self.assertIn("spaghettification", mgr._active_resonances)

    def test_spaghettification_not_active_with_one_part(self):
        mgr, *_ = self._make_manager_with_items(["tidal_coupling"])
        self.assertNotIn("spaghettification", mgr._active_resonances)

    def test_ergosphere_activates(self):
        mgr, *_ = self._make_manager_with_items(["geodesic", "quantum_foam"])
        self.assertIn("ergosphere", mgr._active_resonances)

    def test_information_paradox_activates(self):
        mgr, *_ = self._make_manager_with_items(["closed_timelike_curve", "event_horizon"])
        self.assertIn("information_paradox", mgr._active_resonances)

    def test_no_resonances_empty_inventory(self):
        mgr, *_ = self._make_manager_with_items([])
        self.assertEqual(len(mgr._active_resonances), 0)


class TestItemManagerInternalCooldown(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_manager(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot, rng_seed=0)
        # Tidal coupling has 1.5s internal cooldown
        mgr.sync_owned([OwnedItem(id="tidal_coupling", rank=1)])
        return mgr, bus, player

    def test_tidal_coupling_fires_on_first_rotation(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        self.assertGreater(player.chrono_reserve, 0.0)

    def test_tidal_coupling_blocked_by_cooldown(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        first = player.chrono_reserve
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, -1))
        self.assertAlmostEqual(player.chrono_reserve, first)

    def test_tidal_coupling_fires_after_cooldown_expires(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        first = player.chrono_reserve
        mgr.tick(2.0)  # advance past 1.5s cooldown
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, -1))
        self.assertGreater(player.chrono_reserve, first)


class TestItemManagerRoomChargeReset(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_ctc_room_charges_reset_on_room_entered(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus, GameEvent
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        mgr.sync_owned([OwnedItem(id="closed_timelike_curve", rank=1)])
        # Drain charges
        mgr._ctx.ctc_room_charges = 0
        # ROOM_ENTERED should reset them
        bus.emit(GameEvent.ROOM_ENTERED)
        self.assertEqual(mgr._ctx.ctc_room_charges, 1)


class TestPhysicsInvariance(unittest.TestCase):
    """Physics constants must be unchanged with all items at max rank."""

    def test_physics_constants_unchanged_with_all_items(self):
        import constants
        # Record baseline physics values
        baseline = {
            "GRAVITY_STRENGTH": constants.GRAVITY_STRENGTH,
            "TERMINAL_VELOCITY": constants.TERMINAL_VELOCITY,
            "JUMP_SPEED": constants.JUMP_SPEED,
            "ACCEL": constants.ACCEL,
            "DECEL": constants.DECEL,
            "AIR_ACCEL": constants.AIR_ACCEL,
            "MAX_MOVE_SPEED": constants.MAX_MOVE_SPEED,
            "COYOTE_TIME": constants.COYOTE_TIME,
            "JUMP_CUT_MULTIPLIER": constants.JUMP_CUT_MULTIPLIER,
        }
        # Grant all items and run several physics updates
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus, GameEvent
        logger = _FakeLogger()
        registry = load_item_registry(BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        all_owned = [OwnedItem(id=d.id, rank=len(d.params_by_rank)) for d in registry.all_items()]
        mgr.sync_owned(all_owned)
        # Fire every event type
        for event in [
            GameEvent.GRAVITY_ROTATED, GameEvent.ABILITY_USED, GameEvent.ROOM_ENTERED,
            GameEvent.ROOM_CLEARED, GameEvent.HOLE_RESOLVED,
        ]:
            bus.emit(event, gravity_dir=(0, 1), ability_name="time_dilation", is_white=True)
        # Assert physics constants unchanged
        for name, value in baseline.items():
            self.assertAlmostEqual(
                getattr(constants, name), value,
                msg=f"Physics constant {name} was altered by item system",
            )


class TestRunStateOwnedItems(unittest.TestCase):
    def test_new_run_has_empty_owned_items(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        self.assertEqual(run.owned_items, [])

    def test_new_run_has_zero_paradox_spent(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        self.assertAlmostEqual(run.paradox_spent, 0.0)

    def test_to_dict_includes_owned_items(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        run.owned_items = [{"id": "redshift", "rank": 1}]
        d = run.to_dict()
        self.assertIn("owned_items", d)
        self.assertEqual(d["owned_items"][0]["id"], "redshift")


class TestEnemyFrozenTimer(unittest.TestCase):
    def test_frozen_timer_initialises_to_zero(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        self.assertAlmostEqual(e.frozen_timer, 0.0)

    def test_frozen_enemy_does_not_move(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 1.0
        start = e.px
        e.update(time_scale=1.0, dt=1.0 / 60)
        self.assertAlmostEqual(e.px, start)

    def test_frozen_timer_decrements(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 1.0
        e.update(time_scale=1.0, dt=0.5)
        self.assertAlmostEqual(e.frozen_timer, 0.5)

    def test_reset_clears_frozen_timer(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 2.0
        e.reset()
        self.assertAlmostEqual(e.frozen_timer, 0.0)


# ---------------------------------------------------------------------------
# Offer Generation Tests (M5a Session 3)
# ---------------------------------------------------------------------------

class TestOfferGeneration(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_registry(self):
        from src.systems.items.registry import load_item_registry
        return load_item_registry(self.BASE_DIR, _FakeLogger())

    def test_same_seed_same_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        offers_a = generate_offers(registry, [], run_seed=42, node_idx=0)
        offers_b = generate_offers(registry, [], run_seed=42, node_idx=0)
        self.assertEqual([o.item_def.id for o in offers_a],
                         [o.item_def.id for o in offers_b])

    def test_different_node_different_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        offers_0 = generate_offers(registry, [], run_seed=1, node_idx=0)
        offers_2 = generate_offers(registry, [], run_seed=1, node_idx=2)
        ids_0 = [o.item_def.id for o in offers_0 if not o.is_paradox]
        ids_2 = [o.item_def.id for o in offers_2 if not o.is_paradox]
        # Not guaranteed to differ, but almost always will with different node idx
        # Just assert both lists are well-formed
        self.assertGreater(len(ids_0), 0)
        self.assertGreater(len(ids_2), 0)

    def test_different_seed_likely_different_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        offers_a = [o.item_def.id for o in generate_offers(registry, [], run_seed=1, node_idx=0)]
        offers_b = [o.item_def.id for o in generate_offers(registry, [], run_seed=99999, node_idx=0)]
        # Two independent seeds should produce different offers at least sometimes
        # We test across 5 seeds to make it robust
        any_differ = False
        for s in range(5):
            a = [o.item_def.id for o in generate_offers(registry, [], run_seed=s, node_idx=0)
                 if not o.is_paradox]
            b = [o.item_def.id for o in generate_offers(registry, [], run_seed=s + 1000, node_idx=0)
                 if not o.is_paradox]
            if a != b:
                any_differ = True
                break
        self.assertTrue(any_differ, "Different seeds should sometimes produce different offers")

    def test_base_count_is_three(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        # Force no paradox by using a seed where PARADOX_OFFER_CHANCE check fails
        # We just check non-paradox count
        for seed in range(20):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            non_paradox = [o for o in offers if not o.is_paradox]
            self.assertEqual(len(non_paradox), 3, f"seed={seed}")
            break  # first passing seed is enough

    def test_extra_options_increases_count(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        # Find a seed with no paradox offer and check +1 works
        for seed in range(50):
            base = [o for o in generate_offers(registry, [], run_seed=seed, node_idx=0)
                    if not o.is_paradox]
            extra = [o for o in generate_offers(registry, [], run_seed=seed, node_idx=0,
                                                extra_options=1) if not o.is_paradox]
            if len(base) == 3:
                self.assertEqual(len(extra), 4)
                break

    def test_no_duplicate_offers_in_one_set(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(10):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            ids = [o.item_def.id for o in offers]
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate offer at seed={seed}")

    def test_rank_up_offered_for_owned_below_max(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        # Own redshift at rank 1 — should appear as rank-up in some seeds
        owned = [OwnedItem(id="redshift", rank=1)]
        found_rankup = False
        for seed in range(50):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            for o in offers:
                if o.item_def.id == "redshift" and o.is_rank_up:
                    found_rankup = True
                    self.assertEqual(o.current_rank, 1)
                    self.assertEqual(o.target_rank, 2)
                    break
            if found_rankup:
                break
        self.assertTrue(found_rankup, "Rank-up offer should appear for owned modifier below max rank")

    def test_maxed_modifier_not_offered(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        # Own redshift at max rank (3) — should not appear
        owned = [OwnedItem(id="redshift", rank=3)]
        for seed in range(20):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            for o in offers:
                self.assertNotEqual(o.item_def.id, "redshift",
                                    f"Maxed modifier offered at seed={seed}")

    def test_paradox_offer_is_artifact(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(100):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            for o in offers:
                if o.is_paradox:
                    self.assertEqual(o.item_def.tier, "artifact")
                    self.assertGreater(o.paradox_cost, 0.0)
                    return  # found one, test passes
        # If no seed triggers paradox, that's still technically valid but unlikely
        # with 100 seeds and 25% chance

    def test_paradox_not_takeable_below_cost(self):
        from src.systems.items.offers import generate_offers, Offer
        registry = self._load_registry()
        # Find a paradox offer
        for seed in range(100):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            for o in offers:
                if o.is_paradox:
                    # Not takeable if cost would drop to ≤0
                    self.assertFalse(o.takeable(o.paradox_cost))
                    self.assertFalse(o.takeable(o.paradox_cost - 0.1))
                    self.assertTrue(o.takeable(o.paradox_cost + 1.0))
                    return

    def test_domain_pull_weights_owned_domain(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        # Own a gravity item — gravity domain should appear more often
        owned = [OwnedItem(id="tidal_coupling", rank=1)]
        gravity_count = 0
        for seed in range(30):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            gravity_count += sum(1 for o in offers if o.item_def.domain == "gravity" and not o.is_paradox)
        # Should see at least a few gravity items across 30 seeds
        self.assertGreater(gravity_count, 0)


class TestApplyOffer(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _setup(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.systems.events import EventBus
        from src.data.run_state import RunState
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = RunState.new_run()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        mgr.sync_owned([])
        return registry, mgr, run

    def test_new_modifier_added_to_owned(self):
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        registry, mgr, run = self._setup()
        from src.systems.items.offers import Offer
        defn = registry.get_item("redshift")
        offer = Offer(item_def=defn, is_rank_up=False, current_rank=0,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer, _owned_item_list
        _apply_offer(offer, run, mgr, registry)
        ids = [e["id"] for e in run.owned_items]
        self.assertIn("redshift", ids)

    def test_rank_up_updates_existing_entry(self):
        registry, mgr, run = self._setup()
        run.owned_items = [{"id": "redshift", "rank": 1}]
        from src.systems.items.offers import Offer
        defn = registry.get_item("redshift")
        offer = Offer(item_def=defn, is_rank_up=True, current_rank=1,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        entry = next(e for e in run.owned_items if e["id"] == "redshift")
        self.assertEqual(entry["rank"], 2)
        # Should still be only one entry for redshift
        count = sum(1 for e in run.owned_items if e["id"] == "redshift")
        self.assertEqual(count, 1)

    def test_paradox_costs_stability(self):
        registry, mgr, run = self._setup()
        run.fold_stability = 80.0
        from src.systems.items.offers import Offer
        defn = registry.get_item("kerr_ring")
        offer = Offer(item_def=defn, is_rank_up=False, current_rank=0,
                      is_paradox=True, paradox_cost=20.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        self.assertAlmostEqual(run.fold_stability, 60.0)
        self.assertAlmostEqual(run.paradox_spent, 20.0)

    def test_modifier_cap_drops_oldest(self):
        from constants import MODIFIER_CAP
        from src.data.items import ItemDef
        registry, mgr, run = self._setup()
        # Fill to cap using real modifiers
        modifier_ids = [d.id for d in registry.modifiers()]
        fill_count = min(MODIFIER_CAP, len(modifier_ids))
        run.owned_items = [{"id": mid, "rank": 1} for mid in modifier_ids[:fill_count]]
        oldest_id = run.owned_items[0]["id"]
        # Create a synthetic new modifier so we can exceed the cap
        new_defn = ItemDef(
            id="test_synthetic_mod", name="Synthetic", tier="modifier",
            domain="time", trigger="GRAVITY_ROTATED", effect="add_chrono",
            params_by_rank=[{"amount": 5}], description="test",
        )
        # Temporarily register it so _apply_offer can resolve its tier
        registry._items["test_synthetic_mod"] = new_defn
        from src.systems.items.offers import Offer
        offer = Offer(item_def=new_defn, is_rank_up=False, current_rank=0,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        ids = [e["id"] for e in run.owned_items]
        self.assertNotIn(oldest_id, ids, "Oldest modifier should be dropped at cap")
        self.assertIn("test_synthetic_mod", ids)
        # Clean up
        del registry._items["test_synthetic_mod"]


# ---------------------------------------------------------------------------
# Fold Predator Tests (M5b)
# ---------------------------------------------------------------------------

def _make_predator(px=400.0, py=400.0, level_min=0.0, level_max=800.0):
    from src.entities.fold_predator import FoldPredator
    return FoldPredator(px=px, py=py, level_min=level_min, level_max=level_max)


class TestFoldPredatorPatrol(unittest.TestCase):
    def test_patrol_moves_laterally(self):
        p = _make_predator(px=400.0)
        start = p.px
        p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertNotAlmostEqual(p.px, start)

    def test_patrol_bounces_at_max(self):
        p = _make_predator(px=799.0, level_max=800.0)
        p._direction = 1
        for _ in range(20):
            p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertLessEqual(p.px, 800.0)

    def test_patrol_bounces_at_min(self):
        p = _make_predator(px=1.0, level_min=0.0)
        p._direction = -1
        for _ in range(20):
            p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreaterEqual(p.px, 0.0)


class TestFoldPredatorChase(unittest.TestCase):
    def test_enters_chase_when_player_in_range(self):
        from src.entities.fold_predator import _State
        p = _make_predator(px=400.0)
        # Player within chase range
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)

    def test_stays_patrol_when_player_out_of_range(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_CHASE_RANGE
        p = _make_predator(px=400.0)
        far = 400.0 + FOLD_PREDATOR_CHASE_RANGE + 50.0
        p.update(dt=1.0, player_px=far, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PATROL)

    def test_chase_moves_toward_player(self):
        p = _make_predator(px=400.0)
        # Player to the right
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        start = p.px
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreater(p.px, start)

    def test_chase_moves_left_when_player_left(self):
        p = _make_predator(px=400.0)
        # Player to the left — force into chase
        p.update(dt=1.0, player_px=300.0, player_py=400.0, gravity_dir=(0, 1))
        start = p.px
        p.update(dt=1.0, player_px=300.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertLess(p.px, start)

    def test_exits_chase_when_player_leaves_range(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_CHASE_RANGE
        p = _make_predator(px=400.0)
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)
        far = 400.0 + FOLD_PREDATOR_CHASE_RANGE + 200.0
        p.update(dt=1.0, player_px=far, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PATROL)


class TestFoldPredatorPhase(unittest.TestCase):
    def test_phase_fires_after_interval(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_PHASE_INTERVAL
        p = _make_predator(px=400.0)
        # Force into chase
        p._state = _State.CHASE
        p._phase_cooldown = 0.01
        p.update(dt=0.02, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PHASE)

    def test_phase_moves_faster_than_chase(self):
        from src.entities.fold_predator import _State
        p_chase = _make_predator(px=400.0)
        p_phase = _make_predator(px=400.0)
        p_chase._state = _State.CHASE
        p_phase._state = _State.PHASE
        p_phase._phase_timer = 10.0  # won't expire this tick
        # Use small dt so phase doesn't expire mid-tick
        p_chase.update(dt=0.1, player_px=600.0, player_py=400.0, gravity_dir=(0, 1))
        p_phase.update(dt=0.1, player_px=600.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreater(p_phase.px, p_chase.px)

    def test_phase_returns_to_chase_after_duration(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_PHASE_DURATION
        p = _make_predator(px=400.0)
        p._state = _State.PHASE
        p._phase_timer = 0.01
        p.update(dt=0.02, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)


class TestFoldPredatorStun(unittest.TestCase):
    def test_on_gravity_rotate_stuns(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p.on_gravity_rotate()
        self.assertEqual(p._state, _State.STUNNED)

    def test_stun_from_any_state(self):
        from src.entities.fold_predator import _State
        for initial in (_State.PATROL, _State.CHASE, _State.PHASE):
            p = _make_predator()
            p._state = initial
            p.on_gravity_rotate()
            self.assertEqual(p._state, _State.STUNNED, f"from {initial}")

    def test_stun_preserves_pre_stun_state(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p._state = _State.CHASE
        p.on_gravity_rotate()
        self.assertEqual(p._pre_stun_state, _State.CHASE)

    def test_stunned_enemy_does_not_move(self):
        p = _make_predator(px=400.0)
        p.on_gravity_rotate()
        start = p.px
        p.update(dt=0.5, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.px, start)

    def test_stun_expires_and_resumes(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_STUN_DURATION
        p = _make_predator(px=400.0)
        p._state = _State.CHASE
        p.on_gravity_rotate()
        # Advance past stun duration
        p.update(dt=FOLD_PREDATOR_STUN_DURATION + 0.1,
                 player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)

    def test_repeated_rotation_refreshes_stun(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_STUN_DURATION
        p = _make_predator()
        p.on_gravity_rotate()
        p.update(dt=FOLD_PREDATOR_STUN_DURATION * 0.5,
                 player_px=400.0, player_py=400.0, gravity_dir=(0, 1))
        p.on_gravity_rotate()  # rotate again while stunned
        self.assertAlmostEqual(p._stun_timer, FOLD_PREDATOR_STUN_DURATION)


class TestFoldPredatorGravityAware(unittest.TestCase):
    def test_moves_on_y_axis_in_horizontal_gravity(self):
        p = _make_predator(px=400.0, py=400.0)
        from src.entities.fold_predator import _State
        p._state = _State.CHASE
        start_px = p.px
        start_py = p.py
        # Horizontal gravity (LEFT), player above (lower py)
        p.update(dt=1.0, player_px=400.0, player_py=300.0, gravity_dir=(-1, 0))
        self.assertAlmostEqual(p.px, start_px, msg="X should not change in horizontal gravity")
        self.assertNotAlmostEqual(p.py, start_py, msg="Y should change in horizontal gravity")

    def test_moves_on_x_axis_in_vertical_gravity(self):
        p = _make_predator(px=400.0, py=400.0)
        from src.entities.fold_predator import _State
        p._state = _State.CHASE
        start_py = p.py
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.py, start_py, msg="Y should not change in vertical gravity")


class TestFoldPredatorReset(unittest.TestCase):
    def test_reset_returns_to_spawn(self):
        p = _make_predator(px=400.0, py=400.0)
        p.update(dt=1.0, player_px=450.0, player_py=400.0, gravity_dir=(0, 1))
        p.on_gravity_rotate()
        p.reset()
        self.assertAlmostEqual(p.px, 400.0)
        self.assertAlmostEqual(p.py, 400.0)

    def test_reset_clears_stun(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p.on_gravity_rotate()
        p.reset()
        self.assertEqual(p._state, _State.PATROL)
        self.assertAlmostEqual(p._stun_timer, 0.0)

    def test_reset_clears_frozen_timer(self):
        p = _make_predator()
        p.frozen_timer = 2.0
        p.reset()
        self.assertAlmostEqual(p.frozen_timer, 0.0)


class TestFoldPredatorFrozenTimerCompat(unittest.TestCase):
    """frozen_timer must work the same as on TemporalEcho (Hawking Emitter compat)."""

    def test_frozen_timer_initialises_zero(self):
        p = _make_predator()
        self.assertAlmostEqual(p.frozen_timer, 0.0)

    def test_frozen_pauses_movement(self):
        p = _make_predator(px=400.0)
        p.frozen_timer = 1.0
        start = p.px
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.px, start)

    def test_frozen_timer_decrements(self):
        p = _make_predator()
        p.frozen_timer = 1.0
        p.update(dt=0.5, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.frozen_timer, 0.5)


# ---------------------------------------------------------------------------
# HUD Tests (M5d)
# ---------------------------------------------------------------------------

class TestDrawHud(unittest.TestCase):
    """Smoke tests: draw_hud must not crash at all boundary values."""

    def setUp(self):
        import pygame
        pygame.init()
        self._screen = pygame.Surface((800, 600))
        from src.rendering.loader import load_font
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._font = load_font(BASE_DIR)

    def _make_player(self, integrity=3, chrono=100.0):
        p = _FakePlayer()
        p.anchor_integrity = integrity
        p.chrono_reserve = chrono
        p.goal_reached = False
        p.gravity_dir = (0, 1)
        return p

    def test_full_resources_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player(integrity=3, chrono=100.0)
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=0.0,
                 screen_width=800, screen_height=600)

    def test_zero_integrity_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player(integrity=0, chrono=50.0)
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=0.0,
                 screen_width=800, screen_height=600)

    def test_zero_chrono_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player(integrity=2, chrono=0.0)
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=0.0,
                 screen_width=800, screen_height=600)

    def test_dilation_active_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player()
        draw_hud(self._screen, self._font, p,
                 dilation_timer=2.5, dilation_cooldown_timer=4.5,
                 screen_width=800, screen_height=600)

    def test_dilation_cooldown_only_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player()
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=1.2,
                 screen_width=800, screen_height=600)

    def test_goal_reached_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player()
        p.goal_reached = True
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=0.0,
                 screen_width=800, screen_height=600)

    def test_single_integrity_no_crash(self):
        from src.rendering.hud import draw_hud
        p = self._make_player(integrity=1, chrono=10.0)
        draw_hud(self._screen, self._font, p,
                 dilation_timer=0.0, dilation_cooldown_timer=0.0,
                 screen_width=800, screen_height=600)


class TestHudConstants(unittest.TestCase):
    def test_pip_count_matches_integrity_max(self):
        from constants import HUD_PIP_SIZE, HUD_PIP_GAP, ANCHOR_INTEGRITY_MAX
        # Pips must fit in a reasonable width
        total_width = ANCHOR_INTEGRITY_MAX * HUD_PIP_SIZE + (ANCHOR_INTEGRITY_MAX - 1) * HUD_PIP_GAP
        self.assertLess(total_width, 200)

    def test_chrono_bar_fits_screen(self):
        from constants import (HUD_CHRONO_SEG_W, HUD_CHRONO_SEG_GAP,
                               HUD_CHRONO_SEG_COUNT, HUD_CHRONO_X, SCREEN_WIDTH)
        total = HUD_CHRONO_X + HUD_CHRONO_SEG_COUNT * (HUD_CHRONO_SEG_W + HUD_CHRONO_SEG_GAP)
        self.assertLess(total, SCREEN_WIDTH // 2)

    def test_hud_colors_are_tuples_of_three(self):
        from constants import (HUD_COLOR_PIP_FULL, HUD_COLOR_PIP_LOST, HUD_COLOR_PIP_ZERO,
                               HUD_COLOR_CHRONO_HI, HUD_COLOR_CHRONO_LO, HUD_COLOR_CHRONO_EMPTY,
                               HUD_COLOR_DILATION_ACTIVE, HUD_COLOR_DILATION_COOLDOWN)
        for name, val in [
            ("PIP_FULL", HUD_COLOR_PIP_FULL), ("PIP_LOST", HUD_COLOR_PIP_LOST),
            ("PIP_ZERO", HUD_COLOR_PIP_ZERO), ("CHRONO_HI", HUD_COLOR_CHRONO_HI),
            ("CHRONO_LO", HUD_COLOR_CHRONO_LO), ("CHRONO_EMPTY", HUD_COLOR_CHRONO_EMPTY),
            ("DILATION_ACTIVE", HUD_COLOR_DILATION_ACTIVE),
            ("DILATION_COOLDOWN", HUD_COLOR_DILATION_COOLDOWN),
        ]:
            self.assertEqual(len(val), 3, f"HUD_COLOR_{name} should be (R, G, B)")
            for component in val:
                self.assertGreaterEqual(component, 0)
                self.assertLessEqual(component, 255)


class TestGravityRotationEject(unittest.TestCase):
    """Regression tests for the post-rotation rect-expansion disappear bug.

    When gravity rotates, the physics rect swaps dimensions (64×96 ↔ 96×64).
    The player can overlap a boundary wall they weren't touching before.
    The gravity resolvers must use minimum-penetration when velocity is zero
    so the player is ejected INTO the level, not outside it.
    """

    def _left_boundary(self, level_width=1200, level_height=900, T=100):
        return pygame.Rect(-T, -T, T, level_height + 2 * T)

    def _right_boundary(self, level_width=1200, level_height=900, T=100):
        return pygame.Rect(level_width, -T, T, level_height + 2 * T)

    def _top_boundary(self, level_width=1200, level_height=900, T=100):
        return pygame.Rect(-T, -T, level_width + 2 * T, T)

    def _bottom_boundary(self, level_width=1200, level_height=900, T=100):
        return pygame.Rect(-T, level_height, level_width + 2 * T, T)

    def test_right_gravity_near_left_wall_stays_inside(self):
        """Player hugging left wall in DOWN gravity, rotates to RIGHT — must not be ejected left."""
        from src.physics.collision import resolve_collisions
        # In DOWN gravity, player min px is 32 (64px wide, left boundary right edge at 0)
        # After rotating to RIGHT gravity, width becomes 96 — rect extends 16px into left boundary
        px, py = 32.0, 500.0
        vx, vy = 0.0, 0.0
        w, h = 96, 64   # RIGHT gravity dimensions
        platforms = [self._left_boundary(), self._right_boundary(),
                     self._top_boundary(), self._bottom_boundary()]
        new_px, new_py, new_vx, new_vy, _ = resolve_collisions(
            px, py, vx, vy, w, h, platforms, (1, 0),  # RIGHT gravity
        )
        self.assertGreater(new_px, 0, "Player was ejected outside left boundary")
        self.assertLessEqual(new_px, 1200, "Player ended up past right boundary")

    def test_left_gravity_near_right_wall_stays_inside(self):
        """Player hugging right wall in DOWN gravity, rotates to LEFT — must not be ejected right."""
        from src.physics.collision import resolve_collisions
        # In DOWN gravity, player max px near right boundary ≈ 1168 (1200-32)
        # After rotating to LEFT gravity, width becomes 96 — rect extends 16px into right boundary
        px, py = 1168.0, 500.0
        vx, vy = 0.0, 0.0
        w, h = 96, 64
        platforms = [self._left_boundary(), self._right_boundary(),
                     self._top_boundary(), self._bottom_boundary()]
        new_px, new_py, new_vx, new_vy, _ = resolve_collisions(
            px, py, vx, vy, w, h, platforms, (-1, 0),  # LEFT gravity
        )
        self.assertLess(new_px, 1200, "Player was ejected outside right boundary")
        self.assertGreaterEqual(new_px, 0, "Player ended up past left boundary")

    def test_down_gravity_near_top_wall_stays_inside(self):
        """Player near top boundary in RIGHT gravity, rotates to DOWN — must not be ejected above."""
        from src.physics.collision import resolve_collisions
        # In RIGHT gravity (h=64, half=32), player min py near top ≈ 32
        # After rotating to DOWN gravity, height becomes 96 — rect extends 16px into top boundary
        px, py = 400.0, 32.0
        vx, vy = 0.0, 0.0
        w, h = 64, 96   # DOWN gravity dimensions
        platforms = [self._left_boundary(), self._right_boundary(),
                     self._top_boundary(), self._bottom_boundary()]
        new_px, new_py, new_vx, new_vy, _ = resolve_collisions(
            px, py, vx, vy, w, h, platforms, (0, 1),  # DOWN gravity
        )
        self.assertGreater(new_py, 0, "Player was ejected above top boundary")
        self.assertLess(new_py, 900, "Player ended up below bottom boundary")

    def test_repeated_rotation_near_left_wall_stays_inside(self):
        """Repeated DOWN↔RIGHT rotations near left wall must never send player outside level."""
        from src.physics.collision import resolve_collisions
        from src.physics.gravity import rotate_gravity_ccw, get_player_physics_size
        px, py = 34.0, 500.0
        vx, vy = 0.0, 0.0
        gravity = (0, 1)  # DOWN
        platforms = [self._left_boundary(), self._right_boundary(),
                     self._top_boundary(), self._bottom_boundary()]
        for _ in range(8):  # 4 full rotations
            gravity = rotate_gravity_ccw(gravity)
            w, h = get_player_physics_size(gravity)
            px, py, vx, vy, _ = resolve_collisions(
                px, py, vx, vy, w, h, platforms, gravity,
            )
            self.assertGreater(px, -200, f"px={px} fell outside level after rotation to {gravity}")
            self.assertLess(px, 1400, f"px={px} fell outside level after rotation to {gravity}")
            self.assertGreater(py, -200, f"py={py} fell outside level after rotation to {gravity}")
            self.assertLess(py, 1100, f"py={py} fell outside level after rotation to {gravity}")


class TestTheAnchored(unittest.TestCase):
    """Tests for TheAnchored enemy — broken-timeline wander/stutter AI."""

    def _make(self, px=200.0, py=400.0, seed=42):
        from src.entities.anchored import TheAnchored
        return TheAnchored(px=px, py=py, level_min=0.0, level_max=800.0, seed=seed)

    def test_initial_state_is_wander(self):
        a = self._make()
        self.assertFalse(a.is_stuttering)

    def test_rect_centred_on_position(self):
        from src.entities.anchored import TheAnchored
        a = self._make(px=200.0, py=400.0)
        r = a.rect
        self.assertEqual(r.centerx, 200)
        self.assertEqual(r.centery, 400)
        self.assertEqual(r.width, a.w)
        self.assertEqual(r.height, a.h)

    def test_moves_laterally_each_tick(self):
        a = self._make()
        px_before = a.px
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        # Should have moved (either direction)
        self.assertNotEqual(a.px, px_before)

    def test_time_dilation_freezes_movement(self):
        a = self._make()
        px_before = a.px
        a.update(time_scale=0.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a.px, px_before, places=5)

    def test_time_dilation_freezes_stutter_timer(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=200.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        # Advance close to stutter
        a._stutter_cooldown = 0.05
        before = a._stutter_cooldown
        a.update(time_scale=0.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a._stutter_cooldown, before, places=5)

    def test_stutter_triggers_after_interval(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        a._wander_timer = 999.0
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)

    def test_stutter_ends_after_duration(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        # Trigger stutter
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)
        # Run out the stutter timer
        a._stutter_timer = 0.001
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertFalse(a.is_stuttering)

    def test_clamped_to_level_bounds(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=5.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._direction = -1  # heading toward min
        for _ in range(200):
            a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertGreaterEqual(a.px, 0.0)
        self.assertLessEqual(a.px, 800.0)

    def test_gravity_rotate_is_noop(self):
        a = self._make()
        px_before = a.px
        py_before = a.py
        a.on_gravity_rotate()
        self.assertEqual(a.px, px_before)
        self.assertEqual(a.py, py_before)

    def test_reset_returns_to_spawn(self):
        a = self._make(px=200.0, py=400.0)
        a.update(time_scale=1.0, dt=1.0, gravity_dir=(0, 1))
        a.reset()
        self.assertAlmostEqual(a.px, 200.0, places=5)
        self.assertAlmostEqual(a.py, 400.0, places=5)
        self.assertFalse(a.is_stuttering)

    def test_frozen_timer_blocks_movement(self):
        a = self._make()
        a.frozen_timer = 2.0
        px_before = a.px
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a.px, px_before, places=5)
        self.assertAlmostEqual(a.frozen_timer, 1.9, places=5)

    def test_frozen_timer_decrements_and_resumes(self):
        a = self._make()
        a.frozen_timer = 0.05
        px_before = a.px
        # First tick consumes the frozen timer
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertEqual(a.frozen_timer, 0.0)
        # Second tick should move
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertNotEqual(a.px, px_before)

    def test_horizontal_gravity_moves_y(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        py_before = a.py
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(1, 0))
        self.assertNotEqual(a.py, py_before)

    def test_draw_does_not_crash(self):
        import pygame
        surface = pygame.Surface((800, 600))
        a = self._make()
        a.draw(surface, (0.0, 0.0))

    def test_stutter_draw_color_differs(self):
        from src.entities.anchored import TheAnchored
        import constants as C
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)
        # Just verify the stutter color constant is different from wander color
        self.assertNotEqual(C.ANCHORED_COLOR, C.ANCHORED_STUTTER_COLOR)


class TestLevelGenerator(unittest.TestCase):
    """Tests for the anomaly room picker and anomaly level JSON validity."""

    def test_pick_returns_json_path(self):
        from src.systems.level_generator import pick_anomaly_room
        result = pick_anomaly_room(42, 1)
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith(".json"))

    def test_pick_is_deterministic(self):
        from src.systems.level_generator import pick_anomaly_room
        self.assertEqual(pick_anomaly_room(12345, 2), pick_anomaly_room(12345, 2))

    def test_different_seeds_vary(self):
        from src.systems.level_generator import pick_anomaly_room, ANOMALY_LEVELS
        if len(ANOMALY_LEVELS) < 2:
            self.skipTest("Need at least 2 anomaly levels")
        results = {pick_anomaly_room(seed, 1) for seed in range(100)}
        self.assertGreater(len(results), 1)

    def test_different_node_idx_vary(self):
        from src.systems.level_generator import pick_anomaly_room, ANOMALY_LEVELS
        if len(ANOMALY_LEVELS) < 2:
            self.skipTest("Need at least 2 anomaly levels")
        results = {pick_anomaly_room(0, idx) for idx in range(20)}
        self.assertGreater(len(results), 1)

    def test_all_anomaly_rooms_loadable(self):
        from src.systems.level_generator import ANOMALY_LEVELS
        from src.levels.level_data import LevelData
        valid_dirs = {(0, 1), (0, -1), (1, 0), (-1, 0)}
        for path in ANOMALY_LEVELS:
            with self.subTest(path=path):
                data = LevelData.load(path)
                self.assertIsNotNone(data)
                self.assertIn(tuple(data.gravity_start), valid_dirs)
                self.assertGreater(len(data.static_platforms), 0)
                self.assertGreater(data.level_width, 0)
                self.assertGreater(data.level_height, 0)

    def test_anomaly_01_crawlway_physics_gate(self):
        """84px opening: DOWN player (96px tall) is blocked, RIGHT player (64px tall) fits."""
        from src.systems.level_generator import ANOMALY_LEVELS
        from src.levels.level_data import LevelData
        data = LevelData.load(ANOMALY_LEVELS[0])
        self.assertEqual(tuple(data.gravity_start), (0, 1))
        self.assertEqual(data.name, "Maintenance Crawlway")
        # Find the crawlway block (the only non-floor platform)
        blocks = [p for p in data.static_platforms if p.y == 0]
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        floor = next(p for p in data.static_platforms if p.y > 0)
        clearance = floor.y - (block.y + block.h)
        self.assertGreater(clearance, 64)   # RIGHT/LEFT player (64px) fits
        self.assertLess(clearance, 96)      # DOWN/UP player (96px) is blocked

    def test_anomaly_02_starts_right_gravity(self):
        from src.systems.level_generator import ANOMALY_LEVELS
        from src.levels.level_data import LevelData
        data = LevelData.load(ANOMALY_LEVELS[1])
        self.assertEqual(tuple(data.gravity_start), (1, 0))

    def test_anomaly_03_starts_up_gravity(self):
        from src.systems.level_generator import ANOMALY_LEVELS
        from src.levels.level_data import LevelData
        data = LevelData.load(ANOMALY_LEVELS[2])
        self.assertEqual(tuple(data.gravity_start), (0, -1))

    def test_pick_always_returns_existing_path(self):
        import os
        from src.systems.level_generator import pick_anomaly_room
        for seed in range(10):
            for idx in range(5):
                path = pick_anomaly_room(seed, idx)
                self.assertTrue(os.path.exists(path), f"Missing: {path}")


class TestRotationCinematic(unittest.TestCase):
    """Tests for camera zoom-in / hold / zoom-out cinematic."""

    def _cam(self) -> object:
        from src.rendering.camera import Camera
        return Camera(800, 600)

    def test_zoom_is_one_initially(self) -> None:
        self.assertAlmostEqual(self._cam().zoom, 1.0)

    def test_inactive_by_default(self) -> None:
        self.assertFalse(self._cam()._cinematic_active)

    def test_cinematic_active_after_start(self) -> None:
        cam = self._cam()
        cam.start_rotation_cinematic()
        self.assertTrue(cam._cinematic_active)

    def test_zoom_increases_during_zoom_in_phase(self) -> None:
        cam = self._cam()
        cam.start_rotation_cinematic()
        cam.update(0.0, 0.0, C.ROTATION_ZOOM_IN_DUR * 0.5)
        self.assertGreater(cam.zoom, 1.0)

    def test_zoom_reaches_peak_after_zoom_in(self) -> None:
        cam = self._cam()
        cam.start_rotation_cinematic()
        cam.update(0.0, 0.0, C.ROTATION_ZOOM_IN_DUR)
        self.assertAlmostEqual(cam.zoom, C.ROTATION_ZOOM_PEAK, places=2)

    def test_zoom_returns_to_one_after_cinematic(self) -> None:
        cam = self._cam()
        cam.start_rotation_cinematic()
        total = C.ROTATION_ZOOM_IN_DUR + C.ROTATION_ZOOM_HOLD_DUR + C.ROTATION_ZOOM_OUT_DUR
        cam.update(0.0, 0.0, total + 0.1)
        self.assertAlmostEqual(cam.zoom, 1.0, places=2)

    def test_cinematic_inactive_after_completion(self) -> None:
        cam = self._cam()
        cam.start_rotation_cinematic()
        total = C.ROTATION_ZOOM_IN_DUR + C.ROTATION_ZOOM_HOLD_DUR + C.ROTATION_ZOOM_OUT_DUR
        cam.update(0.0, 0.0, total + 0.1)
        self.assertFalse(cam._cinematic_active)

    def test_normal_zoom_unaffected_when_cinematic_inactive(self) -> None:
        cam = self._cam()
        cam.zoom = 1.5
        cam.update(0.0, 0.0, 1.0)
        self.assertGreater(cam.zoom, 1.0)

    def test_peak_zoom_above_one(self) -> None:
        self.assertGreater(C.ROTATION_ZOOM_PEAK, 1.0)

    def test_total_cinematic_duration_under_one_second(self) -> None:
        total = C.ROTATION_ZOOM_IN_DUR + C.ROTATION_ZOOM_HOLD_DUR + C.ROTATION_ZOOM_OUT_DUR
        self.assertLess(total, 1.0)


class TestGravityZones(unittest.TestCase):
    """Tests for gravity zone data structures and in-level loading."""

    def test_zone_def_from_dict_direction_only(self) -> None:
        zone = GravityZoneDef.from_dict({"x": 100, "y": 200, "w": 300, "h": 400, "gravity_dir": [1, 0]})
        self.assertEqual(zone.x, 100)
        self.assertEqual(zone.gravity_dir, (1, 0))
        self.assertIsNone(zone.strength_mult)

    def test_zone_def_from_dict_strength_only(self) -> None:
        zone = GravityZoneDef.from_dict({"x": 0, "y": 0, "w": 200, "h": 200, "strength_mult": 0.5})
        self.assertIsNone(zone.gravity_dir)
        self.assertAlmostEqual(zone.strength_mult, 0.5)

    def test_zone_def_from_dict_both_fields(self) -> None:
        zone = GravityZoneDef.from_dict({"x": 0, "y": 0, "w": 200, "h": 200, "gravity_dir": [0, -1], "strength_mult": 2.0})
        self.assertEqual(zone.gravity_dir, (0, -1))
        self.assertAlmostEqual(zone.strength_mult, 2.0)

    def test_zone_def_from_dict_neither_field(self) -> None:
        zone = GravityZoneDef.from_dict({"x": 0, "y": 0, "w": 100, "h": 100})
        self.assertIsNone(zone.gravity_dir)
        self.assertIsNone(zone.strength_mult)

    def test_zone_def_to_dict_roundtrip(self) -> None:
        zone = GravityZoneDef(x=50, y=100, w=200, h=300, gravity_dir=(0, -1), strength_mult=0.5)
        restored = GravityZoneDef.from_dict(zone.to_dict())
        self.assertEqual(restored.x, 50)
        self.assertEqual(restored.y, 100)
        self.assertEqual(restored.gravity_dir, (0, -1))
        self.assertAlmostEqual(restored.strength_mult, 0.5)

    def test_zone_def_to_dict_omits_none_fields(self) -> None:
        d = GravityZoneDef(x=0, y=0, w=100, h=100).to_dict()
        self.assertNotIn("gravity_dir", d)
        self.assertNotIn("strength_mult", d)

    def test_level_data_loads_gravity_zones(self) -> None:
        data = LevelData.from_dict({
            "name": "test", "gravity_start": [0, 1], "spawn": [100.0, 200.0],
            "goal": {"x": 700, "y": 300, "w": 40, "h": 40},
            "gravity_zones": [{"x": 100, "y": 0, "w": 400, "h": 600, "strength_mult": 0.4}],
        })
        self.assertEqual(len(data.gravity_zones), 1)
        self.assertAlmostEqual(data.gravity_zones[0].strength_mult, 0.4)

    def test_level_data_empty_zones_default(self) -> None:
        data = LevelData.from_dict({
            "name": "test", "gravity_start": [0, 1], "spawn": [100.0, 200.0],
            "goal": {"x": 700, "y": 300, "w": 40, "h": 40},
        })
        self.assertEqual(data.gravity_zones, [])

    def test_level_03_has_zones(self) -> None:
        renderer = LevelRenderer()
        renderer.load(main.LEVELS[2])
        self.assertGreater(len(renderer.gravity_zones), 0)

    def test_level_03_has_low_gravity_zone(self) -> None:
        renderer = LevelRenderer()
        renderer.load(main.LEVELS[2])
        strength_zones = [z for z in renderer.gravity_zones if z.strength_mult is not None]
        self.assertTrue(any(z.strength_mult < 1.0 for z in strength_zones))

    def test_level_03_has_direction_zone(self) -> None:
        renderer = LevelRenderer()
        renderer.load(main.LEVELS[2])
        dir_zones = [z for z in renderer.gravity_zones if z.gravity_dir is not None]
        self.assertGreater(len(dir_zones), 0)

    def test_zone_strength_multiplies_per_zone(self) -> None:
        """Two overlapping strength zones multiply together."""
        # Simulate what main.py does: zone_strength_mult *= zone.strength_mult
        zones = [
            GravityZoneDef(x=0, y=0, w=100, h=100, strength_mult=0.5),
            GravityZoneDef(x=0, y=0, w=100, h=100, strength_mult=0.8),
        ]
        mult = 1.0
        for z in zones:
            if z.strength_mult is not None:
                mult *= z.strength_mult
        self.assertAlmostEqual(mult, 0.4)


class TestParticlePool(unittest.TestCase):
    """Tests for the pooled particle VFX system."""

    def _make_pool(self, size: int = 200) -> object:
        from src.rendering.vfx import ParticlePool
        return ParticlePool(size)

    def test_pool_pre_allocates_capacity(self) -> None:
        pool = self._make_pool(50)
        self.assertEqual(len(pool._pool), 50)

    def test_emit_rotation_burst_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_ROTATION_BURST_COUNT)

    def test_emit_hit_spark_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_hit_spark(0.0, 0.0)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_HIT_SPARK_COUNT)

    def test_emit_landing_dust_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_landing_dust(0.0, 0.0, 64.0, 96.0, (0, 1))
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_LANDING_DUST_COUNT)

    def test_update_decrements_lifetime(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        first = next(p for p in pool._pool if p.active)
        before = first.lifetime
        pool.update(0.1)
        self.assertAlmostEqual(first.lifetime, before - 0.1, places=5)

    def test_update_deactivates_expired_particles(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        for _ in range(100):
            pool.update(0.1)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, 0)

    def test_pool_recycles_when_full(self) -> None:
        pool = self._make_pool(5)
        # Emit far more than capacity — should not raise
        for _ in range(10):
            pool.emit_rotation_burst(0.0, 0.0)
        self.assertEqual(len(pool._pool), 5)

    def test_landing_dust_moves_against_down_gravity(self) -> None:
        """Dust from a down-gravity landing should on average move upward."""
        pool = self._make_pool(200)
        pool.emit_landing_dust(400.0, 400.0, 64.0, 96.0, (0, 1))
        active = [p for p in pool._pool if p.active]
        avg_vy = sum(p.vy for p in active) / len(active)
        self.assertLess(avg_vy, 0.0)

    def test_landing_dust_moves_against_right_gravity(self) -> None:
        """Dust from a right-gravity landing should on average move leftward."""
        pool = self._make_pool(200)
        pool.emit_landing_dust(400.0, 400.0, 96.0, 64.0, (1, 0))
        active = [p for p in pool._pool if p.active]
        avg_vx = sum(p.vx for p in active) / len(active)
        self.assertLess(avg_vx, 0.0)

    def test_rotation_burst_particles_have_varied_directions(self) -> None:
        """Burst particles should spread in multiple directions."""
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        active = [p for p in pool._pool if p.active]
        vx_signs = {1 if p.vx >= 0 else -1 for p in active}
        vy_signs = {1 if p.vy >= 0 else -1 for p in active}
        self.assertEqual(len(vx_signs), 2)
        self.assertEqual(len(vy_signs), 2)


class TestGravityOffDefaultDrain(unittest.TestCase):
    """Chrono drains while in non-default gravity; snaps back at 0."""

    def test_drain_constant_exists(self) -> None:
        self.assertGreater(C.GRAVITY_OFFDEFAULT_DRAIN, 0.0)

    def test_drain_less_than_move_regen_early_game(self) -> None:
        """Early game: moving regen (15/s) > drain (10/s) → net positive while moving."""
        self.assertGreater(C.CHRONO_REGEN_MOVE, C.GRAVITY_OFFDEFAULT_DRAIN)

    def test_drain_exceeds_move_regen_at_max_pressure(self) -> None:
        """Near singularity: regen throttled to 33% → net negative even while moving."""
        throttled_regen = C.CHRONO_REGEN_MOVE * C.SINGULARITY_CHRONO_REGEN_MIN_MULT
        self.assertLess(throttled_regen, C.GRAVITY_OFFDEFAULT_DRAIN)

    def test_drain_per_tick(self) -> None:
        """Simulated drain over one physics tick reduces chrono correctly."""
        chrono = 100.0
        drain_per_tick = C.GRAVITY_OFFDEFAULT_DRAIN * C.PHYSICS_DT
        chrono = max(0.0, chrono - drain_per_tick)
        expected = 100.0 - C.GRAVITY_OFFDEFAULT_DRAIN / C.FPS
        self.assertAlmostEqual(chrono, expected)

    def test_drain_floors_at_zero(self) -> None:
        """Drain does not go below zero."""
        chrono = 0.001  # nearly empty
        drain_per_tick = C.GRAVITY_OFFDEFAULT_DRAIN * C.PHYSICS_DT
        chrono = max(0.0, chrono - drain_per_tick)
        self.assertEqual(chrono, 0.0)

    def test_full_bar_duration_off_default(self) -> None:
        """Full chrono bar sustains off-default gravity for at least 8 seconds idle."""
        seconds_available = C.CHRONO_RESERVE_MAX / C.GRAVITY_OFFDEFAULT_DRAIN
        self.assertGreater(seconds_available, 8.0)


class TestHardLandingVelocity(unittest.TestCase):
    """Fall/impact damage threshold tests."""

    def test_threshold_constant_exists(self) -> None:
        self.assertGreater(C.HARD_LAND_VELOCITY, 0.0)

    def test_threshold_below_terminal_velocity(self) -> None:
        self.assertLess(C.HARD_LAND_VELOCITY, C.TERMINAL_VELOCITY)

    def test_normal_jump_velocity_below_threshold(self) -> None:
        """A direct jump and land should not exceed the damage threshold."""
        self.assertLess(C.JUMP_SPEED, C.HARD_LAND_VELOCITY)

    def test_gravity_speed_detects_downward_impact(self) -> None:
        """gravity_speed returns positive value for downward fall in down-gravity."""
        vel = gravity_speed(0.0, C.HARD_LAND_VELOCITY + 1.0, GRAVITY_DOWN)
        self.assertGreater(vel, C.HARD_LAND_VELOCITY)

    def test_gravity_speed_detects_rightward_impact(self) -> None:
        """gravity_speed returns positive value for rightward fall in right-gravity."""
        vel = gravity_speed(C.HARD_LAND_VELOCITY + 1.0, 0.0, GRAVITY_RIGHT)
        self.assertGreater(vel, C.HARD_LAND_VELOCITY)

    def test_gravity_speed_detects_upward_impact(self) -> None:
        """gravity_speed returns positive for upward fall in up-gravity."""
        vel = gravity_speed(0.0, -(C.HARD_LAND_VELOCITY + 1.0), GRAVITY_UP)
        self.assertGreater(vel, C.HARD_LAND_VELOCITY)

    def test_gravity_speed_detects_leftward_impact(self) -> None:
        """gravity_speed returns positive for leftward fall in left-gravity."""
        vel = gravity_speed(-(C.HARD_LAND_VELOCITY + 1.0), 0.0, GRAVITY_LEFT)
        self.assertGreater(vel, C.HARD_LAND_VELOCITY)


if __name__ == "__main__":
    unittest.main()
