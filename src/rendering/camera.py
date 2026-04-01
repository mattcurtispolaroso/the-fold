"""Camera system for The Fold.

Smooth follow with dead zone, level bounds clamping, gravity rotation
re-centre, screen shake, and zoom. All rendering is offset by the
camera — physics stays in world space.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from constants import (
    CAMERA_DEAD_ZONE_X,
    CAMERA_DEAD_ZONE_Y,
    CAMERA_FOLLOW_SPEED,
    CAMERA_RECENTRE_DURATION,
    CAMERA_RECENTRE_SPEED,
    CAMERA_ZOOM_SPEED,
    SCREEN_HEIGHT,
    SCREEN_SHAKE_ENABLED,
    SCREEN_WIDTH,
)


@dataclass
class _ShakeInstance:
    """A single active screen shake."""

    intensity: float
    remaining: float
    duration: float


class Camera:
    """2D camera with smooth follow, bounds, shake, and zoom."""

    def __init__(self, screen_w: int = SCREEN_WIDTH, screen_h: int = SCREEN_HEIGHT) -> None:
        """Initialise camera centred at origin."""
        self.x: float = 0.0
        self.y: float = 0.0
        self.screen_w: int = screen_w
        self.screen_h: int = screen_h

        # Bounds (None = unbounded)
        self._bound_left: float | None = None
        self._bound_top: float | None = None
        self._bound_right: float | None = None
        self._bound_bottom: float | None = None

        # Shake
        self._shakes: list[_ShakeInstance] = []
        self._shake_offset_x: float = 0.0
        self._shake_offset_y: float = 0.0

        # Zoom
        self._zoom: float = 1.0
        self._target_zoom: float = 1.0

        # Gravity rotation re-centre
        self._recentre_timer: float = 0.0

    # --- Bounds ---

    def set_bounds(
        self,
        level_width: int,
        level_height: int,
    ) -> None:
        """Set camera bounds from level dimensions."""
        self._bound_left = 0.0
        self._bound_top = 0.0
        self._bound_right = float(level_width)
        self._bound_bottom = float(level_height)

    def _clamp_to_bounds(self) -> None:
        """Clamp camera so the viewport stays inside level bounds."""
        if self._bound_left is None:
            return
        half_w = self.screen_w / (2.0 * self._zoom)
        half_h = self.screen_h / (2.0 * self._zoom)
        self.x = max(self._bound_left + half_w, min(self._bound_right - half_w, self.x))
        self.y = max(self._bound_top + half_h, min(self._bound_bottom - half_h, self.y))

    # --- Follow ---

    def update(self, target_x: float, target_y: float, dt: float) -> None:
        """Update camera position toward target with dead zone and lerp."""
        speed = self._current_follow_speed()
        self._follow(target_x, target_y, dt, speed)
        self._clamp_to_bounds()
        self._update_shake(dt)
        self._update_zoom(dt)
        self._tick_recentre(dt)

    def _current_follow_speed(self) -> float:
        """Return follow speed — boosted during gravity re-centre."""
        if self._recentre_timer > 0:
            return CAMERA_RECENTRE_SPEED
        return CAMERA_FOLLOW_SPEED

    def _follow(
        self, target_x: float, target_y: float, dt: float, speed: float,
    ) -> None:
        """Lerp toward target, respecting dead zone."""
        dx = target_x - self.x
        dy = target_y - self.y
        # Dead zone — only follow if outside threshold
        if abs(dx) > CAMERA_DEAD_ZONE_X:
            self.x += dx * min(speed * dt, 1.0)
        if abs(dy) > CAMERA_DEAD_ZONE_Y:
            self.y += dy * min(speed * dt, 1.0)

    # --- Gravity Rotation ---

    def on_gravity_rotate(self) -> None:
        """Trigger smooth re-centre after a gravity rotation."""
        self._recentre_timer = CAMERA_RECENTRE_DURATION

    def _tick_recentre(self, dt: float) -> None:
        """Count down the re-centre timer."""
        if self._recentre_timer > 0:
            self._recentre_timer = max(0.0, self._recentre_timer - dt)

    # --- Screen Shake ---

    def shake(self, intensity: float, duration: float) -> None:
        """Add a screen shake that decays over duration. Stacks additively."""
        if not SCREEN_SHAKE_ENABLED:
            return
        self._shakes.append(_ShakeInstance(
            intensity=intensity,
            remaining=duration,
            duration=duration,
        ))

    def _update_shake(self, dt: float) -> None:
        """Tick all active shakes, compute combined offset."""
        ox, oy = 0.0, 0.0
        alive: list[_ShakeInstance] = []
        for s in self._shakes:
            s.remaining -= dt
            if s.remaining > 0:
                t = s.remaining / s.duration  # 1→0 decay
                mag = s.intensity * t
                ox += random.uniform(-mag, mag)
                oy += random.uniform(-mag, mag)
                alive.append(s)
        self._shakes = alive
        self._shake_offset_x = ox
        self._shake_offset_y = oy

    # --- Zoom ---

    @property
    def zoom(self) -> float:
        """Current zoom level."""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        """Set target zoom (lerps toward it)."""
        self._target_zoom = max(0.1, value)

    def _update_zoom(self, dt: float) -> None:
        """Lerp current zoom toward target."""
        diff = self._target_zoom - self._zoom
        self._zoom += diff * min(CAMERA_ZOOM_SPEED * dt, 1.0)

    # --- Coordinate Transform ---

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert world coordinates to screen coordinates."""
        sx = (wx - self.x) * self._zoom + self.screen_w / 2 + self._shake_offset_x
        sy = (wy - self.y) * self._zoom + self.screen_h / 2 + self._shake_offset_y
        return sx, sy

    def world_rect_to_screen(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        """Convert a world-space rect to screen-space (x, y, w, h)."""
        sx, sy = self.world_to_screen(x, y)
        return sx, sy, w * self._zoom, h * self._zoom

    @property
    def offset(self) -> tuple[float, float]:
        """Screen offset for simple rendering (no zoom)."""
        return (
            -self.x + self.screen_w / 2 + self._shake_offset_x,
            -self.y + self.screen_h / 2 + self._shake_offset_y,
        )
