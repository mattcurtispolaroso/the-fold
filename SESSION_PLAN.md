# Session Plan — Engine Foundation (audit follow-up, 2026-11-05)

Source: `docs/engine-audit-2026-11-05.md`. Three sessions, run in order, each committed separately with the full suite green. Session 3 is a refactor, so it runs on its own branch with no new features mixed in (CLAUDE.md).

---

## Session 1 — Physics hardening (bugs 1–5 plus the missing tests)

| # | Task | Acceptance |
|---|---|---|
| 1.1 | Moving platforms record their actual per-step displacement (after clamping and truncation) and their previous rect; `riding_velocity` returns that displacement | Riding through turnarounds: the player's offset on the platform stays constant (was 92↔100) |
| 1.2 | Moving platforms push the player: an overlap after platforms move is resolved along the platform's motion | Side-push scenario: player moved horizontally, y unchanged (was popped 80 px up) |
| 1.3 | Combined gravity multiplier clamped to `GRAVITY_MULT_MAX` (5×, CLAUDE.md) and logged; collision sub-steps so no pass moves more than half the player's smallest dimension | Terminal-velocity fall onto a 20 px platform lands at 1×–5× and every alignment (tunnelled at 3×). Results unchanged for normal speeds |
| 1.4 | `find_safe_position()`; rotation moves the player to the nearest valid spot, or is **refused** (no chrono cost, no cooldown) when none exists nearby | Shaft scenario: never inside geometry after any rotation |
| 1.5 | Post-step `validate_player()`: NaN/inf → restore last valid state; overlap → eject via `find_safe_position`; both logged as physics violations | Injected NaN and injected overlap are both corrected and logged |
| 1.6 | Real engine fuzz test (10k random steps across random geometry, inputs and rotations; asserts finite values and never inside geometry after every step), plus a rotation-near-geometry stress test | Both pass. They would have caught bugs 1, 2 and 4 |
| 1.7 | Small items in touched files: EPSILON zero checks in collision; cached platform-rect list; lightweight physics history (no per-step deep copy) | Suite green |

## Session 2 — Smoothness

| # | Task | Acceptance |
|---|---|---|
| 2.1 | Render interpolation: previous and current state for the player, enemies and moving platforms; GPU draw at `lerp(prev, cur, alpha)`; the camera follows the interpolated player; snaps on teleports (respawn, level load, rotation/eject move) | A frame-time simulation shows on-screen speed jitter for a constant-speed player falling to about 0 (from the measured 0/2-step judder) |
| 2.2 | vsync on and render at display rate (cap `MAX_RENDER_FPS`); physics stays a fixed 60 Hz | Real window: runs at display refresh (120 Hz here), no GL errors |
| 2.3 | Camera: `1 − exp(−k·dt)` follow, soft dead zone, smooth time-based shake noise | Same camera path at 30/60/120 fps (within tolerance); no step change at the dead-zone edge |

## Session 3 — World and determinism (refactor, own branch)

| # | Task | Acceptance |
|---|---|---|
| 3.1 | `GameState` enum replaces the state strings | No string states left in `main.py` |
| 3.2 | `InputFrame`: held keys plus edge presses sampled per frame and consumed by the fixed step (jump, jump cut, rotate, dilate no longer applied at event time) | Same input sequence gives the same result regardless of frame timing |
| 3.3 | `World` owns all simulation state; `World.step(input, PHYSICS_DT)` runs physics, enemies, abilities, items, zones, hits, falls, goal and **all gameplay timers on the fixed step**, and returns step events for presentation (feel, particles, camera) | Hitstop freezes ability/item timers too; `main()` is much shorter |
| 3.4 | `World.snapshot()` / `restore()` | Snapshot → N steps → restore → same N steps gives identical state; two runs with the same inputs are identical |
| 3.5 | Fuzz test drives the real `World.step` (replacing session 1's mirror harness) | Passes |

## Rules for the run
- `python test_game.py` after every change; fix failures before moving on.
- Plans for >3-file changes go into `DECISIONS_NEEDED.md` before coding.
- One line per completed task in `SESSION_LOG.md`.
- Creative calls (e.g. the feedback when a rotation is refused, or what happens when crushed) go to `DECISIONS_NEEDED.md`, and the most conservative option is used.
- `SUMMARY.md` at the end.
