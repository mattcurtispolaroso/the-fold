"""Physics safety net: valid-position search, safe gravity rotation, post-step validation.

Implements three CLAUDE.md stability rules:
- Gravity rotation safety: never rotate into geometry; find the nearest spot
  where the rotated hitbox fits, or refuse the rotation.
- Physics validation: after every step, the player must have finite values and
  must not overlap a solid. Violations are corrected and reported.
- Floating point safety: non-finite values never propagate.

All functions are pure (no logging, no game state); callers log the returned issues.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from src.physics.collision import check_ground_adjacent, resolve_collisions
from src.physics.gravity import GravityDir, get_player_physics_size


def player_rect(px: float, py: float, w: float, h: float) -> pygame.Rect:
    """The player's collision rect, built exactly as the collision code builds it."""
    return pygame.Rect(px - w / 2, py - h / 2, w, h)


def overlaps_any(px: float, py: float, w: float, h: float, rects: list[pygame.Rect]) -> bool:
    """True if the player rect at (px, py) intersects any solid."""
    pr = player_rect(px, py, w, h)
    return pr.collidelist(rects) != -1


def find_safe_position(
    px: float, py: float, w: float, h: float,
    rects: list[pygame.Rect], max_dist: float,
) -> tuple[float, float] | None:
    """Nearest (px, py) within max_dist where a w×h player fits, else None.

    Candidates are the current position plus every combination of positions
    flush against the sides of nearby solids — exact, and far cheaper than a
    pixel grid search. Checked nearest-first.
    """
    if not overlaps_any(px, py, w, h, rects):
        return px, py
    reach = pygame.Rect(px - w / 2 - max_dist, py - h / 2 - max_dist,
                        w + 2 * max_dist, h + 2 * max_dist)
    near = [r for r in rects if r.colliderect(reach)]
    xs = {float(px)} | {r.left - w / 2 for r in near} | {r.right + w / 2 for r in near}
    ys = {float(py)} | {r.top - h / 2 for r in near} | {r.bottom + h / 2 for r in near}
    candidates = sorted(
        ((x, y) for x in xs for y in ys if math.hypot(x - px, y - py) <= max_dist),
        key=lambda c: math.hypot(c[0] - px, c[1] - py),
    )
    for x, y in candidates:
        if not overlaps_any(x, y, w, h, rects):
            return x, y
    return None


@dataclass
class RotationResult:
    """Player state after a successful gravity rotation."""

    px: float
    py: float
    vx: float
    vy: float
    w: int
    h: int
    on_ground: bool


def try_rotate(
    px: float, py: float, vx: float, vy: float,
    new_dir: GravityDir, rects: list[pygame.Rect], max_dist: float,
) -> RotationResult | None:
    """Rotate the player's hitbox to `new_dir` without entering geometry.

    Moves the player to the nearest valid spot (≤ max_dist) for the rotated
    hitbox, then runs the normal collision pass. Returns None — rotation
    refused — when the rotated hitbox fits nowhere nearby.
    """
    w, h = get_player_physics_size(new_dir)
    spot = find_safe_position(round(px), round(py), w, h, rects, max_dist)
    if spot is None:
        return None
    px, py, vx, vy, on_ground = resolve_collisions(spot[0], spot[1], vx, vy, w, h, rects, new_dir)
    on_ground = on_ground or check_ground_adjacent(px, py, w, h, rects, new_dir)
    return RotationResult(px, py, vx, vy, w, h, on_ground)


@dataclass
class ValidatedState:
    """Corrected player kinematics plus a description of every fix applied."""

    px: float
    py: float
    vx: float
    vy: float
    issues: list[str] = field(default_factory=list)


def _all_finite(*values: float) -> bool:
    """True if no value is NaN or ±inf."""
    return all(math.isfinite(v) for v in values)


def validate_player(
    px: float, py: float, vx: float, vy: float, w: float, h: float,
    rects: list[pygame.Rect], fallback: tuple[float, float], max_dist: float,
) -> ValidatedState:
    """Return a valid player state; `issues` is empty when nothing needed fixing.

    - Non-finite position → move to `fallback`, stop.  Non-finite velocity → stop.
    - Inside a solid → eject to the nearest valid spot (≤ max_dist), or to
      `fallback` if none (e.g. crushed between a platform and a wall).
    """
    state = ValidatedState(px, py, vx, vy)
    if not _all_finite(px, py):
        state.issues.append(f"non-finite position ({px}, {py}) → fallback {fallback}")
        state.px, state.py = fallback
        state.vx = state.vy = 0.0
    elif not _all_finite(vx, vy):
        state.issues.append(f"non-finite velocity ({vx}, {vy}) → zeroed")
        state.vx = state.vy = 0.0
    if overlaps_any(state.px, state.py, w, h, rects):
        spot = find_safe_position(state.px, state.py, w, h, rects, max_dist)
        if spot is None:
            state.issues.append(f"inside geometry at ({state.px:.0f}, {state.py:.0f}), "
                                f"no room within {max_dist:.0f}px → fallback {fallback}")
            state.px, state.py = fallback
            state.vx = state.vy = 0.0
        else:
            state.issues.append(f"inside geometry at ({state.px:.0f}, {state.py:.0f}) "
                                f"→ ejected to ({spot[0]:.0f}, {spot[1]:.0f})")
            state.px, state.py = spot
    return state
