"""ItemManager — subscribes owned items to the event bus, tracks charges, detects resonances.

One instance lives in main.py. Call sync_owned() when the run's item list changes.
Call on_room_enter() at every ROOM_ENTERED to reset per-room charges.
"""
from __future__ import annotations

import random
from typing import Any

from src.data.items import OwnedItem
from src.systems.events import EventBus, EventResult, GameEvent
from src.systems.items.effects import EFFECT_REGISTRY, EffectContext
from src.systems.items.registry import ItemRegistry


class ItemManager:
    """Wires owned items to the event bus and manages charges/cooldowns."""

    def __init__(
        self,
        registry: ItemRegistry,
        bus: EventBus,
        player: Any,
        enemies: list,
        run_state: Any,
        ability_slot: Any,
        rng_seed: int = 0,
    ) -> None:
        """Create manager and subscribe to bus. Call sync_owned() to activate items."""
        self._registry = registry
        self._bus = bus
        self._player = player
        self._enemies = enemies
        self._run_state = run_state
        self._ability_slot = ability_slot
        self._rng = random.Random(rng_seed)
        self._ctx = EffectContext(
            player=player,
            enemies=enemies,
            run_state=run_state,
            ability_slot=ability_slot,
            rng=self._rng,
        )
        self._internal_cooldowns: dict[str, float] = {}
        self._active_resonances: set[str] = set()

        bus.subscribe(GameEvent.ROOM_ENTERED, self._on_room_entered)
        bus.subscribe(GameEvent.GRAVITY_ROTATED, self._make_handler(GameEvent.GRAVITY_ROTATED))
        bus.subscribe(GameEvent.ABILITY_USED, self._make_handler(GameEvent.ABILITY_USED))
        bus.subscribe(GameEvent.ABILITY_ENDED, self._make_handler(GameEvent.ABILITY_ENDED))
        bus.subscribe(GameEvent.PLAYER_HIT, self._make_handler(GameEvent.PLAYER_HIT))
        bus.subscribe(GameEvent.INTEGRITY_ZERO, self._make_handler(GameEvent.INTEGRITY_ZERO))
        bus.subscribe(GameEvent.ROOM_CLEARED, self._make_handler(GameEvent.ROOM_CLEARED))
        bus.subscribe(GameEvent.HOLE_RESOLVED, self._make_handler(GameEvent.HOLE_RESOLVED))

    # --- Public API ---

    def sync_owned(self, owned_items: list[OwnedItem]) -> None:
        """Update context and recompute resonances after item list changes."""
        self._owned = owned_items
        self._detect_resonances()

    def tick(self, dt: float) -> None:
        """Advance internal cooldown timers."""
        for item_id in list(self._internal_cooldowns):
            self._internal_cooldowns[item_id] = max(0.0, self._internal_cooldowns[item_id] - dt)

    def on_room_enter(self) -> None:
        """Reset per-room charges for all owned items (called by ROOM_ENTERED handler)."""
        for owned in getattr(self, "_owned", []):
            defn = self._registry.get_item(owned.id)
            if defn and defn.effect == "cancel_and_restore":
                rank_idx = owned.rank - 1
                params = defn.params_by_rank[rank_idx]
                self._ctx.ctc_room_charges = params["per_room_charges"]

    def reset(self) -> None:
        """Clear all state — call on run reset."""
        self._owned = []
        self._active_resonances.clear()
        self._internal_cooldowns.clear()
        self._ctx.kerr_ring_rotations = 0
        self._ctx.ctc_room_charges = 0
        self._ctx.ctc_run_bonus = 0
        self._ctx._phase_blocked = False

    def snapshot_state(self) -> dict[str, Any]:
        """Copy of all mutable item state (for World snapshots / rewind)."""
        ctx = self._ctx
        return {
            "owned": list(getattr(self, "_owned", [])),
            "cooldowns": dict(self._internal_cooldowns),
            "resonances": set(self._active_resonances),
            "rng": self._rng.getstate(),
            "ctx": (ctx._phase_blocked, ctx.kerr_ring_rotations,
                    ctx.ctc_room_charges, ctx.ctc_run_bonus),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore state from snapshot_state(), in place (bus subscriptions stay valid)."""
        self._owned = list(state["owned"])
        self._internal_cooldowns = dict(state["cooldowns"])
        self._active_resonances = set(state["resonances"])
        self._rng.setstate(state["rng"])  # ctx.rng is this same Random object
        ctx = self._ctx
        (ctx._phase_blocked, ctx.kerr_ring_rotations,
         ctx.ctc_room_charges, ctx.ctc_run_bonus) = state["ctx"]

    # --- Internal ---

    def _on_room_entered(self, result: EventResult, **_: Any) -> None:
        self.on_room_enter()
        self._ctx._phase_blocked = False

    def _make_handler(self, event: GameEvent):
        """Return a bus handler that fires all owned items whose trigger matches this event."""
        event_name = event.name  # e.g. "GRAVITY_ROTATED"

        def handler(result: EventResult, **kwargs: Any) -> None:
            self._ctx._phase_blocked = False
            # Fire modifier/artifact effects
            for owned in getattr(self, "_owned", []):
                defn = self._registry.get_item(owned.id)
                if defn is None or defn.trigger != event_name:
                    continue
                # Check internal cooldown
                cd = defn.internal_cooldown
                if cd > 0.0 and self._internal_cooldowns.get(owned.id, 0.0) > 0.0:
                    continue
                primitive = EFFECT_REGISTRY.get(defn.effect)
                if primitive is None:
                    continue
                rank_idx = min(owned.rank - 1, len(defn.params_by_rank) - 1)
                params = defn.params_by_rank[rank_idx]
                primitive(result, self._ctx, params, **kwargs)
                if cd > 0.0:
                    self._internal_cooldowns[owned.id] = cd
            # Fire resonance effects
            for res_id in self._active_resonances:
                res = self._registry.get_resonance(res_id)
                if res is None or res.trigger != event_name:
                    continue
                primitive = EFFECT_REGISTRY.get(res.effect)
                if primitive is None:
                    continue
                primitive(result, self._ctx, res.params, **kwargs)

        return handler

    def _detect_resonances(self) -> None:
        """Recompute which resonances are active based on owned items."""
        owned_ids = {o.id for o in getattr(self, "_owned", [])}
        self._active_resonances.clear()
        for res in self._registry.all_resonances():
            if all(req in owned_ids for req in res.requires):
                self._active_resonances.add(res.id)
