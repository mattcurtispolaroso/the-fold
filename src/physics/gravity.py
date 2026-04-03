"""Gravity direction system and gravity-related physics.

All gravity calculations read from a direction vector tuple (dx, dy).
No hardcoded direction assumptions — works for all 4 orientations.
"""
from __future__ import annotations

from constants import (
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


def apply_gravity(
    vx: float, vy: float,
    gravity_dir: GravityDir,
    on_ground: bool,
) -> tuple[float, float]:
    """Apply gravity to velocity with peak multiplier for weighty jumps."""
    grav_vel = gravity_speed(vx, vy, gravity_dir)
    at_peak = not on_ground and abs(grav_vel) < PEAK_SPEED_THRESHOLD
    mult = PEAK_GRAVITY_MULT if at_peak else 1.0
    vx += gravity_dir[0] * GRAVITY_STRENGTH * mult
    vy += gravity_dir[1] * GRAVITY_STRENGTH * mult
    return vx, vy


def clamp_terminal_velocity(
    vx: float, vy: float,
    gravity_dir: GravityDir,
) -> tuple[float, float]:
    """Clamp gravity-axis velocity to terminal velocity, preserving lateral."""
    grav_component = gravity_speed(vx, vy, gravity_dir)
    if abs(grav_component) > TERMINAL_VELOCITY:
        clamped = max(-TERMINAL_VELOCITY, min(TERMINAL_VELOCITY, grav_component))
        diff = clamped - grav_component
        vx += diff * gravity_dir[0]
        vy += diff * gravity_dir[1]
    return vx, vy
