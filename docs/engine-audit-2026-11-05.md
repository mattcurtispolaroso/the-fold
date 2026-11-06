# Engine Audit — 2026-11-05

**Scope:** the core engine under everything else: physics and collision, timestep and game loop, input, camera, entities, and the render pipeline's per-frame costs.
**Goal (Matt):** make the foundation tight, smooth, fast and elegant before layering on more content.
**Method:** I read the code, then *measured or reproduced* each finding. Every bug below was reproduced against the real engine functions, and the reproduction scripts are summarised alongside each one. Nothing here is fixed yet; this is the to-do list.

---

## Verdict

**Fast: yes, comfortably.**
- The whole game loop costs about 1.0 ms CPU per frame (profiled headless with scripted play).
- The GPU frame is about 3 ms.
- Particles at 500 cost about 1 ms CPU.
- There is no performance work worth doing yet.

**Smooth: no, measurably.** Rendering isn't interpolated between physics steps. On this Mac, 4% of frames (no vsync) to 15% (vsync) show a repeated or skipped step, which is visible judder.

**Tight: not yet.**
- Physics has five reproducible correctness bugs.
- Three CLAUDE.md stability rules aren't implemented: post-step validation, gravity-rotation safety, and the gravity cap.
- The required fuzz and rotation-stress tests don't test the engine.

**Elegant / ready for layers: partly.**
- The physics functions themselves are clean, pure and gravity-agnostic.
- But simulation state and timing are split between the fixed step and frame time, and spread across a 633-line `main()`. That blocks determinism, replay, and the planned Closed Loop rewind.

### What's good and should be kept
- The fixed 60 Hz accumulator with a 0.05 s delta-time cap.
- Pure-function physics (`apply_gravity`, `resolve_collisions`, …) with no hidden state.
- Gravity-direction-agnostic collision.
- The event bus.
- Data-driven levels and items.
- The GPU pipeline, comfortably within budget.

---

## P0 — Correctness bugs (all reproduced)

### 1. Gravity rotation can leave the player inside a wall
**Repro:** a 64×96 player standing in an 80 px-wide shaft rotates to horizontal gravity. The hitbox becomes 96×64, and after `_do_gravity_rotation`'s single collision pass the player is **still overlapping a wall** (on rotations 1 and 3 of 4).
**Why:** rotation resizes the hitbox and runs one collision pass. There's no search for a valid position, which breaks the CLAUDE.md rule "Gravity rotation safety: never rotate into an invalid state."
**Fix:** `find_safe_position()` searches outward along both axes for the nearest spot where the rotated hitbox fits. If there's none within a small radius, refuse the rotation: no cost, plus a "blocked" feedback cue.

### 2. A moving platform pushing sideways teleports the player
**Repro:** a horizontal moving platform reaches a player standing on the floor. The player isn't pushed; they **pop 80 px straight up** onto the platform's top.
**Why:** the lateral-axis pass (`_resolve_axis_x/_y`) only resolves when the player's own velocity is non-zero. A platform moving *into* a still player falls through to the gravity-axis pass, which ejects along the shortest overlap.
**Fix:** moving platforms push. Resolve the overlap along the platform's motion direction, using its per-step displacement (see bug 3).

### 3. The player slips 8 px at every platform turnaround
**Repro:** riding a platform (speed 4) through its turnarounds, the player's offset on the platform swings 92↔100, i.e. 2× speed at each reversal.
**Why:** `MovingPlatform.update()` flips `direction` in the same step it reaches a bound. `riding_velocity()` then reads the *new* direction, so the player moves the opposite way to the platform for that step. Also, `rect.x = int(_fx)` truncates while riding uses the float speed.
**Fix:** each platform records its actual displacement this step (`delta_x`, `delta_y`, after clamping and truncation), and riding uses exactly that.

### 4. No cap on gravity strength; tunnelling from about 2.7×
**Repro:** a player falling at terminal velocity onto a 20 px platform lands at every alignment up to 2.5× gravity, and **falls through at 3×** (step 132 px > 96 px player + 20 px platform).
**Why:** `gravity_mult = level × zone × singularity pressure` is unclamped (zone `strength_mult` comes straight from JSON), and terminal velocity scales with it. Collision is discrete, not swept. Today's maximum is 1.5×, so the game is safe *now*, but one 2× zone near the singularity breaks it. CLAUDE.md requires a 5× cap and swept collision.
**Fix:**
- Clamp the combined multiplier to a `GRAVITY_MULT_MAX` constant, logging the clamp as a physics violation.
- Sub-step movement so no single collision pass moves further than half the thinnest dimension. That's swept-equivalent, and safe at any speed and any future gravity.

### 5. No post-step validation or NaN/inf guard
**Why:** CLAUDE.md "Physics validation: after every physics update, validate the player state. If inside a solid, eject and log." There is no such function. A NaN anywhere (a future ability's divide, a bad JSON value) would propagate silently.
**Fix:** `validate_player(player, rects) -> list[str]`, run after every physics step. It resets non-finite values to the last valid state, ejects from geometry using bug 1's search, and logs to the physics violation log.

---

## P1 — Smoothness

### 6. No render interpolation: measured judder, plus tearing
**Measurement** (real window, the game's own loop pattern, 370 frames):

| | frame ms (min / median / max) | frames with 0 or 2 physics steps |
|---|---|---|
| no vsync (current) | 16 / 17 / 19 | **4%** (about 2–3 judders a second), plus tearing |
| vsync on | 16 / 17 / 25 | **15%** |

**Why:** the renderer draws the raw physics state. When frame time and the 60 Hz step drift apart, a frame shows the same position twice (0 steps) or jumps two steps. This display is also a 120 Hz ProMotion panel, but the game is capped at 60 fps.
**Fix (the standard one):**
- Keep the previous and current physics state for everything that moves (player, enemies, platforms).
- Render at `lerp(prev, curr, alpha)` where `alpha = accumulator / PHYSICS_DT`, with the camera following the interpolated player.
- Turn on vsync and drop the 60 fps cap, so it renders at the display rate (120 Hz on this Mac).
- Physics stays a fixed 60 Hz and fully deterministic.

### 7. Camera follow and shake depend on frame rate
- **Follow** uses `x += dx * min(speed·dt, 1)`. That isn't frame-rate independent (it converges at different rates at 60 vs 120 fps) and it clips at 1. Should be `1 − exp(−speed·dt)`.
- **The dead zone is a hard threshold.** The camera snaps from still to chasing when the player crosses it. A soft dead zone (follow strength ramps up with distance) removes the jerk.
- **Shake** picks fresh white noise every frame, so it's busier at higher frame rates and reads as jitter rather than shake. Sample smooth noise over time instead (a few sines or value noise at fixed frequencies).

---

## P2 — Foundation for layering (determinism and architecture)

### 8. Gameplay time is split between the fixed step and frame time
These advance on **frame time** (`frame_dt`), not physics steps:
- Time Dilation duration and cooldown.
- Item cooldowns (Kerr Ring, Hawking Emitter …).
- The rotation cooldown.
- The hole timer.

These run **once per frame**, after all physics steps: gravity-zone entry, enemy hit detection, hard-landing processing, goal check. And input is applied **at event time, outside any step**: jump impulse, jump cut, rotation, dilation activation.

**Consequences:**
- The same inputs don't give the same result. Simulation outcomes depend on frame timing.
- Hitstop freezes physics but not ability or item timers.
- No replay or recording is possible.
- **The planned Closed Loop rewind ("rewind the last 10 seconds of world state") can't be built.** ROADMAP Risk 3 says determinism was "locked in at M1/M2", but it isn't.

**Fix:** a single `World.step(input_frame, PHYSICS_DT)` that owns *all* simulation: physics, enemies, abilities, items, zones, hits and timers. Input is sampled into an `InputFrame` (held keys plus edge presses) that the next step consumes. Frame time drives only presentation: camera, feel, particles, animation.

### 9. Game state lives in `main()` locals and strings
- `main()` is **633 lines** and owns about 15 pieces of live game state as local variables: timers, `anomaly_pending`, `active_zone_indices`, `reward_offers`, `current_level_idx`, and so on.
- `game_state` is a string (`"playing"`, `"node_map"`, …). CLAUDE.md says to use enums and state machines.
- Every new system has to be threaded through this function, and there's nothing to snapshot.

**Fix (a refactor session):**
- A `GameState` enum plus a small screen state machine.
- A `World` dataclass (player, level, enemies, abilities, items, timers) with `snapshot()` / `restore()`.
- `main()` shrinks to: pump events → `InputFrame` → `world.step()` × n → render.

This is also what makes full-game behaviour testable headless.

### 10. Physics units are implicitly per step
Velocities are px per step (`TERMINAL_VELOCITY ≈ 44 px/frame`), gravity is px per step², and particles (since TA-7) use px/s. That's correct with a fixed step, but it's undocumented, and changing `PHYSICS_DT` would silently break everything. **Fix:** document the convention in `constants.py`, or move physics to px/s. The documentation is the cheap option.

---

## P3 — Tests that CLAUDE.md requires but are hollow or missing

- **Fuzz test:** the "10,000 iteration" tests re-implement the terminal-velocity clamp inline and never call the engine. There's no randomised physics run checking "never inside geometry, never NaN".
- **Rotation stress:** "1000 rotations" only rotates a direction tuple. No player and no geometry, so it didn't catch bug 1.
- **Memory-growth test (10-minute simulated session):** missing.
- **Regression tests for bugs 1–4:** the reproductions above become tests.

**Fix:** add a headless engine fuzz harness: random level, random inputs, random rotations, 10k steps, asserting validity after every step. It would have caught bugs 1, 2 and 4.

---

## P4 — Small and cheap (performance hygiene, no urgency)

- **11.** `SpriteBatch.flush()` converts the whole 768 KB vertex buffer to bytes, then slices it. Use `memoryview(...)[:n].tobytes()`: 0.031 ms → 0.0006 ms. `draw_fullscreen_surface` has the same pattern.
- **12.** `physics_history.append(player.to_dict())` runs `dataclasses.asdict` (a deep copy) on every physics step, only for crash logs. Store a lightweight tuple and build dicts only on crash.
- **13.** `level.all_platform_rects() + level.boundary_rects()` allocates new lists every step. Cache them; the list only changes on level load.
- **14.** Collision uses exact float zero branches (`if vx > 0 … elif vx < 0 … else`). CLAUDE.md asks for `abs(v) < EPSILON`.

---

## Recommended plan (3 focused sessions)

1. **Physics hardening** (bugs 1–5 plus P3 tests). Validation and NaN guard, safe rotation, a gravity cap with sub-stepped movement, and platform displacement, which fixes both the slip and the side-push. Every reproduction becomes a regression test, plus a real fuzz harness. *Feature-neutral; makes the engine trustworthy.*
2. **Smoothness** (6–7). Render interpolation, vsync with display-rate rendering, frame-rate-independent camera, smooth shake. *The biggest felt improvement.*
3. **World and determinism** (8–9, a refactor session per CLAUDE.md; may split in two). A `World` object, all gameplay timers on the fixed step, an input queue, a `GameState` enum, snapshot/restore. *Unlocks replays, the Closed Loop rewind and headless full-game tests.*

The P4 items fit into whichever session touches those files.
