# Session Log — Fix C3: Physics Rect Swap

- [1] Added PLAYER_PHYSICS_WIDTH_NORMAL=64, PLAYER_PHYSICS_HEIGHT_NORMAL=96, PLAYER_PHYSICS_WIDTH_HORIZONTAL=96, PLAYER_PHYSICS_HEIGHT_HORIZONTAL=64 to constants.py.
- [2] Added get_player_physics_size(gravity_dir) to src/physics/gravity.py — returns (w,h) based on gravity direction. Exported from __init__.py.
- [3] Updated main.py: player_w/player_h computed from get_player_physics_size() at init and swapped on every R press. Position rounded to integer on swap. Sprite draw uses animator.width/height (visual), physics uses player_w/player_h (collision).
- [4] Added 5 tests for get_player_physics_size() in test_ground_detection.py. 190/190 tests pass.
- [5] Fix C1: Renamed _check_ground_adjacent → check_ground_adjacent (public API). Exported from __init__.py. In main.py rotation block, immediately call check_ground_adjacent() after rect resize with new gravity_dir and new player_w/player_h. Sets on_ground, coyote_timer, jumping correctly before next physics step.
- [6] Added 4 new tests: on_ground recompute after rotation (3 scenarios), no-clip during rotation (1). 194/194 tests pass.
