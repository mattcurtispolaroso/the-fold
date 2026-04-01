"""Player movement physics — acceleration, jumping, jump cut.

All functions read gravity direction from parameters, not hardcoded axes.
"""
from __future__ import annotations

from constants import (
    ACCEL,
    AIR_ACCEL,
    AIR_DECEL,
    DECEL,
    JUMP_CUT_MULTIPLIER,
    JUMP_SPEED,
    MAX_MOVE_SPEED,
)
from src.physics.gravity import GravityDir, gravity_is_vertical, gravity_speed


def apply_lateral_movement(
    vx: float, vy: float,
    move_input: int,
    gravity_dir: GravityDir,
    on_ground: bool,
) -> tuple[float, float]:
    """Apply acceleration or deceleration along the lateral axis.

    move_input: -1, 0, or 1 along the lateral axis.
    Returns updated (vx, vy).
    """
    accel = ACCEL if on_ground else AIR_ACCEL
    decel = DECEL if on_ground else AIR_DECEL
    grav_vert = gravity_is_vertical(gravity_dir)

    if grav_vert:
        vx = _accel_decel(vx, move_input, accel, decel)
    else:
        vy = _accel_decel(vy, move_input, accel, decel)
    return vx, vy


def _accel_decel(
    vel: float, move_input: int, accel: float, decel: float,
) -> float:
    """Apply acceleration or deceleration to a single axis velocity."""
    if move_input != 0:
        vel += move_input * accel
        vel = max(-MAX_MOVE_SPEED, min(MAX_MOVE_SPEED, vel))
    else:
        if abs(vel) < decel:
            vel = 0.0
        else:
            vel -= decel if vel > 0 else -decel
    return vel


def apply_jump_impulse(
    vx: float, vy: float,
    gravity_dir: GravityDir,
) -> tuple[float, float]:
    """Apply jump velocity opposite to gravity direction."""
    vx -= gravity_dir[0] * JUMP_SPEED
    vy -= gravity_dir[1] * JUMP_SPEED
    return vx, vy


def apply_jump_cut(
    vx: float, vy: float,
    gravity_dir: GravityDir,
) -> tuple[float, float]:
    """Cut velocity for variable jump height on early key release.

    Only cuts if player is still moving against gravity.
    Returns updated (vx, vy).
    """
    going_up = gravity_speed(vx, vy, gravity_dir) < 0
    if not going_up:
        return vx, vy

    if gravity_is_vertical(gravity_dir):
        vy *= JUMP_CUT_MULTIPLIER
    else:
        vx *= JUMP_CUT_MULTIPLIER
    return vx, vy
