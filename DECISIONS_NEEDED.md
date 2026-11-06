# Decisions Needed — Code Quality Audit

---

## Engine Session 3 — World and determinism (plan, 2026-11-05)

**Refactor session on branch `refactor/world-determinism`. Touches more than 3 files.** Source: engine audit items 8–9.

### New modules
- `src/systems/game_state.py`: `GameState` enum (START, NODE_MAP, PLAYING, REWARD, HOLE_ENCOUNTER, DEAD, WIN) replaces the string states.
- `src/systems/input_frame.py`: `InputFrame` (held move axes plus edge presses: jump, jump release, rotate, dilate) and `InputBuffer`. Edge presses accumulate until a physics step consumes them, so a press is never lost on a frame with no step (hitstop, or 120 Hz frames).
- `src/systems/world.py`: `World` owns all simulation state: player, level, enemies, run state, Time Dilation, items, rotation cooldown, active zones, the anomaly flag. Provides `load_level()`, `new_run()` (updates `RunState` **in place**), `step(input) -> StepEvents`, and `snapshot()` / `restore()`.
- `src/systems/world_phases.py`: the step, split into phases of 40 lines or fewer: timers, zones, input, integrate, hazards, goal.

### Behaviour changes (intended; these are the point)
- **All gameplay timers run on the fixed step:** Time Dilation, item cooldowns, rotation cooldown. Hitstop now freezes them too.
- **Input (jump, jump cut, rotate, dilate) is applied at the next physics step,** not at key-event time. That's at most one 16 ms step later.
- **Gravity zones, hits, falls, hard landings, snap-back and the goal are checked every step,** not once per frame.
- **Presentation (feel, particles, camera, flashes, animation) reacts to the `StepEvents` that `World.step` returns,** so simulation never calls rendering.

### Bug fixed as a side effect (found while reading)
- **The Penrose Diagram and Event Horizon never worked in real play.** `main` replaced `run_state` with a new object on every run start, while `ItemManager` and its effect context kept the old one, so those effects wrote to a stale object. Reproduced: after Penrose fired, the live `extra_reward_options` was 0 and the stale object's was 1. `World.new_run()` updates the run state in place.

### Snapshot design
Explicit, per component, restored **in place** so every cross-reference stays valid (event-bus subscriptions, item context, cached collision rects):
- `__dict__` copies for the player, run state, Time Dilation and enemies (including each enemy's RNG).
- Field copies for moving platforms; their rects are updated in place.
- `ItemManager.snapshot_state()` / `restore_state()` (cooldowns, counters, RNG state).
- World scalars.

A snapshot is only valid within the same level load; restoring across loads raises.

### Found during the session (needs a look, Matt)
- **Levels 05–08 spawn at y=790, 18 px inside the floor** (level_01 uses 772 for the same floor). The engine now nudges respawns to the nearest valid spot, so nothing is broken, but the JSON should probably say `"spawn": [100.0, 772.0]`. I left the level files untouched because they're your data.
- **Old unused imports in 8 files outside this refactor** (`level_renderer`, `spacetime`, `events`, `logging_manager`, `effects`, `offers`, `data/items`). Harmless; a one-minute cleanup whenever.

---

## Engine Session 2 — Smoothness (plan, 2026-11-05)

**Touches more than 3 files.** Source: engine audit items 6–7.

- **`src/rendering/interpolation.py` (new):** `RenderInterpolator` records each entity's position at the start of every physics step (player, enemies keyed per object; platforms reuse `prev_rect` from session 1). It returns lerped positions at `alpha = accumulator / PHYSICS_DT`. It snaps (prev = current) on level reset, and automatically on any jump larger than `TELEPORT_SNAP_PX`, so respawns never streak across the screen.
- **`world_draw.py` / `hud.draw_world`:** draw at interpolated positions. The GPU path does player, enemies and moving platforms; the software path does the player, so it doesn't jitter against the now-smooth camera.
- **Camera:** follows the interpolated player. `1 − exp(−k·dt)` follow, a continuous ("window") dead zone, and time-based smooth shake noise.
- **`main.py`:** vsync on (GPU path; falls back cleanly if unsupported), render cap `MAX_RENDER_FPS` instead of 60. Physics stays a fixed 60 Hz.
- **Tests:** a frame-time judder simulation (raw vs interpolated), camera frame-rate independence, dead-zone continuity, snap on teleport.

No creative decisions involved.

---

## Engine Session 1 — Physics hardening (plan, 2026-11-05)

**Touches more than 3 files.** Source: `docs/engine-audit-2026-11-05.md` bugs 1–5. Matt approved ("do it in that order").

**Files:** `constants.py`, `src/levels/level_renderer.py` (platform displacement, prev rect, mover list, cached collision rects), `src/levels/level_data.py` (clamp zone strength / level gravity on load), `src/physics/collision.py` (sub-stepping, platform push, EPSILON), `src/physics/gravity.py` (`combined_gravity_mult`), `src/physics/validation.py` (new: `find_safe_position`, `try_rotate`, `validate_player`), `src/systems/logging_manager.py` (`log_physics_violation`), `main.py` (wire in), tests.

**Creative calls — conservative defaults used, please confirm:**
1. **Refused rotation** (no room for the rotated hitbox): no chrono cost, no cooldown, gravity unchanged, plus a tiny camera shake as "blocked" feedback. *Alternatives: a distinct sound or flash later, or allow a partial rotation.*
2. **Crushed** (a moving platform pushes the player into a wall and there's no valid spot within the search radius): the player is placed at their last safe ground position with **no damage**. *Alternative: crushing costs 1 integrity, like a fall. That's a design choice, so I didn't make it.*

---

## Refactor: split oversized render modules (plan, 2026-11-05)

**Touches more than 3 files. Pure refactor: no behaviour change.** Matt chose a refactor session. Work happens on branch `refactor/render-module-split`.

| Change | Files |
|---|---|
| Move `gpu_draw_world` and its helpers out of `sprite_batch.py` into `gpu/world_draw.py`, and split it into functions under 40 lines (zones, platforms+goal, enemies, player) | `sprite_batch.py`, `world_draw.py` (new), `main.py` |
| Public `load_shader()` in a new `gpu/shader_source.py`, replacing the private `sprite_batch._load_shader` that 4 modules import | `shader_source.py` (new), `sprite_batch.py`, `layer.py`, `light_buffer.py`, `post_stack.py`, `particles.py` |
| Move the 6 full-screen menus from `hud.py` into `rendering/screens.py`. Split `draw_reward_screen` and `draw_node_map` under 40 lines, and share the duplicated run-stats / all-time-best blocks between the death and win screens (same pixels, positions passed in) | `hud.py`, `screens.py` (new), `main.py` |

**Out of scope (noted, not done):**
- `main()` is far over 40 lines. It's the orchestrator, and splitting it is a much bigger, riskier job than this session.
- Hard-coded colours and y positions in the menu screens should eventually become constants. That's a separate task.

**Verification:** the test suite, plus reference renders captured *before* the change and compared byte for byte afterwards: all 6 menus in several states, HUD variants, flash/tint/debug overlays, the software world draw, and the GPU playfield with and without feel effects.

---

## TA-7 — GPU Particles (plan, 2026-11-05)

**Touches more than 3 files.** The spec is approved in `docs/tech-art-plan.md` §3 TA-7. Matt said "next".

### Problems found first
1. **The GPU renderer draws no particles at all** (since TA-1). The rotation burst, hit spark and landing dust are only visible in software mode.
2. **`ParticlePool.update` ignores delta time.** It does `px += vx` per frame, so particles move twice as fast at 120 fps as at 60. This breaks the delta-time rule in CLAUDE.md.
3. **Emitter speeds, lifetimes and colours are magic numbers** inside `vfx.py`.
4. **Hit sparks fire only on hard landings**, never when an enemy hits the player.

### Approach
- **`vfx.py`:**
  - Velocities in px/s, with per-particle acceleration (sparks fall along the player's gravity) and drag.
  - Size goes from a birth size to a death size: bursts and sparks shrink, dust puffs grow.
  - A per-particle `glow` flag.
  - Emitters read effect specs (count, speed range, life, sizes, drag, gravity, glow, colours) from `constants.py`.
  - New `write_instances(buffer, offset)` packs active particles for the GPU, with no GL code in `vfx.py`.
  - Software `draw` is kept, using the new fields.
- **`src/rendering/gpu/particles.py` (new):** `ParticleRenderer`. One instanced draw call for every active particle: a unit quad plus a per-instance buffer of position, size, colour, alpha and glow. It counts draw calls for the test.
  - *Spec deviation:* this is its own module rather than an instanced path inside `sprite_batch.py`, which is already over the 300-line limit.
- **`shaders/particle.vert/.frag` (new):** soft round particles. Glow particles have a hot core and blend additively (alpha 0 under premultiplied blending), so additive and normal particles share one draw call. Bloom picks up the bright ones.
- **Particles draw into the play layer** after the sprites, so they parallax and zoom with the world. That also means they're lit by the light buffer, which is correct for dust; glow particles are bright enough to survive it. An unlit fx layer could come later if needed.
- **Visual upgrade (spec):**
  - Rotation burst: a tight-speed amber *ring*.
  - Hit spark: fast red-orange sparks that fall with gravity.
  - Landing dust: a grey fan that puffs out and slows.
- **`VFX_POOL_SIZE` goes from 200 to 500** (`MAX_PARTICLES`). The pool is still fixed-size and recycles the oldest; there is no allocation during play.
- **`main.py`:** draws particles on the GPU path, and fires hit sparks on enemy hits as well as hard landings, falling with the player's gravity.
- **`tools/shader_watch.py`:** pairs `particle.frag` with `particle.vert`.

### Files
`constants.py`, `src/rendering/vfx.py`, `src/rendering/gpu/particles.py` (new), `shaders/particle.vert` + `particle.frag` (new), `main.py`, `tools/shader_watch.py`, `tests/test_gpu_particles.py` (new).

---

## TA-6 — Feel Framework (plan, 2026-11-05)

**Touches more than 3 files.** The spec is approved in `docs/tech-art-plan.md` §3 TA-6. Matt said "next" after the rotation zoom.

### Approach
`Feel` becomes the single entry point for game feel, with each effect as a small component (composition) in a new `src/rendering/gpu/feel_effects.py`:
- **`Hitstop`:** `feel.hitstop(dur)`. `feel.physics_time(frame_dt)` returns 0 while frozen, so the fixed-step accumulator gets nothing and physics stops exactly. If the hitstop ends mid-frame, the remainder carries on. Overlapping hitstops take the longest, not the sum, and duration is clamped.
- **`SpriteFlash`:** `feel.flash(color, dur)`. A white flash on hit, an amber flash when Time Dilation starts (the exosuit colour).
- **`Squash`:** `feel.squash(amount)`. Positive squashes along gravity and negative stretches, scaled to roughly preserve area, decaying back to 1. Triggered by landing, a harder landing, and jumps.
- **Camera:** `feel.shake(intensity, duration)`, `feel.punch(dx, dy, duration)` and `feel.rotation_cinematic()` forward to `Camera`, scaled by intensity. They replace the two direct calls in `main.py`.
- **`feel.intensity`:** 1.0 normally, 0.3 in **reduced-effects mode**. It scales shake, punch, hitstop, sprite flash, squash, ripple, bend, aberration and the full-screen rotation/impact flashes. Reduced mode also skips the rotation zoom. The default comes from `ACCESSIBILITY_REDUCED_EFFECTS` in `constants.py`; with F3 open, key 0 toggles it and the overlay shows its state.

### Hooks in main.py
- **Enemy hit (not cancelled):** hitstop 0.06 s, white flash, small shake.
- **Hard landing:** hitstop 0.04 s, strong squash, punch through feel.
- **Normal landing:** squash.
- **Jumps:** stretch. That's both jump sites: the key press and the buffered jump.
- **Time Dilation starts:** amber flash (alongside the existing ripple).
- **Rotation:** shake and zoom through feel.

### Rendering
Sprite flash and squash are drawn on the **GPU path only**. `sprite.vert/frag` gain an `a_flash` (rgb, amount) vertex attribute; `gpu_draw_world` scales the player quad and keeps the feet planted. The software renderer gets hitstop, shake, punch and the intensity scaling, but not flash or squash. Software is CI-only (Q3 recommendation); revisit if Q3 decides otherwise.

### Spec deviations (conservative)
- **`feel.shake` keeps the camera's existing intensity/duration shake** rather than a new trauma model. Swapping the shake model would be a refactor of `Camera` and its tests, and CLAUDE.md says not to mix that with feature work.
- **`feel.squash(amount)` always acts along the gravity axis**, which is the only axis the game needs. There is no separate axis parameter.

### Files
`constants.py`, `src/rendering/gpu/feel.py`, `src/rendering/gpu/feel_effects.py` (new), `src/rendering/gpu/sprite_batch.py`, `shaders/sprite.vert`, `shaders/sprite.frag`, `src/rendering/gpu/debug_overlay.py`, `main.py`, `tests/test_feel_framework.py` (new).

Note: `sprite_batch.py` is already over the 300-line limit (since TA-1). This adds only a few lines; splitting `gpu_draw_world` out is a separate refactor session.

---

## GPU rotation-cinematic zoom (plan, 2026-11-05)

**Touches 5 files.** Matt chose this ahead of TA-6. It closes the last vertical-slice gap: the zoom-in/zoom-out on gravity rotation only worked on the software renderer.

- **`shaders/upscale.frag`:** new `u_zoom` uniform. Sample UVs are scaled around the screen centre, `0.5 + (uv - 0.5) / zoom`. That covers the layer texture and the light buffer, so lighting stays registered to the geometry. Samples outside [0,1] (only possible at zoom < 1) come back transparent, matching the black border the software renderer shows.
- **`src/rendering/gpu/layer.py`:** `composite(target, light, zoom=1.0)`. Image-layer draws keep zoom 1.
- **`src/rendering/gpu/feel.py`:** `distortion_params(..., zoom=1.0)` scales ripple centres and radii by the same zoom, so a ripple fired mid-cinematic still centres on the player.
- **`main.py`:** passes `camera.zoom` to both.
- **Tests:** a GPU readback of a marker scaled about the centre, a transparent border at zoom < 1, and the ripple maths under zoom.

Zoom is applied before post-processing, so vignette, grain and the HUD stay fixed to the screen, as in the software path.

---

## TA-5 — Fold Distortion + Gravity-Flip Bend (plan, 2026-11-05)

**Touches more than 3 files.** The spec is approved in `docs/tech-art-plan.md` §3 TA-5, and Matt said to go ahead.

### Approach
- **`src/rendering/gpu/feel.py` (new):** a `Feel` class with no GL code, so it runs headless and in the software renderer. Its API is `distortion(x, y, strength, dur)` (queues a ripple at a world position; a zero or negative duration does nothing; strength is clamped; at most 4 ripples, the oldest recycled) and `gravity_bend(direction)`. It also has `track_dilation(is_active, x, y)` (fires a ripple from the player whenever Time Dilation switches on, which covers both E and Kerr Ring's free activation, since that one sets timers directly), `update(dt)` and `distortion_params(cam_offset, size)`. TA-6 grows this into the full feel framework.
- **`shaders/distortion.frag` (new):** a new post pass, placed after bloom and before the grade/vignette/grain, so the glow warps but the screen-fixed effects don't. It does three things:
  - Ripple: an expanding ring that pushes pixels outward.
  - Gravity bend: the frame bows toward the new gravity, most at the centre line and not at all at the edges.
  - Chromatic aberration: a red/blue split that follows whichever effect is strongest.
  - The total offset is clamped in the shader. The pass is skipped when nothing is active.
- **`main.py`:** creates `Feel`, calls `feel.track_dilation(...)` and `feel.update(frame_dt)` each frame, passes `feel` into `_do_gravity_rotation` (3 call sites), and gives the params to the post stack.
- **Toggles:** distortion becomes post pass 2, so keys 1–6 (crt moves to 6).

### Files
`constants.py`, `src/rendering/gpu/feel.py` (new), `shaders/distortion.frag` (new), `src/rendering/gpu/post_stack.py`, `src/rendering/gpu/debug_overlay.py`, `main.py`, `tests/test_gpu_feel.py` (new), `tests/test_gpu_post.py` (crt key index).

### Conservative choices
- The rotation-cinematic zoom is still not applied on the GPU path (pre-existing since TA-1). The bend is added on top of the existing flash and shake; nothing is replaced yet.
- The bend fires wherever `_do_gravity_rotation` runs: the R key, entering a gravity zone, and the snap-back when chrono runs out. These already get the flash and shake. Respawn resets don't bend.

---

## TA-4 — Post-Processing Stack v1 (plan, 2026-11-05)

**Touches more than 3 files.** The spec is approved in `docs/tech-art-plan.md` §3 TA-4, and Matt said to go ahead. Q5 is decided: the CRT toggle exists but its shader is an empty pass-through, off by default.

### Approach
The parallax composite now renders into a half-float **scene buffer** instead of straight to the screen, so overbright light from TA-3 survives for bloom. `PostStack` runs the enabled passes in a fixed order, ping-ponging between two buffers, then copies the result to the screen. The HUD and fold tint are still drawn afterwards, so the effects don't touch them (as the spec says).

Pass order: **bloom → lut → vignette → grain → crt**.
- **bloom:** extract everything above a brightness threshold (soft knee) at half resolution, blur it 2× with a separable 9-tap Gaussian, then add it back.
- **lut:** 16×16×16 3D colour-grading table. Default is built in code from constants (mild contrast, slight desaturation, teal shadows and warm highlights, in keeping with the retrofuturistic tone). A strip at `assets/luts/grade.png` (256×16) replaces it with no code change.
- **vignette:** radial darkening, aspect-corrected.
- **grain:** hash noise reseeded every frame from an internal frame counter.
- **crt:** stub. Pass-through, off by default.

### Spec deviations (conservative)
- **Bloom uses a brightness threshold, not an emissive channel.** The emissive mask is TA-8 (optional). The pass's inputs won't change when masks arrive.
- **The vignette "golden image" test compares against a Python reference of the same formula** at sample points (±5 luma) rather than a stored PNG, so it doesn't break on harmless driver differences.
- **`tools/shader_watch.py`** is a standalone watcher: it recompiles every shader in `shaders/` whenever one changes and prints compile errors. There is no in-game hot reload yet.

### Files
| File | Change |
|---|---|
| `constants.py` | Pass order and defaults, bloom/vignette/grain/grade parameters |
| `src/rendering/gpu/post_stack.py` (new) | `PostStack`: scene buffer, ping-pong buffers, passes, toggles, resize, per-pass timing |
| `src/rendering/gpu/lut.py` (new) | Builds the procedural grade LUT, loads a strip LUT, uploads the 3D texture |
| `shaders/post.vert`, `bloom_extract.frag`, `blur.frag`, `bloom_combine.frag`, `lut.frag`, `vignette.frag`, `grain.frag`, `crt.frag` (new) | One small shader per pass |
| `src/rendering/gpu/debug_overlay.py` | Pass list with ON/OFF state and ms; hint for keys 1–5 |
| `main.py` | Composite into the scene buffer, run the post stack, keys 1–5 toggle passes while F3 is open |
| `tools/shader_watch.py` (new) | Shader compile watcher |
| `tests/test_gpu_post.py` (new) | Toggles, pass order, vignette reference, grain changing per frame, bloom spreading, LUT identity/strip, resize |

---

## TA-3 — 2D Light Buffer (plan, 2026-11-05)

**Touches more than 3 files.** The spec is approved in `docs/tech-art-plan.md` §3 TA-3, and Matt said to go ahead. Plan recorded for review.

### Approach
One fullscreen pass writes the light buffer: ambient plus the sum of up to 10 level lights and 1 player light. Each light has a smooth quadratic falloff, and spot lights also have a soft-edged cone. The buffer is half-float, so lights can brighten above 1.0 (clamped at 2.0). It is applied during the parallax composite by multiplying the **mid** and **play** layers. Sky and far stay unlit, since distant space is self-lit.

### Files
| File | Change |
|---|---|
| `constants.py` | Light caps and clamps, default ambient, player light radius/colour/intensity, lit layer names |
| `src/levels/light_data.py` (new) | `LightDef` dataclass plus `parse_lights()`. Validates type, clamps radius/intensity/colour, keeps at most 10 point/spot lights |
| `src/levels/level_data.py` | Optional `"lights"` key becomes `LevelData.lights` (written by `to_dict` only when there are lights) |
| `src/rendering/gpu/light_buffer.py` (new) | `pack_lights()` (world → screen, padded uniform arrays), `make_player_light()`, `LightBuffer` (half-float FBO, render, resize) |
| `shaders/light.frag` (new) | Light accumulation. Reuses `upscale.vert` for the fullscreen quad instead of adding a duplicate `light.vert` |
| `shaders/upscale.frag` + `src/rendering/gpu/layer.py` | Composite takes an optional light texture and multiplies the lit layers by it |
| `src/rendering/gpu/debug_overlay.py` | Adds a `light` line to the F3 timings |
| `main.py` | Render the light buffer each playing frame, then pass it to composite |
| `levels/level_01.json` | Adds `"lights"`: dim cool ambient plus 3 point lights, matching the vertical-slice target |
| `tests/test_gpu_lights.py` (new) | Schema and clamping, packing, GPU readback of ambient-only / single / additive lights, lit composite |

### Conservative choices
- **Only levels that have a `"lights"` key are lit**, and only level_01 gets one. Every other level renders exactly as after TA-2, with no player light either. Lighting the rest of the levels is an art pass.
- **The player light is a warm amber point light**, nodding to the exoskeleton glow. Its strength is a constant to tune by eye.
- **The 2 ms budget for 10 lights** is measured in a smoke script and reported, not asserted in unit tests, because a timing test would be flaky on a busy machine.

---

## TA-2 — Parallax Layer System (plan, 2026-11-05)

**Touches more than 3 files.** The spec is already approved in `docs/tech-art-plan.md` §3 TA-2, and Matt asked for this session to implement it, so this plan is recorded for review and work goes ahead.

### Files

| File | Change |
|---|---|
| `constants.py` | Layer names (back to front), default scroll factors (sky 0.05, far 0.20, mid 0.50, play 1.00, fore 1.30), scroll clamp, placeholder tint values |
| `src/rendering/gpu/layer.py` (new) | `parallax_offset()` math, `LayerFBO` (one FBO plus a resize), `ParallaxStack` (5 FBOs, image-layer draw, play-layer bind, composite, per-layer GPU timings) |
| `src/rendering/gpu/layer_images.py` (new) | Builds the sky/far/mid images. Uses `assets/backgrounds/layers/<name>.png` if present, otherwise procedural tinted copies of `background.png` (Q6) |
| `src/rendering/gpu/debug_overlay.py` (new) | Per-layer ms text, drawn when the debug overlay is on |
| `shaders/upscale.vert` / `upscale.frag` (new) | Fullscreen quad with a UV offset and mirror wrap. Draws the layer images into their FBOs and composites the FBOs to the screen |
| `src/rendering/gpu/sprite_batch.py` | `gpu_draw_world` stops drawing the background (it now lives in the parallax layers) |
| `src/levels/level_data.py` | Optional `"layers": {"sky": {"scroll": 0.1}, ...}` per-level scroll overrides. Unknown names and `play` are dropped with a warning; values are clamped |
| `main.py` | Builds the stack at startup. GPU playing path: image layers → play layer → composite → tint/HUD |
| `tests/test_gpu_layers.py` (new) | Scroll math, FBO resize, schema, and a GPU readback test showing the sky shifts 0.05× as far as the playfield |

### Conservative choices made
- **Foreground layer** is allocated and composited but left empty. There is no foreground art yet, and putting silhouettes over the playfield is a design call.
- **FBOs stay at 800×600 internal resolution.** The upscale shader is ready for any display size, but window scaling is not changed.
- **The debug overlay moved from backquote to F3** (Matt approved 2026-11-05, matching CLAUDE.md and the tech-art plan). On the GPU path it now draws, with per-layer ms. GPU timer queries run only while the overlay is on, because reading them stalls the pipeline.
- **The rotation-cinematic zoom is still ignored on the GPU path**, as before TA-2. Out of scope.
- **The software renderer is unchanged.**

### Resolved
- ~~Should the debug overlay move to F3?~~ Yes, done 2026-11-05.

---

## M4b — Node Map, Hole Encounters, Death/Win Screens ✅ APPROVED 2026-11-01

**Touches 5 files. Requires review before coding.**

### What this sprint delivers

A completable run: 5 nodes, two platform rooms, two hole encounters, a singularity win. The loop that M4 is gating on.

| Task | Done when |
|---|---|
| Node sequence on `RunState` | 5-node list generated at run start from `run_seed`; `current_node_idx` advances on room clear |
| Node map screen | `game_state = "node_map"` — draws 5 node icons, current position, ENTER advances |
| Hole encounter screen | `game_state = "hole_encounter"` — black screen, 2s reveal, applies resource consequences, ENTER continues |
| Death screen | `game_state = "dead"` — run summary (nodes reached, deaths), ENTER → start screen |
| Win screen | `game_state = "win"` — singularity reached, ENTER → start screen |

---

### Node sequence

Fixed pattern, seeded-random combat level assignment:

```
Node 0: combat   → level picked from [level_01, level_02] via run_seed
Node 1: hole     → black or white (50/50 from run_seed, unknown until entered)
Node 2: combat   → level picked from [level_03, level_04] via run_seed
Node 3: hole     → black or white (50/50 from run_seed, unknown until entered)
Node 4: singularity → win condition, no room
```

Hole outcomes are fixed at run start (same run, same holes) but unknown to the player until entered. This is the core design bible mechanic.

`RunState` gains two new fields:
- `combat_levels: list[int]` — level indices for the two combat nodes (e.g. `[1, 3]`)
- `hole_outcomes: list[bool]` — `True` = white hole, one per hole node (e.g. `[True, False]`)

Both generated deterministically from `run_seed` in `new_run()`.

---

### game_state additions

Current states: `"start"`, `"playing"`

M4b adds: `"node_map"`, `"hole_encounter"`, `"dead"`, `"win"`

Flow:
```
"start" → ENTER → "node_map"
"node_map" → ENTER → "playing" (loads combat level) or "hole_encounter" or "win" (singularity)
"playing" → goal_reached → "node_map" (advance node_idx)
"playing" → fold_stability ≤ 0 → "dead"
"hole_encounter" → 2s timer → apply consequences → "node_map" (advance node_idx)
"dead" → ENTER → "start"
"win" → ENTER → "start"
```

---

### Node map visual

Text-only for M4b (styled UI is M5). One line per node:

```
  ● NODE 1 — COMBAT          [completed]
  ● NODE 2 — ANOMALY          ← current
  ○ NODE 3 — COMBAT
  ○ NODE 4 — ANOMALY
  ○ NODE 5 — SINGULARITY
```

Current node highlighted. Completed nodes dimmed. ENTER continues into the current node.

---

### Hole encounter screen

Black screen. Two phases, timed:

**Phase 1 (0.0–1.5s):** "ENTERING THE ANOMALY..." — no information, both outcomes look identical.

**Phase 2 (1.5–3.5s, auto-advance):** Reveal outcome and apply consequences immediately:
- White hole: "WHITE HOLE — TEMPORAL ANCHOR RESTORED" — restore `anchor_integrity` to max, `fold_stability += WHITE_HOLE_STABILITY_RESTORE`
- Black hole: "BLACK HOLE — ANCHOR DESTABILISED" — `anchor_integrity -= 1` (can trigger level reset if at 0), `fold_stability -= BLACK_HOLE_STABILITY_COST`

After phase 2 ends: return to `"node_map"` with node advanced.

If the black hole integrity hit triggers fold_stability ≤ 0: go to `"dead"` instead.

→ **Decision needed: white hole restores +5 or +10 fold_stability? Black hole costs 10 or 15?**
→ **Recommendation: white +5, black -15. Black holes should feel genuinely dangerous.**

---

### Death screen

```
RUN OVER

Nodes reached:  3 / 5
Deaths:         3
Fold stability: 0

Press ENTER
```

Stats read from `RunState`. No run history yet (M5+).

---

### Win screen

```
THE FOLD HOLDS

Nodes reached:  5 / 5
Deaths:         1
Fold stability: 60

Press ENTER
```

---

### Files to change

| File | Change |
|---|---|
| `constants.py` | `WHITE_HOLE_STABILITY_RESTORE`, `BLACK_HOLE_STABILITY_COST`, `HOLE_ENCOUNTER_PHASE1_DURATION`, `HOLE_ENCOUNTER_PHASE2_DURATION`, node map colors |
| `src/data/run_state.py` | Add `combat_levels`, `hole_outcomes`, `deaths` fields; update `new_run()`; add `current_node_type` property, `advance_node()`, `hole_index_for_current_node()` |
| `src/rendering/hud.py` | Add `draw_node_map()`, `draw_hole_screen()`, `draw_death_screen()`, `draw_win_screen()` |
| `main.py` | New `game_state` branches, hole timer, node advancement on goal_reached, death/win routing |
| `tests/test_core.py` | `TestRunStateM4b`, `TestHoleEncounter` classes |

---

### What this is NOT

- Star chart / branching node map (M5)
- Merchant or rest nodes (M5)
- Fold distortion shader (M6)
- Run history or meta-progression (M7)
- Hole encounter as a playable room (M5 — for M4b it's a resolve screen)

---

## M4a — fold_stability, RunState, Start Screen ✅ APPROVED 2026-11-01

**Touches 5 files (1 new). Requires review before coding.**

### What this sprint delivers

Foundation for M4. Nothing in the game loop changes until these three are in place.

| Task | Done when |
|---|---|
| `fold_stability` resource + tint | field on RunState, tint deepens as it depletes, integrity-0 death costs fold_stability |
| `RunState` dataclass | serialisable, holds fold_stability + node + seed, lives in `src/data/run_state.py` |
| Start screen | game shows black screen + text on launch, ENTER starts run, ESC quits |

---

### Design decisions — answers needed

**1. Where does `fold_stability` live?**

It is a run-level resource (permanent depletion across rooms), not a character stat. It belongs on `RunState`, not `Player`. When `anchor_integrity` hits 0, main.py pays the fold_stability cost from `run_state.fold_stability` before resetting the level.

→ **Recommendation: RunState. No question.**

**2. How much fold_stability does each integrity-0 death cost?**

`FOLD_STABILITY_MAX = 100`. With a cost of:
- 25 → run ends after 4 deaths
- 20 → run ends after 5 deaths
- 33 → run ends after 3 deaths

Hole encounters, enemy abilities, and node timers will also cost fold_stability in M4b, so deaths shouldn't eat the whole budget. **Recommendation: 20 (5 deaths). Leaves room for other drains.**

→ **Decision needed: 20, 25, or other?**

**3. Fold tint visual**

A full-screen red overlay. Alpha scales linearly:
- fold_stability ≥ 80 → alpha 0 (invisible)
- fold_stability = 50 → alpha 40 (subtle red)
- fold_stability = 0 → alpha 110 (strong red, world is visibly dying)

Drawn on top of the background but under level geometry + player. Later (M6) replaced by real shader distortion.

→ **Recommendation: tint starts at 80, max alpha 110. Confirm or adjust threshold.**

**4. Start screen**

Black screen, two lines of text:

```
THE FOLD

Press ENTER to begin
```

ENTER → starts a new run (new RunState, resets level to level_01, resets player).
ESC → quits.

No game world visible behind it. Styled UI is M5.

→ **Recommendation: yes. Any text changes?**

**5. Game state machine**

Add `game_state: str` variable in `main()` with two values for this sprint: `"start"` and `"playing"`. Sets up the pattern for `"dead"` and `"win"` screens in M4b.

When `game_state == "start"`: draw start screen, only ENTER/ESC handled.
When `game_state == "playing"`: current game loop runs as-is.

→ **No question — just noting the approach.**

**6. Run seed**

`RunState.run_seed` is generated with `random.randint(0, 2**32)` in `RunState.new_run()`. Stored but not consumed yet — procedural node map (M4b) will use it.

→ **No question — just noting it's there.**

---

### Files to change

| File | Change |
|---|---|
| `constants.py` | `FOLD_STABILITY_MAX`, `FOLD_STABILITY_INTEGRITY_COST` |
| `src/data/run_state.py` | **new** — `RunState` dataclass |
| `src/rendering/hud.py` | `draw_fold_tint()`, `draw_start_screen()` |
| `main.py` | `game_state`, `RunState` integration, fold_stability drain on death |
| `tests/test_core.py` | `TestRunState` class |

---

### Death flow change (M3 → M4a)

Currently: integrity 0 → `_reset_level_state()` immediately (free).

M4a: integrity 0 → `run_state.fold_stability -= FOLD_STABILITY_INTEGRITY_COST` → if fold_stability ≤ 0: `game_state = "dead"` (M4b will render death screen; for now just reset back to start screen) → else: `_reset_level_state()` as before.

---

### What this is NOT

- Node map UI or navigation (M4b)
- Hole encounter mechanics (M4b)
- Death screen with run summary (M4b)
- Win screen / singularity node (M4b)
- Fold distortion shader (M6)

---

## M3 Combat — Hit Detection, Knockback, I-frames ✅ APPROVED 2026-11-01

### Design decisions (resolved)

- **Anchored state**: no per-frame death timer. Integrity 0 → level resets immediately (same level, same as TAB but same index). Full anchored state with fold_stability cost is M4.
- **Knockback**: override velocity (not add) — predictable, testable.
- **Fall damage at integrity 0**: same level-reset path as combat death (unified).

### Files changed

| File | Change |
|---|---|
| `constants.py` | `IFRAMES_DURATION`, `KNOCKBACK_FORCE` |
| `src/entities/player.py` | `iframes_timer` field; `take_hit()` returns bool; `take_fall_damage()` returns bool |
| `src/systems/combat.py` | new — `check_hit()`, `compute_knockback()` |
| `main.py` | `_reset_level_state()` helper; hit detection; iframes tick |
| `tests/test_core.py` | `TestCombat` class |

### Signal convention

Both `take_hit()` and `take_fall_damage()` return `True` when integrity hits 0. Caller handles the level reset — Player has no reference to level/camera/enemy.

---

## Open Items

### C2: Level bounds clamping precision
- **File:** main.py (bounds clamping section)
- **Risk:** Uses `round()` comparison which could miss sub-pixel edge cases. Different code path from platform collision.
- **Recommended fix:** Unify bounds clamping into resolve_collisions by adding virtual boundary platforms. Moderate effort — defer to physics refactor session.

### C3: Sprite/physics rect size mismatch in horizontal gravity
- **File:** src/rendering/animation.py
- **Risk:** 90/270 degree rotation swaps sprite width/height but physics rect stays PLAYER_SPRITE_WIDTH x PLAYER_SPRITE_HEIGHT. Visual and collision rects disagree in left/right gravity.
- **Recommended fix:** Either swap player_w/player_h in main.py when gravity is horizontal, or keep physics rect as the larger dimension always. Needs design decision — gameplay implications.

---

## M5e — The Anchored Enemy ✅ APPROVED 2026-11-01

**Touches 5 files (1 new). Includes architecture change: single enemy → enemy list.**

### What this delivers

The third enemy type. Distinct from the Fold Predator: no chase, unpredictable stutter, countered by Time Dilation rather than gravity rotation. Both enemies in the same room forces the "rotate (free, stops Predator) vs dilate (costs chrono, stops Anchored)" decision the item system was built to make interesting.

### Behaviour

| State | Description |
|---|---|
| WANDER | Slow random lateral movement; direction changes every `ANCHORED_WANDER_CHANGE_INTERVAL` seconds |
| STUTTER | Every `ANCHORED_STUTTER_INTERVAL` s: burst at `ANCHORED_STUTTER_SPEED_MULT`× in a random lateral direction for `ANCHORED_STUTTER_DURATION` s — the broken-timeline moment |

No CHASE state — The Anchored doesn't track the player. Unpredictability is the threat.
All movement scaled by `time_scale`, so Time Dilation (`time_scale=0`) freezes it completely.
`on_gravity_rotate()` is a no-op — gravity rotation has no special effect.

### Architecture change: single enemy → list

`enemy` in `main.py` becomes `enemies: list[FoldPredator | TheAnchored]`.  
All 8 use-sites updated: reset, update, rotation, combat check, draw.  
`_reset_level_state` and `draw_world` signatures updated.  
`ItemManager` already accepts a list — no change there.

### Files
| File | Change |
|---|---|
| `constants.py` | 9 ANCHORED_* constants |
| `src/entities/anchored.py` | new — TheAnchored class |
| `src/rendering/hud.py` | `draw_world` takes `enemies: list` |
| `main.py` | `enemy` → `enemies`; all 8 use-sites; `_reset_level_state` signature |
| `tests/test_core.py` | TestAnchored: wander, stutter fires + returns, time_scale freezes, rotation no-op, frozen_timer compat |

### Accept criteria
- Wander changes direction randomly without leaving level bounds.
- Stutter fires after interval, speed is higher, returns to WANDER after duration.
- Movement stops completely when `time_scale=0`.
- `on_gravity_rotate()` does not stun or change state.
- `frozen_timer` works identically to other enemies.
- Both enemies present and hittable in combat simultaneously.

---

## M5d — HUD ✅ APPROVED 2026-11-01

**Touches 4 files.**

### What this delivers

Always-visible resource readouts so the player can read integrity, chrono, and dilation state without the debug overlay. The exoskeleton glow design (CLAUDE.md) is deferred pending art — these are geometric placeholders with the same information.

### Layout

```
[top-left]                                        [top-right]
■ ■ ■   ← integrity pips (3 squares, amber/dark)

[game world]

[bottom-left]
━━━━━━░░░░  CHRONO   ← 10-segment bar
◀ TIME DILATION 2.1s ▶  ← only shown when active or cooling
```

Fold Stability: tint only (already done). Gravity label removed from production HUD (stays in debug overlay).

### Integrity pips
- 3 squares, 16×16px, 5px gap, top-left at (14, 14).
- Intact: amber `(210, 160, 50)`. Lost: dark `(40, 30, 15)`. All zero: pips go dark red `(150, 30, 30)`.

### Chrono bar
- 10 segments × 16px wide × 8px tall, 2px gap, bottom-left.
- Filled segments: amber when >50%, fading to dim orange below. Empty: near-black.
- Label "CHRONO" rendered in dim text to the right.

### Dilation status
- Active: `"◀ TIME DILATION X.Xs ▶"` in bright cyan, centred bottom.
- Cooling down (not active, timer > 0): dim version with remaining time.
- Ready and idle: nothing shown.

### Files
| File | Change |
|---|---|
| `constants.py` | HUD layout + colour constants |
| `src/rendering/hud.py` | rename `draw_hud_labels` → `draw_hud`; rewrite body |
| `main.py` | update import + call site |
| `tests/test_core.py` | smoke tests: no crash at boundaries (0 integrity, 100 chrono, active dilation) |

---

## M5b — Fold Predator Enemy ✅ APPROVED 2026-11-01

**Touches 4 files (1 new).**

### What this delivers

A second enemy that makes gravity rotation tactically meaningful in combat. Replaces the TemporalEcho placeholder in the active enemy slot. TemporalEcho class stays (available for future use).

### States

| State | Behaviour |
|---|---|
| PATROL | Oscillates laterally within level bounds |
| CHASE | Player within `FOLD_PREDATOR_CHASE_RANGE` px laterally — moves toward player |
| PHASE | Every `FOLD_PREDATOR_PHASE_INTERVAL`s during chase: burst at `FOLD_PREDATOR_PHASE_SPEED_MULT`× speed for `FOLD_PREDATOR_PHASE_DURATION`s |
| STUNNED | Any gravity rotation stuns for `FOLD_PREDATOR_STUN_DURATION`s; resumes previous state after |

### Decisions locked
- Stun triggers on **any** gravity rotation, regardless of distance to player.
- Movement is gravity-aware: lateral axis = X for vertical gravity, Y for horizontal.
- STUNNED color = pale blue-white (temporal disruption visual). PHASE color = brighter purple.

### Interface (matches TemporalEcho so main.py surgery is minimal)
- `update(time_scale, dt)` — same signature
- `reset()` — same
- `rect` property — same
- `draw(surface, offset)` — same
- `frozen_timer` field — same (Hawking Emitter compatible)
- `on_gravity_rotate()` — new; called from R-key handler in main.py

### Files
| File | Change |
|---|---|
| `constants.py` | 9 FOLD_PREDATOR_* constants |
| `src/entities/fold_predator.py` | new — FoldPredator class |
| `main.py` | swap TemporalEcho → FoldPredator; call `enemy.on_gravity_rotate()` from R key |
| `tests/test_core.py` | TestFoldPredator: patrol, chase entry/exit, phase burst, stun, gravity-aware movement, frozen_timer compat |

### Accept criteria
- Patrol oscillates and turns at bounds.
- CHASE entered when player within range, exited when player leaves range.
- PHASE burst fires after interval, speed doubles, returns to CHASE after duration.
- STUN freezes movement for full duration on any gravity rotation.
- After stun expires, resumes previous state.
- Gravity-aware: moves on Y axis when gravity is horizontal.
- frozen_timer field works (Hawking Emitter test passes unchanged).

---

## M5a Session 3 — Reward Flow ✅ APPROVED 2026-11-01

**Touches 5 files (1 new).**

### What this session delivers

The `"reward"` game state. After a combat room clears or a white hole resolves, the player sees a pick-1-of-3 offer screen before returning to the node map. Black holes give no reward.

### Flow

```
"playing" → goal_reached → generate offers → "reward" → pick → advance_node → "node_map"
"hole_encounter" (white) → timer ends → generate offers → "reward" → pick → advance_node → "node_map"
"hole_encounter" (black) → timer ends → advance_node → "node_map"  (unchanged)
```

`run_state.advance_node()` moves to the reward screen handler — called after pick or skip, not before. Two new flags in main.py locals: `reward_offers: list` and `pending_node_advance: bool`.

### Offer generation — `src/systems/items/offers.py` (new)

```python
@dataclass
class Offer:
    item_def: ItemDef
    is_rank_up: bool
    is_paradox: bool
    paradox_cost: float   # fold_stability; 0 if not paradox

def generate_offers(
    registry, run_state, node_idx, extra_options=0
) -> list[Offer]:
    ...
```

**Algorithm:**
1. Base count = 3 + `extra_options` (Penrose Diagram adds 1).
2. RNG seeded from `run_state.run_seed ^ (node_idx * 0x9e3779b9 & 0xFFFFFFFF)` — deterministic per run+node.
3. Build candidate pool:
   - Owned modifiers below max rank → rank-up offers (prioritised first).
   - Unowned modifiers — if player has ≥1 item in a domain, weight that domain × 3.
   - Filter out fully-maxed modifiers.
4. Fill base_count slots (no duplicates within a single offer set).
5. Paradox check: `rng.random() < PARADOX_OFFER_CHANCE` → append one artifact offer, cost from constants. Can only be taken if `fold_stability - cost > 0`.

### Modifier-cap handling

When MODIFIER_CAP (6) is reached and player picks a new modifier: auto-drop the oldest one in `run_state.owned_items`. Show a note on screen. No explicit drop screen in this session (Session 4 tuning pass can add it).

### Key bindings on reward screen

| Key | Action |
|---|---|
| `1` / `2` / `3` (`4` with Penrose) | Pick that offer |
| `S` or `0` | Skip — no item, advance |

### Node map update

Show owned items as a compact list below the node list:
```
ITEMS: Tidal Coupling R1, Redshift R2
```
One line, truncated if too many.

### Files

| File | Change |
|---|---|
| `src/systems/items/offers.py` | new — `Offer` dataclass, `generate_offers()` |
| `src/rendering/hud.py` | add `draw_reward_screen()`, update `draw_node_map()` |
| `main.py` | "reward" game_state branch, key handlers, transition logic |
| `tests/test_core.py` | `TestOfferGeneration`, `TestRewardFlow` |
| `qa_checklist.md` | add "Build system" section |

### Accept criteria (from brief §6 Session 3)

- Same seed + node index produces the same offers.
- A Paradox offer is never takeable if cost would drop stability to ≤ 0.
- A full 5-node run is playable with picks (at least one reward screen works end to end).
- `qa_checklist.md` gets a "Build system" section.
- 450+ tests pass (≥32 new).

---

## M5a Session 1 — Event Bus + Spacetime Refactor ✅ APPROVED 2026-11-01

**Touches 5+ files. Pure refactor — zero behaviour change.**

### Decisions locked (from M5_BUILD_BRIEF.md §0)

1. **Pool size:** Time Dilation is the only ability in this slice. No new abilities. 6 modifiers + 3 artifacts are Session 2.
2. **Domain names:** Time / Gravity / Horizon confirmed.
3. **Artifact costs:** Penrose Diagram 10 fold_stability, Kerr Ring 20, Hawking Emitter 25. Tunable later.
4. **Skip reward:** gives nothing.

### What Session 1 delivers

Infrastructure only. No gameplay change. All 352 existing tests pass unchanged.

| Task | File |
|---|---|
| `GameEvent` enum + `EventBus` pub/sub | `src/systems/events.py` (new) |
| `AbilitySlot` dataclass; `TimeDilationAbility` instance | `src/systems/spacetime.py` (new) |
| Wire `dilation_timer`/`dilation_cooldown` through `AbilitySlot` | `main.py` |
| Emit 8 events from existing code paths | `main.py` |
| Remove `CHRONO_DRAIN_TEST` Q key | `main.py`, `constants.py` |
| Tests: event dispatch, cancellation, AbilitySlot tick | `tests/test_core.py` |

### Event list (all emitted in Session 1, no handlers yet)

| Event | Emitted when |
|---|---|
| `GRAVITY_ROTATED` | R key handler |
| `ABILITY_USED` | Time Dilation activates (E key) |
| `ABILITY_ENDED` | `AbilitySlot.tick()` — active_timer hits 0 |
| `PLAYER_HIT` | cancellable — before `player.take_hit()` |
| `INTEGRITY_ZERO` | cancellable — when integrity hits 0 (hit or fall) |
| `ROOM_ENTERED` | game_state transitions to "playing" |
| `ROOM_CLEARED` | goal reached, before advance_node |
| `HOLE_RESOLVED` | inside `_apply_hole_consequences` |

### AbilitySlot interface

```python
@dataclass
class AbilitySlot:
    name: str
    duration: float   # reads from constants, modifiers can adjust later
    cost: float
    cooldown: float
    active_timer: float = 0.0
    cooldown_timer: float = 0.0

    @property
    def is_active(self) -> bool: ...
    @property
    def is_ready(self) -> bool: ...
    def activate(self, chrono_reserve: float) -> float: ...  # returns updated reserve
    def tick(self, dt: float, bus: EventBus) -> None: ...    # emits ABILITY_ENDED
    def reset(self) -> None: ...                             # clears both timers
    def time_scale(self) -> float: ...                       # TIME_DILATION_FACTOR or 1.0
```

### Accept criteria

- All 352 existing tests pass.
- New tests: EventBus dispatches to registered handlers; cancellable events respect cancelled flag; AbilitySlot.tick emits ABILITY_ENDED exactly once when active_timer reaches 0; time_scale() returns correct values.
- Time Dilation behaves identically in play (same duration, same cost, same cooldown).
- Q key removed; CHRONO_DRAIN_TEST removed from constants.py.

---

## Resolved (removed from active list)

- **C1** — Stale on_ground after gravity rotation. Fixed: commit `426edb9`.
- **C4** — Camera shake applied to offset. Not a bug; documented for clarity only.
- **D1** — No top-level exception handler. Fixed: commit `b7f1ef2`.
- **D2** — No logging infrastructure. Fixed: commit `b7f1ef2`.
- **D3** — No physics watchdog. Fixed: commit `b7f1ef2`.
- **D4** — No error handling on level load. Fixed: commit `b7f1ef2`.
- **D5** — No entity count limits. Fixed: MAX_ENEMIES/MAX_PARTICLES/MAX_PROJECTILES added to constants.py.
- **D6** — System font dependency. Fixed: bundled TTF loaded first with SysFont fallback.
