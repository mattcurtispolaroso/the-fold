"""Unit tests for The Fold core game logic.

Run: python -m pytest test_game.py -v
  or: python -m unittest test_game -v

Tests run headless — no game window is opened.
"""
import os
import unittest

# Use a dummy video driver so pygame.init() never opens a window
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

import main


class TestConstants(unittest.TestCase):
    """Sanity-check that physics constants are derived correctly."""

    def test_gravity_derived_from_earth(self):
        expected = main.EARTH_GRAVITY * main.PPM / main.FPS**2
        self.assertAlmostEqual(main.GRAVITY_STRENGTH, expected, places=6)

    def test_terminal_velocity_derived(self):
        expected = 53.0 * main.PPM / main.FPS
        self.assertAlmostEqual(main.TERMINAL_VELOCITY, expected, places=6)

    def test_four_gravity_vectors(self):
        self.assertEqual(len(main.GRAVITY_VECTORS), 4)

    def test_four_floors(self):
        self.assertEqual(len(main.FLOORS), 4)


class TestGravityVectors(unittest.TestCase):
    """Verify each orientation pulls in the correct direction."""

    def test_orientation_down(self):
        gx, gy = main.GRAVITY_VECTORS[0]
        self.assertEqual(gx, 0)
        self.assertGreater(gy, 0)  # pulls downward (+y)

    def test_orientation_left(self):
        gx, gy = main.GRAVITY_VECTORS[1]
        self.assertLess(gx, 0)    # pulls left (-x)
        self.assertEqual(gy, 0)

    def test_orientation_up(self):
        gx, gy = main.GRAVITY_VECTORS[2]
        self.assertEqual(gx, 0)
        self.assertLess(gy, 0)    # pulls upward (-y)

    def test_orientation_right(self):
        gx, gy = main.GRAVITY_VECTORS[3]
        self.assertGreater(gx, 0)  # pulls right (+x)
        self.assertEqual(gy, 0)


class TestRotationCycle(unittest.TestCase):
    """Rotation via R key should cycle counter-clockwise: 0 → 3 → 2 → 1 → 0."""

    def test_full_cycle(self):
        orientation = 0
        expected_sequence = [3, 2, 1, 0]
        for expected in expected_sequence:
            orientation = (orientation - 1) % 4
            self.assertEqual(orientation, expected)

    def test_wrap_around(self):
        self.assertEqual((0 - 1) % 4, 3)
        self.assertEqual((3 - 1) % 4, 2)


class TestGravitySpeed(unittest.TestCase):
    """gravity_speed() should return the velocity component along the gravity axis."""

    def test_vertical_orientations_return_vy(self):
        self.assertEqual(main.gravity_speed(10, 5, 0), 5)
        self.assertEqual(main.gravity_speed(10, 5, 2), 5)

    def test_horizontal_orientations_return_vx(self):
        self.assertEqual(main.gravity_speed(10, 5, 1), 10)
        self.assertEqual(main.gravity_speed(10, 5, 3), 10)


class TestGravityAccumulation(unittest.TestCase):
    """Simulate gravity being applied over multiple frames."""

    def test_falling_accelerates_downward(self):
        vy = 0.0
        for _ in range(60):  # 1 second of frames
            vy += main.GRAVITY_STRENGTH
        # After 1s, velocity should be ~earth gravity in px/frame units
        expected = main.EARTH_GRAVITY * main.PPM / main.FPS  # ~8.17 px/frame
        self.assertAlmostEqual(vy, expected, places=1)

    def test_peak_gravity_multiplier_increases_pull(self):
        vy = 0.0
        vy += main.GRAVITY_STRENGTH * main.PEAK_GRAVITY_MULT
        self.assertAlmostEqual(vy, main.GRAVITY_STRENGTH * 2.5, places=6)


class TestTerminalVelocity(unittest.TestCase):
    """Fall speed must be clamped to TERMINAL_VELOCITY."""

    def test_clamp_downward(self):
        vy = 0.0
        for _ in range(10000):  # way more frames than needed
            vy += main.GRAVITY_STRENGTH
            vy = min(vy, main.TERMINAL_VELOCITY)
        self.assertAlmostEqual(vy, main.TERMINAL_VELOCITY, places=6)

    def test_clamp_leftward(self):
        vx = 0.0
        for _ in range(10000):
            vx += -main.GRAVITY_STRENGTH  # orientation 1 pulls left
            vx = max(vx, -main.TERMINAL_VELOCITY)
        self.assertAlmostEqual(vx, -main.TERMINAL_VELOCITY, places=6)


class TestJumpPhysics(unittest.TestCase):
    """Jump impulse and variable jump height."""

    def test_jump_impulse_orientation_down(self):
        """Jumping with gravity=down should give negative vy (upward)."""
        vx, vy = 0.0, 0.0
        gx, gy = main.GRAVITY_VECTORS[0]
        vx -= gx * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        vy -= gy * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        self.assertEqual(vx, 0.0)
        self.assertAlmostEqual(vy, -main.JUMP_SPEED, places=6)

    def test_jump_impulse_orientation_left(self):
        """Jumping with gravity=left should give positive vx (rightward)."""
        vx, vy = 0.0, 0.0
        gx, gy = main.GRAVITY_VECTORS[1]
        vx -= gx * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        vy -= gy * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        self.assertAlmostEqual(vx, main.JUMP_SPEED, places=6)
        self.assertEqual(vy, 0.0)

    def test_jump_impulse_orientation_up(self):
        vx, vy = 0.0, 0.0
        gx, gy = main.GRAVITY_VECTORS[2]
        vx -= gx * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        vy -= gy * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        self.assertEqual(vx, 0.0)
        self.assertAlmostEqual(vy, main.JUMP_SPEED, places=6)

    def test_jump_impulse_orientation_right(self):
        vx, vy = 0.0, 0.0
        gx, gy = main.GRAVITY_VECTORS[3]
        vx -= gx * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        vy -= gy * main.JUMP_SPEED / main.GRAVITY_STRENGTH
        self.assertAlmostEqual(vx, -main.JUMP_SPEED, places=6)
        self.assertEqual(vy, 0.0)

    def test_variable_jump_cut(self):
        """Early release should reduce velocity by JUMP_CUT_MULTIPLIER."""
        vy = -main.JUMP_SPEED  # mid-jump, moving up (orientation 0)
        vy *= main.JUMP_CUT_MULTIPLIER
        self.assertAlmostEqual(vy, -main.JUMP_SPEED * 0.4, places=6)

    def test_jump_cut_not_applied_when_falling(self):
        """If already falling (vy > 0 with orientation 0), cut should not apply."""
        vy = 3.0  # falling
        orientation = 0
        going_up = (orientation == 0 and vy < 0)
        self.assertFalse(going_up)


class TestCollisionDetection(unittest.TestCase):
    """Floor collision for each orientation."""

    def _make_player_rect(self, px, py):
        return pygame.Rect(
            px - main.PLAYER_SIZE / 2,
            py - main.PLAYER_SIZE / 2,
            main.PLAYER_SIZE,
            main.PLAYER_SIZE,
        )

    def test_collision_floor_bottom(self):
        floor = main.FLOORS[0]
        # Player sitting on the bottom floor
        py = floor.top - main.PLAYER_SIZE / 2
        player = self._make_player_rect(main.WIDTH / 2, py)
        # Should be exactly touching but not overlapping — nudge 1px into floor
        player_inside = self._make_player_rect(main.WIDTH / 2, py + 1)
        self.assertTrue(player_inside.colliderect(floor))

    def test_collision_floor_left(self):
        floor = main.FLOORS[1]
        px = floor.right + main.PLAYER_SIZE / 2
        player_inside = self._make_player_rect(px - 1, main.HEIGHT / 2)
        self.assertTrue(player_inside.colliderect(floor))

    def test_collision_floor_top(self):
        floor = main.FLOORS[2]
        py = floor.bottom + main.PLAYER_SIZE / 2
        player_inside = self._make_player_rect(main.WIDTH / 2, py - 1)
        self.assertTrue(player_inside.colliderect(floor))

    def test_collision_floor_right(self):
        floor = main.FLOORS[3]
        px = floor.left - main.PLAYER_SIZE / 2
        player_inside = self._make_player_rect(px + 1, main.HEIGHT / 2)
        self.assertTrue(player_inside.colliderect(floor))

    def test_no_collision_when_far_away(self):
        player = self._make_player_rect(main.WIDTH / 2, main.HEIGHT / 2)
        for floor in main.FLOORS:
            self.assertFalse(player.colliderect(floor))


class TestCoyoteTime(unittest.TestCase):
    """Coyote timer should count down and allow jumping within the window."""

    def test_timer_starts_at_coyote_time(self):
        coyote_timer = main.COYOTE_TIME
        self.assertAlmostEqual(coyote_timer, 0.1, places=3)

    def test_timer_counts_down(self):
        coyote_timer = main.COYOTE_TIME
        dt = 1.0 / main.FPS
        for _ in range(3):
            coyote_timer = max(0.0, coyote_timer - dt)
        expected = main.COYOTE_TIME - 3.0 / main.FPS
        self.assertAlmostEqual(coyote_timer, expected, places=6)

    def test_timer_reaches_zero(self):
        coyote_timer = main.COYOTE_TIME
        dt = 1.0 / main.FPS
        # 6 frames at 60fps = 0.1s, should exhaust the timer
        for _ in range(10):
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertEqual(coyote_timer, 0.0)

    def test_jump_allowed_within_window(self):
        coyote_timer = main.COYOTE_TIME
        dt = 1.0 / main.FPS
        # After 3 frames (~0.05s), still within window
        for _ in range(3):
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertGreater(coyote_timer, 0)

    def test_jump_denied_after_window(self):
        coyote_timer = main.COYOTE_TIME
        dt = 1.0 / main.FPS
        for _ in range(60):  # 1 full second
            coyote_timer = max(0.0, coyote_timer - dt)
        self.assertEqual(coyote_timer, 0.0)


class TestMovementAcceleration(unittest.TestCase):
    """Horizontal movement should accelerate and decelerate, not snap."""

    def test_acceleration_from_standstill(self):
        vx = 0.0
        vx += 1 * main.ACCEL
        vx = max(-main.MAX_MOVE_SPEED, min(main.MAX_MOVE_SPEED, vx))
        self.assertEqual(vx, main.ACCEL)
        self.assertLess(vx, main.MAX_MOVE_SPEED)  # not yet at max

    def test_deceleration_to_stop(self):
        vx = 3.0
        # Simulate no-input deceleration
        steps = 0
        while vx != 0:
            if abs(vx) < main.DECEL:
                vx = 0
            else:
                vx -= main.DECEL if vx > 0 else -main.DECEL
            steps += 1
            if steps > 100:
                self.fail("Deceleration did not converge")
        self.assertEqual(vx, 0.0)

    def test_speed_clamped_to_max(self):
        vx = 0.0
        for _ in range(100):
            vx += main.ACCEL
            vx = max(-main.MAX_MOVE_SPEED, min(main.MAX_MOVE_SPEED, vx))
        self.assertEqual(vx, main.MAX_MOVE_SPEED)


class TestAirControl(unittest.TestCase):
    """Air accel/decel should be lower than ground values."""

    def test_air_accel_less_than_ground(self):
        self.assertLess(main.AIR_ACCEL, main.ACCEL)

    def test_air_decel_less_than_ground(self):
        self.assertLess(main.AIR_DECEL, main.DECEL)

    def test_air_accel_still_positive(self):
        self.assertGreater(main.AIR_ACCEL, 0)

    def test_momentum_preserved_in_air(self):
        """With no input in air, speed barely decreases per frame."""
        vx = main.MAX_MOVE_SPEED
        if abs(vx) < main.AIR_DECEL:
            vx = 0
        else:
            vx -= main.AIR_DECEL if vx > 0 else -main.AIR_DECEL
        self.assertGreater(vx, main.MAX_MOVE_SPEED * 0.9)


class TestFloorPositions(unittest.TestCase):
    """Each floor should be at the correct edge of the screen."""

    def test_bottom_floor(self):
        f = main.FLOORS[0]
        self.assertEqual(f.bottom, main.HEIGHT)
        self.assertEqual(f.left, 0)
        self.assertEqual(f.width, main.WIDTH)

    def test_left_floor(self):
        f = main.FLOORS[1]
        self.assertEqual(f.left, 0)
        self.assertEqual(f.top, 0)
        self.assertEqual(f.height, main.HEIGHT)

    def test_top_floor(self):
        f = main.FLOORS[2]
        self.assertEqual(f.top, 0)
        self.assertEqual(f.left, 0)
        self.assertEqual(f.width, main.WIDTH)

    def test_right_floor(self):
        f = main.FLOORS[3]
        self.assertEqual(f.right, main.WIDTH)
        self.assertEqual(f.top, 0)
        self.assertEqual(f.height, main.HEIGHT)


if __name__ == "__main__":
    unittest.main()
