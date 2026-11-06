"""Camera system for The Fold.

Smooth follow with dead zone, level bounds clamping, gravity rotation
re-centre, screen shake, and zoom. All rendering is offset by the
camera — physics stays in world space.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import constants
from constants import (
    CAMERA_DEAD_ZONE_X,
    CAMERA_DEAD_ZONE_Y,
    CAMERA_FOLLOW_SPEED,
    CAMERA_RECENTRE_DURATION,
    CAMERA_RECENTRE_SPEED,
    CAMERA_SHAKE_FREQS_HZ,
    CAMERA_ZOOM_SPEED,
    ROTATION_ZOOM_HOLD_DUR,
    ROTATION_ZOOM_IN_DUR,
    ROTATION_ZOOM_OUT_DUR,
    ROTATION_ZOOM_PEAK,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


@dataclass
class _ShakeInstance:
    """A single active screen shake with its own random noise phases."""

    intensity: float
    remaining: float
    duration: float
    phases: tuple[float, ...] = field(
        default_factory=lambda: tuple(random.uniform(0.0, 2.0 * math.pi) for _ in range(4)))


def _smooth_noise(t: float, phases: tuple[float, ...], offset: int) -> float:
    """Smooth pseudo-random signal in [-1, 1] sampled at time t (two blended sines).

    Being a function of time (not a fresh random value per frame) makes shake
    look the same at 30, 60 or 120 fps and read as shake rather than jitter.
    """
    f1, f2 = CAMERA_SHAKE_FREQS_HZ
    return (0.6 * math.sin(2.0 * math.pi * f1 * t + phases[offset])
            + 0.4 * math.sin(2.0 * math.pi * f2 * t + phases[offset + 1]))


def _beyond_dead_zone(delta: float, dead_zone: float) -> float:
    """How far `delta` extends past ±dead_zone (0 inside). Continuous at the edge."""
    if delta > dead_zone:
        return delta - dead_zone
    if delta < -dead_zone:
        return delta + dead_zone
    return 0.0


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

        # Directional punch (hard landing feedback)
        self._punch_x0: float = 0.0   # initial displacement
        self._punch_y0: float = 0.0
        self._punch_x: float = 0.0    # current displacement
        self._punch_y: float = 0.0
        self._punch_remaining: float = 0.0
        self._punch_duration: float = 1.0

        # Zoom
        self._zoom: float = 1.0
        self._target_zoom: float = 1.0

        # Rotation cinematic
        self._cinematic_active: bool = False
        self._cinematic_timer: float = 0.0

        # Gravity rotation re-centre
        self._recentre_timer: float = 0.0

        # Running time for smooth shake noise
        self._time: float = 0.0

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
        self._update_punch(dt)
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
        """Ease toward the target, frame-rate independently, through a window dead zone.

        The camera chases only the part of the offset beyond the dead zone, so
        following starts from zero speed at the edge (no jolt). During a
        post-rotation re-centre the dead zone is ignored so the player is truly
        centred. 1 − e^(−speed·dt) gives the same path at any frame rate.
        """
        recentring = self._recentre_timer > 0
        dz_x = 0.0 if recentring else CAMERA_DEAD_ZONE_X
        dz_y = 0.0 if recentring else CAMERA_DEAD_ZONE_Y
        k = 1.0 - math.exp(-speed * dt)
        self.x += _beyond_dead_zone(target_x - self.x, dz_x) * k
        self.y += _beyond_dead_zone(target_y - self.y, dz_y) * k

    # --- Gravity Rotation ---

    def on_gravity_rotate(self) -> None:
        """Trigger smooth re-centre after a gravity rotation."""
        self._recentre_timer = CAMERA_RECENTRE_DURATION

    def _tick_recentre(self, dt: float) -> None:
        """Count down the re-centre timer."""
        if self._recentre_timer > 0:
            self._recentre_timer = max(0.0, self._recentre_timer - dt)

    # --- Directional Punch ---

    def punch(self, dx: float, dy: float, duration: float) -> None:
        """Apply a directional camera jolt that decays linearly to zero over duration seconds."""
        if not constants.SCREEN_SHAKE_ENABLED:
            return
        self._punch_x0 = dx
        self._punch_y0 = dy
        self._punch_x = dx
        self._punch_y = dy
        self._punch_remaining = duration
        self._punch_duration = max(duration, 0.001)

    def _update_punch(self, dt: float) -> None:
        """Linearly decay the punch offset toward zero."""
        if self._punch_remaining <= 0.0:
            self._punch_x = self._punch_y = 0.0
            return
        self._punch_remaining = max(0.0, self._punch_remaining - dt)
        t = self._punch_remaining / self._punch_duration  # 1.0→0.0
        self._punch_x = self._punch_x0 * t
        self._punch_y = self._punch_y0 * t

    # --- Screen Shake ---

    def shake(self, intensity: float, duration: float) -> None:
        """Add a screen shake that decays over duration. Stacks additively."""
        if not constants.SCREEN_SHAKE_ENABLED:
            return
        self._shakes.append(_ShakeInstance(
            intensity=intensity,
            remaining=duration,
            duration=duration,
        ))

    def _update_shake(self, dt: float) -> None:
        """Tick all active shakes, compute combined offset from smooth noise."""
        self._time += dt
        ox, oy = 0.0, 0.0
        alive: list[_ShakeInstance] = []
        for s in self._shakes:
            s.remaining -= dt
            if s.remaining > 0:
                mag = s.intensity * (s.remaining / s.duration)  # linear 1→0 decay
                ox += mag * _smooth_noise(self._time, s.phases, 0)
                oy += mag * _smooth_noise(self._time, s.phases, 2)
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

    def start_rotation_cinematic(self) -> None:
        """Begin zoom-in → hold → zoom-out sequence around a gravity rotation."""
        self._cinematic_timer = 0.0
        self._cinematic_active = True

    def _update_zoom(self, dt: float) -> None:
        """Drive cinematic zoom sequence; otherwise lerp toward target."""
        if self._cinematic_active:
            self._cinematic_timer += dt
            _total = ROTATION_ZOOM_IN_DUR + ROTATION_ZOOM_HOLD_DUR + ROTATION_ZOOM_OUT_DUR
            if self._cinematic_timer < ROTATION_ZOOM_IN_DUR:
                t = self._cinematic_timer / ROTATION_ZOOM_IN_DUR
                self._zoom = 1.0 + (ROTATION_ZOOM_PEAK - 1.0) * (1.0 - (1.0 - t) ** 2)
            elif self._cinematic_timer < ROTATION_ZOOM_IN_DUR + ROTATION_ZOOM_HOLD_DUR:
                self._zoom = ROTATION_ZOOM_PEAK
            elif self._cinematic_timer < _total:
                t = (self._cinematic_timer - ROTATION_ZOOM_IN_DUR - ROTATION_ZOOM_HOLD_DUR) / ROTATION_ZOOM_OUT_DUR
                self._zoom = ROTATION_ZOOM_PEAK + (1.0 - ROTATION_ZOOM_PEAK) * (t * t)
            else:
                self._zoom = 1.0
                self._cinematic_active = False
            return
        diff = self._target_zoom - self._zoom
        self._zoom += diff * (1.0 - math.exp(-CAMERA_ZOOM_SPEED * dt))  # frame-rate independent

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
            -self.x + self.screen_w / 2 + self._shake_offset_x + self._punch_x,
            -self.y + self.screen_h / 2 + self._shake_offset_y + self._punch_y,
        )
