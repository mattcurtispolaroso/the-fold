"""Light definitions for the optional "lights" key in level JSON (TA-3).

Example:
    "lights": [
      {"type": "ambient", "color": [0.05, 0.08, 0.12]},
      {"type": "point", "x": 400, "y": 200, "radius": 300, "color": [0.3, 0.6, 1.0], "intensity": 1.2},
      {"type": "spot", "x": 800, "y": 0, "radius": 400, "angle": 270, "spread": 40,
       "color": [0.8, 0.5, 0.2], "intensity": 0.9}
    ]
Positions are world pixels. Spot "angle" is degrees counter-clockwise from +x
(270 points down the screen); "spread" is the full cone width in degrees.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import constants as C

logger = logging.getLogger(__name__)


class LightKind(Enum):
    """The three light types a level can declare."""

    AMBIENT = "ambient"
    POINT = "point"
    SPOT = "spot"


@dataclass
class LightDef:
    """One light. Ambient lights use only color and intensity."""

    kind: LightKind
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    x: float = 0.0
    y: float = 0.0
    radius: float = 100.0
    angle: float = 0.0
    spread: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the JSON shape; ambient lights omit position fields."""
        d: dict[str, Any] = {"type": self.kind.value, "color": list(self.color),
                             "intensity": self.intensity}
        if self.kind is not LightKind.AMBIENT:
            d.update(x=self.x, y=self.y, radius=self.radius)
        if self.kind is LightKind.SPOT:
            d.update(angle=self.angle, spread=self.spread)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LightDef:
        """Parse one light, clamping every value to its safe range."""
        color = tuple(_clamp(float(c), 0.0, 1.0) for c in d.get("color", (1.0, 1.0, 1.0)))
        if len(color) != 3:
            raise TypeError(f"light color must have 3 components, got {len(color)}")
        return cls(
            kind=LightKind(d["type"]),
            color=color,
            intensity=_clamp(float(d.get("intensity", 1.0)), 0.0, C.LIGHT_INTENSITY_MAX),
            x=float(d.get("x", 0.0)),
            y=float(d.get("y", 0.0)),
            radius=_clamp(float(d.get("radius", 100.0)), C.LIGHT_RADIUS_MIN, C.LIGHT_RADIUS_MAX),
            angle=float(d.get("angle", 0.0)),
            spread=_clamp(float(d.get("spread", 0.0)), 0.0, C.LIGHT_SPREAD_MAX),
        )


def parse_lights(raw: Any) -> list[LightDef]:
    """Parse the "lights" list. Unknown types are dropped; extra lights are truncated.

    At most one ambient light is kept (the first) and at most
    LIGHT_MAX_PER_LEVEL point/spot lights. Every drop is logged.
    """
    if not isinstance(raw, list):
        raise TypeError(f"level 'lights' must be a list, got {type(raw).__name__}")
    ambient: list[LightDef] = []
    emitters: list[LightDef] = []
    known_types = {kind.value for kind in LightKind}
    for entry in raw:
        light_type = entry.get("type") if isinstance(entry, dict) else None
        if light_type not in known_types:
            logger.warning("Light entry %r ignored (unknown or missing type)", entry)
            continue
        light = LightDef.from_dict(entry)
        (ambient if light.kind is LightKind.AMBIENT else emitters).append(light)
    if len(ambient) > 1:
        logger.warning("Level has %d ambient lights; using the first", len(ambient))
    if len(emitters) > C.LIGHT_MAX_PER_LEVEL:
        logger.warning("Level has %d lights; keeping the first %d",
                       len(emitters), C.LIGHT_MAX_PER_LEVEL)
    return ambient[:1] + emitters[:C.LIGHT_MAX_PER_LEVEL]


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp value into [low, high]."""
    return max(low, min(high, value))
