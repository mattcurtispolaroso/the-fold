"""Pooled particle VFX system.

All Particle objects are pre-allocated at startup and recycled in a ring
buffer. No heap allocation happens during gameplay.
"""
from __future__ import annotations

import math
import random

import pygame

from constants import (
    VFX_HIT_SPARK_COUNT,
    VFX_LANDING_DUST_COUNT,
    VFX_POOL_SIZE,
    VFX_ROTATION_BURST_COUNT,
)


class Particle:
    """Single reusable particle slot — never created after startup."""

    __slots__ = (
        "px", "py", "vx", "vy",
        "lifetime", "max_lifetime",
        "r", "g", "b", "size", "active",
    )

    def __init__(self) -> None:
        """Initialise to inactive state."""
        self.px: float = 0.0
        self.py: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.lifetime: float = 0.0
        self.max_lifetime: float = 1.0
        self.r: int = 255
        self.g: int = 255
        self.b: int = 255
        self.size: int = 2
        self.active: bool = False


class ParticlePool:
    """Pre-allocated ring-buffer particle pool. Emit effects via named helpers."""

    def __init__(self, capacity: int = VFX_POOL_SIZE) -> None:
        """Pre-allocate all particle slots."""
        self._pool: list[Particle] = [Particle() for _ in range(capacity)]
        self._cursor: int = 0

    def _acquire(self) -> Particle:
        """Return the next slot, recycling the oldest if pool is exhausted."""
        p = self._pool[self._cursor]
        self._cursor = (self._cursor + 1) % len(self._pool)
        return p

    def emit_rotation_burst(self, px: float, py: float) -> None:
        """Amber ring burst from player centre — fired on every gravity rotation."""
        for _ in range(VFX_ROTATION_BURST_COUNT):
            angle = random.uniform(0.0, 2.0 * math.pi)
            speed = random.uniform(3.0, 9.0)
            p = self._acquire()
            p.px, p.py = px, py
            p.vx = math.cos(angle) * speed
            p.vy = math.sin(angle) * speed
            p.lifetime = random.uniform(0.25, 0.5)
            p.max_lifetime = p.lifetime
            if random.random() < 0.7:
                p.r, p.g, p.b = 210, 160, 50   # amber
            else:
                p.r, p.g, p.b = 240, 230, 210  # warm white
            p.size = random.randint(2, 4)
            p.active = True

    def emit_hit_spark(self, px: float, py: float) -> None:
        """Red-orange burst on player taking damage."""
        for _ in range(VFX_HIT_SPARK_COUNT):
            angle = random.uniform(0.0, 2.0 * math.pi)
            speed = random.uniform(2.0, 7.0)
            p = self._acquire()
            p.px, p.py = px, py
            p.vx = math.cos(angle) * speed
            p.vy = math.sin(angle) * speed
            p.lifetime = random.uniform(0.15, 0.3)
            p.max_lifetime = p.lifetime
            p.r, p.g, p.b = random.choice(
                [(220, 80, 40), (255, 140, 60), (255, 200, 80)]
            )
            p.size = random.randint(2, 3)
            p.active = True

    def emit_landing_dust(
        self,
        px: float, py: float,
        player_w: float, player_h: float,
        gravity_dir: tuple[int, int],
    ) -> None:
        """Gray fan from the foot contact point, directed against gravity."""
        gx, gy = gravity_dir
        # Foot contact centre (player edge in gravity direction)
        foot_x = px + gx * player_w / 2
        foot_y = py + gy * player_h / 2
        # Perpendicular axis for lateral spread
        perp_x, perp_y = -gy, gx
        lateral_dim = abs(perp_x) * player_w + abs(perp_y) * player_h
        for _ in range(VFX_LANDING_DUST_COUNT):
            spread = random.uniform(-lateral_dim / 4, lateral_dim / 4)
            p = self._acquire()
            p.px = foot_x + perp_x * spread
            p.py = foot_y + perp_y * spread
            main_speed = random.uniform(1.5, 4.0)
            lateral = random.uniform(-2.0, 2.0)
            p.vx = -gx * main_speed + perp_x * lateral
            p.vy = -gy * main_speed + perp_y * lateral
            p.lifetime = random.uniform(0.2, 0.4)
            p.max_lifetime = p.lifetime
            p.r, p.g, p.b = 175, 165, 155
            p.size = random.randint(2, 4)
            p.active = True

    def update(self, dt: float) -> None:
        """Advance all active particles by dt seconds."""
        for p in self._pool:
            if p.active:
                p.px += p.vx
                p.py += p.vy
                p.lifetime -= dt
                if p.lifetime <= 0.0:
                    p.active = False

    def draw(self, surface: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw active particles with linear alpha fade to black."""
        ox, oy = offset
        for p in self._pool:
            if p.active:
                alpha = p.lifetime / p.max_lifetime
                color = (int(p.r * alpha), int(p.g * alpha), int(p.b * alpha))
                pygame.draw.circle(
                    surface, color,
                    (int(p.px + ox), int(p.py + oy)),
                    max(1, p.size),
                )
