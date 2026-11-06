"""Capture and restore all World simulation state (Engine Session 3).

Restores happen IN PLACE: the live player, enemy, platform and run-state
objects are updated rather than replaced, because other objects hold references
to them (the ItemManager and its effect context, event-bus subscriptions, the
level's cached collision-rect list). Replacing objects would silently cut
those links.

A snapshot is valid only within the level load it was taken in.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.systems.world import World

_SCALARS = ("anomaly_pending", "rotation_cooldown", "active_zones", "gravity_clamped",
            "gravity_mult", "time_scale", "gravity_expired", "steps")


@dataclass(frozen=True)
class WorldSnapshot:
    """Opaque saved simulation state."""

    level_token: int                 # identity of the level load this belongs to
    player: dict[str, Any]
    run_state: dict[str, Any]
    dilation: dict[str, Any]
    enemies: tuple[dict[str, Any], ...]
    platforms: tuple[tuple, ...]
    items: dict[str, Any]
    scalars: dict[str, Any]


def _platform_state(mp: Any) -> tuple:
    """Everything that changes on a moving platform."""
    return (mp._fx, mp._fy, mp.direction, tuple(mp.rect), tuple(mp.prev_rect), mp.delta)


def capture(world: World) -> WorldSnapshot:
    """Deep-copy every piece of simulation state out of the world."""
    return WorldSnapshot(
        level_token=id(world.level.level_data),
        player=copy.deepcopy(vars(world.player)),
        run_state=copy.deepcopy(vars(world.run_state)),
        dilation=copy.deepcopy(vars(world.time_dilation)),
        enemies=tuple(copy.deepcopy(vars(e)) for e in world.enemies),
        platforms=tuple(_platform_state(mp) for mp in world.level.moving_platforms),
        items=world.item_manager.snapshot_state(),
        scalars=copy.deepcopy({k: getattr(world, k) for k in _SCALARS}),
    )


def restore(world: World, snap: WorldSnapshot) -> None:
    """Put the world back exactly as captured (same level load only)."""
    if snap.level_token != id(world.level.level_data) or len(snap.enemies) != len(world.enemies):
        raise ValueError("snapshot belongs to a different level load")
    vars(world.player).update(copy.deepcopy(snap.player))
    vars(world.run_state).update(copy.deepcopy(snap.run_state))
    vars(world.time_dilation).update(copy.deepcopy(snap.dilation))
    for enemy, state in zip(world.enemies, snap.enemies):
        vars(enemy).update(copy.deepcopy(state))
    for mp, (fx, fy, direction, rect, prev, delta) in zip(world.level.moving_platforms, snap.platforms):
        mp._fx, mp._fy, mp.direction, mp.delta = fx, fy, direction, delta
        mp.rect.update(rect)        # in place: the cached collision list holds this Rect
        mp.prev_rect.update(prev)
    world.item_manager.restore_state(snap.items)
    for key, value in copy.deepcopy(snap.scalars).items():
        setattr(world, key, value)
