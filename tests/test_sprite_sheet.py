"""Tests for sprite sheet slicing and helmet overlay system."""
import os
import tempfile
import unittest

import tests.conftest  # noqa: F401
import pygame

import constants as C
from src.rendering.sprite_sheet import load_sheet
from src.rendering.animation import (
    HelmetOverlay,
    HelmetState,
    PlayerAnimator,
    PlayerState,
)


class TestLoadSheet(unittest.TestCase):
    """Sprite sheet slicer returns correct frames."""

    def setUp(self):
        """Create a temporary sprite sheet for testing."""
        self.frame_w = 32
        self.frame_h = 48
        self.frame_count = 4
        sheet = pygame.Surface(
            (self.frame_w * self.frame_count, self.frame_h), pygame.SRCALPHA,
        )
        # Paint each frame a distinct color
        self.colors = [
            (255, 0, 0, 255),
            (0, 255, 0, 255),
            (0, 0, 255, 255),
            (255, 255, 0, 255),
        ]
        for i, color in enumerate(self.colors):
            rect = pygame.Rect(i * self.frame_w, 0, self.frame_w, self.frame_h)
            sheet.fill(color, rect)
        self.tmpdir = tempfile.mkdtemp()
        self.sheet_path = os.path.join(self.tmpdir, "test_sheet.png")
        pygame.image.save(sheet, self.sheet_path)

    def test_returns_correct_frame_count(self):
        frames = load_sheet(
            self.sheet_path, self.frame_count, 16, 24,
            self.frame_w, self.frame_h,
        )
        self.assertEqual(len(frames), self.frame_count)

    def test_frames_scaled_to_target(self):
        target_w, target_h = 16, 24
        frames = load_sheet(
            self.sheet_path, self.frame_count, target_w, target_h,
            self.frame_w, self.frame_h,
        )
        for frame in frames:
            self.assertEqual(frame.get_width(), target_w)
            self.assertEqual(frame.get_height(), target_h)

    def test_frames_preserve_distinct_colors(self):
        """Each sliced frame should have its own dominant color."""
        frames = load_sheet(
            self.sheet_path, self.frame_count, self.frame_w, self.frame_h,
            self.frame_w, self.frame_h,
        )
        centers = []
        for frame in frames:
            cx = frame.get_width() // 2
            cy = frame.get_height() // 2
            centers.append(tuple(frame.get_at((cx, cy))))
        # All four centre colours should be distinct
        self.assertEqual(len(set(centers)), self.frame_count)

    def test_missing_file_returns_empty(self):
        frames = load_sheet("/nonexistent/sheet.png", 4, 16, 24)
        self.assertEqual(frames, [])

    def test_auto_frame_width(self):
        """When source_frame_width=0, width is inferred from sheet."""
        frames = load_sheet(
            self.sheet_path, self.frame_count, 16, 24,
            0, self.frame_h,
        )
        self.assertEqual(len(frames), self.frame_count)

    def test_frame_count_exceeding_sheet_truncates(self):
        """Requesting more frames than fit should return fewer frames."""
        frames = load_sheet(
            self.sheet_path, self.frame_count + 4, 16, 24,
            self.frame_w, self.frame_h,
        )
        self.assertEqual(len(frames), self.frame_count)


class TestHelmetStateMachine(unittest.TestCase):
    """Helmet overlay transitions through all states correctly."""

    def setUp(self):
        """Create a HelmetOverlay with no real sprites."""
        # Use a nonexistent directory — all sprites will be missing,
        # which is fine for state machine testing
        self.helmet = HelmetOverlay("/nonexistent/sprites/")

    def test_starts_off(self):
        self.assertEqual(self.helmet.state, HelmetState.OFF)

    def test_request_on_transitions_to_activating(self):
        self.helmet.request_on()
        self.assertEqual(self.helmet.state, HelmetState.ACTIVATING)

    def test_activating_reaches_on(self):
        """After enough updates, ACTIVATING should reach ON."""
        self.helmet.request_on()
        # Run enough frames to complete the animation
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        self.assertEqual(self.helmet.state, HelmetState.ON)

    def test_request_off_from_on(self):
        # Get to ON state
        self.helmet.request_on()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        self.assertEqual(self.helmet.state, HelmetState.ON)
        # Now request off
        self.helmet.request_off()
        self.assertEqual(self.helmet.state, HelmetState.DEACTIVATING)

    def test_deactivating_reaches_off(self):
        """Full cycle: OFF -> ACTIVATING -> ON -> DEACTIVATING -> OFF."""
        self.helmet.request_on()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        self.helmet.request_off()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        self.assertEqual(self.helmet.state, HelmetState.OFF)

    def test_request_on_when_already_on_is_noop(self):
        self.helmet.request_on()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        self.helmet.request_on()  # Should be no-op
        self.assertEqual(self.helmet.state, HelmetState.ON)

    def test_request_off_when_already_off_is_noop(self):
        self.helmet.request_off()  # Should be no-op
        self.assertEqual(self.helmet.state, HelmetState.OFF)

    def test_reverse_mid_activation(self):
        """Requesting off during ACTIVATING should reverse to DEACTIVATING."""
        self.helmet.request_on()
        self.helmet.update(1.0 / C.HELMET_ANIM_FPS)  # advance 1 frame
        self.helmet.request_off()
        self.assertEqual(self.helmet.state, HelmetState.DEACTIVATING)

    def test_reverse_mid_deactivation(self):
        """Requesting on during DEACTIVATING should reverse to ACTIVATING."""
        # Get to ON
        self.helmet.request_on()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        # Start deactivating
        self.helmet.request_off()
        self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        # Reverse
        self.helmet.request_on()
        self.assertEqual(self.helmet.state, HelmetState.ACTIVATING)

    def test_off_state_returns_no_frame(self):
        self.assertIsNone(self.helmet.get_frame())

    def test_on_state_update_is_stable(self):
        """ON state should not change after many updates."""
        self.helmet.request_on()
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            self.helmet.update(1.0 / C.HELMET_ANIM_FPS)
        for _ in range(100):
            self.helmet.update(1.0 / 60)
        self.assertEqual(self.helmet.state, HelmetState.ON)


class TestHelmetOverlayDraw(unittest.TestCase):
    """Helmet overlay draws placeholder when no sprites are loaded."""

    def setUp(self):
        self.helmet = HelmetOverlay("/nonexistent/sprites/")
        self.surface = pygame.Surface((200, 200))

    def test_draw_off_does_not_draw(self):
        """OFF state should not modify the surface."""
        self.surface.fill((0, 0, 0))
        self.helmet.draw(self.surface, 100, 100, True, (0, 1))
        # Centre should still be black
        color = self.surface.get_at((100, 100))
        self.assertEqual((color.r, color.g, color.b), (0, 0, 0))

    def test_draw_activating_draws_placeholder(self):
        """ACTIVATING state draws a placeholder rectangle at head position."""
        self.surface.fill((0, 0, 0))
        self.helmet.request_on()
        self.helmet.draw(self.surface, 100, 100, True, (0, 1))
        # Head position for gravity DOWN is above centre
        hx, hy = HelmetOverlay.head_position(100, 100, (0, 1))
        color = self.surface.get_at((int(hx), int(hy)))
        self.assertNotEqual((color.r, color.g, color.b), (0, 0, 0))

    def test_draw_with_facing_left_does_not_crash(self):
        """Drawing with facing_right=False should not crash."""
        self.helmet.request_on()
        self.helmet.draw(self.surface, 100, 100, False, (0, 1))

    def test_draw_with_all_gravity_dirs(self):
        """Drawing in all gravity orientations should not crash."""
        self.helmet.request_on()
        for gdir in [(0, 1), (0, -1), (-1, 0), (1, 0)]:
            self.helmet.draw(self.surface, 100, 100, True, gdir)


class TestPlayerAnimatorHelmetIntegration(unittest.TestCase):
    """PlayerAnimator has a helmet overlay that draws without crashing."""

    def test_animator_has_helmet(self):
        animator = PlayerAnimator()
        self.assertIsInstance(animator.helmet, HelmetOverlay)

    def test_draw_with_helmet_activating(self):
        """Drawing with helmet activating should not crash."""
        animator = PlayerAnimator()
        animator.helmet.request_on()
        surface = pygame.Surface((200, 200))
        animator.draw(surface, 50, 50, PlayerState.IDLE, True, (0, 1))

    def test_helmet_updates_with_animator(self):
        """Helmet update is called through animator.update."""
        animator = PlayerAnimator()
        animator.helmet.request_on()
        self.assertEqual(animator.helmet.state, HelmetState.ACTIVATING)
        for _ in range(C.HELMET_ACTIVATE_FRAMES * 2):
            animator.update(1.0 / C.HELMET_ANIM_FPS, PlayerState.IDLE)
        self.assertEqual(animator.helmet.state, HelmetState.ON)


class TestNewPlayerStates(unittest.TestCase):
    """New player animation states exist and have fallback colors."""

    def test_jump_anticipation_state_exists(self):
        self.assertIsNotNone(PlayerState.JUMP_ANTICIPATION)

    def test_land_state_exists(self):
        self.assertIsNotNone(PlayerState.LAND)

    def test_fallback_drawn_for_jump_anticipation(self):
        animator = PlayerAnimator()
        surface = pygame.Surface((200, 200))
        surface.fill((0, 0, 0))
        animator.draw(surface, 10, 10, PlayerState.JUMP_ANTICIPATION, True, (0, 1))
        cx = 10 + C.PLAYER_SPRITE_WIDTH // 2
        cy = 10 + C.PLAYER_SPRITE_HEIGHT // 2
        color = surface.get_at((cx, cy))
        self.assertNotEqual((color.r, color.g, color.b), (0, 0, 0))

    def test_fallback_drawn_for_land(self):
        animator = PlayerAnimator()
        surface = pygame.Surface((200, 200))
        surface.fill((0, 0, 0))
        animator.draw(surface, 10, 10, PlayerState.LAND, True, (0, 1))
        cx = 10 + C.PLAYER_SPRITE_WIDTH // 2
        cy = 10 + C.PLAYER_SPRITE_HEIGHT // 2
        color = surface.get_at((cx, cy))
        self.assertNotEqual((color.r, color.g, color.b), (0, 0, 0))


class TestSpriteSheetConstants(unittest.TestCase):
    """All sprite sheet constants are defined correctly."""

    def test_source_frame_dimensions(self):
        self.assertEqual(C.SPRITE_SHEET_FRAME_WIDTH, 256)
        self.assertEqual(C.SPRITE_SHEET_FRAME_HEIGHT, 384)

    def test_jump_sheet_frame_count(self):
        self.assertEqual(C.JUMP_SHEET_FRAMES, 8)

    def test_jump_frame_indices_sequential(self):
        indices = [
            C.JUMP_SHEET_ANTICIPATION,
            C.JUMP_SHEET_LAUNCH,
            C.JUMP_SHEET_RISING_FAST,
            C.JUMP_SHEET_RISING_SLOW,
            C.JUMP_SHEET_PEAK,
            C.JUMP_SHEET_FALLING_SLOW,
            C.JUMP_SHEET_FALLING_FAST,
            C.JUMP_SHEET_LAND_IMPACT,
        ]
        self.assertEqual(indices, list(range(8)))

    def test_helmet_constants_exist(self):
        self.assertIsInstance(C.HELMET_HEAD_OFFSET_X, int)
        self.assertIsInstance(C.HELMET_HEAD_OFFSET_Y, int)
        self.assertEqual(C.HELMET_ACTIVATE_FRAMES, 5)
        self.assertGreater(C.HELMET_ANIM_FPS, 0)


class TestHelmetHeadPosition(unittest.TestCase):
    """Head position calculation places helmet in correct quadrant per gravity."""

    def test_gravity_down_head_in_top_quarter(self):
        """Gravity DOWN: head is above sprite centre (top quarter)."""
        cx, cy = 100.0, 100.0
        hx, hy = HelmetOverlay.head_position(cx, cy, (0, 1))
        # Head should be above centre
        self.assertLess(hy, cy)
        # Head should be in the top quarter of the sprite
        top_edge = cy - C.PLAYER_SPRITE_HEIGHT / 2
        quarter_line = cy - C.PLAYER_SPRITE_HEIGHT / 4
        self.assertGreaterEqual(hy, top_edge)
        self.assertLessEqual(hy, quarter_line)
        # Horizontal position should be near centre
        self.assertAlmostEqual(hx, cx + C.HELMET_HEAD_OFFSET_X, delta=1)

    def test_gravity_up_head_in_bottom_quarter(self):
        """Gravity UP: head is below sprite centre (bottom quarter)."""
        cx, cy = 100.0, 100.0
        hx, hy = HelmetOverlay.head_position(cx, cy, (0, -1))
        # Head should be below centre
        self.assertGreater(hy, cy)
        # Head should be in the bottom quarter of the sprite
        bottom_edge = cy + C.PLAYER_SPRITE_HEIGHT / 2
        quarter_line = cy + C.PLAYER_SPRITE_HEIGHT / 4
        self.assertLessEqual(hy, bottom_edge)
        self.assertGreaterEqual(hy, quarter_line)

    def test_gravity_left_head_in_right_quarter(self):
        """Gravity LEFT: head is to the right of sprite centre."""
        cx, cy = 100.0, 100.0
        hx, hy = HelmetOverlay.head_position(cx, cy, (-1, 0))
        # Head should be to the right of centre
        self.assertGreater(hx, cx)
        # Vertical position should be near centre
        self.assertAlmostEqual(hy, cy + C.HELMET_HEAD_OFFSET_Y, delta=1)

    def test_gravity_right_head_in_left_quarter(self):
        """Gravity RIGHT: head is to the left of sprite centre."""
        cx, cy = 100.0, 100.0
        hx, hy = HelmetOverlay.head_position(cx, cy, (1, 0))
        # Head should be to the left of centre
        self.assertLess(hx, cx)
        # Vertical position should be near centre
        self.assertAlmostEqual(hy, cy + C.HELMET_HEAD_OFFSET_Y, delta=1)

    def test_head_distance_matches_constant(self):
        """Head distance from centre should match HELMET_HEAD_DISTANCE."""
        cx, cy = 100.0, 100.0
        expected_dist = C.HELMET_HEAD_DISTANCE * C.PLAYER_SPRITE_HEIGHT
        # Test gravity DOWN — head offset is purely vertical
        hx, hy = HelmetOverlay.head_position(cx, cy, (0, 1))
        actual_dist = cy - hy  # head is above, so cy > hy
        self.assertAlmostEqual(actual_dist, expected_dist, delta=1)

    def test_debug_dot_drawn_when_debug_true(self):
        """Debug cyan dot should appear at head position."""
        helmet = HelmetOverlay("/nonexistent/sprites/")
        surface = pygame.Surface((200, 200))
        surface.fill((0, 0, 0))
        # Even when OFF, debug dot should draw
        helmet.draw(surface, 100, 100, True, (0, 1), debug=True)
        hx, hy = HelmetOverlay.head_position(100, 100, (0, 1))
        color = surface.get_at((int(hx), int(hy)))
        # Cyan = (0, 255, 255)
        self.assertEqual((color.r, color.g, color.b), (0, 255, 255))

    def test_no_debug_dot_when_debug_false(self):
        """No debug dot when debug is False and helmet is OFF."""
        helmet = HelmetOverlay("/nonexistent/sprites/")
        surface = pygame.Surface((200, 200))
        surface.fill((0, 0, 0))
        helmet.draw(surface, 100, 100, True, (0, 1), debug=False)
        hx, hy = HelmetOverlay.head_position(100, 100, (0, 1))
        color = surface.get_at((int(hx), int(hy)))
        self.assertEqual((color.r, color.g, color.b), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
