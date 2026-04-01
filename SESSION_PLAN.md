# Session Plan — Module 2: Level Architecture

## Goal
Refactor the hardcoded level in main.py into a proper tile-based level system with JSON format, a renderer class, an ASCII-to-JSON helper tool, and full backwards compatibility.

---

## Task 1: Create Directory Structure
- Create `src/levels/`, `levels/`, `tools/`, `tests/`
- Add `__init__.py` files where needed
- **Acceptance:** Directories exist, Python can import from `src.levels`

## Task 2: Define Level Data Format
- Design JSON schema for level files
- Support: static platforms, moving platforms, spawn point, goal rect, level metadata (name, gravity start direction), tile size
- Write `src/levels/level_data.py` with dataclasses: `LevelData`, `PlatformDef`, `MovingPlatformDef`
- **Acceptance:** Dataclasses can be instantiated and serialised to/from JSON

## Task 3: Create Level Renderer
- Write `src/levels/level_renderer.py` with `LevelRenderer` class
- `load(path) -> LevelData` — reads JSON, returns populated LevelData
- `build_platforms(level_data) -> (list[Rect], list[MovingPlatform])` — creates Pygame objects
- `draw(surface, static_platforms, moving_platforms, goal_rect)` — renders level geometry
- Completely separated from main.py logic
- **Acceptance:** LevelRenderer can load a JSON file and produce the same platform list as the current hardcoded level

## Task 4: Create ASCII Level Editor Helper
- Write `tools/level_helper.py`
- Character map: `#` = solid, `M` = moving platform, `S` = spawn, `X` = goal, `.` = empty
- Moving platform properties specified in a separate dict keyed by grid position
- Outputs valid level JSON to stdout or file
- **Acceptance:** Running the helper with the test level ASCII produces a valid JSON file

## Task 5: Convert Existing Level to JSON
- Recreate the current hardcoded level as `levels/level_01.json`
- Include all 7 static platforms, 2 moving platforms, spawn point, goal rect
- Verify the JSON matches the current hardcoded geometry exactly
- **Acceptance:** JSON file exists and contains all current level geometry

## Task 6: Integrate with main.py
- main.py imports LevelRenderer, loads `levels/level_01.json`
- Remove hardcoded STATIC_PLATFORMS, GOAL_RECT, create_moving_platforms()
- MovingPlatform class stays in main.py for now (it's physics, not level data)
- All gameplay identical to current version
- **Acceptance:** Game runs, looks identical, all existing tests pass

## Task 7: Add Tests for Level System
- Test JSON loading/parsing
- Test platform generation from level data
- Test level validation (missing fields, bad data)
- Test ASCII helper conversion
- Test that level_01.json produces same geometry as old hardcoded level
- Gravity rotation stress test with loaded level
- **Acceptance:** All new + existing tests pass

## Task 8: Final Cleanup and Session Close
- Run full test suite one final time
- Update `qa_checklist.md` with level-related items
- Git commit
- Write `SUMMARY.md`

---

## Constraints
- No functions longer than 40 lines
- Type hints on all function signatures
- Dataclasses for all data structures
- No file longer than 300 lines
- Tests after every code change
- Log every step to SESSION_LOG.md
- Decisions to DECISIONS_NEEDED.md
