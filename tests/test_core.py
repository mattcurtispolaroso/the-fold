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
from src.physics import (
    GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT, GRAVITY_LABELS,
    rotate_gravity_ccw, gravity_is_vertical, gravity_speed,
    apply_gravity, clamp_terminal_velocity,
    resolve_collisions,
    apply_jump_impulse, apply_jump_cut, apply_lateral_movement,
)
from src.levels.level_renderer import LevelRenderer, MovingPlatform
from src.levels.level_data import LevelData, PlatformDef, MovingPlatformDef, GoalDef

# Load level_01 once for level geometry tests
_level = LevelRenderer()
_level.load(main.DEFAULT_LEVEL)


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
        self.assertTrue(os.path.isfile(main.DEFAULT_LEVEL))


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
        data = renderer.load(main.DEFAULT_LEVEL)
        self.assertEqual(data.name, "Test Level")

    def test_level_01_has_correct_platform_count(self):
        self.assertEqual(len(_level.static_platforms), 7)

    def test_level_01_has_correct_moving_platform_count(self):
        self.assertEqual(len(_level.moving_platforms), 2)

    def test_level_01_spawn(self):
        self.assertEqual(_level.spawn, (110.0, 300.0))

    def test_level_01_gravity_start(self):
        self.assertEqual(_level.gravity_start, (0, 1))

    def test_level_01_goal_rect(self):
        self.assertEqual(_level.goal_rect, pygame.Rect(15, 100, 50, 40))

    def test_roundtrip_serialisation(self):
        data = LevelData.load(main.DEFAULT_LEVEL)
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

    def test_all_platforms_within_screen(self):
        for i, plat in enumerate(_level.static_platforms):
            self.assertGreaterEqual(plat.left, 0, f"Platform {i} left edge off-screen")
            self.assertLessEqual(plat.right, main.WIDTH, f"Platform {i} right edge off-screen")
            self.assertGreaterEqual(plat.top, 0, f"Platform {i} top edge off-screen")
            self.assertLessEqual(plat.bottom, main.HEIGHT, f"Platform {i} bottom edge off-screen")

    def test_goal_within_screen(self):
        g = _level.goal_rect
        self.assertGreaterEqual(g.left, 0)
        self.assertLessEqual(g.right, main.WIDTH)
        self.assertGreaterEqual(g.top, 0)
        self.assertLessEqual(g.bottom, main.HEIGHT)

    def test_start_platform_at_bottom_left(self):
        start = _level.static_platforms[0]
        self.assertEqual(start.left, 0)
        self.assertGreater(start.bottom, main.HEIGHT - 100)

    def test_goal_platform_exists(self):
        goal_area = _level.goal_rect.inflate(40, 40)
        found = any(plat.colliderect(goal_area) for plat in _level.static_platforms)
        self.assertTrue(found, "No platform near the goal")


if __name__ == "__main__":
    unittest.main()
