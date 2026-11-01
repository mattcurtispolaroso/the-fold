"""Item data structures — Module 5a.

ItemDef is the static definition loaded from JSON.
OwnedItem is the per-run instance (id + rank).
ResonanceDef is the static definition of a cross-domain combo.
These are pure data; no imports from systems.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ItemDef:
    """Static definition of a modifier, artifact, or resonance loaded from JSON."""

    id: str
    name: str
    tier: str               # "modifier" | "artifact"
    domain: str             # "time" | "gravity" | "horizon" | "none"
    trigger: str            # GameEvent name string, e.g. "GRAVITY_ROTATED"
    effect: str             # effect primitive name, e.g. "add_chrono"
    params_by_rank: list    # list of dicts, index 0 = rank 1
    description: str
    internal_cooldown: float = 0.0
    unlocked_by: str | None = None


@dataclass
class OwnedItem:
    """A modifier or artifact owned by the player in the current run."""

    id: str
    rank: int = 1           # 1-3 for modifiers; always 1 for artifacts


@dataclass
class ResonanceDef:
    """Static definition of a cross-domain resonance combo."""

    id: str
    name: str
    requires: list          # two item ids (strings)
    trigger: str            # GameEvent name that fires the resonance effect
    effect: str             # effect primitive name
    params: dict            # single-rank params (resonances have no rank)
    description: str
