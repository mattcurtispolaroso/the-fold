"""Feel framework (TA-5, TA-6) — the one API gameplay code uses for game feel.

Fold ripples, gravity-flip bend, hitstop, sprite flash, squash/stretch and
camera shake/punch, all scaled by a single intensity (reduced in
accessibility mode). No GL code lives here, so it runs headless and in the
software renderer; the GPU path draws the visual parts (distortion pass,
sprite flash/squash), the software path gets hitstop, shake and punch.

Coordinates: effects are queued in world pixels; distortion_params() converts
them to GL framebuffer pixels (origin bottom-left, Y up) for the shader.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import constants as C
from src.rendering.gpu.feel_effects import Hitstop, SpriteFlash, Squash, squash_scale

if TYPE_CHECKING:
    from src.rendering.camera import Camera


@dataclass
class Ripple:
    """One expanding Fold ripple anchored at a world position."""

    x: float
    y: float
    strength: float
    duration: float
    age: float = 0.0

    @property
    def progress(self) -> float:
        """Fraction of the ripple's life elapsed, 0 → 1."""
        return min(self.age / self.duration, 1.0)


@dataclass
class DistortionParams:
    """Everything the distortion shader needs for one frame."""

    ripples: list[tuple[float, float, float, float]] = field(default_factory=list)  # cx, cy, radius, amp
    bend: tuple[float, float, float] = (0.0, -1.0, 0.0)  # GL direction x, y, amount px
    aberration: float = 0.0

    @property
    def active(self) -> bool:
        """True when any effect would visibly move pixels."""
        return bool(self.ripples) or self.bend[2] > C.EPSILON or self.aberration > C.EPSILON


def ripple_envelope(progress: float) -> tuple[float, float]:
    """Return (radius fraction, amplitude fraction): ring eases out while fading."""
    radius = 1.0 - (1.0 - progress) ** 2
    amplitude = (1.0 - progress) ** 2
    return radius, amplitude


def zoomed_screen_point(
    x: float, y: float,
    cam_offset: tuple[float, float],
    size: tuple[int, int],
    zoom: float,
) -> tuple[float, float]:
    """World point → screen pixels (Y down), including zoom about the screen centre."""
    cx, cy = size[0] / 2.0, size[1] / 2.0
    sx, sy = x + cam_offset[0], y + cam_offset[1]
    return (cx + (sx - cx) * zoom, cy + (sy - cy) * zoom)


def bend_envelope(progress: float) -> float:
    """Bend amount fraction: rises and returns to zero (sin arch)."""
    return math.sin(math.pi * min(max(progress, 0.0), 1.0))


class Feel:
    """Single entry point for game feel: screen distortion, hitstop, sprite flash,
    squash/stretch and camera shake/punch, all scaled by one intensity multiplier.

    `intensity` is FEEL_INTENSITY_DEFAULT, or FEEL_INTENSITY_REDUCED in
    reduced-effects (accessibility) mode. Pass a Camera to route shake, punch
    and the rotation zoom through here; without one those calls are no-ops,
    which keeps Feel fully usable headless.
    """

    def __init__(self, camera: Camera | None = None) -> None:
        """Start with no active effects, in the configured accessibility mode."""
        self._camera = camera
        self.reduced_effects: bool = C.ACCESSIBILITY_REDUCED_EFFECTS
        self.ripples: list[Ripple] = []
        self.bend_dir: tuple[int, int] = (0, 1)
        self.bend_age: float | None = None   # None = no bend in progress
        self._dilation_was_active: bool = False
        self._hitstop = Hitstop()
        self._flash = SpriteFlash()
        self._squash = Squash()

    # --- Intensity / accessibility ---

    @property
    def intensity(self) -> float:
        """Global multiplier on every feel effect."""
        return C.FEEL_INTENSITY_REDUCED if self.reduced_effects else C.FEEL_INTENSITY_DEFAULT

    def toggle_reduced_effects(self) -> bool:
        """Flip reduced-effects mode; return the new state."""
        self.reduced_effects = not self.reduced_effects
        return self.reduced_effects

    # --- Queueing effects ---

    def distortion(self, x: float, y: float, strength: float = 1.0,
                   dur: float = C.RIPPLE_DURATION) -> None:
        """Queue a Fold ripple at world (x, y). Zero/negative duration is a no-op."""
        if dur <= 0.0:
            return
        strength = min(max(strength, 0.0), C.DISTORTION_STRENGTH_MAX)
        if strength <= 0.0:
            return
        if len(self.ripples) >= C.DISTORTION_MAX_RIPPLES:
            self.ripples.pop(0)  # recycle the oldest
        self.ripples.append(Ripple(x, y, strength, dur))

    def gravity_bend(self, direction: tuple[int, int]) -> None:
        """Start (or restart) the frame bend toward the new gravity direction."""
        self.bend_dir = (int(direction[0]), int(direction[1]))
        self.bend_age = 0.0

    def hitstop(self, duration: float) -> None:
        """Freeze physics for `duration` × intensity seconds (see physics_time)."""
        self._hitstop.trigger(duration * self.intensity)

    def flash(self, color: tuple[float, float, float], duration: float) -> None:
        """Flash the player sprite toward `color`, fading over `duration`."""
        self._flash.trigger(color, duration)

    def squash(self, amount: float) -> None:
        """Squash (+) or stretch (−) the player along gravity, springing back."""
        self._squash.trigger(amount)

    def shake(self, intensity: float, duration: float) -> None:
        """Camera shake scaled by the feel intensity."""
        if self._camera is not None:
            self._camera.shake(intensity * self.intensity, duration)

    def punch(self, dx: float, dy: float, duration: float) -> None:
        """Directional camera punch scaled by the feel intensity."""
        if self._camera is not None:
            self._camera.punch(dx * self.intensity, dy * self.intensity, duration)

    def rotation_cinematic(self) -> None:
        """Start the rotation zoom; skipped entirely in reduced-effects mode."""
        if self._camera is not None and not self.reduced_effects:
            self._camera.start_rotation_cinematic()

    def track_dilation(self, is_active: bool, x: float, y: float) -> None:
        """On the frame Time Dilation switches on: ripple from (x, y) + amber flash."""
        if is_active and not self._dilation_was_active:
            self.distortion(x, y)
            self.flash(C.DILATION_FLASH_COLOR, C.DILATION_FLASH_DURATION)
        self._dilation_was_active = is_active

    # --- Per-frame ---

    def physics_time(self, frame_dt: float) -> float:
        """Simulation time to feed the physics accumulator this frame (0 during hitstop)."""
        return self._hitstop.consume(frame_dt)

    def update(self, dt: float) -> None:
        """Age every visual effect and drop the finished ones (real time, not hitstopped)."""
        for ripple in self.ripples:
            ripple.age += dt
        self.ripples = [r for r in self.ripples if r.age < r.duration]
        if self.bend_age is not None:
            self.bend_age += dt
            if self.bend_age >= C.BEND_DURATION:
                self.bend_age = None
        self._flash.update(dt)
        self._squash.update(dt)

    def reset(self) -> None:
        """Clear every effect (e.g. on level change)."""
        self.ripples.clear()
        self.bend_age = None
        self._hitstop = Hitstop()
        self._flash = SpriteFlash()
        self._squash = Squash()

    # --- Read by renderers ---

    @property
    def hitstop_active(self) -> bool:
        """True while physics is frozen."""
        return self._hitstop.active

    def sprite_flash(self) -> tuple[float, float, float, float]:
        """(r, g, b, amount) for the player sprite; amount is intensity-scaled."""
        return (*self._flash.color, self._flash.amount() * self.intensity)

    def sprite_scale(self) -> tuple[float, float]:
        """(along-gravity, across-gravity) scale for the player sprite."""
        return squash_scale(self._squash.current() * self.intensity)

    def screen_flash_scale(self) -> float:
        """Multiplier for the full-screen rotation/impact flash timers (alpha ∝ timer)."""
        return self.intensity

    def distortion_params(self, cam_offset: tuple[float, float],
                          size: tuple[int, int], zoom: float = 1.0) -> DistortionParams:
        """Convert active effects to shader parameters in GL framebuffer pixels.

        `zoom` is the camera zoom applied at composite time (scaled about the
        screen centre); ripple centres and radii follow it so they stay on target.
        Every amplitude is scaled by the feel intensity.
        """
        height = size[1]
        k = self.intensity
        params = DistortionParams()
        peak = 0.0
        for r in self.ripples:
            radius_frac, amp_frac = ripple_envelope(r.progress)
            amplitude = min(r.strength * C.RIPPLE_AMPLITUDE_PX * amp_frac, C.DISTORTION_MAX_OFFSET_PX)
            sx, sy = zoomed_screen_point(r.x, r.y, cam_offset, size, zoom)
            params.ripples.append((sx, height - sy,
                                   radius_frac * C.RIPPLE_MAX_RADIUS_PX * zoom, amplitude * k))
            peak = max(peak, min(r.strength, 1.0) * amp_frac)
        if self.bend_age is not None:
            amount = bend_envelope(self.bend_age / C.BEND_DURATION)
            gx, gy = self.bend_dir
            params.bend = (float(gx), float(-gy), amount * C.BEND_AMPLITUDE_PX * k)
            peak = max(peak, amount)
        params.aberration = peak * C.ABERRATION_MAX_PX * k
        return params
