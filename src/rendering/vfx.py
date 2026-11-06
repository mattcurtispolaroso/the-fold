"""Pooled particle VFX system.

All Particle objects are pre-allocated at startup and recycled in a ring
buffer. No heap allocation happens during gameplay.

Units (TA-7): positions px, velocities px/s, accelerations px/s², drag 1/s —
everything is multiplied by dt, so particles behave identically at any frame
rate. Effect shapes come from the VFX_* specs in constants.py.

Rendering: draw() is the software path; write_instances() packs active
particles for the GPU ParticleRenderer (src/rendering/gpu/particles.py).
"""
from __future__ import annotations

import array
import math
import random

import pygame

from constants import (
    VFX_HIT_SPARK,
    VFX_LANDING_DUST,
    VFX_POOL_SIZE,
    VFX_ROTATION_BURST,
)

INSTANCE_FLOATS: int = 8   # per particle for the GPU: x, y, radius, r, g, b, alpha, glow
_MAX_CHANNEL: int = 255


class Particle:
    """Single reusable particle slot — never created after startup."""

    __slots__ = (
        "px", "py", "vx", "vy", "ax", "ay", "drag",
        "lifetime", "max_lifetime",
        "r", "g", "b", "size0", "size1", "glow", "active",
    )

    def __init__(self) -> None:
        """Initialise to inactive state."""
        self.px: float = 0.0
        self.py: float = 0.0
        self.vx: float = 0.0
        self.vy: float = 0.0
        self.ax: float = 0.0
        self.ay: float = 0.0
        self.drag: float = 0.0
        self.lifetime: float = 0.0
        self.max_lifetime: float = 1.0
        self.r: float = 1.0
        self.g: float = 1.0
        self.b: float = 1.0
        self.size0: float = 2.0
        self.size1: float = 2.0
        self.glow: float = 0.0
        self.active: bool = False

    @property
    def life_frac(self) -> float:
        """Remaining life, 1 at birth → 0 at death."""
        return max(self.lifetime / self.max_lifetime, 0.0)

    @property
    def size(self) -> float:
        """Current radius, interpolated from birth size to death size."""
        t = self.life_frac
        return self.size1 + (self.size0 - self.size1) * t


class ParticlePool:
    """Pre-allocated ring-buffer particle pool. Emit effects via named helpers."""

    def __init__(self, capacity: int = VFX_POOL_SIZE) -> None:
        """Pre-allocate all particle slots."""
        self._pool: list[Particle] = [Particle() for _ in range(capacity)]
        self._cursor: int = 0

    @property
    def capacity(self) -> int:
        """Fixed number of particle slots (never grows)."""
        return len(self._pool)

    def _acquire(self) -> Particle:
        """Return the next slot, recycling the oldest if pool is exhausted."""
        p = self._pool[self._cursor]
        self._cursor = (self._cursor + 1) % len(self._pool)
        return p

    def _spawn(self, spec: dict, px: float, py: float, vx: float, vy: float,
               gravity_dir: tuple[int, int]) -> None:
        """Initialise one particle from an effect spec."""
        p = self._acquire()
        p.px, p.py, p.vx, p.vy = px, py, vx, vy
        p.ax = gravity_dir[0] * spec["gravity"]
        p.ay = gravity_dir[1] * spec["gravity"]
        p.drag = spec["drag"]
        p.lifetime = random.uniform(*spec["life"])
        p.max_lifetime = p.lifetime
        p.r, p.g, p.b = random.choice(spec["colors"])
        p.size0, p.size1 = spec["size"]
        p.glow = spec["glow"]
        p.active = True

    def _emit_radial(self, spec: dict, px: float, py: float,
                     gravity_dir: tuple[int, int]) -> None:
        """Emit spec["count"] particles in random directions from one point."""
        for _ in range(spec["count"]):
            angle = random.uniform(0.0, 2.0 * math.pi)
            speed = random.uniform(*spec["speed"])
            self._spawn(spec, px, py, math.cos(angle) * speed, math.sin(angle) * speed,
                        gravity_dir)

    def emit_rotation_burst(self, px: float, py: float) -> None:
        """Expanding amber ring from the player centre — fired on every gravity rotation."""
        self._emit_radial(VFX_ROTATION_BURST, px, py, (0, 0))

    def emit_hit_spark(self, px: float, py: float,
                       gravity_dir: tuple[int, int] = (0, 1)) -> None:
        """Red-orange sparks on damage; they fall along the player's gravity."""
        self._emit_radial(VFX_HIT_SPARK, px, py, gravity_dir)

    def emit_landing_dust(
        self,
        px: float, py: float,
        player_w: float, player_h: float,
        gravity_dir: tuple[int, int],
    ) -> None:
        """Grey fan from the foot contact point, directed against gravity."""
        spec = VFX_LANDING_DUST
        gx, gy = gravity_dir
        foot_x = px + gx * player_w / 2   # player edge in the gravity direction
        foot_y = py + gy * player_h / 2
        perp_x, perp_y = -gy, gx          # lateral axis along the ground
        lateral_dim = abs(perp_x) * player_w + abs(perp_y) * player_h
        for _ in range(spec["count"]):
            spread = random.uniform(-lateral_dim / 4, lateral_dim / 4)
            main_speed = random.uniform(*spec["speed"])
            lateral = random.uniform(-spec["lateral_speed"], spec["lateral_speed"])
            self._spawn(spec,
                        foot_x + perp_x * spread, foot_y + perp_y * spread,
                        -gx * main_speed + perp_x * lateral,
                        -gy * main_speed + perp_y * lateral,
                        (0, 0))

    def update(self, dt: float) -> None:
        """Advance all active particles by dt seconds.

        Position uses the exact constant-acceleration step and drag is
        exponential, so results don't depend on frame rate (a plain
        v += a·dt; p += v·dt drifts ~8% between 30 and 120 fps under gravity).
        """
        for p in self._pool:
            if not p.active:
                continue
            p.px += p.vx * dt + 0.5 * p.ax * dt * dt
            p.py += p.vy * dt + 0.5 * p.ay * dt * dt
            damping = math.exp(-p.drag * dt)
            p.vx = (p.vx + p.ax * dt) * damping
            p.vy = (p.vy + p.ay * dt) * damping
            p.lifetime -= dt
            if p.lifetime <= 0.0:
                p.active = False

    def active_count(self) -> int:
        """Number of live particles."""
        return sum(1 for p in self._pool if p.active)

    def write_instances(self, buf: array.array, offset: tuple[float, float]) -> int:
        """Pack active particles into `buf` (INSTANCE_FLOATS each, screen space).

        `buf` must hold capacity × INSTANCE_FLOATS floats. Returns the count written.
        """
        ox, oy = offset
        n = 0
        for p in self._pool:
            if not p.active:
                continue
            i = n * INSTANCE_FLOATS  # write in place: no per-particle allocation
            buf[i] = p.px + ox
            buf[i + 1] = p.py + oy
            buf[i + 2] = p.size
            buf[i + 3] = p.r
            buf[i + 4] = p.g
            buf[i + 5] = p.b
            buf[i + 6] = p.life_frac
            buf[i + 7] = p.glow
            n += 1
        return n

    def draw(self, surface: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Software path: draw active particles as circles fading toward black."""
        ox, oy = offset
        for p in self._pool:
            if p.active:
                fade = p.life_frac * _MAX_CHANNEL
                color = (int(p.r * fade), int(p.g * fade), int(p.b * fade))
                pygame.draw.circle(
                    surface, color,
                    (int(p.px + ox), int(p.py + oy)),
                    max(1, round(p.size)),
                )
