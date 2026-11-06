"""Top-level screen/flow states (Engine Session 3).

Replaces the string states ("playing", "node_map", ...) that main.py used, per
CLAUDE.md "use enums for game states": a typo is now an AttributeError, not a
silently dead branch.
"""
from __future__ import annotations

from enum import Enum, auto


class GameState(Enum):
    """Which screen the game is on."""

    START = auto()
    NODE_MAP = auto()
    PLAYING = auto()
    REWARD = auto()
    HOLE_ENCOUNTER = auto()
    DEAD = auto()
    WIN = auto()
