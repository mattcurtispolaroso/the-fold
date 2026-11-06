"""Collision detection and resolution.

Two-pass system: lateral axis first, gravity axis second.
Works correctly with any gravity direction — no hardcoded assumptions.
All positions snapped to integer after collision. Ground detection uses
a separate adjacency check to avoid colliderect gap oscillation.

Tunnelling: movement is split into sub-steps no longer than
COLLISION_SUBSTEP_FRACTION × the player's smallest side, so a solid of any
thickness is always detected, at any speed (swept-equivalent).
"""
from __future__ import annotations

import math

import pygame

from constants import COLLISION_SUBSTEP_FRACTION, EPSILON
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
            if vx > EPSILON:
                px = plat.left - player_w / 2
            elif vx < -EPSILON:
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
            if vy > EPSILON:
                py = plat.top - player_h / 2
            elif vy < -EPSILON:
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
            if vy > EPSILON:
                py = plat.top - player_h / 2
                if gravity_dir[1] > 0:
                    on_ground = True
            elif vy < -EPSILON:
                py = plat.bottom + player_h / 2
                if gravity_dir[1] < 0:
                    on_ground = True
            else:
                # vy ≈ 0: use minimum penetration to avoid ejecting the wrong way.
                # This fires after a gravity rotation resizes the rect into a boundary.
                depth_from_above = pr.bottom - plat.top
                depth_from_below = plat.bottom - pr.top
                if depth_from_above <= depth_from_below:
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
            if vx > EPSILON:
                px = plat.left - player_w / 2
                if gravity_dir[0] > 0:
                    on_ground = True
            elif vx < -EPSILON:
                px = plat.right + player_w / 2
                if gravity_dir[0] < 0:
                    on_ground = True
            else:
                # vx ≈ 0: use minimum penetration to avoid ejecting the wrong way.
                # This fires after a gravity rotation resizes the rect into a boundary.
                depth_from_left = pr.right - plat.left
                depth_from_right = plat.right - pr.left
                if depth_from_left <= depth_from_right:
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


def collision_substeps(vx: float, vy: float, player_w: float, player_h: float) -> int:
    """Number of collision passes so no pass moves further than the safe step."""
    max_step = COLLISION_SUBSTEP_FRACTION * min(player_w, player_h)
    return max(1, math.ceil(max(abs(vx), abs(vy)) / max_step))


def push_out_of_movers(
    px: float, py: float,
    player_w: float, player_h: float,
    movers: list[tuple[pygame.Rect, int, int]],
) -> tuple[float, float]:
    """Push the player out of any moving platform that moved into them.

    `movers` is (rect, dx, dy) per platform for this step. The player is moved
    flush with the platform's leading edge along its dominant motion axis —
    a sideways platform shoves the player sideways instead of the gravity-axis
    pass popping them on top. Walls behind the player are handled afterwards by
    resolve_collisions and post-step validation (crush case).
    """
    for rect, dx, dy in movers:
        pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        if not pr.colliderect(rect):
            continue
        if abs(dx) >= abs(dy) and dx != 0:
            px = rect.right + player_w / 2 if dx > 0 else rect.left - player_w / 2
        elif dy != 0:
            py = rect.bottom + player_h / 2 if dy > 0 else rect.top - player_h / 2
    return px, py


def resolve_collisions(
    px: float, py: float,
    vx: float, vy: float,
    player_w: float, player_h: float,
    platforms: list[pygame.Rect],
    gravity_dir: GravityDir,
) -> tuple[float, float, float, float, bool]:
    """Two-pass collision (lateral axis first, gravity axis second), sub-stepped.

    The move is split into collision_substeps() equal parts; an axis whose
    velocity is zeroed by a hit stops moving for the remaining parts. At normal
    speeds this is a single pass. Uses an adjacency probe for stable ground
    detection. Returns (px, py, vx, vy, on_ground).
    """
    n = collision_substeps(vx, vy, player_w, player_h)
    svx, svy = vx / n, vy / n
    on_ground = False
    vertical = gravity_is_vertical(gravity_dir)
    for _ in range(n):
        if vertical:
            px, svx = _resolve_axis_x(px, py, svx, player_w, player_h, platforms)
            py, svy, hit_ground = _resolve_gravity_y(
                px, py, svy, player_w, player_h, platforms, gravity_dir,
            )
        else:
            py, svy = _resolve_axis_y(px, py, svy, player_w, player_h, platforms)
            px, svx, hit_ground = _resolve_gravity_x(
                px, py, svx, player_w, player_h, platforms, gravity_dir,
            )
        on_ground = on_ground or hit_ground
    vx, vy = svx * n, svy * n

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
