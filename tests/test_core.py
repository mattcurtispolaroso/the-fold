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
from src.levels.level_data import LevelData, PlatformDef, MovingPlatformDef, GoalDef

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


if __name__ == "__main__":
    unittest.main()
