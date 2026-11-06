"""Render interpolation between fixed physics steps (Engine Session 2).

Physics runs at a fixed 60 Hz while frames arrive at the display rate with
jitter. Drawing the raw physics state shows a repeated position on frames with
no physics step and a jump on frames with two (measured: 4–15% of frames).
Instead we draw every moving thing at lerp(previous step, current step, alpha)
where alpha = physics_accumulator / PHYSICS_DT, the fraction of the next step
already elapsed. Physics itself is untouched and stays deterministic.

Moving platforms already keep `prev_rect` (their rect before the last step),
so only the player and enemies are recorded here.
"""
from __future__ import annotations

import math

import constants as C


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from a (t=0) to b (t=1)."""
    return a + (b - a) * t


class RenderInterpolator:
    """Remembers each entity's position at the start of the latest physics step."""

    def __init__(self) -> None:
        """Start with nothing recorded (everything draws at its current position)."""
        self._player_prev: tuple[float, float] | None = None
        self._enemy_prev: dict[int, tuple[float, float]] = {}

    def begin_step(self, player: object, enemies: list) -> None:
        """Call at the start of every physics step, before anything moves."""
        self._player_prev = (player.px, player.py)
        # Rebuilt each step: entries for despawned enemies disappear immediately,
        # so a recycled id() can never inherit a stale previous position.
        self._enemy_prev = {id(e): (e.px, e.py) for e in enemies}

    def snap(self) -> None:
        """Forget previous positions (teleport, respawn, level load): draw current state."""
        self._player_prev = None
        self._enemy_prev = {}

    def player_pos(self, player: object, alpha: float) -> tuple[float, float]:
        """Interpolated player centre; snaps if the last step was a teleport."""
        return self._lerp_pos(self._player_prev, player.px, player.py, alpha)

    def enemy_offset(self, enemy: object, alpha: float) -> tuple[float, float]:
        """(dx, dy) to add to the enemy's current rect to draw it interpolated."""
        x, y = self._lerp_pos(self._enemy_prev.get(id(enemy)), enemy.px, enemy.py, alpha)
        return x - enemy.px, y - enemy.py

    @staticmethod
    def platform_pos(platform: object, alpha: float) -> tuple[float, float]:
        """Interpolated top-left of a moving platform (prev_rect → rect)."""
        prev, cur = platform.prev_rect, platform.rect
        return lerp(prev.x, cur.x, alpha), lerp(prev.y, cur.y, alpha)

    @staticmethod
    def _lerp_pos(prev: tuple[float, float] | None, x: float, y: float,
                  alpha: float) -> tuple[float, float]:
        """Lerp from prev to (x, y), or (x, y) if there's no prev or it was a teleport."""
        if prev is None or math.hypot(x - prev[0], y - prev[1]) > C.TELEPORT_SNAP_PX:
            return x, y
        return lerp(prev[0], x, alpha), lerp(prev[1], y, alpha)


def step_alpha(accumulator: float, physics_dt: float) -> float:
    """Fraction of the next physics step already elapsed, clamped to [0, 1]."""
    return min(max(accumulator / physics_dt, 0.0), 1.0)
