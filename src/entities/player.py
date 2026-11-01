"""Player entity state for The Fold.

Single source of truth for all mutable player state — physics, movement,
and game flags. All fields are primitive types so the instance is
serialisable with to_dict() for crash logging and save files.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from constants import PLAYER_PHYSICS_WIDTH_NORMAL, PLAYER_PHYSICS_HEIGHT_NORMAL
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

    @classmethod
    def from_spawn(
        cls, spawn: tuple[float, float], gravity_start: GravityDir = (0, 1),
    ) -> Player:
        """Create player at spawn with physics dimensions matching gravity."""
        w, h = get_player_physics_size(gravity_start)
        return cls(px=spawn[0], py=spawn[1], gravity_dir=gravity_start,
                   player_w=w, player_h=h)

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

    def set_gravity(self, new_dir: GravityDir) -> None:
        """Update gravity direction and keep physics dimensions in sync."""
        self.gravity_dir = new_dir
        self.player_w, self.player_h = get_player_physics_size(new_dir)

    def to_dict(self) -> dict:
        """Serialise player state for crash logging and save files."""
        return dataclasses.asdict(self)
