"""Small timed feel effects composed by Feel (TA-6): hitstop, sprite flash, squash.

Each class owns one effect's timer and envelope and nothing else. None of them
know about the global intensity multiplier — Feel applies that, so the scaling
lives in one place.
"""
from __future__ import annotations

import math

import constants as C


class Hitstop:
    """Freezes simulation time for a short duration (classic impact pause)."""

    def __init__(self) -> None:
        """Start unfrozen."""
        self.remaining: float = 0.0

    def trigger(self, duration: float) -> None:
        """Freeze for `duration` seconds; overlapping calls keep the longest, never sum."""
        duration = min(max(duration, 0.0), C.HITSTOP_MAX)
        self.remaining = max(self.remaining, duration)

    def consume(self, frame_dt: float) -> float:
        """Advance real time by frame_dt; return how much simulation time passes.

        Returns 0 while frozen. If the freeze ends part-way through the frame,
        the leftover time is returned so physics resumes without a hiccup.
        """
        if self.remaining <= 0.0:
            return frame_dt
        if frame_dt <= self.remaining:
            self.remaining -= frame_dt
            return 0.0
        leftover = frame_dt - self.remaining
        self.remaining = 0.0
        return leftover

    @property
    def active(self) -> bool:
        """True while simulation time is frozen."""
        return self.remaining > 0.0


class SpriteFlash:
    """A short full-sprite colour flash that fades linearly."""

    def __init__(self) -> None:
        """Start with no flash."""
        self.color: tuple[float, float, float] = C.HIT_FLASH_COLOR
        self.duration: float = 0.0
        self.remaining: float = 0.0

    def trigger(self, color: tuple[float, float, float], duration: float) -> None:
        """Start a flash; a zero/negative duration is a no-op."""
        if duration <= 0.0:
            return
        self.color = color
        self.duration = duration
        self.remaining = duration

    def update(self, dt: float) -> None:
        """Fade the flash."""
        self.remaining = max(0.0, self.remaining - dt)

    def amount(self) -> float:
        """Current mix toward the flash colour, 0 → SPRITE_FLASH_MAX."""
        if self.remaining <= 0.0:
            return 0.0
        return C.SPRITE_FLASH_MAX * (self.remaining / self.duration)


class Squash:
    """Squash (positive) or stretch (negative) along the gravity axis, springing back."""

    def __init__(self) -> None:
        """Start at rest (scale 1)."""
        self.amount: float = 0.0
        self.remaining: float = 0.0

    def trigger(self, amount: float) -> None:
        """Start a squash/stretch of `amount`, clamped to ±SQUASH_MAX."""
        self.amount = min(max(amount, -C.SQUASH_MAX), C.SQUASH_MAX)
        self.remaining = C.SQUASH_DURATION

    def update(self, dt: float) -> None:
        """Spring back toward rest."""
        self.remaining = max(0.0, self.remaining - dt)

    def current(self) -> float:
        """Current signed amount, easing out to 0 (quadratic)."""
        t = self.remaining / C.SQUASH_DURATION
        return self.amount * t * t


def squash_scale(amount: float) -> tuple[float, float]:
    """(along-gravity scale, across-gravity scale) for a signed squash amount.

    Partial area compensation: across = 1 / sqrt(along), so area = sqrt(along).
    Full preservation (1 / along) bulges 1.43× wide on a hard landing — too
    cartoony for the game's sleek tone; this gives ~1.2×.
    """
    along = 1.0 - amount
    return along, 1.0 / math.sqrt(along)
