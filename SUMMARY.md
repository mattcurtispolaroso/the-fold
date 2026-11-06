# Session Summary — Engine Foundation (2026-11-05)

Follow-up to `docs/engine-audit-2026-11-05.md`. Three sessions run in order, each committed with the full suite green:

| Commit | Session |
|---|---|
| `fe6692d` | 1 — Physics hardening |
| `e433f0f` | 2 — Smoothness |
| `42e2d50` | 3 — World and determinism (refactor; on a branch, then fast-forwarded to main) |

**Tests:** 770 → **814**, all passing.

---

## What was completed

### Session 1 — Physics hardening (all 5 audit bugs fixed)
- **Gravity rotation never enters geometry.** The player is moved to the nearest spot where the rotated hitbox fits. If there's none, the rotation is refused: no chrono cost, no cooldown, a tiny "blocked" shake.
- **Moving platforms push the player** sideways instead of teleporting them on top.
- **No slip at platform turnarounds.** Riding uses the platform's real per-step displacement, and fast vertical platforms carry the player.
- **Gravity is capped at 5×** and logged when clamped. Collision is sub-stepped, so nothing tunnels at any speed.
- **Post-step validation** fixes NaN and in-geometry states and logs them as `PHYSICS VIOLATION` in `logs/crash_log.txt`.
- **A real engine fuzz test,** mutation-tested: it fails when the old bugs are put back.

### Session 2 — Smoothness
- **Render interpolation** between 60 Hz physics steps for the player, enemies and platforms. On-screen motion is more than 5× steadier on measured jittery frame times.
- **vsync on,** and the render cap raised from 60 to 240. The physics rate is unchanged.
- **The camera is frame-rate independent:**
  - Follow and zoom ease the same way at any frame rate.
  - A continuous dead zone, so there's no jolt when the camera starts following.
  - The post-rotation re-centre truly centres.
  - Shake is smooth noise rather than per-frame jitter.

### Session 3 — World and determinism
- **`World.step(InputFrame)`** owns all simulation on the fixed step, including ability, item and cooldown timers, so hitstop now freezes them too.
- **Input is buffered and applied by the physics step,** so results don't depend on frame timing.
- **A `GameState` enum** replaces the string states.
- **`main()` went from 633 lines to 38.**
- **`snapshot()` / `restore()`:** identical inputs give identical results, outcomes match at 30, 60 and 144 fps, and replays reproduce exactly. **The Closed Loop rewind is now buildable.**

### Bugs found along the way (beyond the audit)
1. **The Penrose Diagram and Event Horizon never worked in real play.** The item system held a stale run-state object after every run start. Fixed.
2. **Levels 05–08 spawn the player 18 px inside the floor.** The engine now corrects respawns.
3. **Respawn never refreshed the "last safe position"** used as the crush fallback. Fixed.
4. **Nested GPU timer queries could raise GL errors** (found in TA-7). Made safe.

---

## What was skipped, and why
- **The load-time clamp on gravity-zone JSON.** `level_data.py` is at 295 of its 300 lines, and the runtime clamp on the combined multiplier already covers every source.
- **Old unused imports in 8 files** outside these sessions. Harmless, and left so the refactor didn't touch unrelated files.
- **120 Hz on the MacBook's own screen.** macOS only gives windowed OpenGL 60 Hz; 120 Hz on ProMotion is Metal-only. External 120/144 Hz monitors, and Windows, now run at full rate.

---

## Needs human review (Matt)
1. **Two design calls made conservatively** (`DECISIONS_NEEDED.md`, Session 1):
   - A refused rotation costs nothing and gives a tiny shake.
   - Being crushed by a platform puts you back at your last safe spot **with no damage**. Should crushing cost integrity?
2. **Level data:** should levels 05–08's `"spawn"` y-value change from 790 to 772? The engine compensates either way.
3. **Feel check in play:**
   - Is jump, rotate and dilate still as responsive? They're now applied at the next 60 Hz step, at most 16 ms later.
   - Is motion visibly smoother?
   - Is the new camera dead zone and shake right?
4. **`qa_checklist.md`** has new sections for all three sessions. Penrose and Event Horizon especially are worth a first real test.

---

## What the next session should tackle
- **Play it.** These sessions changed how the game *feels* (smoothness, camera, input timing). A 10-minute run is the real test.
- **Then back to the game.** The foundation is now sound for layering. Strong options:
  - The M4 external playtest kit.
  - Audio v1 (the game is still silent).
  - **The Closed Loop rewind.** It's a planned ultimate, and with `World.snapshot()` it's now a natural next feature: keep a ring buffer of snapshots and restore one 10 s back.
