"""Item registry — loads and validates all item JSON files at startup.

Invalid entries are logged and skipped; they never cause a crash.
"""
from __future__ import annotations

import json
import os

from src.data.items import ItemDef, ResonanceDef

_REQUIRED_ITEM_KEYS = {"id", "name", "tier", "domain", "trigger", "effect", "params_by_rank", "description"}
_REQUIRED_RESONANCE_KEYS = {"id", "name", "requires", "trigger", "effect", "params", "description"}
_VALID_TIERS = {"modifier", "artifact"}
_VALID_DOMAINS = {"time", "gravity", "horizon", "none"}


def _validate_item(raw: dict) -> str | None:
    """Return an error string if raw item dict is invalid, else None."""
    missing = _REQUIRED_ITEM_KEYS - raw.keys()
    if missing:
        return f"missing keys: {missing}"
    if raw["tier"] not in _VALID_TIERS:
        return f"unknown tier: {raw['tier']!r}"
    if raw["domain"] not in _VALID_DOMAINS:
        return f"unknown domain: {raw['domain']!r}"
    if not isinstance(raw["params_by_rank"], list) or len(raw["params_by_rank"]) == 0:
        return "params_by_rank must be a non-empty list"
    return None


def _validate_resonance(raw: dict) -> str | None:
    """Return an error string if raw resonance dict is invalid, else None."""
    missing = _REQUIRED_RESONANCE_KEYS - raw.keys()
    if missing:
        return f"missing keys: {missing}"
    if not isinstance(raw["requires"], list) or len(raw["requires"]) != 2:
        return "requires must be a list of exactly 2 item ids"
    return None


class ItemRegistry:
    """Holds all loaded item and resonance definitions."""

    def __init__(self) -> None:
        """Initialise empty registry."""
        self._items: dict[str, ItemDef] = {}
        self._resonances: dict[str, ResonanceDef] = {}

    def get_item(self, item_id: str) -> ItemDef | None:
        """Return ItemDef by id, or None if not found."""
        return self._items.get(item_id)

    def get_resonance(self, resonance_id: str) -> ResonanceDef | None:
        """Return ResonanceDef by id, or None if not found."""
        return self._resonances.get(resonance_id)

    def all_items(self) -> list[ItemDef]:
        """All registered item definitions."""
        return list(self._items.values())

    def all_resonances(self) -> list[ResonanceDef]:
        """All registered resonance definitions."""
        return list(self._resonances.values())

    def modifiers(self) -> list[ItemDef]:
        """All modifier definitions."""
        return [d for d in self._items.values() if d.tier == "modifier"]

    def artifacts(self) -> list[ItemDef]:
        """All artifact definitions."""
        return [d for d in self._items.values() if d.tier == "artifact"]

    def _add_item(self, raw: dict, logger: object) -> None:
        error = _validate_item(raw)
        if error:
            logger.log_event(f"[ItemRegistry] Skipped item {raw.get('id', '?')!r}: {error}")
            return
        self._items[raw["id"]] = ItemDef(
            id=raw["id"],
            name=raw["name"],
            tier=raw["tier"],
            domain=raw["domain"],
            trigger=raw["trigger"],
            effect=raw["effect"],
            params_by_rank=list(raw["params_by_rank"]),
            description=raw["description"],
            internal_cooldown=float(raw.get("internal_cooldown", 0.0)),
            unlocked_by=raw.get("unlocked_by"),
        )

    def _add_resonance(self, raw: dict, logger: object) -> None:
        error = _validate_resonance(raw)
        if error:
            logger.log_event(f"[ItemRegistry] Skipped resonance {raw.get('id', '?')!r}: {error}")
            return
        self._resonances[raw["id"]] = ResonanceDef(
            id=raw["id"],
            name=raw["name"],
            requires=list(raw["requires"]),
            trigger=raw["trigger"],
            effect=raw["effect"],
            params=dict(raw["params"]),
            description=raw["description"],
        )


def load_item_registry(base_dir: str, logger: object) -> ItemRegistry:
    """Load all item JSON files from assets/data/items/ and return a populated registry."""
    registry = ItemRegistry()
    items_dir = os.path.join(base_dir, "assets", "data", "items")

    for filename, adder in [
        ("modifiers.json", registry._add_item),
        ("artifacts.json", registry._add_item),
        ("resonances.json", registry._add_resonance),
    ]:
        path = os.path.join(items_dir, filename)
        if not os.path.exists(path):
            logger.log_event(f"[ItemRegistry] File not found: {path}")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.log_event(f"[ItemRegistry] Failed to load {filename}: {exc}")
            continue
        for raw in entries:
            adder(raw, logger)

    logger.log_event(
        f"[ItemRegistry] Loaded {len(registry._items)} items, "
        f"{len(registry._resonances)} resonances."
    )
    return registry
