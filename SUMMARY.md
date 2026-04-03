# Session Summary — Fix C1 and C3

## What Was Fixed

### C3: Physics rect dimensions in horizontal gravity
- Added 4 physics size constants to constants.py (PLAYER_PHYSICS_WIDTH/HEIGHT_NORMAL and _HORIZONTAL)
- Added `get_player_physics_size(gravity_dir)` to src/physics/gravity.py
- main.py recomputes player_w/player_h on every gravity rotation with centre preservation
- Sprite rendering uses PLAYER_SPRITE_WIDTH/HEIGHT (visual), physics uses get_player_physics_size() (collision)
- Physics rect is now 64x96 for DOWN/UP, 96x64 for LEFT/RIGHT

### C1: Stale on_ground after gravity rotation
- Renamed `_check_ground_adjacent` → `check_ground_adjacent` (public API)
- After gravity rotation in main.py, immediately probes ground adjacency with new gravity_dir and new rect dimensions
- Sets on_ground, coyote_timer, jumping correctly before next physics step
- Eliminates single-frame gravity skip/apply error after rotation

## Files Modified
- constants.py — added 4 physics size constants
- src/physics/gravity.py — added get_player_physics_size()
- src/physics/collision.py — renamed check_ground_adjacent to public
- src/physics/__init__.py — exported check_ground_adjacent and get_player_physics_size
- main.py — dynamic physics rect sizing, on_ground recompute after rotation
- tests/test_ground_detection.py — updated imports, added 9 new tests

## Test Count
- Before: 185
- After: 194
- All passing

## What Was NOT Changed
- No rendering code modified
- PLAYER_SPRITE_WIDTH/HEIGHT unchanged
- No new features added
