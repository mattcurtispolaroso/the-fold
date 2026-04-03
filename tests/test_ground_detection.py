"""Tests for ground detection, adjacency probe, and player state determination.

Covers coverage gaps E1, E2, E3 from the audit.
"""
import unittest

import tests.conftest  # noqa: F401
import pygame

import constants as C
import constants as C
from src.physics import (
    GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT,
    get_player_physics_size,
    gravity_speed,
)
from src.physics.collision import _check_ground_adjacent, resolve_collisions


class TestGroundAdjacencyProbe(unittest.TestCase):
    """_check_ground_adjacent detects platforms adjacent to player."""

    def test_adjacent_below_gravity_down(self):
        plat = pygame.Rect(0, 500, 200, 20)
        result = _check_ground_adjacent(100, 500 - 15, 30, 30, [plat], GRAVITY_DOWN)
        self.assertTrue(result)

    def test_not_adjacent_when_airborne(self):
        plat = pygame.Rect(0, 500, 200, 20)
        result = _check_ground_adjacent(100, 400, 30, 30, [plat], GRAVITY_DOWN)
        self.assertFalse(result)

    def test_adjacent_above_gravity_up(self):
        plat = pygame.Rect(0, 100, 200, 20)
        result = _check_ground_adjacent(100, 120 + 15, 30, 30, [plat], GRAVITY_UP)
        self.assertTrue(result)

    def test_adjacent_left_gravity_left(self):
        plat = pygame.Rect(100, 0, 20, 200)
        result = _check_ground_adjacent(120 + 15, 100, 30, 30, [plat], GRAVITY_LEFT)
        self.assertTrue(result)

    def test_adjacent_right_gravity_right(self):
        plat = pygame.Rect(200, 0, 20, 200)
        result = _check_ground_adjacent(200 - 15, 100, 30, 30, [plat], GRAVITY_RIGHT)
        self.assertTrue(result)

    def test_no_platforms_returns_false(self):
        result = _check_ground_adjacent(100, 100, 30, 30, [], GRAVITY_DOWN)
        self.assertFalse(result)


class TestGroundStabilityMultiFrame(unittest.TestCase):
    """Player should remain on_ground across multiple frames without oscillation."""

    def test_grounded_stays_grounded_10_frames(self):
        """Simulate 10 frames of standing still — on_ground every frame."""
        plat = pygame.Rect(0, 500, 200, 20)
        px, py = 100.0, 500.0 - 15
        vx, vy = 0.0, 0.0
        for _ in range(10):
            px, py, vx, vy, on_ground = resolve_collisions(
                px, py, vx, vy, 30, 30, [plat], GRAVITY_DOWN,
            )
            self.assertTrue(on_ground, f"Lost ground at px={px}, py={py}")
            self.assertEqual(vy, 0.0)

    def test_grounded_stays_grounded_gravity_up(self):
        plat = pygame.Rect(0, 100, 200, 20)
        px, py = 100.0, 120.0 + 15
        vx, vy = 0.0, 0.0
        for _ in range(10):
            px, py, vx, vy, on_ground = resolve_collisions(
                px, py, vx, vy, 30, 30, [plat], GRAVITY_UP,
            )
            self.assertTrue(on_ground)
            self.assertEqual(vy, 0.0)


class TestDeterminePlayerState(unittest.TestCase):
    """_determine_player_state in main.py should return correct states."""

    def test_idle_on_ground_no_input(self):
        from main import _determine_player_state
        from src.rendering.animation import PlayerState
        state = _determine_player_state(True, 0, 0, GRAVITY_DOWN, 0)
        self.assertEqual(state, PlayerState.IDLE)

    def test_walk_on_ground_with_input(self):
        from main import _determine_player_state
        from src.rendering.animation import PlayerState
        state = _determine_player_state(True, 3, 0, GRAVITY_DOWN, 1)
        self.assertEqual(state, PlayerState.WALK)

    def test_jump_rising_airborne(self):
        from main import _determine_player_state
        from src.rendering.animation import PlayerState
        state = _determine_player_state(False, 0, -5, GRAVITY_DOWN, 0)
        self.assertEqual(state, PlayerState.JUMP_RISING)

    def test_jump_falling_airborne(self):
        from main import _determine_player_state
        from src.rendering.animation import PlayerState
        state = _determine_player_state(False, 0, 5, GRAVITY_DOWN, 0)
        self.assertEqual(state, PlayerState.JUMP_FALLING)

    def test_jump_peak_airborne(self):
        from main import _determine_player_state
        from src.rendering.animation import PlayerState
        state = _determine_player_state(False, 0, 0.5, GRAVITY_DOWN, 0)
        self.assertEqual(state, PlayerState.JUMP_PEAK)


class TestGetPlayerPhysicsSize(unittest.TestCase):
    """get_player_physics_size returns correct dimensions per gravity."""

    def test_gravity_down_returns_normal(self):
        w, h = get_player_physics_size(GRAVITY_DOWN)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_NORMAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_NORMAL)

    def test_gravity_up_returns_normal(self):
        w, h = get_player_physics_size(GRAVITY_UP)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_NORMAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_NORMAL)

    def test_gravity_left_returns_horizontal(self):
        w, h = get_player_physics_size(GRAVITY_LEFT)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_HORIZONTAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL)

    def test_gravity_right_returns_horizontal(self):
        w, h = get_player_physics_size(GRAVITY_RIGHT)
        self.assertEqual(w, C.PLAYER_PHYSICS_WIDTH_HORIZONTAL)
        self.assertEqual(h, C.PLAYER_PHYSICS_HEIGHT_HORIZONTAL)

    def test_normal_and_horizontal_are_swapped(self):
        """Width/height swap when switching between vertical and horizontal gravity."""
        nw, nh = get_player_physics_size(GRAVITY_DOWN)
        hw, hh = get_player_physics_size(GRAVITY_LEFT)
        self.assertEqual(nw, hh)
        self.assertEqual(nh, hw)


if __name__ == "__main__":
    unittest.main()
