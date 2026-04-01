# Session Plan — Module 3: Camera System

## Goal
Build a complete camera system in `src/rendering/camera.py` with smooth follow, bounds clamping, gravity rotation handling, screen shake, and zoom foundation. Integrate into main.py.

---

## Task 1: Constants and Level Bounds Setup
- Create `constants.py` with camera constants: CAMERA_FOLLOW_SPEED, CAMERA_DEAD_ZONE_X, CAMERA_DEAD_ZONE_Y, CAMERA_RECENTRE_DURATION, SCREEN_SHAKE_ENABLED, CAMERA_ZOOM_SPEED, LAND_SHAKE_INTENSITY, LAND_SHAKE_DURATION, ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION
- Add `level_width` and `level_height` fields to `LevelData` in level_data.py
- Update `level_01.json` with level bounds (1200x900 — larger than 800x600 screen)
- Run tests, fix any failures from the new fields
- **Acceptance:** constants.py importable, LevelData has bounds, level_01.json loads with bounds, all tests pass

## Task 2: Basic Smooth Follow Camera
- Create `src/rendering/camera.py` with `Camera` class
- Properties: `x`, `y` (world position of camera centre), `offset` (returns screen offset tuple for rendering)
- `update(target_x, target_y, dt)` — lerp toward target with dead zone
- `world_to_screen(wx, wy)` — convert world coordinates to screen coordinates
- **Acceptance:** Camera follows a moving target, dead zone suppresses small movements, unit tests pass

## Task 3: Camera Bounds
- Add `set_bounds(level_width, level_height, screen_width, screen_height)` to Camera
- Camera never shows beyond level edges — clamps position so viewport stays inside level bounds
- Wire into LevelRenderer so bounds are set on load
- **Acceptance:** Camera at level edge locks rather than following player beyond, tests pass

## Task 4: Gravity Rotation Camera Handling
- Add `on_gravity_rotate()` to Camera that triggers a smooth re-centre
- Internal state: `_recentre_timer` that counts down over CAMERA_RECENTRE_DURATION
- During re-centre, follow speed is boosted so camera reaches correct position smoothly
- No snap, no jump — smooth interpolation
- **Acceptance:** After rotation, camera smoothly re-centres within 0.3s, tests pass

## Task 5: Screen Shake
- Add `shake(intensity, duration)` method to Camera
- Internal shake state: list of active shakes, each with remaining time and intensity
- `_apply_shake()` called during update — adds random offset, decays over time
- Shakes stack additively
- Controlled by SCREEN_SHAKE_ENABLED constant
- **Acceptance:** shake decays to zero, multiple shakes stack, disabled when constant is False, tests pass

## Task 6: Zoom Foundation
- Add `zoom` property and `target_zoom` setter with lerp interpolation
- `world_to_screen(wx, wy)` accounts for zoom
- Zoom is rendering-only — no physics changes
- **Acceptance:** zoom=2.0 doubles apparent size, zoom=0.5 halves it, world_to_screen correct at all zoom levels, tests pass

## Task 7: Integration with main.py
- Import Camera, create instance in main()
- Set bounds from level data
- All rendering offset by camera (level.draw, player draw, goal)
- HUD stays in screen space (not offset)
- Trigger shake on landing and gravity rotation
- Remove player-on-screen clamping (camera handles framing now)
- Run all tests
- **Acceptance:** Game runs identically but with smooth camera, all 80+ tests pass

## Task 8: Camera Tests
- Create `tests/test_camera.py` with comprehensive tests
- Test classes: smooth follow lerp, dead zone, bounds clamping, screen shake, zoom transform, gravity rotation re-centre
- **Acceptance:** All new + existing tests pass

## Task 9: Session Close
- Run full test suite
- Update qa_checklist.md
- Git commit
- Write SUMMARY.md

---

## Constraints
- No functions longer than 40 lines
- Type hints on all function signatures
- No file longer than 300 lines
- Tests after every code change
- Log every step to SESSION_LOG.md
- Decisions to DECISIONS_NEEDED.md
- Git commit after each major task
