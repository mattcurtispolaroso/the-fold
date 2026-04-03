"""Physics module for The Fold.

Public API — import everything main.py and other modules need from here.
"""
from src.physics.collision import check_ground_adjacent, resolve_collisions
from src.physics.gravity import (
    GRAVITY_DOWN,
    GRAVITY_LABELS,
    GRAVITY_LEFT,
    GRAVITY_RIGHT,
    GRAVITY_UP,
    GravityDir,
    apply_gravity,
    get_player_physics_size,
    clamp_terminal_velocity,
    gravity_is_vertical,
    gravity_speed,
    rotate_gravity_ccw,
)
from src.physics.movement import (
    apply_jump_cut,
    apply_jump_impulse,
    apply_lateral_movement,
)

__all__ = [
    "GRAVITY_DOWN", "GRAVITY_LEFT", "GRAVITY_UP", "GRAVITY_RIGHT",
    "GRAVITY_LABELS", "GravityDir",
    "rotate_gravity_ccw", "gravity_is_vertical", "gravity_speed",
    "apply_gravity", "clamp_terminal_velocity", "get_player_physics_size",
    "check_ground_adjacent", "resolve_collisions",
    "apply_lateral_movement", "apply_jump_impulse", "apply_jump_cut",
]
