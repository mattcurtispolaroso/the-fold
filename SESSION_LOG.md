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

[2026-11-01] M5a Session 2: Item system (no UI) — complete.
- Created src/data/items.py: ItemDef, OwnedItem, ResonanceDef dataclasses.
- Created assets/data/items/modifiers.json (6 modifiers), artifacts.json (3 artifacts), resonances.json (3 resonances).
- Created src/systems/items/registry.py: load_item_registry(), ItemRegistry — validates JSON on load, logs and skips invalid entries.
- Created src/systems/items/effects.py: 11 effect primitives in EFFECT_REGISTRY (add_chrono, grant_iframes, extend_active_ability, cancel_and_restore, phase_hit, modify_hole_outcome, add_reward_option, freeze_enemies_in_radius, trigger_ability, grant_iframes_on_phase, ctc_undo_integrity_loss).
- Created src/systems/items/manager.py: ItemManager subscribes owned items to event bus, tracks internal cooldowns, per-room charges, and resonances.
- Updated RunState: added owned_items, paradox_spent, extra_reward_options fields.
- Updated TemporalEcho: added frozen_timer field and Hawking Emitter freeze support.
- Wired ItemManager into main.py: load at startup, tick() each frame, F-key debug grant.
- Added MODIFIER_CAP, HAWKING_RADIUS, PARADOX_OFFER_CHANCE, DEBUG_ITEMS, artifact cost constants.
- 418 tests pass (46 new: registry validation, each effect primitive, resonance detection, cooldown management, physics invariance).

[2026-11-01] M5a Session 3: Reward flow — complete.
- Created src/systems/items/offers.py: Offer dataclass + generate_offers() with seeded RNG, domain pull, rank-ups, Paradox offers.
- Updated src/rendering/hud.py: draw_reward_screen() (text-only pick UI), draw_node_map() shows ITEMS line.
- Updated main.py: "reward" game_state, 1/2/3/S key handlers, _apply_offer() helper, _owned_item_list() helper. Combat clear and white hole now route through reward before node_map.
- Updated qa_checklist.md: "Build system" section added.
- 433 tests pass (15 new: offer generation, determinism, domain pull, _apply_offer, cap drop).

## 2026-11-05 — TA-2 Parallax Layer System
- Plan written to DECISIONS_NEEDED.md first (touches >3 files; spec pre-approved in docs/tech-art-plan.md).
- Added src/rendering/gpu/layer.py: parallax_offset(), resolve_scroll_factors(), LayerFBO, ParallaxStack (5 FBOs, image-layer draw, play-layer target, premultiplied composite, optional GPU timer queries).
- Added src/rendering/gpu/layer_images.py: sky/far/mid from assets/backgrounds/layers/<name>.png, else procedural split of background.png (blurred haze / luminance-keyed bright features / lower silhouette band).
- Added src/rendering/gpu/debug_overlay.py: per-layer ms block for the debug overlay.
- Added shaders/upscale.vert + upscale.frag: fullscreen quad with UV scroll and mirror wrap; used for both layer draws and the composite/upscale.
- gpu_draw_world no longer draws the background (moved into the parallax layers); `background` / `width` / `height` params removed.
- LevelData gains optional "layers" key → layer_scrolls (unknown/play names dropped, values clamped, malformed value → fallback level).
- main.py GPU playing path: begin_frame → image layers → play layer → composite → tint/HUD. Debug overlay now also draws on the GPU path.
- 659 tests pass (22 new in tests/test_gpu_layers.py, incl. a GPU readback test of sky vs playfield scroll). Real-window smoke test: no GL errors, ~0.7ms for all layers.
- Debug overlay toggle moved from backquote to F3 (Matt approved), matching CLAUDE.md and the tech-art plan. Applies to both renderers.

## 2026-11-05 — TA-3 2D Light Buffer
- Plan written to DECISIONS_NEEDED.md first (touches >3 files; spec pre-approved).
- Added src/levels/light_data.py: LightKind enum, LightDef, parse_lights() (clamps values, ≤1 ambient, ≤10 emitters, unknown types dropped with a warning).
- LevelData gains optional "lights" → lights (serialised only when non-empty).
- Added shaders/light.frag (ambient + quadratic-falloff point/spot lights in one pass; reuses upscale.vert) and src/rendering/gpu/light_buffer.py (pack_lights, make_player_light, LightBuffer with half-float FBO).
- upscale.frag + ParallaxStack.composite(target, light): mid/play multiplied by the light buffer; 1×1 white fallback bound to the light unit otherwise (fixes a macOS "unloadable texture" driver warning). ParallaxStack.timed() made public so main can time the light pass.
- main.py renders the light buffer each playing frame; F3 overlay shows a `light` line.
- level_01.json lit: ambient + 3 point lights.
- 683 tests pass (24 new in tests/test_gpu_lights.py incl. GPU readback of ambient, additive, capped, spot-cone, player-follow, lit composite). Window smoke: 10 lights + player ~0.53ms avg, no GL errors.
- Lighting too dark on first look (Matt): level_01 ambient raised (0.30,0.34,0.42) → (0.72,0.75,0.82); PLAYER_LIGHT_INTENSITY 0.7 → 0.85 so the player pool still reads over the brighter ambient.

## 2026-11-05 — TA-4 Post-Processing Stack v1
- Plan written to DECISIONS_NEEDED.md first. Q5 decided: CRT toggle wired, shader is a pass-through stub.
- Added src/rendering/gpu/post_stack.py (scene buffer → bloom/lut/vignette/grain/crt via ping-pong half-float targets → copy to screen; toggles, per-pass timing via ParallaxStack.timed) and src/rendering/gpu/lut.py (procedural grade LUT, 256×16 strip loader, 3D texture upload).
- Added shaders: post.vert, bloom_extract, blur, bloom_combine, lut, vignette, grain, crt (stub), copy.
- Debug overlay lists passes with [1]-[5] keys, ON/off and ms; main toggles them with F3 open.
- Added tools/shader_watch.py (compile/link watcher, --once for a one-shot check) and a test that runs it over every shader.
- First render crushed the dark art: contrast pivot moved 0.5 → 0.18, shadow tint made a lift, grain scaled down in shadows, bloom threshold 0.75 → 0.55.
- Build fix: requirements.txt gains numpy; build/the_fold.spec no longer excludes numpy and bundles shaders/. A full PyInstaller build has not been run.
- 703 tests pass (20 new). Window timing: post ≈1.0-1.15ms avg, whole GPU frame ≈2.7ms.

## 2026-11-05 — TA-5 Fold Distortion + Gravity Bend
- Plan written to DECISIONS_NEEDED.md first.
- Added src/rendering/gpu/feel.py: Feel (distortion(), gravity_bend(), track_dilation() rising-edge ripple, update(), reset(), distortion_params()), Ripple, DistortionParams, envelopes. No GL; runs in both renderers.
- Added shaders/distortion.frag (ripples, bend, chromatic aberration, offset cap) as post pass 2; PostStack.set_distortion(); the pass is skipped when idle. Keys 1-6 now.
- main.py: Feel created at startup, track_dilation + update each playing frame, passed into _do_gravity_rotation (3 call sites) which calls gravity_bend after the new direction is set.
- Updated 2 TA-4 tests (crt key index 5→6; idle distortion skipped by the timing hook).
- 723 tests pass (20 new in tests/test_gpu_feel.py incl. GPU readback of bend, ripple, aberration, offset cap). Distortion ≈0.2ms. One timing run showed a single 5.2ms post frame (likely query/compositor noise; avg 1.2-1.5ms).

## 2026-11-05 — GPU rotation-cinematic zoom
- Matt chose this over TA-6 (last vertical-slice gap). Plan noted in DECISIONS_NEEDED.md (5 files).
- upscale.frag: u_zoom scales sample UVs about the screen centre for both the layer and the light buffer; outside-frame samples are transparent (zoom < 1 parity with software's black border). layer.py: composite(..., zoom) with COMPOSITE_ZOOM_MIN guard; image-layer draws force zoom 1.
- feel.py: distortion_params(..., zoom) + zoomed_screen_point(), so ripples stay centred under zoom.
- main.py passes camera.zoom to composite and distortion_params.
- 729 tests pass (6 new: centre-scaling readback, identity at 1×, empty border at 0.5×, no zoom leak into image layers, ripple centre/radius under zoom).

## 2026-11-05 — TA-6 Feel Framework
- Plan written to DECISIONS_NEEDED.md first.
- Added src/rendering/gpu/feel_effects.py (Hitstop, SpriteFlash, Squash, squash_scale) composed by Feel. Feel gains intensity / reduced-effects mode, hitstop, flash, squash, shake/punch/rotation_cinematic forwarding to Camera, physics_time(), sprite_flash(), sprite_scale(), screen_flash_scale(); distortion amplitudes are intensity-scaled.
- Sprite shaders + SpriteBatch: a_flash vertex attribute (12 floats/vertex). gpu_draw_world takes feel: flash + squash with feet planted.
- main.py: physics accumulator fed via feel.physics_time; rotation shake/zoom and hard-landing punch routed through feel (no direct camera shake/punch calls remain); hooks on enemy hit, landings, both jump sites; feel.reset on level reset; full-screen flashes scaled; F3 + 0 toggles reduced effects (shown in overlay).
- Test caught an over-claiming docstring (squash "preserves area"): behaviour kept (partial compensation, deliberate), docstring + test corrected.
- 752 tests pass (23 new in tests/test_feel_framework.py incl. hitstop accumulator maths, intensity scaling of every effect, headless/no-camera safety, GPU silhouette flash readback).

## 2026-11-05 — TA-7 GPU Particles
- Plan written to DECISIONS_NEEDED.md first. Found: GPU path drew no particles; ParticlePool.update was per-frame (not dt-based); emitter values hard-coded; hit sparks only on hard landings.
- vfx.py: px/s velocities, acceleration + exponential drag with an exact constant-acceleration step (a test caught the naive integrator drifting ~8% between 30/120 fps), birth→death size, glow flag, effect specs from constants (VFX_ROTATION_BURST / VFX_HIT_SPARK / VFX_LANDING_DUST), write_instances() with in-place writes (no per-frame allocation). Pool 200 → 500 (MAX_PARTICLES).
- Added src/rendering/gpu/particles.py (ParticleRenderer: one instanced draw, draw_calls counter, capacity guard) and shaders/particle.vert/.frag (soft discs; glow = additive via alpha 0 under premultiplied blend). shader_watch pairs particle.frag with particle.vert.
- main.py: particles drawn into the play layer on the GPU path; hit sparks on enemy hits too, falling along the player's gravity.
- Visual pass: first render had near-invisible sparks; glow core widened (PARTICLE_GLOW_CORE) and glow sizes increased.
- Found while timing: nested ParallaxStack.timed() blocks raise GL_INVALID_OPERATION; timed() now runs nested blocks untimed. Test added.
- 770 tests pass (18 new). 500 particles: 1 draw call; CPU update + pack ≈1ms/frame (Python); no GL errors.

## 2026-11-05 — Refactor: split oversized render modules (no behaviour change)
- **Reason (written before restructuring, per CLAUDE.md):** two logic files break the 300-line rule. `src/rendering/hud.py` is 437 lines and `src/rendering/gpu/sprite_batch.py` is 387. Three functions break the 40-line rule: `gpu_draw_world` (66), `draw_reward_screen` (56), `draw_node_map` (49). Four GPU modules also import the private `_load_shader` from `sprite_batch`, coupling them to the sprite batch just to read a file.
- **Work is on branch `refactor/render-module-split`; `main` is untouched until it's verified.** Verification: the full test suite, plus pixel-identical reference renders of every menu screen, the HUD overlays, the software world draw and the GPU playfield, captured before and after.
- Done. `hud.py` 437→197 (menus → `src/rendering/screens.py`, 236). `sprite_batch.py` 387→252 (playfield → `src/rendering/gpu/world_draw.py`, 162; shader loading → `src/rendering/gpu/shader_source.py`; `__init__` split). The 4 GPU modules now import the public `load_shader`. Over-40-line functions split: `gpu_draw_world`, `draw_reward_screen`, `draw_node_map`, `SpriteBatch.__init__`. Death/win screens share stat helpers. Removed unused imports (`hud.py`: TheAnchored, FoldPredator, GRAVITY_LABELS; `sprite_batch.py`: constants, WHITE_FRAME, os). Inline GPU colour literals became named constants in `world_draw.py` (same values).
- Verification: 474 reference renders (all menus in multiple states, HUD variants, flash/tint/debug overlays, software world draw, GPU playfield with and without feel) captured before, confirmed deterministic, and identical pixel for pixel after. 770 tests pass. pyflakes is clean on every touched module. Real-window GPU smoke test: GL_NO_ERROR.
- Left alone: `main()` length; the pre-existing redundant local import in `_do_gravity_rotation` (pyflakes redefinition warning); menu colour/position literals.

## 2026-11-05 — Engine Session 1: Physics hardening (audit bugs 1–5)
- [1.1] MovingPlatform records prev_rect + actual per-step delta; riding_velocity probes the previous rect and returns the real displacement. Turnaround slip (8px) gone; vertical platforms carry the player at any speed.
- [1.2] push_out_of_movers(): platforms moving into the player push them along their motion. The side-push "pop 80px up" teleport is gone.
- [1.3] combined_gravity_mult() clamps level × zone × pressure to GRAVITY_MULT_MAX (5×), logged once per excursion. resolve_collisions sub-steps (≤ ½ the player's smallest side per pass), so there's no tunnelling at any speed (a 2px platform at 10× terminal velocity still lands). Normal speeds still take a single pass. Skipped the load-time JSON clamp (level_data.py at 295/300 lines; the runtime clamp covers every source).
- [1.4] find_safe_position() (exact nearest-fit search over solid edges) + try_rotate(). Rotation moves the player to the nearest spot where the rotated hitbox fits, or is refused (no chrono cost, no cooldown, small "blocked" shake). Zone/snap-back rotations retry naturally.
- [1.5] validate_player() after every physics step: NaN position → last safe spot; NaN velocity → zeroed; inside geometry → ejected (or last safe spot if crushed, no damage). Logged via LoggingManager.log_physics_violation.
- [1.6] tests/test_physics_hardening.py: regression tests for each audit repro + engine fuzz (2 × 12k random steps across random rooms, gravity up to 5×, rotations, long-fall launches). Mutation-tested: restoring each old behaviour makes the tests fail; the fuzz alone catches the old rotation and the missing sub-steps.
- [1.7] Cached collision rect list (no per-step allocation); EPSILON zero checks in collision; physics history stores a small dict (no per-step deep copy); main.py lint-clean (also removed 4 unused imports and a redundant local import); physics units documented in constants.py.
- Verified: 791 tests pass; 3,000 frames of scripted headless play through real main() → 0 physics violations logged.

## 2026-11-05 — Engine Session 2: Smoothness (audit items 6–7)
- [2.1] src/rendering/interpolation.py: RenderInterpolator records player/enemy positions at the start of each physics step; platforms reuse prev_rect. GPU draws player, enemies and moving platforms at lerp(prev, cur, alpha), alpha = accumulator / PHYSICS_DT. The software path interpolates the player. Camera, player light and particles follow the interpolated position. Snaps on level reset and on any jump > TELEPORT_SNAP_PX (respawns never streak). Verified: on a replay of the measured jittery frame times, interpolated on-screen speed is >5× steadier than raw, and motion at 120 fps is even although half the frames get no physics step.
- [2.2] vsync on the GPU window (clean fallback if unsupported); render cap MAX_RENDER_FPS=240 instead of 60; physics stays a fixed 60 Hz. Measured: macOS gives windowed OpenGL 60 Hz even on the ProMotion panel (120 Hz is Metal-only), so this Mac runs at 60; 120/144 Hz displays elsewhere now render at full rate. Removed the `FPS` import from main (physics constants still derive from it).
- [2.3] Camera: 1 − e^(−k·dt) follow and zoom (same path at 30/60/120 fps, within 0.5 px); window dead zone (no jolt at the edge); the post-rotation re-centre now truly centres; shake uses smooth time-based noise. A test caught my first frequencies (19/31 Hz) aliasing into jitter at 60 fps; now 8/13 Hz.
- Verified: 801 tests pass (10 new in tests/test_smoothness.py); real GPU game ran ~700 frames of scripted play cleanly with no crash or violation log lines.
