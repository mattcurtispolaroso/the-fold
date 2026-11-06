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
