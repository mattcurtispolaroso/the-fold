# Session Log — Stability Infrastructure

- [T1] Created src/systems/logging_manager.py — LoggingManager with game_log.txt, performance_log.txt, crash_log.txt. Rotation at 10MB. All file ops wrapped in try/except.
- [T2] Wrapped main game loop in try/except. Catches all exceptions, writes crash report with traceback + player state + last 50 physics frames. Graceful pygame shutdown in finally block.
- [T3] Physics watchdog — time.perf_counter() around physics step. Logs warning if >16ms, CRITICAL if 3 consecutive. PHYSICS_WATCHDOG_THRESHOLD_MS and PHYSICS_WATCHDOG_ENABLED in constants.py.
- [T4] Level load fallback — LevelData.load() wrapped in try/except. Malformed/missing JSON falls back to LevelData.fallback() (single flat platform). Added LevelLoadError exception class.
- [T5] Font infrastructure — FONT_PATH and FONT_SIZE in constants.py, _load_font() in main.py tries bundled font first, falls back to SysFont. assets/fonts/ directory created.
- [T6] Entity count limits — MAX_ENEMIES=20, MAX_PARTICLES=500, MAX_PROJECTILES=50, MAX_ACTIVE_ABILITIES=10 in constants.py.
- [T7] F-key audit — no F1-F12 usage found. Debug overlay correctly on backtick.
- [T8] tests/test_stability.py — 20 new tests covering logging, rotation, crash resilience, level fallback, watchdog constants, entity limits. 214/214 pass.
- [T9] main.py trimmed to 296 lines (<300). All files under limit. logs/ added to .gitignore.

## 2026-04-10 — Helmet Overlay Position Fix

### Audit Findings
- **Bug:** Helmet overlay appears at wrong position (feet/mid-body) in non-DOWN gravity.
- **Root cause:** `HelmetOverlay.draw()` applies HELMET_HEAD_OFFSET_X (0) and HELMET_HEAD_OFFSET_Y (-10) as fixed screen-space offsets from sprite centre. Only correct for gravity DOWN.
- Gravity UP: head at bottom, but offset pushes overlay upward (to feet area).
- Gravity LEFT: head at right, but offset pushes overlay upward (mid-body).
- Gravity RIGHT: head at left, but offset pushes overlay upward (mid-body).
- Placeholder path also hardcodes position at top of unrotated sprite, rotates surface shape but not draw position.
- **Fix:** Calculate head offset as `(-gravity_dir * HEAD_DIST)` — always opposite to gravity direction.
- Fixed HelmetOverlay.draw() — head position now computed via `head_position()` static method using gravity vector.
- Added HELMET_HEAD_DISTANCE constant (0.35 = fraction of sprite height from centre to head).
- Reset HELMET_HEAD_OFFSET_Y to 0 (was -10, which was a workaround for the old broken positioning).
- Added debug cyan dot at head position when backtick debug mode is active.
- Added 7 new tests for head positioning in all 4 gravity orientations + debug dot.
- All 253 tests pass.
