"""The Anchored — M5e enemy.

Broken-timeline entity. Wanders erratically; periodically stutters in a
random direction at high speed. Countered by Time Dilation (time_scale=0
freezes it). Gravity rotation has no special effect.

Unlike the Fold Predator, it does not chase. The threat is unpredictability.
"""
from __future__ import annotations

import random
from enum import Enum, auto

import pygame

from constants import (
    ANCHORED_COLOR,
    ANCHORED_H,
    ANCHORED_SPEED,
    ANCHORED_STUTTER_COLOR,
    ANCHORED_STUTTER_DURATION,
    ANCHORED_STUTTER_INTERVAL,
    ANCHORED_STUTTER_SPEED_MULT,
    ANCHORED_W,
    ANCHORED_WANDER_CHANGE_INTERVAL,
)


class _State(Enum):
    WANDER = auto()
    STUTTER = auto()


class TheAnchored:
    """Broken-timeline enemy. Wanders and stutters; frozen by Time Dilation."""

    def __init__(
        self,
        px: float,
        py: float,
        level_min: float,
        level_max: float,
        w: int = ANCHORED_W,
        h: int = ANCHORED_H,
        speed: float = ANCHORED_SPEED,
        seed: int = 0,
    ) -> None:
        """Create at centre position (px, py) with lateral bounds level_min/max."""
        self.px = px
        self.py = py
        self._start_px = px
        self._start_py = py
        self.level_min = level_min
        self.level_max = level_max
        self.w = w
        self.h = h
        self.speed = speed
        self._rng = random.Random(seed)

        self._state: _State = _State.WANDER
        self._direction: int = self._rng.choice([-1, 1])
        self._wander_timer: float = self._rng.uniform(0.5, ANCHORED_WANDER_CHANGE_INTERVAL)
        self._stutter_cooldown: float = ANCHORED_STUTTER_INTERVAL
        self._stutter_timer: float = 0.0
        self._stutter_dir: int = 1
        self.frozen_timer: float = 0.0  # Hawking Emitter compatibility

    # --- Public API ---

    def update(
        self,
        time_scale: float = 1.0,
        dt: float = 0.0,
        player_px: float = 0.0,
        player_py: float = 0.0,
        gravity_dir: tuple = (0, 1),
    ) -> None:
        """Advance AI by one physics step. time_scale=0 freezes movement completely."""
        if self.frozen_timer > 0.0:
            self.frozen_timer = max(0.0, self.frozen_timer - dt)
            return

        # All movement and timers scale with time — time_scale=0 freezes everything
        scaled_dt = dt * time_scale

        if self._state == _State.STUTTER:
            self._stutter_timer -= scaled_dt
            if self._stutter_timer <= 0.0:
                self._state = _State.WANDER
                self._stutter_cooldown = ANCHORED_STUTTER_INTERVAL
                self._wander_timer = self._rng.uniform(0.5, ANCHORED_WANDER_CHANGE_INTERVAL)
        else:
            # WANDER: tick direction-change timer and stutter cooldown
            self._wander_timer -= scaled_dt
            if self._wander_timer <= 0.0:
                self._direction = self._rng.choice([-1, 1])
                self._wander_timer = self._rng.uniform(0.5, ANCHORED_WANDER_CHANGE_INTERVAL)

            self._stutter_cooldown -= scaled_dt
            if self._stutter_cooldown <= 0.0:
                self._state = _State.STUTTER
                self._stutter_timer = ANCHORED_STUTTER_DURATION
                self._stutter_dir = self._rng.choice([-1, 1])

        # Move
        if self._state == _State.STUTTER:
            move = self.speed * ANCHORED_STUTTER_SPEED_MULT * self._stutter_dir * time_scale
        else:
            move = self.speed * self._direction * time_scale

        self._move_lateral(move, gravity_dir)

        # Clamp to level bounds
        gx, gy = gravity_dir
        if gy != 0:
            self.px = max(self.level_min, min(self.level_max, self.px))
            if self.px <= self.level_min or self.px >= self.level_max:
                self._direction = -self._direction
        else:
            self.py = max(self.level_min, min(self.level_max, self.py))
            if self.py <= self.level_min or self.py >= self.level_max:
                self._direction = -self._direction

    def on_gravity_rotate(self) -> None:
        """No-op — gravity rotation has no special effect on The Anchored."""

    def reset(self) -> None:
        """Return to spawn state."""
        self.px = self._start_px
        self.py = self._start_py
        self._state = _State.WANDER
        self._direction = self._rng.choice([-1, 1])
        self._wander_timer = self._rng.uniform(0.5, ANCHORED_WANDER_CHANGE_INTERVAL)
        self._stutter_cooldown = ANCHORED_STUTTER_INTERVAL
        self._stutter_timer = 0.0
        self.frozen_timer = 0.0

    @property
    def rect(self) -> pygame.Rect:
        """Current axis-aligned bounding rect."""
        return pygame.Rect(
            int(self.px - self.w / 2),
            int(self.py - self.h / 2),
            self.w,
            self.h,
        )

    def draw(self, surface: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw enemy rect, shifted by camera offset."""
        ox, oy = offset
        color = ANCHORED_STUTTER_COLOR if self._state == _State.STUTTER else ANCHORED_COLOR
        pygame.draw.rect(surface, color, self.rect.move(ox, oy))

    @property
    def is_stuttering(self) -> bool:
        """True during a stutter burst."""
        return self._state == _State.STUTTER

    # --- Internal ---

    def _move_lateral(self, amount: float, gravity_dir: tuple) -> None:
        """Move along the lateral axis for the given gravity direction."""
        gx, gy = gravity_dir
        if gy != 0:  # vertical gravity — lateral is X
            self.px += amount
        else:         # horizontal gravity — lateral is Y
            self.py += amount
