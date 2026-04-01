"""Tests for the extracted src/physics/ module.

Tests the public API directly — gravity, collision, movement.
"""
import unittest

import tests.conftest  # noqa: F401
import pygame

import constants as C
from src.physics import (
    GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT,
    rotate_gravity_ccw, gravity_is_vertical, gravity_speed,
    apply_gravity, clamp_terminal_velocity,
    resolve_collisions,
    apply_lateral_movement, apply_jump_impulse, apply_jump_cut,
)


class TestApplyGravityAllDirections(unittest.TestCase):
    """apply_gravity() increases velocity along gravity axis."""

    def test_gravity_down_increases_vy(self):
        vx, vy = apply_gravity(0, 0, GRAVITY_DOWN, on_ground=False)
        self.assertGreater(vy, 0)
        self.assertEqual(vx, 0)

    def test_gravity_up_decreases_vy(self):
        vx, vy = apply_gravity(0, 0, GRAVITY_UP, on_ground=False)
        self.assertLess(vy, 0)
        self.assertEqual(vx, 0)

    def test_gravity_left_decreases_vx(self):
        vx, vy = apply_gravity(0, 0, GRAVITY_LEFT, on_ground=False)
        self.assertLess(vx, 0)
        self.assertEqual(vy, 0)

    def test_gravity_right_increases_vx(self):
        vx, vy = apply_gravity(0, 0, GRAVITY_RIGHT, on_ground=False)
        self.assertGreater(vx, 0)
        self.assertEqual(vy, 0)

    def test_peak_multiplier_when_slow(self):
        """Near peak of jump, gravity should be stronger."""
        vx_normal, vy_normal = apply_gravity(0, 5, GRAVITY_DOWN, on_ground=False)
        vx_peak, vy_peak = apply_gravity(0, 0.5, GRAVITY_DOWN, on_ground=False)
        # Peak gravity adds more than normal when near peak
        delta_normal = vy_normal - 5
        delta_peak = vy_peak - 0.5
        self.assertGreater(delta_peak, delta_normal)

    def test_no_peak_mult_on_ground(self):
        """On ground, peak multiplier should not apply even at low speed."""
        vx, vy = apply_gravity(0, 0, GRAVITY_DOWN, on_ground=True)
        self.assertAlmostEqual(vy, C.GRAVITY_STRENGTH)


class TestClampTerminalVelocity(unittest.TestCase):
    """clamp_terminal_velocity() caps speed along gravity axis."""

    def test_clamps_high_speed_down(self):
        vx, vy = clamp_terminal_velocity(0, 999, GRAVITY_DOWN)
        self.assertAlmostEqual(vy, C.TERMINAL_VELOCITY)

    def test_clamps_high_speed_left(self):
        vx, vy = clamp_terminal_velocity(-999, 0, GRAVITY_LEFT)
        self.assertAlmostEqual(vx, -C.TERMINAL_VELOCITY)

    def test_preserves_lateral(self):
        vx, vy = clamp_terminal_velocity(42.0, 999, GRAVITY_DOWN)
        self.assertAlmostEqual(vx, 42.0)

    def test_does_not_clamp_below_terminal(self):
        vx, vy = clamp_terminal_velocity(0, 5, GRAVITY_DOWN)
        self.assertAlmostEqual(vy, 5.0)


class TestApplyLateralMovement(unittest.TestCase):
    """apply_lateral_movement() accelerates along the lateral axis."""

    def test_accelerate_right_gravity_down(self):
        vx, vy = apply_lateral_movement(0, 0, 1, GRAVITY_DOWN, on_ground=True)
        self.assertAlmostEqual(vx, C.ACCEL)

    def test_accelerate_left_gravity_down(self):
        vx, vy = apply_lateral_movement(0, 0, -1, GRAVITY_DOWN, on_ground=True)
        self.assertAlmostEqual(vx, -C.ACCEL)

    def test_decelerate_to_zero(self):
        vx, vy = apply_lateral_movement(0.5, 0, 0, GRAVITY_DOWN, on_ground=True)
        self.assertEqual(vx, 0.0)

    def test_air_accel_slower_than_ground(self):
        vx_ground, _ = apply_lateral_movement(0, 0, 1, GRAVITY_DOWN, on_ground=True)
        vx_air, _ = apply_lateral_movement(0, 0, 1, GRAVITY_DOWN, on_ground=False)
        self.assertGreater(vx_ground, vx_air)

    def test_horizontal_gravity_moves_vy(self):
        vx, vy = apply_lateral_movement(0, 0, 1, GRAVITY_LEFT, on_ground=True)
        self.assertEqual(vx, 0)
        self.assertAlmostEqual(vy, C.ACCEL)

    def test_clamped_to_max(self):
        vx, vy = apply_lateral_movement(C.MAX_MOVE_SPEED, 0, 1, GRAVITY_DOWN, on_ground=True)
        self.assertEqual(vx, C.MAX_MOVE_SPEED)


class TestApplyJumpImpulse(unittest.TestCase):
    """apply_jump_impulse() launches player opposite to gravity."""

    def test_all_four_directions(self):
        for gdir, expected_sign in [
            (GRAVITY_DOWN, (0, -1)),
            (GRAVITY_UP, (0, 1)),
            (GRAVITY_LEFT, (1, 0)),
            (GRAVITY_RIGHT, (-1, 0)),
        ]:
            vx, vy = apply_jump_impulse(0, 0, gdir)
            if expected_sign[0] != 0:
                self.assertEqual(vx / abs(vx), expected_sign[0], f"Failed for {gdir}")
            else:
                self.assertEqual(vx, 0)
            if expected_sign[1] != 0:
                self.assertEqual(vy / abs(vy), expected_sign[1], f"Failed for {gdir}")
            else:
                self.assertEqual(vy, 0)

    def test_impulse_magnitude(self):
        vx, vy = apply_jump_impulse(0, 0, GRAVITY_DOWN)
        self.assertAlmostEqual(abs(vy), C.JUMP_SPEED)


class TestApplyJumpCut(unittest.TestCase):
    """apply_jump_cut() reduces velocity on early release."""

    def test_cuts_when_going_up(self):
        vx, vy = apply_jump_cut(0, -C.JUMP_SPEED, GRAVITY_DOWN)
        self.assertAlmostEqual(vy, -C.JUMP_SPEED * C.JUMP_CUT_MULTIPLIER)

    def test_no_cut_when_falling(self):
        vx, vy = apply_jump_cut(0, 5, GRAVITY_DOWN)
        self.assertAlmostEqual(vy, 5)

    def test_cuts_correct_axis_horizontal(self):
        vx, vy = apply_jump_cut(C.JUMP_SPEED, 0, GRAVITY_LEFT)
        self.assertAlmostEqual(vx, C.JUMP_SPEED * C.JUMP_CUT_MULTIPLIER)

    def test_no_cut_when_falling_horizontal(self):
        vx, vy = apply_jump_cut(-5, 0, GRAVITY_LEFT)
        self.assertAlmostEqual(vx, -5)


class TestCollisionAllOrientations(unittest.TestCase):
    """resolve_collisions works correctly in all 4 gravity directions."""

    def test_ground_detection_all_four(self):
        """Player placed 1px into platform detects ground in all orientations."""
        cases = [
            (GRAVITY_DOWN, pygame.Rect(0, 500, 200, 20), 100.0, 486.0),
            (GRAVITY_UP, pygame.Rect(0, 100, 200, 20), 100.0, 134.0),
            (GRAVITY_LEFT, pygame.Rect(100, 0, 20, 200), 134.0, 100.0),
            (GRAVITY_RIGHT, pygame.Rect(200, 0, 20, 200), 186.0, 100.0),
        ]
        for gdir, plat, px, py in cases:
            _, _, _, _, on_ground = resolve_collisions(
                px, py, 0, 0, 30, 30, [plat], gdir,
            )
            self.assertTrue(on_ground, f"Not grounded with gravity={gdir}")

    def test_no_ground_when_airborne(self):
        plat = pygame.Rect(0, 500, 200, 20)
        _, _, _, _, on_ground = resolve_collisions(
            100, 300, 0, 0, 30, 30, [plat], GRAVITY_DOWN,
        )
        self.assertFalse(on_ground)

    def test_wall_collision_stops_lateral(self):
        wall = pygame.Rect(300, 0, 20, 600)
        px, _, vx, _, _ = resolve_collisions(
            290, 300, 5, 0, 30, 30, [wall], GRAVITY_DOWN,
        )
        self.assertEqual(vx, 0)
        self.assertAlmostEqual(px, 300 - 15)


class TestGravityRotationStress(unittest.TestCase):
    """Rapid gravity rotation stress test."""

    def test_1000_rotations_stay_valid(self):
        gdir = GRAVITY_DOWN
        for _ in range(1000):
            gdir = rotate_gravity_ccw(gdir)
        self.assertEqual(gdir, GRAVITY_DOWN)  # 1000 % 4 == 0

    def test_gravity_speed_consistent_after_rotations(self):
        gdir = GRAVITY_DOWN
        for _ in range(7):  # 7 rotations = 1 full + 3 = GRAVITY_LEFT
            gdir = rotate_gravity_ccw(gdir)
        self.assertEqual(gdir, GRAVITY_LEFT)
        self.assertEqual(gravity_speed(-5, 0, gdir), 5)


if __name__ == "__main__":
    unittest.main()
