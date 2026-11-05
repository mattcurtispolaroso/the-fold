"""Combat helpers — hit detection and knockback calculation.

Thin Phase 1 system. Full Module 7 (swept collision, damage calc, death states)
comes later; this covers the M3 vertical slice.
"""
from __future__ import annotations

from typing import Protocol

import pygame

from constants import KNOCKBACK_FORCE, KNOCKBACK_VERTICAL_FORCE
from src.entities.player import Player
from src.physics import gravity_is_vertical


class _Hittable(Protocol):
    """Minimal interface required to check hit against an entity."""
    rect: pygame.Rect


def check_hit(player: Player, enemy: _Hittable) -> bool:
    """True if player rect overlaps enemy rect and player is not in i-frames."""
    if player.iframes_timer > 0:
        return False
    player_rect = pygame.Rect(
        int(player.px - player.player_w / 2),
        int(player.py - player.player_h / 2),
        player.player_w, player.player_h,
    )
    return bool(player_rect.colliderect(enemy.rect))


def compute_knockback(
    player_px: float,
    player_py: float,
    enemy_px: float,
    enemy_py: float,
    gravity_dir: tuple[int, int],
    force: float = KNOCKBACK_FORCE,
) -> tuple[float, float]:
    """Return (vx, vy) impulse that pushes the player away from the enemy.

    Applies a lateral component (away from enemy) and an upward component
    (against gravity direction) so hits near ledges are genuinely dangerous.
    """
    kick = KNOCKBACK_VERTICAL_FORCE  # upward component, opposite to gravity
    if gravity_is_vertical(gravity_dir):
        vx = force if player_px >= enemy_px else -force
        vy = -gravity_dir[1] * kick  # kick against gravity
        return vx, vy
    vy = force if player_py >= enemy_py else -force
    vx = -gravity_dir[0] * kick  # kick against gravity (horizontal case)
    return vx, vy
