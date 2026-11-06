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


class TestJumpBuffer(unittest.TestCase):
    """Jump buffer stores an airborne jump press and fires it on the next landing."""

    def test_buffer_time_matches_frames(self):
        self.assertAlmostEqual(C.JUMP_BUFFER_TIME, C.JUMP_BUFFER_FRAMES / C.FPS, places=6)

    def test_buffer_expires_after_window(self):
        timer = C.JUMP_BUFFER_TIME
        dt = C.PHYSICS_DT
        for _ in range(C.JUMP_BUFFER_FRAMES + 1):
            timer = max(0.0, timer - dt)
        self.assertEqual(timer, 0.0)

    def test_buffer_still_alive_within_window(self):
        timer = C.JUMP_BUFFER_TIME
        dt = C.PHYSICS_DT
        for _ in range(C.JUMP_BUFFER_FRAMES - 1):
            timer = max(0.0, timer - dt)
        self.assertGreater(timer, 0.0)

    def test_player_has_jump_buffer_field(self):
        p = Player.from_spawn((100.0, 772.0))
        self.assertEqual(p.jump_buffer_timer, 0.0)

    def test_player_reset_clears_buffer(self):
        p = Player.from_spawn((100.0, 772.0))
        p.jump_buffer_timer = C.JUMP_BUFFER_TIME
        p.reset((100.0, 772.0), (0, 1))
        self.assertEqual(p.jump_buffer_timer, 0.0)

    def test_fall_damage_clears_buffer(self):
        p = Player.from_spawn((100.0, 772.0))
        p.jump_buffer_timer = C.JUMP_BUFFER_TIME
        p.anchor_integrity = 2
        p.take_fall_damage()
        self.assertEqual(p.jump_buffer_timer, 0.0)

    def test_buffer_in_player_to_dict(self):
        p = Player.from_spawn((100.0, 772.0))
        p.jump_buffer_timer = 0.05
        d = p.to_dict()
        self.assertIn("jump_buffer_timer", d)
        self.assertAlmostEqual(d["jump_buffer_timer"], 0.05)


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
        self.assertEqual(_level.goal_rect, pygame.Rect(660, 490, 220, 130))

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

    def test_no_enemies_field_defaults_to_empty(self):
        minimal = json.dumps({
            "name": "minimal", "gravity_start": [0, 1], "spawn": [0, 0],
            "goal": {"x": 0, "y": 0, "w": 10, "h": 10},
        })
        data = LevelData.from_json(minimal)
        self.assertEqual(len(data.enemies), 0)


class TestEnemyDef(unittest.TestCase):
    """EnemyDef round-trips through JSON and loads from level files."""

    def test_roundtrip_temporal_echo(self):
        from src.levels.level_data import EnemyDef
        e = EnemyDef(type="temporal_echo", x=100.0, y=790.0, min_x=30.0, max_x=500.0)
        restored = EnemyDef.from_dict(e.to_dict())
        self.assertEqual(restored.type, "temporal_echo")
        self.assertAlmostEqual(restored.x, 100.0)
        self.assertAlmostEqual(restored.min_x, 30.0)
        self.assertAlmostEqual(restored.max_x, 500.0)
        self.assertAlmostEqual(restored.speed, 0.0)

    def test_speed_included_only_when_nonzero(self):
        from src.levels.level_data import EnemyDef
        e_default = EnemyDef(type="fold_predator", x=0.0, y=0.0, min_x=0.0, max_x=100.0)
        self.assertNotIn("speed", e_default.to_dict())
        e_custom = EnemyDef(type="fold_predator", x=0.0, y=0.0, min_x=0.0, max_x=100.0, speed=3.5)
        self.assertIn("speed", e_custom.to_dict())
        self.assertAlmostEqual(e_custom.to_dict()["speed"], 3.5)

    def test_level_file_enemies_load_correctly(self):
        data = LevelData.load("levels/level_01.json")
        self.assertEqual(len(data.enemies), 1)
        self.assertEqual(data.enemies[0].type, "temporal_echo")
        self.assertAlmostEqual(data.enemies[0].y, 790.0)

    def test_level_04_has_two_enemies(self):
        data = LevelData.load("levels/level_04.json")
        self.assertEqual(len(data.enemies), 2)
        types = {e.type for e in data.enemies}
        self.assertIn("fold_predator", types)
        self.assertIn("anchored", types)

    def test_anomaly_rooms_have_no_enemies(self):
        import glob
        for path in glob.glob("levels/anomaly_*.json"):
            data = LevelData.load(path)
            self.assertEqual(len(data.enemies), 0, f"{path} should have no enemies")

    def test_enemies_field_in_to_dict(self):
        from src.levels.level_data import EnemyDef
        data = LevelData(
            name="t", gravity_start=(0, 1), spawn=(0.0, 0.0),
            goal=GoalDef(0, 0, 10, 10),
            enemies=[EnemyDef(type="temporal_echo", x=50.0, y=790.0, min_x=0.0, max_x=200.0)],
        )
        d = data.to_dict()
        self.assertIn("enemies", d)
        self.assertEqual(len(d["enemies"]), 1)
        self.assertEqual(d["enemies"][0]["type"], "temporal_echo")


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
        # 9-node sequence: last playable = node 7 (node 8 is singularity)
        self.assertAlmostEqual(self._run(7).singularity_pressure, 1.0)

    def test_pressure_increases_monotonically(self) -> None:
        pressures = [self._run(i).singularity_pressure for i in range(8)]
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
        """Player to right of enemy gets positive vx and upward anti-gravity vy."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(150.0, 100.0, 100.0, 100.0, (0, 1))
        self.assertGreater(vx, 0.0)
        self.assertLess(vy, 0.0)  # upward kick against DOWN gravity

    def test_compute_knockback_pushes_left(self) -> None:
        """Player to left of enemy gets negative vx and upward anti-gravity vy."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(50.0, 100.0, 100.0, 100.0, (0, 1))
        self.assertLess(vx, 0.0)
        self.assertLess(vy, 0.0)  # upward kick against DOWN gravity

    def test_compute_knockback_horizontal_gravity_uses_y(self) -> None:
        """With RIGHT gravity, lateral component is vy and anti-gravity kick is -vx."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(100.0, 150.0, 100.0, 100.0, (1, 0))
        self.assertLess(vx, 0.0)  # kick against RIGHT gravity = leftward
        self.assertGreater(vy, 0.0)  # player below enemy, pushed down (lateral)

    def test_take_fall_damage_returns_false_above_zero(self) -> None:
        p = self._make_player()
        result = p.take_fall_damage()
        self.assertFalse(result)

    def test_take_fall_damage_returns_true_at_zero(self) -> None:
        p = self._make_player()
        p.anchor_integrity = 1
        result = p.take_fall_damage()
        self.assertTrue(result)


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
