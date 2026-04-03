# Session Log — Code Quality Audit

- [T1] Removed all 0.5px hacks from collision.py. Replaced with clean integer snapping via round(). Added _check_ground_adjacent() probe — a 2px rect extended in the gravity direction detects platform adjacency without requiring colliderect overlap. This solves the oscillation without fractional offsets. 172/172 tests pass.
- [T2] Full codebase audit complete. Files audited:

## File Inventory
| File | Lines | Purpose |
|---|---|---|
| main.py | 249 | Game loop orchestrator |
| constants.py | 75 | All tunable constants |
| src/physics/gravity.py | 67 | Gravity vector system |
| src/physics/collision.py | 135 | Collision resolution |
| src/physics/movement.py | 83 | Player movement |
| src/physics/__init__.py | 32 | Physics public API |
| src/rendering/animation.py | 186 | Sprite animation |
| src/rendering/camera.py | 188 | Camera system |
| src/levels/level_renderer.py | 120 | Level geometry |
| src/levels/level_data.py | 149 | Level data structures |
| tests/test_core.py | 647 | Core game tests |
| tests/test_camera.py | 286 | Camera tests |
| tests/test_physics.py | 340 | Physics tests |
| tests/test_animation.py | 104 | Animation tests |
| test_game.py | 20 | Test runner |
| tools/level_helper.py | 181 | ASCII level converter |

## CATEGORY A — Physics Correctness Issues
- A1: main.py:156 — gravity applied every frame including when on_ground. Causes 0.136px push into platform each frame. Should skip gravity when grounded.
- A2: movement.py — no delta time applied to acceleration/deceleration. Movement is frame-rate dependent. ACCEL/DECEL are per-frame not per-second.
- A3: collision.py — no tunneling prevention. Fast objects can pass through thin platforms.
- A4: main.py:66-70 — magic numbers -1.0 and 1.0 in _determine_player_state for jump peak detection, not in constants.py.
- A5: constants.py:45 — COLLISION_EPSILON=0.1 is unused after 0.5px hack removal. Dead constant.
- A6: constants.py:68 — SETTLE_THRESHOLD=0.5 is unused. Dead constant.

## CATEGORY B — Architectural Violations
- B1: main.py:38-40 — color constants (BLACK, BLUE, GREEN) hardcoded in main.py, not in constants.py.
- B2: main.py:47-53 — load_background() is rendering logic, belongs in src/rendering/.
- B3: main.py:56-71 — _determine_player_state() mixes physics (gravity_speed) with animation state, could be in animation.py.
- B4: tests/test_physics.py — 340 lines, exceeds 300-line limit.
- B5: tests/test_core.py — 647 lines, far exceeds 300-line limit.
- B6: level_renderer.py:22-23 — color constants PLATFORM_COLOR etc hardcoded, not in constants.py.
- B7: animation.py:21-28 — FALLBACK_COLORS hardcoded, not in constants.py.
- B8: constants.py:31 — PLAYER_SIZE=90 is unused (replaced by PLAYER_SPRITE_WIDTH/HEIGHT).
- B9: constants.py:33 — MOVE_SPEED=5.0 is unused (replaced by MAX_MOVE_SPEED).
- B10: src/levels/level_renderer.py imports unused `Any` from typing.

## CATEGORY C — Dangerous Interactions
- C1: main.py:101 — on_ground from previous frame used in current frame physics. If gravity rotates mid-frame, on_ground may be stale.
- C2: main.py:173-189 — level bounds clamping uses round() comparison which could miss 0.5px differences, creating edge-case disagreement with collision system.
- C3: animation.py — sprite rotation changes surface dimensions for 90/270 degrees, but physics rect stays at PLAYER_SPRITE_WIDTH x PLAYER_SPRITE_HEIGHT. Visual and physics rects disagree in left/right gravity.
- C4: camera.py — shake offset applied to camera.offset which is used for both rendering and debug overlay, but never for physics. Safe but undocumented.

## CATEGORY D — Stability Risks
- D1: No try/except around main game loop — crash to desktop on any unhandled exception.
- D2: No crash_log.txt, performance_log.txt, or game_log.txt as defined in CLAUDE.md stability rules.
- D3: No physics watchdog monitoring update time.
- D4: LevelData.load() has no try/except — bad JSON crashes the game.
- D5: No entity count limits defined.
- D6: font = pygame.font.SysFont(None, 28) — system font may not exist on all platforms.

## CATEGORY E — Test Coverage Gaps
- E1: _check_ground_adjacent() has no dedicated tests.
- E2: Level bounds ground detection in main.py has no tests.
- E3: _determine_player_state() has no tests.
- E4: load_background() has no tests.
- E5: tools/level_helper.py has no tests.
- [T3] Fixed Category A/B issues: A1 (gravity when grounded), A4 (magic numbers), A5/A6/B8/B9 (dead constants), B10 (unused import). 172/172 pass.
- [T4] Documented 6 Category C items and 6 Category D items in DECISIONS_NEEDED.md.
- [T5] Added tests/test_ground_detection.py: 13 new tests for adjacency probe, multi-frame ground stability, _determine_player_state. 185/185 pass.
- [T6] Constants audit: removed WALK_ANIM_FPS (unused), COLLISION_EPSILON (unused), SETTLE_THRESHOLD (unused), PLAYER_SIZE (unused), MOVE_SPEED (unused). Added JUMP_RISING_THRESHOLD and JUMP_PEAK_THRESHOLD. All remaining constants verified used.
- [T7] Final verification: 185 tests pass, no 0.5px hack in codebase, all files under 300 lines (except test files).
