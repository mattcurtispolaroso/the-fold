"""Tests for the HUD rendering system."""
from __future__ import annotations

import os
import unittest

import tests.conftest  # noqa: F401


class _FakeHudPlayer:
    """Minimal player stub for draw_hud tests."""
    def __init__(self):
        self.anchor_integrity = 3
        self.chrono_reserve = 100.0
        self.goal_reached = False
        self.gravity_dir = (0, 1)


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
        p = _FakeHudPlayer()
        p.anchor_integrity = integrity
        p.chrono_reserve = chrono
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


if __name__ == "__main__":
    unittest.main()
