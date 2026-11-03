"""Data structures for level definitions.

All level geometry and metadata is represented by these dataclasses.
Serialisable to/from JSON via to_dict() and from_dict() class methods.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LevelLoadError(Exception):
    """Raised when a level file cannot be loaded or parsed."""


@dataclass
class PlatformDef:
    """A static rectangular platform."""

    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        """Serialise to JSON-compatible dict."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlatformDef:
        """Deserialise from dict."""
        return cls(x=int(d["x"]), y=int(d["y"]), w=int(d["w"]), h=int(d["h"]))


@dataclass
class MovingPlatformDef:
    """A platform that oscillates along one axis."""

    x: int
    y: int
    w: int
    h: int
    axis: str          # "x" or "y"
    min_val: int
    max_val: int
    speed: int

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        return {
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "axis": self.axis, "min_val": self.min_val,
            "max_val": self.max_val, "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MovingPlatformDef:
        """Deserialise from dict."""
        return cls(
            x=int(d["x"]), y=int(d["y"]), w=int(d["w"]), h=int(d["h"]),
            axis=str(d["axis"]), min_val=int(d["min_val"]),
            max_val=int(d["max_val"]), speed=int(d["speed"]),
        )


@dataclass
class GoalDef:
    """The goal area the player must reach."""

    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        """Serialise to JSON-compatible dict."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GoalDef:
        """Deserialise from dict."""
        return cls(x=int(d["x"]), y=int(d["y"]), w=int(d["w"]), h=int(d["h"]))


@dataclass
class GravityZoneDef:
    """A rectangular area that locally modifies gravity.

    gravity_dir: snaps player gravity to this direction on entry (one-shot per entry).
    strength_mult: scales gravity strength while player overlaps this zone.
    Either or both fields may be set.
    """

    x: int
    y: int
    w: int
    h: int
    gravity_dir: tuple[int, int] | None = None
    strength_mult: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        d: dict[str, Any] = {"x": self.x, "y": self.y, "w": self.w, "h": self.h}
        if self.gravity_dir is not None:
            d["gravity_dir"] = list(self.gravity_dir)
        if self.strength_mult is not None:
            d["strength_mult"] = self.strength_mult
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GravityZoneDef:
        """Deserialise from dict."""
        gravity_dir: tuple[int, int] | None = (
            tuple(d["gravity_dir"]) if "gravity_dir" in d else None  # type: ignore[assignment]
        )
        strength_mult: float | None = (
            float(d["strength_mult"]) if "strength_mult" in d else None
        )
        return cls(
            x=int(d["x"]), y=int(d["y"]), w=int(d["w"]), h=int(d["h"]),
            gravity_dir=gravity_dir,
            strength_mult=strength_mult,
        )


@dataclass
class EnemyDef:
    """An enemy spawn point defined in a level file."""

    type: str       # "temporal_echo" | "fold_predator" | "anchored"
    x: float        # centre x at spawn
    y: float        # centre y at spawn
    min_x: float    # left patrol bound
    max_x: float    # right patrol bound
    speed: float = 0.0  # 0.0 = use class default for that enemy type

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        d: dict[str, Any] = {
            "type": self.type, "x": self.x, "y": self.y,
            "min_x": self.min_x, "max_x": self.max_x,
        }
        if self.speed > 0.0:
            d["speed"] = self.speed
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EnemyDef:
        """Deserialise from dict."""
        return cls(
            type=str(d["type"]),
            x=float(d["x"]),
            y=float(d["y"]),
            min_x=float(d["min_x"]),
            max_x=float(d["max_x"]),
            speed=float(d.get("speed", 0.0)),
        )


@dataclass
class LevelData:
    """Complete level definition loaded from a JSON file."""

    name: str
    gravity_start: tuple[int, int]
    spawn: tuple[float, float]
    goal: GoalDef
    static_platforms: list[PlatformDef] = field(default_factory=list)
    moving_platforms: list[MovingPlatformDef] = field(default_factory=list)
    gravity_zones: list[GravityZoneDef] = field(default_factory=list)
    enemies: list[EnemyDef] = field(default_factory=list)
    tile_size: int = 40
    level_width: int = 800
    level_height: int = 600
    gravity_multiplier: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        return {
            "name": self.name,
            "gravity_start": list(self.gravity_start),
            "spawn": list(self.spawn),
            "tile_size": self.tile_size,
            "goal": self.goal.to_dict(),
            "level_width": self.level_width,
            "level_height": self.level_height,
            "gravity_multiplier": self.gravity_multiplier,
            "static_platforms": [p.to_dict() for p in self.static_platforms],
            "moving_platforms": [p.to_dict() for p in self.moving_platforms],
            "gravity_zones": [z.to_dict() for z in self.gravity_zones],
            "enemies": [e.to_dict() for e in self.enemies],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LevelData:
        """Deserialise from dict."""
        return cls(
            name=str(d["name"]),
            gravity_start=tuple(d["gravity_start"]),
            spawn=tuple(d["spawn"]),
            tile_size=int(d.get("tile_size", 40)),
            level_width=int(d.get("level_width", 800)),
            level_height=int(d.get("level_height", 600)),
            gravity_multiplier=float(d.get("gravity_multiplier", 1.0)),
            goal=GoalDef.from_dict(d["goal"]),
            static_platforms=[
                PlatformDef.from_dict(p) for p in d.get("static_platforms", [])
            ],
            moving_platforms=[
                MovingPlatformDef.from_dict(p)
                for p in d.get("moving_platforms", [])
            ],
            gravity_zones=[
                GravityZoneDef.from_dict(z) for z in d.get("gravity_zones", [])
            ],
            enemies=[
                EnemyDef.from_dict(e) for e in d.get("enemies", [])
            ],
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> LevelData:
        """Deserialise from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def load(cls, path: str | Path) -> LevelData:
        """Load a level from a JSON file. Falls back to safe level on error."""
        try:
            with open(path, "r") as f:
                return cls.from_json(f.read())
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Level file failed to load (%s): %s", path, e)
            logger.warning("WARNING: Using fallback level")
            return cls.fallback()

    @classmethod
    def fallback(cls) -> LevelData:
        """Return a minimal safe level — single platform and spawn point."""
        return cls(
            name="Fallback Level",
            gravity_start=(0, 1),
            spawn=(400.0, 250.0),
            goal=GoalDef(x=700, y=350, w=40, h=40),
            static_platforms=[PlatformDef(x=0, y=400, w=800, h=40)],
            level_width=800,
            level_height=600,
        )

    def save(self, path: str | Path) -> None:
        """Save the level to a JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())
