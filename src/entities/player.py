"""Player entity state for The Fold.

Single source of truth for all mutable player state — physics, movement,
and game flags. All fields are primitive types so the instance is
serialisable with to_dict() for crash logging and save files.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from constants import (
    ANCHOR_INTEGRITY_MAX,
    CHRONO_RESERVE_MAX,
    CHRONO_REGEN_IDLE,
    CHRONO_REGEN_MOVE,
    IFRAMES_DURATION,
    PLAYER_PHYSICS_HEIGHT_NORMAL,
    PLAYER_PHYSICS_WIDTH_NORMAL,
)
from src.physics.gravity import GravityDir, get_player_physics_size


@dataclass
class Player:
    """All mutable player state — physics position, velocity, and flags."""

    px: float
    py: float
    vx: float = 0.0
    vy: float = 0.0
    gravity_dir: GravityDir = (0, 1)
    player_w: int = PLAYER_PHYSICS_WIDTH_NORMAL
    player_h: int = PLAYER_PHYSICS_HEIGHT_NORMAL
    on_ground: bool = False
    coyote_timer: float = 0.0
    jumping: bool = False
    facing_right: bool = True
    move_input: int = 0
    goal_reached: bool = False
    chrono_reserve: float = CHRONO_RESERVE_MAX
    anchor_integrity: int = ANCHOR_INTEGRITY_MAX
    last_safe_px: float = 0.0
    last_safe_py: float = 0.0
    iframes_timer: float = 0.0

    @classmethod
    def from_spawn(
        cls, spawn: tuple[float, float], gravity_start: GravityDir = (0, 1),
    ) -> Player:
        """Create player at spawn with physics dimensions matching gravity."""
        w, h = get_player_physics_size(gravity_start)
        return cls(px=spawn[0], py=spawn[1], gravity_dir=gravity_start,
                   player_w=w, player_h=h,
                   last_safe_px=float(spawn[0]), last_safe_py=float(spawn[1]))

    def reset(self, spawn: tuple[float, float], gravity_start: GravityDir) -> None:
        """Reset all state to a fresh spawn — used when switching levels."""
        self.px, self.py = spawn
        self.vx = self.vy = 0.0
        self.gravity_dir = gravity_start
        self.player_w, self.player_h = get_player_physics_size(gravity_start)
        self.on_ground = False
        self.coyote_timer = 0.0
        self.jumping = False
        self.facing_right = True
        self.move_input = 0
        self.goal_reached = False
        self.chrono_reserve = CHRONO_RESERVE_MAX
        self.anchor_integrity = ANCHOR_INTEGRITY_MAX
        self.last_safe_px = float(spawn[0])
        self.last_safe_py = float(spawn[1])
        self.iframes_timer = 0.0

    def set_gravity(self, new_dir: GravityDir) -> None:
        """Update gravity direction and keep physics dimensions in sync."""
        self.gravity_dir = new_dir
        self.player_w, self.player_h = get_player_physics_size(new_dir)

    def tick_chrono_regen(
        self, dt: float, is_moving: bool, regen_mult: float = 1.0,
    ) -> None:
        """Advance Chrono Reserve regen for one physics step.

        Moving earns regen; idling earns nothing (CHRONO_REGEN_IDLE = 0).
        regen_mult scales the rate — used by the singularity pressure curve.
        """
        regen = CHRONO_REGEN_MOVE if is_moving else CHRONO_REGEN_IDLE
        self.chrono_reserve = min(
            CHRONO_RESERVE_MAX, self.chrono_reserve + regen * regen_mult * dt,
        )

    def take_fall_damage(self) -> bool:
        """Decrement integrity for a fall. Returns True if integrity hit 0 (level reset needed)."""
        self.anchor_integrity = max(0, self.anchor_integrity - 1)
        if self.anchor_integrity <= 0:
            return True
        self.px = self.last_safe_px
        self.py = self.last_safe_py
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.jumping = False
        self.coyote_timer = 0.0
        return False

    def take_hit(self, knockback_vx: float, knockback_vy: float) -> bool:
        """Take one combat hit. Returns True if integrity hit 0 (level reset needed)."""
        self.anchor_integrity = max(0, self.anchor_integrity - 1)
        if self.anchor_integrity <= 0:
            return True
        self.iframes_timer = IFRAMES_DURATION
        self.vx = knockback_vx
        self.vy = knockback_vy
        return False

    def to_dict(self) -> dict:
        """Serialise player state for crash logging and save files."""
        return dataclasses.asdict(self)
