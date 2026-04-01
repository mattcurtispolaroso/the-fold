# Session Log — Module 1: Physics Extraction

- [T1] Audit complete — main.py inventoried, every function categorised in SESSION_PLAN.md.
- [T2] Physics constants moved to constants.py (PPM, EARTH_GRAVITY, GRAVITY_STRENGTH, TERMINAL_VELOCITY, JUMP_SPEED, ACCEL, DECEL, etc).
- [T3] src/physics/gravity.py built — gravity directions, rotate_gravity_ccw, gravity_is_vertical, gravity_speed, apply_gravity, clamp_terminal_velocity.
- [T4] src/physics/collision.py built — resolve_collisions decomposed into _resolve_axis_x/y and _resolve_gravity_x/y helpers.
- [T5] src/physics/movement.py built — apply_lateral_movement, apply_jump_impulse, apply_jump_cut.
- [T6] src/physics/__init__.py built — clean public API exporting all physics functions.
- [T7] main.py cleaned — now 190 lines, imports all physics from src.physics, no physics calculations inline.
- [T8] test_core.py updated — all imports changed from main.* to src.physics.* and constants.*. 118/118 tests pass.
