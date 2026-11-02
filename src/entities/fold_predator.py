"""Fold Predator — M5b enemy.

Multi-temporal hunter countered by gravity rotation. Four states:
  PATROL  — oscillates within level bounds
  CHASE   — moves toward player when within lateral range
  PHASE   — burst of speed (multi-temporal closing move), fires periodically during chase
  STUNNED — gravity rotation freezes it; resumes previous state after

Gravity-aware: tracks the player on the lateral axis relative to gravity direction,
so it works correctly in all four gravity orientations.
"""
from __future__ import annotations

from enum import Enum, auto

import pygame

from constants import (
    FOLD_PREDATOR_CHASE_RANGE,
    FOLD_PREDATOR_COLOR,
    FOLD_PREDATOR_H,
    FOLD_PREDATOR_PHASE_COLOR,
    FOLD_PREDATOR_PHASE_DURATION,
    FOLD_PREDATOR_PHASE_INTERVAL,
    FOLD_PREDATOR_PHASE_SPEED_MULT,
    FOLD_PREDATOR_SPEED,
    FOLD_PREDATOR_STUN_COLOR,
    FOLD_PREDATOR_STUN_DURATION,
    FOLD_PREDATOR_W,
)


class _State(Enum):
    PATROL = auto()
    CHASE = auto()
    PHASE = auto()
    STUNNED = auto()


def _lateral_distance(
    px: float, py: float, ex: float, ey: float, gravity_dir: tuple,
) -> float:
    """Return the signed lateral distance from enemy to player for the given gravity."""
    gx, gy = gravity_dir
    if gy != 0:  # vertical gravity (DOWN or UP) — lateral is X
        return px - ex
    else:         # horizontal gravity (LEFT or RIGHT) — lateral is Y
        return py - ey


class FoldPredator:
    """Multi-temporal hunter. Countered by gravity rotation."""

    def __init__(
        self,
        px: float,
        py: float,
        level_min: float,
        level_max: float,
        w: int = FOLD_PREDATOR_W,
        h: int = FOLD_PREDATOR_H,
        speed: float = FOLD_PREDATOR_SPEED,
    ) -> None:
        """Create at centre position (px, py). level_min/max are lateral patrol bounds."""
        self.px = px
        self.py = py
        self._start_px = px
        self._start_py = py
        self.level_min = level_min
        self.level_max = level_max
        self.w = w
        self.h = h
        self.speed = speed

        self._state: _State = _State.PATROL
        self._pre_stun_state: _State = _State.PATROL
        self._direction: int = 1       # +1 or -1 along the lateral axis
        self._stun_timer: float = 0.0
        self._phase_cooldown: float = FOLD_PREDATOR_PHASE_INTERVAL
        self._phase_timer: float = 0.0
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
        """Advance AI by one physics step."""
        if self.frozen_timer > 0.0:
            self.frozen_timer = max(0.0, self.frozen_timer - dt)
            return

        if self._state == _State.STUNNED:
            self._stun_timer = max(0.0, self._stun_timer - dt)
            if self._stun_timer <= 0.0:
                self._state = self._pre_stun_state
            return

        lateral_dist = _lateral_distance(player_px, player_py, self.px, self.py, gravity_dir)

        # Transition: PATROL ↔ CHASE
        if self._state == _State.PATROL:
            if abs(lateral_dist) <= FOLD_PREDATOR_CHASE_RANGE:
                self._state = _State.CHASE
                self._phase_cooldown = FOLD_PREDATOR_PHASE_INTERVAL
        elif self._state in (_State.CHASE, _State.PHASE):
            if abs(lateral_dist) > FOLD_PREDATOR_CHASE_RANGE:
                self._state = _State.PATROL

        # Tick phase timers during CHASE
        if self._state == _State.CHASE:
            self._phase_cooldown = max(0.0, self._phase_cooldown - dt)
            if self._phase_cooldown <= 0.0:
                self._state = _State.PHASE
                self._phase_timer = FOLD_PREDATOR_PHASE_DURATION
                self._phase_cooldown = FOLD_PREDATOR_PHASE_INTERVAL

        if self._state == _State.PHASE:
            self._phase_timer = max(0.0, self._phase_timer - dt)
            if self._phase_timer <= 0.0:
                self._state = _State.CHASE

        # Move
        effective_speed = self.speed * time_scale
        if self._state == _State.PHASE:
            effective_speed *= FOLD_PREDATOR_PHASE_SPEED_MULT

        if self._state == _State.PATROL:
            self._move_lateral(effective_speed * self._direction, gravity_dir)
            # Bounce at bounds
            lat = self.px if gravity_dir[1] != 0 else self.py
            if lat >= self.level_max:
                self._direction = -1
            elif lat <= self.level_min:
                self._direction = 1
        elif self._state in (_State.CHASE, _State.PHASE):
            move = effective_speed if lateral_dist > 0 else -effective_speed
            self._move_lateral(move, gravity_dir)
            self._direction = 1 if lateral_dist > 0 else -1

    def on_gravity_rotate(self) -> None:
        """Stun the predator for FOLD_PREDATOR_STUN_DURATION. Any gravity rotation triggers this."""
        if self._state != _State.STUNNED:
            self._pre_stun_state = self._state
        self._state = _State.STUNNED
        self._stun_timer = FOLD_PREDATOR_STUN_DURATION

    def reset(self) -> None:
        """Return to spawn state."""
        self.px = self._start_px
        self.py = self._start_py
        self._state = _State.PATROL
        self._pre_stun_state = _State.PATROL
        self._direction = 1
        self._stun_timer = 0.0
        self._phase_cooldown = FOLD_PREDATOR_PHASE_INTERVAL
        self._phase_timer = 0.0
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
        if self._state == _State.STUNNED:
            color = FOLD_PREDATOR_STUN_COLOR
        elif self._state == _State.PHASE:
            color = FOLD_PREDATOR_PHASE_COLOR
        else:
            color = FOLD_PREDATOR_COLOR
        pygame.draw.rect(surface, color, self.rect.move(ox, oy))

    @property
    def is_stunned(self) -> bool:
        """True while the stun from gravity rotation is active."""
        return self._state == _State.STUNNED

    # --- Internal ---

    def _move_lateral(self, amount: float, gravity_dir: tuple) -> None:
        """Move along the lateral axis relative to gravity direction."""
        gx, gy = gravity_dir
        if gy != 0:  # vertical gravity — lateral is X
            self.px += amount
        else:         # horizontal gravity — lateral is Y
            self.py += amount
