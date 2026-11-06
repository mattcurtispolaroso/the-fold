"""Feel framework, first slice (TA-5) — Fold ripples and the gravity-flip bend.

Gameplay code queues effects here; the post stack's distortion pass renders
them. No GL code lives in this module, so it runs headless and alongside the
software renderer (where its effects are simply never drawn). TA-6 extends it
with hitstop, sprite flash, squash/stretch and an accessibility multiplier.

Coordinates: effects are queued in world pixels; distortion_params() converts
them to GL framebuffer pixels (origin bottom-left, Y up) for the shader.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import constants as C


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


def bend_envelope(progress: float) -> float:
    """Bend amount fraction: rises and returns to zero (sin arch)."""
    return math.sin(math.pi * min(max(progress, 0.0), 1.0))


class Feel:
    """Holds active screen-space feel effects and ages them each frame."""

    def __init__(self) -> None:
        """Start with no active effects."""
        self.ripples: list[Ripple] = []
        self.bend_dir: tuple[int, int] = (0, 1)
        self.bend_age: float | None = None   # None = no bend in progress
        self._dilation_was_active: bool = False

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

    def track_dilation(self, is_active: bool, x: float, y: float) -> None:
        """Fire a ripple from (x, y) on the frame Time Dilation switches on."""
        if is_active and not self._dilation_was_active:
            self.distortion(x, y)
        self._dilation_was_active = is_active

    def update(self, dt: float) -> None:
        """Age every effect and drop the finished ones."""
        for ripple in self.ripples:
            ripple.age += dt
        self.ripples = [r for r in self.ripples if r.age < r.duration]
        if self.bend_age is not None:
            self.bend_age += dt
            if self.bend_age >= C.BEND_DURATION:
                self.bend_age = None

    def reset(self) -> None:
        """Clear every effect (e.g. on level change)."""
        self.ripples.clear()
        self.bend_age = None

    def distortion_params(self, cam_offset: tuple[float, float],
                          size: tuple[int, int]) -> DistortionParams:
        """Convert active effects to shader parameters in GL framebuffer pixels."""
        ox, oy = cam_offset
        height = size[1]
        params = DistortionParams()
        peak = 0.0
        for r in self.ripples:
            radius_frac, amp_frac = ripple_envelope(r.progress)
            amplitude = min(r.strength * C.RIPPLE_AMPLITUDE_PX * amp_frac, C.DISTORTION_MAX_OFFSET_PX)
            params.ripples.append((r.x + ox, height - (r.y + oy),
                                   radius_frac * C.RIPPLE_MAX_RADIUS_PX, amplitude))
            peak = max(peak, min(r.strength, 1.0) * amp_frac)
        if self.bend_age is not None:
            amount = bend_envelope(self.bend_age / C.BEND_DURATION)
            gx, gy = self.bend_dir
            params.bend = (float(gx), float(-gy), amount * C.BEND_AMPLITUDE_PX)
            peak = max(peak, amount)
        params.aberration = peak * C.ABERRATION_MAX_PX
        return params
