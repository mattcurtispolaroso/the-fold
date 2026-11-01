"""Effect primitives for item system — Module 5a.

Each primitive is a callable stored in EFFECT_REGISTRY by name.
Items reference primitives by name in JSON; new items need only JSON.
New behaviour needs a new primitive added here.

Primitive signature:
    fn(result, context, params, **event_kwargs) -> None

- result:     EventResult (may be cancelled)
- context:    EffectContext (player, enemy list, run_state, ability_slot, rng)
- params:     dict of per-rank parameters from ItemDef
- **event_kwargs: keyword args forwarded from the event (e.g. gravity_dir, is_white)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from constants import CHRONO_RESERVE_MAX, IFRAMES_DURATION


@dataclass
class EffectContext:
    """Mutable game state accessible to effect primitives."""

    player: Any
    enemies: list
    run_state: Any
    ability_slot: Any
    rng: random.Random
    # Resonance-local state for cross-primitive signalling
    _phase_blocked: bool = field(default=False)
    # Kerr Ring rotation counter (tracks full 4-rotation cycle)
    kerr_ring_rotations: int = field(default=0)
    # CTC charges: per-room and per-run bonus (managed by manager on room enter)
    ctc_room_charges: int = field(default=0)
    ctc_run_bonus: int = field(default=0)


# --- Primitive implementations ---

def _add_chrono(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Add chrono_reserve, clamped to CHRONO_RESERVE_MAX."""
    amount = float(params["amount"])
    ctx.player.chrono_reserve = min(CHRONO_RESERVE_MAX, ctx.player.chrono_reserve + amount)


def _grant_iframes(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Grant i-frames for params["seconds"] (stacks with existing timer)."""
    seconds = float(params["seconds"])
    ctx.player.iframes_timer = max(ctx.player.iframes_timer, seconds)


def _extend_active_ability(result: Any, ctx: EffectContext, params: dict, **kwargs: Any) -> None:
    """Extend a named ability's active_timer by params["seconds"] if it is currently active."""
    ability_name = params["ability_name"]
    seconds = float(params["seconds"])
    only_when_active = bool(params.get("only_when_active", False))
    if ctx.ability_slot.name != ability_name:
        return
    if only_when_active and not ctx.ability_slot.is_active:
        return
    if not ctx.ability_slot.is_active:
        return
    ctx.ability_slot.active_timer = min(
        ctx.ability_slot.active_timer + seconds,
        ctx.ability_slot.duration * 3,  # cap extension at 3× base duration
    )


def _cancel_and_restore(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Cancel integrity-zero, restore 1 integrity, return player to last safe position.

    Uses per-room charges first; if exhausted uses per_run_bonus charges.
    """
    if ctx.ctc_room_charges > 0:
        ctx.ctc_room_charges -= 1
    elif ctx.ctc_run_bonus > 0:
        ctx.ctc_run_bonus -= 1
    else:
        return  # no charges available, don't cancel
    result.cancelled = True
    ctx.player.anchor_integrity = min(ctx.player.anchor_integrity + 1, 3)
    ctx.player.px = ctx.player.last_safe_px
    ctx.player.py = ctx.player.last_safe_py
    ctx.player.vx = 0.0
    ctx.player.vy = 0.0


def _phase_hit(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Chance to cancel a PLAYER_HIT event (phase through the hit)."""
    chance = float(params["chance"])
    if ctx.rng.random() < chance:
        result.cancelled = True
        ctx._phase_blocked = True


def _modify_hole_outcome(result: Any, ctx: EffectContext, params: dict, **kwargs: Any) -> None:
    """Reduce black hole stability cost; add extra reward option on white holes at rank 3."""
    is_white = bool(kwargs.get("is_white", False))
    if not is_white:
        reduction = float(params["stability_reduction"])
        ctx.run_state.fold_stability = min(
            100.0, ctx.run_state.fold_stability + reduction,
        )
    extra = int(params.get("extra_reward_options", 0))
    if is_white and extra > 0:
        ctx.run_state.extra_reward_options = getattr(ctx.run_state, "extra_reward_options", 0) + extra


def _add_reward_option(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Permanently add extra reward options to all future reward screens this run."""
    extra = int(params.get("extra_options", 1))
    ctx.run_state.extra_reward_options = getattr(ctx.run_state, "extra_reward_options", 0) + extra


def _freeze_enemies_in_radius(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Freeze all enemies within radius for params["duration"] seconds."""
    radius = float(params["radius"])
    duration = float(params["duration"])
    for enemy in ctx.enemies:
        ex = getattr(enemy, "px", 0.0)
        ey = getattr(enemy, "py", 0.0)
        dist = ((ctx.player.px - ex) ** 2 + (ctx.player.py - ey) ** 2) ** 0.5
        if dist <= radius:
            enemy.frozen_timer = max(getattr(enemy, "frozen_timer", 0.0), duration)


def _trigger_ability(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Trigger a free ability activation every N events (Kerr Ring: every 4 rotations)."""
    ability_name = params["ability_name"]
    every_n = int(params["every_n"])
    if ctx.ability_slot.name != ability_name:
        return
    ctx.kerr_ring_rotations += 1
    if ctx.kerr_ring_rotations >= every_n:
        ctx.kerr_ring_rotations = 0
        if not ctx.ability_slot.is_active:
            ctx.ability_slot.active_timer = ctx.ability_slot.duration
            ctx.ability_slot.cooldown_timer = ctx.ability_slot.duration + ctx.ability_slot.cooldown


def _grant_iframes_on_phase(result: Any, ctx: EffectContext, params: dict, **_: Any) -> None:
    """Grant i-frames when a PLAYER_HIT was phased by Quantum Foam (Ergosphere resonance)."""
    if ctx._phase_blocked:
        seconds = float(params["seconds"])
        ctx.player.iframes_timer = max(ctx.player.iframes_timer, seconds)


def _ctc_undo_integrity_loss(result: Any, ctx: EffectContext, params: dict, **kwargs: Any) -> None:
    """Undo integrity loss from a black hole without spending CTC's room charge (Information Paradox)."""
    is_white = bool(kwargs.get("is_white", False))
    if not is_white:
        ctx.player.anchor_integrity = min(ctx.player.anchor_integrity + 1, 3)


# --- Registry ---

EFFECT_REGISTRY: dict[str, Callable] = {
    "add_chrono": _add_chrono,
    "grant_iframes": _grant_iframes,
    "extend_active_ability": _extend_active_ability,
    "cancel_and_restore": _cancel_and_restore,
    "phase_hit": _phase_hit,
    "modify_hole_outcome": _modify_hole_outcome,
    "add_reward_option": _add_reward_option,
    "freeze_enemies_in_radius": _freeze_enemies_in_radius,
    "trigger_ability": _trigger_ability,
    "grant_iframes_on_phase": _grant_iframes_on_phase,
    "ctc_undo_integrity_loss": _ctc_undo_integrity_loss,
}
