"""Tests for the animation system.

Covers sprite rotation, walk animation speed-gating, and debug rect control.
"""
import unittest

import tests.conftest  # noqa: F401
import pygame

import constants as C
from src.rendering.animation import PlayerAnimator, PlayerState


class TestSpriteRotation(unittest.TestCase):
    """Sprite rotation angle must match gravity direction."""

    def test_gravity_down_zero_rotation(self):
        self.assertEqual(C.SPRITE_ROTATION[(0, 1)], 0)

    def test_gravity_up_180_rotation(self):
        self.assertEqual(C.SPRITE_ROTATION[(0, -1)], 180)

    def test_gravity_left_neg90_rotation(self):
        self.assertEqual(C.SPRITE_ROTATION[(-1, 0)], -90)

    def test_gravity_right_90_rotation(self):
        self.assertEqual(C.SPRITE_ROTATION[(1, 0)], 90)

    def test_all_four_directions_defined(self):
        self.assertEqual(len(C.SPRITE_ROTATION), 4)


class TestWalkAnimationSpeedGating(unittest.TestCase):
    """Walk animation should pause when lateral speed is below threshold."""

    def test_walk_frame_stays_zero_when_slow(self):
        animator = PlayerAnimator()
        # Update with speed below threshold
        for _ in range(60):
            animator.update(1 / 60, PlayerState.WALK, lateral_speed=0.1)
        self.assertEqual(animator._walk_frame, 0)

    def test_walk_frame_advances_when_fast(self):
        animator = PlayerAnimator()
        if not animator.has_sprite(PlayerState.WALK):
            self.skipTest("Walk sprite not loaded in test environment")
        # Track whether the frame ever changed from 0
        frame_changed = False
        for _ in range(30):
            animator.update(1 / 60, PlayerState.WALK, lateral_speed=C.MAX_MOVE_SPEED)
            if animator._walk_frame != 0:
                frame_changed = True
        self.assertTrue(frame_changed, "Walk frame never advanced from 0")

    def test_walk_frame_resets_on_stop(self):
        animator = PlayerAnimator()
        # Walk for a bit
        for _ in range(30):
            animator.update(1 / 60, PlayerState.WALK, lateral_speed=5.0)
        # Now stop — switch to idle
        animator.update(1 / 60, PlayerState.IDLE, lateral_speed=0.0)
        self.assertEqual(animator._walk_frame, 0)

    def test_walk_frame_resets_when_speed_drops(self):
        animator = PlayerAnimator()
        for _ in range(30):
            animator.update(1 / 60, PlayerState.WALK, lateral_speed=5.0)
        # Speed drops below threshold while still in walk state
        animator.update(1 / 60, PlayerState.WALK, lateral_speed=0.1)
        self.assertEqual(animator._walk_frame, 0)


class TestDebugDrawRects(unittest.TestCase):
    """Debug rect constant and fallback rect behaviour."""

    def test_debug_draw_rects_default_false(self):
        self.assertFalse(C.DEBUG_DRAW_RECTS)

    def test_fallback_rect_drawn_for_missing_sprite(self):
        """When no sprite exists, a coloured fallback rect is drawn."""
        animator = PlayerAnimator()
        surface = pygame.Surface((200, 200))
        surface.fill((0, 0, 0))
        # JUMP_PEAK has no sprite — should draw fallback
        animator.draw(surface, 10, 10, PlayerState.JUMP_PEAK, True, (0, 1))
        # Centre of the fallback rect should not be black
        cx = 10 + C.PLAYER_SPRITE_WIDTH // 2
        cy = 10 + C.PLAYER_SPRITE_HEIGHT // 2
        color = surface.get_at((cx, cy))
        self.assertNotEqual((color.r, color.g, color.b), (0, 0, 0))


class TestSpritePhysicsOffset(unittest.TestCase):
    """SPRITE_PHYSICS_OFFSET_Y should be defined and tunable."""

    def test_offset_exists(self):
        self.assertIsInstance(C.SPRITE_PHYSICS_OFFSET_Y, int)

    def test_offset_default_zero(self):
        self.assertEqual(C.SPRITE_PHYSICS_OFFSET_Y, 0)


if __name__ == "__main__":
    unittest.main()
