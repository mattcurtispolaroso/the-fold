"""Level renderer — loads level data and builds/draws Pygame geometry.

Separated from game logic. Reads level files, produces platform rects
and draws them. Never modifies game state.
"""
from __future__ import annotations

from pathlib import Path

import pygame

from src.levels.level_data import (
    GoalDef,
    GravityZoneDef,
    LevelData,
    MovingPlatformDef,
    PlatformDef,
)

# Colors for level geometry
PLATFORM_COLOR = (100, 100, 100)
MOVING_PLATFORM_COLOR = (50, 200, 200)
GOAL_COLOR = (50, 220, 50)

# Must exceed TERMINAL_VELOCITY (~44px/frame) so the player can't tunnel through
# a boundary in a single physics step.
_BOUNDARY_THICKNESS: int = 100


class MovingPlatform:
    """A platform that oscillates along one axis."""

    def __init__(self, definition: MovingPlatformDef) -> None:
        """Create from a MovingPlatformDef."""
        self.rect = pygame.Rect(
            definition.x, definition.y, definition.w, definition.h,
        )
        self.axis: str = definition.axis
        self.min_val: int = definition.min_val
        self.max_val: int = definition.max_val
        self.speed: int = definition.speed
        self.direction: int = 1

    def update(self, time_scale: float = 1.0) -> None:
        """Move the platform one step and reverse at bounds.

        time_scale=0.0 freezes the platform (Time Dilation ability).
        """
        if self.axis == "x":
            self.rect.x += int(self.speed * self.direction * time_scale)
            if self.rect.x >= self.max_val:
                self.rect.x = self.max_val
                self.direction = -1
            elif self.rect.x <= self.min_val:
                self.rect.x = self.min_val
                self.direction = 1
        else:
            self.rect.y += int(self.speed * self.direction * time_scale)
            if self.rect.y >= self.max_val:
                self.rect.y = self.max_val
                self.direction = -1
            elif self.rect.y <= self.min_val:
                self.rect.y = self.min_val
                self.direction = 1


class LevelRenderer:
    """Loads a level from JSON and builds Pygame geometry."""

    def __init__(self) -> None:
        """Initialise with empty state."""
        self.level_data: LevelData | None = None
        self.static_platforms: list[pygame.Rect] = []
        self.moving_platforms: list[MovingPlatform] = []
        self.goal_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.spawn: tuple[float, float] = (0.0, 0.0)
        self.gravity_start: tuple[int, int] = (0, 1)
        self.gravity_multiplier: float = 1.0
        self.gravity_zones: list[GravityZoneDef] = []
        self.level_width: int = 800
        self.level_height: int = 600
        self._boundary: list[pygame.Rect] = []

    def load(self, path: str | Path) -> LevelData:
        """Load a level JSON file and build all geometry."""
        self.level_data = LevelData.load(path)
        self._build_from_data(self.level_data)
        return self.level_data

    def load_from_data(self, data: LevelData) -> None:
        """Build geometry from an already-parsed LevelData."""
        self.level_data = data
        self._build_from_data(data)

    def _build_from_data(self, data: LevelData) -> None:
        """Convert LevelData into Pygame rects and objects."""
        self.static_platforms = [
            pygame.Rect(p.x, p.y, p.w, p.h)
            for p in data.static_platforms
        ]
        self.moving_platforms = [
            MovingPlatform(mp) for mp in data.moving_platforms
        ]
        self.goal_rect = pygame.Rect(
            data.goal.x, data.goal.y, data.goal.w, data.goal.h,
        )
        self.spawn = data.spawn
        self.gravity_start = data.gravity_start
        self.gravity_multiplier = data.gravity_multiplier
        self.gravity_zones = data.gravity_zones
        self.level_width = data.level_width
        self.level_height = data.level_height
        W, H, T = self.level_width, self.level_height, _BOUNDARY_THICKNESS
        self._boundary = [
            pygame.Rect(-T, -T, T, H + 2 * T),       # left wall
            pygame.Rect(W, -T, T, H + 2 * T),         # right wall
            pygame.Rect(-T, -T, W + 2 * T, T),        # top wall
            pygame.Rect(-T, H, W + 2 * T, T),         # bottom wall
        ]

    def update(self, time_scale: float = 1.0) -> None:
        """Update all dynamic level elements. time_scale=0 freezes moving platforms."""
        for mp in self.moving_platforms:
            mp.update(time_scale)

    def riding_velocity(
        self,
        px: float, py: float,
        player_w: float, player_h: float,
        gravity_dir: tuple[int, int],
        time_scale: float = 1.0,
    ) -> tuple[float, float]:
        """Return (vx, vy) of the moving platform the player is standing on.

        Uses a 2px probe in the gravity direction — same geometry as
        check_ground_adjacent. Returns (0.0, 0.0) if not on any moving platform
        or if time is frozen (time_scale=0 means platform isn't moving either).
        """
        if time_scale == 0.0 or not self.moving_platforms:
            return 0.0, 0.0
        if gravity_dir == (0, 1):
            probe = pygame.Rect(px - player_w / 2 + 1, py + player_h / 2, player_w - 2, 2)
        elif gravity_dir == (0, -1):
            probe = pygame.Rect(px - player_w / 2 + 1, py - player_h / 2 - 2, player_w - 2, 2)
        elif gravity_dir == (-1, 0):
            probe = pygame.Rect(px - player_w / 2 - 2, py - player_h / 2 + 1, 2, player_h - 2)
        elif gravity_dir == (1, 0):
            probe = pygame.Rect(px + player_w / 2, py - player_h / 2 + 1, 2, player_h - 2)
        else:
            return 0.0, 0.0
        for mp in self.moving_platforms:
            if probe.colliderect(mp.rect):
                vel = mp.speed * mp.direction * time_scale
                if mp.axis == "x":
                    return float(vel), 0.0
                else:
                    return 0.0, float(vel)
        return 0.0, 0.0

    def all_platform_rects(self) -> list[pygame.Rect]:
        """Return all collision rects (static + moving)."""
        return self.static_platforms + [
            mp.rect for mp in self.moving_platforms
        ]

    def boundary_rects(self) -> list[pygame.Rect]:
        """Return four platforms sealing the level boundary for collision."""
        return self._boundary

    def draw(self, surface: pygame.Surface, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        """Draw all level geometry to the surface, offset by camera."""
        ox, oy = offset
        for zone in self.gravity_zones:
            zone_rect = pygame.Rect(zone.x, zone.y, zone.w, zone.h).move(ox, oy)
            if zone.gravity_dir is not None:
                color = (220, 160, 50)   # amber — direction snap
            elif zone.strength_mult is not None and zone.strength_mult < 1.0:
                color = (80, 140, 220)   # blue — low gravity
            else:
                color = (220, 80, 50)    # red-orange — high gravity
            pygame.draw.rect(surface, color, zone_rect, 2)
        for plat in self.static_platforms:
            pygame.draw.rect(surface, PLATFORM_COLOR, plat.move(ox, oy))
        for mp in self.moving_platforms:
            pygame.draw.rect(surface, MOVING_PLATFORM_COLOR, mp.rect.move(ox, oy))
        pygame.draw.rect(surface, GOAL_COLOR, self.goal_rect.move(ox, oy))
