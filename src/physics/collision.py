"""Collision detection and resolution.

Two-pass system: lateral axis first, gravity axis second.
Works correctly with any gravity direction — no hardcoded assumptions.
All positions snapped to integer after collision. Ground detection uses
a separate adjacency check to avoid colliderect gap oscillation.
"""
from __future__ import annotations

import pygame

from src.physics.gravity import GravityDir, gravity_is_vertical


def _resolve_axis_x(
    px: float, py: float, vx: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
) -> tuple[float, float]:
    """Resolve collisions along the X axis. Returns (px, vx)."""
    px += vx
    pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    for plat in platforms:
        if pr.colliderect(plat):
            if vx > 0:
                px = plat.left - player_w / 2
            elif vx < 0:
                px = plat.right + player_w / 2
            vx = 0.0
            px = round(px)
            pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    return px, vx


def _resolve_axis_y(
    px: float, py: float, vy: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
) -> tuple[float, float]:
    """Resolve collisions along the Y axis. Returns (py, vy)."""
    py += vy
    pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    for plat in platforms:
        if pr.colliderect(plat):
            if vy > 0:
                py = plat.top - player_h / 2
            elif vy < 0:
                py = plat.bottom + player_h / 2
            vy = 0.0
            py = round(py)
            pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    return py, vy


def _resolve_gravity_y(
    px: float, py: float, vy: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
    gravity_dir: GravityDir,
) -> tuple[float, float, bool]:
    """Resolve Y-axis collision with ground detection."""
    on_ground = False
    py += vy
    pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    for plat in platforms:
        if pr.colliderect(plat):
            if vy > 0 or (vy == 0 and gravity_dir[1] > 0):
                py = plat.top - player_h / 2
                if gravity_dir[1] > 0:
                    on_ground = True
            else:
                py = plat.bottom + player_h / 2
                if gravity_dir[1] < 0:
                    on_ground = True
            vy = 0.0
            py = round(py)
            pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    return py, vy, on_ground


def _resolve_gravity_x(
    px: float, py: float, vx: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
    gravity_dir: GravityDir,
) -> tuple[float, float, bool]:
    """Resolve X-axis collision with ground detection."""
    on_ground = False
    px += vx
    pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    for plat in platforms:
        if pr.colliderect(plat):
            if vx > 0 or (vx == 0 and gravity_dir[0] > 0):
                px = plat.left - player_w / 2
                if gravity_dir[0] > 0:
                    on_ground = True
            else:
                px = plat.right + player_w / 2
                if gravity_dir[0] < 0:
                    on_ground = True
            vx = 0.0
            px = round(px)
            pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    return px, vx, on_ground


def check_ground_adjacent(
    px: float, py: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
    gravity_dir: GravityDir,
) -> bool:
    """Check if player is touching a platform in the gravity direction.

    Uses a 1px probe rect extended in the gravity direction to detect
    adjacency without requiring overlap. Solves the colliderect gap issue.
    """
    if gravity_dir == (0, 1):  # DOWN
        probe = pygame.Rect(px - player_w / 2 + 1, py + player_h / 2, player_w - 2, 2)
    elif gravity_dir == (0, -1):  # UP
        probe = pygame.Rect(px - player_w / 2 + 1, py - player_h / 2 - 2, player_w - 2, 2)
    elif gravity_dir == (-1, 0):  # LEFT
        probe = pygame.Rect(px - player_w / 2 - 2, py - player_h / 2 + 1, 2, player_h - 2)
    elif gravity_dir == (1, 0):  # RIGHT
        probe = pygame.Rect(px + player_w / 2, py - player_h / 2 + 1, 2, player_h - 2)
    else:
        return False
    return any(probe.colliderect(plat) for plat in platforms)


def resolve_collisions(
    px: float, py: float,
    vx: float, vy: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
    gravity_dir: GravityDir,
) -> tuple[float, float, float, float, bool]:
    """Two-pass collision: lateral axis first, gravity axis second.

    Uses adjacency probe for stable ground detection.
    Returns (px, py, vx, vy, on_ground).
    """
    if gravity_is_vertical(gravity_dir):
        px, vx = _resolve_axis_x(px, py, vx, player_w, player_h, platforms)
        py, vy, on_ground = _resolve_gravity_y(
            px, py, vy, player_w, player_h, platforms, gravity_dir,
        )
    else:
        py, vy = _resolve_axis_y(px, py, vy, player_w, player_h, platforms)
        px, vx, on_ground = _resolve_gravity_x(
            px, py, vx, player_w, player_h, platforms, gravity_dir,
        )

    # Stable ground detection via adjacency probe
    if not on_ground:
        on_ground = check_ground_adjacent(
            px, py, player_w, player_h, platforms, gravity_dir,
        )

    # Zero gravity-axis velocity when grounded
    if on_ground:
        if gravity_is_vertical(gravity_dir):
            vy = 0.0
        else:
            vx = 0.0

    return px, py, vx, vy, on_ground
