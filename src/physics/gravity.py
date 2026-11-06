"""Gravity direction system and gravity-related physics.

All gravity calculations read from a direction vector tuple (dx, dy).
No hardcoded direction assumptions — works for all 4 orientations.
"""
from __future__ import annotations

from constants import (
    GRAVITY_MULT_MAX,
    GRAVITY_MULT_MIN,
    GRAVITY_STRENGTH,
    PEAK_GRAVITY_MULT,
    PEAK_SPEED_THRESHOLD,
    PLAYER_PHYSICS_HEIGHT_HORIZONTAL,
    PLAYER_PHYSICS_HEIGHT_NORMAL,
    PLAYER_PHYSICS_WIDTH_HORIZONTAL,
    PLAYER_PHYSICS_WIDTH_NORMAL,
    TERMINAL_VELOCITY,
)

# Gravity direction constants — unit vectors.
GRAVITY_DOWN: tuple[int, int] = (0, 1)
GRAVITY_LEFT: tuple[int, int] = (-1, 0)
GRAVITY_UP: tuple[int, int] = (0, -1)
GRAVITY_RIGHT: tuple[int, int] = (1, 0)

GravityDir = tuple[int, int]

GRAVITY_LABELS: dict[GravityDir, str] = {
    GRAVITY_DOWN: "Down",
    GRAVITY_LEFT: "Left",
    GRAVITY_UP: "Up",
    GRAVITY_RIGHT: "Right",
}


def rotate_gravity_ccw(gravity_dir: GravityDir) -> GravityDir:
    """Rotate gravity 90 degrees counter-clockwise in screen coordinates."""
    dx, dy = gravity_dir
    return (dy, -dx)


def get_player_physics_size(gravity_dir: GravityDir) -> tuple[int, int]:
    """Return (width, height) for the player physics rect given gravity direction."""
    if gravity_is_vertical(gravity_dir):
        return (PLAYER_PHYSICS_WIDTH_NORMAL, PLAYER_PHYSICS_HEIGHT_NORMAL)
    return (PLAYER_PHYSICS_WIDTH_HORIZONTAL, PLAYER_PHYSICS_HEIGHT_HORIZONTAL)


def gravity_is_vertical(gravity_dir: GravityDir) -> bool:
    """True if gravity pulls along the Y axis."""
    return gravity_dir[1] != 0


def gravity_speed(vx: float, vy: float, gravity_dir: GravityDir) -> float:
    """Return velocity component along the gravity axis (dot product)."""
    return vx * gravity_dir[0] + vy * gravity_dir[1]


def combined_gravity_mult(
    level_mult: float, zone_mult: float, pressure_mult: float,
) -> tuple[float, bool]:
    """Product of every gravity multiplier, clamped to [GRAVITY_MULT_MIN, GRAVITY_MULT_MAX].

    Returns (multiplier, was_clamped) so the caller can log the violation.
    Terminal velocity scales with this, so the cap also bounds fall speed.
    """
    raw = level_mult * zone_mult * pressure_mult
    clamped = max(GRAVITY_MULT_MIN, min(GRAVITY_MULT_MAX, raw))
    return clamped, abs(clamped - raw) > 1e-9


def apply_gravity(
    vx: float, vy: float,
    gravity_dir: GravityDir,
    on_ground: bool,
    strength_mult: float = 1.0,
) -> tuple[float, float]:
    """Apply gravity to velocity with peak multiplier for weighty jumps.

    strength_mult scales the base gravity — used for level gravity_multiplier
    and singularity pressure scaling.
    """
    grav_vel = gravity_speed(vx, vy, gravity_dir)
    at_peak = not on_ground and abs(grav_vel) < PEAK_SPEED_THRESHOLD
    mult = PEAK_GRAVITY_MULT if at_peak else 1.0
    vx += gravity_dir[0] * GRAVITY_STRENGTH * mult * strength_mult
    vy += gravity_dir[1] * GRAVITY_STRENGTH * mult * strength_mult
    return vx, vy


def clamp_terminal_velocity(
    vx: float, vy: float,
    gravity_dir: GravityDir,
    strength_mult: float = 1.0,
) -> tuple[float, float]:
    """Clamp gravity-axis velocity to terminal velocity, preserving lateral.

    strength_mult scales the cap proportionally with gravity strength.
    """
    effective_tv = TERMINAL_VELOCITY * strength_mult
    grav_component = gravity_speed(vx, vy, gravity_dir)
    if abs(grav_component) > effective_tv:
        clamped = max(-effective_tv, min(effective_tv, grav_component))
        diff = clamped - grav_component
        vx += diff * gravity_dir[0]
        vy += diff * gravity_dir[1]
    return vx, vy
