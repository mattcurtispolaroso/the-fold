"""Data structures for level definitions.

All level geometry and metadata is represented by these dataclasses.
Serialisable to/from JSON via to_dict() and from_dict() class methods.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
class LevelData:
    """Complete level definition loaded from a JSON file."""

    name: str
    gravity_start: tuple[int, int]
    spawn: tuple[float, float]
    goal: GoalDef
    static_platforms: list[PlatformDef] = field(default_factory=list)
    moving_platforms: list[MovingPlatformDef] = field(default_factory=list)
    tile_size: int = 40
    level_width: int = 800
    level_height: int = 600

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
            "static_platforms": [p.to_dict() for p in self.static_platforms],
            "moving_platforms": [p.to_dict() for p in self.moving_platforms],
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
            goal=GoalDef.from_dict(d["goal"]),
            static_platforms=[
                PlatformDef.from_dict(p) for p in d.get("static_platforms", [])
            ],
            moving_platforms=[
                MovingPlatformDef.from_dict(p)
                for p in d.get("moving_platforms", [])
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
        """Load a level from a JSON file."""
        with open(path, "r") as f:
            return cls.from_json(f.read())

    def save(self, path: str | Path) -> None:
        """Save the level to a JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())
