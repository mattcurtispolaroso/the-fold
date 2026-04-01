"""Level renderer — loads level data and builds/draws Pygame geometry.

Separated from game logic. Reads level files, produces platform rects
and draws them. Never modifies game state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame

from src.levels.level_data import (
    GoalDef,
    LevelData,
    MovingPlatformDef,
    PlatformDef,
)

# Colors for level geometry
PLATFORM_COLOR = (100, 100, 100)
MOVING_PLATFORM_COLOR = (50, 200, 200)
GOAL_COLOR = (50, 220, 50)


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

    def update(self) -> None:
        """Move the platform one step and reverse at bounds."""
        if self.axis == "x":
            self.rect.x += self.speed * self.direction
            if self.rect.x >= self.max_val:
                self.rect.x = self.max_val
                self.direction = -1
            elif self.rect.x <= self.min_val:
                self.rect.x = self.min_val
                self.direction = 1
        else:
            self.rect.y += self.speed * self.direction
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
        self.level_width: int = 800
        self.level_height: int = 600

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
        self.level_width = data.level_width
        self.level_height = data.level_height

    def update(self) -> None:
        """Update all dynamic level elements."""
        for mp in self.moving_platforms:
            mp.update()

    def all_platform_rects(self) -> list[pygame.Rect]:
        """Return all collision rects (static + moving)."""
        return self.static_platforms + [
            mp.rect for mp in self.moving_platforms
        ]

    def draw(self, surface: pygame.Surface) -> None:
        """Draw all level geometry to the surface."""
        for plat in self.static_platforms:
            pygame.draw.rect(surface, PLATFORM_COLOR, plat)
        for mp in self.moving_platforms:
            pygame.draw.rect(surface, MOVING_PLATFORM_COLOR, mp.rect)
        pygame.draw.rect(surface, GOAL_COLOR, self.goal_rect)
