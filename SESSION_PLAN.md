# Session Plan — Module 1: Physics Extraction

## Goal
Extract all physics code from main.py into src/physics/. Pure refactor — identical behaviour.

---

## Task 1: Audit main.py

### Inventory of main.py (357 lines)

**Physics constants (lines 19-38) → constants.py**
- PPM, EARTH_GRAVITY, GRAVITY_STRENGTH, TERMINAL_VELOCITY
- JUMP_SPEED, MOVE_SPEED, ACCEL, DECEL, AIR_ACCEL, AIR_DECEL, MAX_MOVE_SPEED
- COYOTE_TIME, JUMP_CUT_MULTIPLIER, PEAK_GRAVITY_MULT

**Gravity direction constants (lines 47-58) → src/physics/gravity.py**
- GRAVITY_DOWN, GRAVITY_LEFT, GRAVITY_UP, GRAVITY_RIGHT, GRAVITY_LABELS

**Physics functions (lines 65-141) → src/physics/**
- `rotate_gravity_ccw()` → src/physics/gravity.py
- `gravity_is_vertical()` → src/physics/gravity.py
- `gravity_speed()` → src/physics/gravity.py
- `resolve_collisions()` → src/physics/collision.py

**Rendering functions (lines 143-160) → stay (asset loading)**
- `load_player_sprite()` — rendering logic, stays in main.py for now
- `load_background()` — rendering logic, stays in main.py for now

**Inline physics in main loop (lines 234-297) → src/physics/movement.py**
- Movement accel/decel (lines 234-267)
- Gravity application + peak mult (lines 269-274)
- Terminal velocity clamping (lines 276-282)
- Jump impulse (lines 216-220) — orchestration, stays
- Jump cut (lines 222-229) — uses physics helpers, stays as orchestration
- Coyote timer (lines 293-297) — stays as orchestration

**Orchestration (stays in main.py)**
- pygame init, display setup, asset loading
- Main game loop, event handling, draw calls
- Camera integration, level loading

## Task 2: constants.py — move physics constants
- **Acceptance:** All physics constants in constants.py. main.py imports from there. 118 tests pass.

## Task 3: src/physics/gravity.py
- Gravity direction constants + GRAVITY_LABELS
- `rotate_gravity_ccw()`, `gravity_is_vertical()`, `gravity_speed()`
- `apply_gravity()` — gravity + peak multiplier
- `clamp_terminal_velocity()` — vector clamping
- **Acceptance:** All gravity functions importable, type hints, docstrings, 118 tests pass.

## Task 4: src/physics/collision.py
- `resolve_collisions()` — exact same logic, moved
- **Acceptance:** Collision works in all 4 orientations, 118 tests pass.

## Task 5: src/physics/movement.py
- `apply_lateral_movement()` — accel/decel logic extracted
- `apply_jump_impulse()` — jump velocity calculation
- `apply_jump_cut()` — variable jump height cut
- **Acceptance:** Movement functions importable, 118 tests pass.

## Task 6: src/physics/__init__.py
- Clean public API exporting all physics functions.
- **Acceptance:** `from src.physics import ...` works for everything main.py needs.

## Task 7: Clean main.py
- Import from src/physics/, remove inline physics.
- Target: under 200 lines (150 is aggressive given rendering is still inline).
- **Acceptance:** No physics calculations in main.py. All tests pass.

## Task 8: Update existing tests
- Tests import from src.physics instead of main for physics functions.
- Constants tests import from constants.
- **Acceptance:** 118 tests pass, all importing from correct modules.

## Task 9: New physics tests (tests/test_physics.py)
- 20+ new tests for the extracted physics API.
- **Acceptance:** Total test count >= 138.

## Task 10: Final cleanup, commit, SUMMARY.md
