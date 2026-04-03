# Session Plan — Stability Infrastructure

## Goal
Build crash handler, logging, physics watchdog, level load error handling, bundled font, entity limits. No gameplay changes.

## Tasks
1. Create src/systems/logging_manager.py — 3 log files, rotation, crash logging
2. Wrap main game loop in try/except — crash handler with physics frame history
3. Physics watchdog — timer around physics step, warning on slow frames
4. Level load error handling — try/except on JSON, fallback level
5. Bundle a font in assets/fonts/
6. Entity count limits in constants.py
7. F-key audit — confirm no F1-F12 usage
8. Tests in tests/test_stability.py — 10+ new tests
9. Cleanup — file lengths, commit, SUMMARY.md
