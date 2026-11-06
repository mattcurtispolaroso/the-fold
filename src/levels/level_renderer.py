"""Level renderer — loads level data and builds/draws Pygame geometry.

Separated from game logic. Reads level files, produces platform rects
and draws them. Never modifies game state.
"""
from __future__ import annotations

from pathlib import Path

import pygame

from constants import EPSILON
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
        # Float positions prevent drift from repeated int truncation at fractional
        # time_scale values (e.g. speed=1, time_scale=0.5 → int(0.5)=0 would freeze the platform)
        self._fx: float = float(definition.x)
        self._fy: float = float(definition.y)
        # Where the platform was before this step, and how far its rect actually
        # moved (after clamping and int truncation). Riding and pushing use these
        # so the player moves exactly with the platform, including at turnarounds.
        self.prev_rect: pygame.Rect = self.rect.copy()
        self.delta: tuple[int, int] = (0, 0)

    def update(self, time_scale: float = 1.0) -> None:
        """Move the platform one step and reverse at bounds.

        time_scale=0.0 freezes the platform (Time Dilation ability).
        """
        self.prev_rect.update(self.rect)
        self._advance(time_scale)
        self.delta = (self.rect.x - self.prev_rect.x, self.rect.y - self.prev_rect.y)

    def _advance(self, time_scale: float) -> None:
        """Move the float position along the axis, reversing at the bounds."""
        if self.axis == "x":
            self._fx += self.speed * self.direction * time_scale
            if self._fx >= self.max_val:
                self._fx = float(self.max_val)
                self.direction = -1
            elif self._fx <= self.min_val:
                self._fx = float(self.min_val)
                self.direction = 1
            self.rect.x = int(self._fx)
        else:
            self._fy += self.speed * self.direction * time_scale
            if self._fy >= self.max_val:
                self._fy = float(self.max_val)
                self.direction = -1
            elif self._fy <= self.min_val:
                self._fy = float(self.min_val)
                self.direction = 1
            self.rect.y = int(self._fy)


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
        self._collision_rects: list[pygame.Rect] = []

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
        # Built once per load: moving platforms mutate their rects in place, so
        # the list itself never changes during play (no per-step allocation).
        self._collision_rects = self.all_platform_rects() + self._boundary

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
        """Return how far the platform the player stands on moved this step.

        Probes (2px in the gravity direction, same geometry as
        check_ground_adjacent) against each platform's PREVIOUS rect — where
        the player was standing — and returns that platform's actual
        displacement, so the player stays locked to it even when it reverses.
        Returns (0.0, 0.0) if not on a moving platform or time is frozen.
        """
        if abs(time_scale) < EPSILON or not self.moving_platforms:
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
            if probe.colliderect(mp.prev_rect):
                return float(mp.delta[0]), float(mp.delta[1])
        return 0.0, 0.0

    def movers(self) -> list[tuple[pygame.Rect, int, int]]:
        """(rect, dx, dy) for each moving platform's motion this step — for pushing."""
        return [(mp.rect, mp.delta[0], mp.delta[1]) for mp in self.moving_platforms]

    def collision_rects(self) -> list[pygame.Rect]:
        """Every solid rect (static, moving, boundary). Cached; do not mutate."""
        return self._collision_rects

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
