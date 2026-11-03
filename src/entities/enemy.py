"""Temporal Echo — M3 patrol enemy placeholder.

Moves horizontally between two bounds. Freezes when time_scale=0 (Time Dilation).
No health, no combat yet — pure patrol rect until the entity system is built in M3.
"""
from __future__ import annotations

import pygame

from constants import TEMPORAL_ECHO_COLOR, TEMPORAL_ECHO_H, TEMPORAL_ECHO_W


class TemporalEcho:
    """Placeholder patrol enemy — colored rect that oscillates, stops on Time Dilation."""

    def __init__(
        self,
        px: float,
        py: float,
        min_x: float,
        max_x: float,
        speed: float,
        w: int = TEMPORAL_ECHO_W,
        h: int = TEMPORAL_ECHO_H,
    ) -> None:
        """Create at centre position (px, py) with horizontal patrol bounds."""
        self.px = px
        self.py = py
        self.min_x = min_x
        self.max_x = max_x
        self.speed = speed
        self.w = w
        self.h = h
        self.direction: int = 1
        self._start_px: float = px
        self.frozen_timer: float = 0.0  # seconds remaining of Hawking Emitter freeze

    def update(
        self,
        time_scale: float = 1.0,
        dt: float = 0.0,
        player_px: float = 0.0,
        player_py: float = 0.0,
        gravity_dir: tuple = (0, 1),
    ) -> None:
        """Move one step; time_scale=0 or frozen_timer>0 freezes the enemy."""
        if self.frozen_timer > 0.0:
            self.frozen_timer = max(0.0, self.frozen_timer - dt)
            return
        self.px += self.speed * self.direction * time_scale
        if self.px >= self.max_x:
            self.px = self.max_x
            self.direction = -1
        elif self.px <= self.min_x:
            self.px = self.min_x
            self.direction = 1

    def on_gravity_rotate(self) -> None:
        """No-op — gravity rotation has no special effect on the Temporal Echo."""

    def reset(self) -> None:
        """Return to spawn position and initial direction."""
        self.px = self._start_px
        self.direction = 1
        self.frozen_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        """Current axis-aligned bounding rect (computed from centre position)."""
        return pygame.Rect(
            int(self.px - self.w / 2),
            int(self.py - self.h / 2),
            self.w,
            self.h,
        )

    def draw(self, surface: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw enemy rect to surface, shifted by camera offset."""
        ox, oy = offset
        pygame.draw.rect(surface, TEMPORAL_ECHO_COLOR, self.rect.move(ox, oy))
