# The Fold: Roadmap

Written 2026-10-31 after a repo review. Estimates are rough and assume one ~3 hr session per week. Overnight Claude Code runs can compress them.

## Vision
A retrofuturistic 1962 roguelite platformer where you bend gravity and time, and every black/white hole is a committed gamble. Powers weaken as you near the singularity. Physics never changes, so players can master it.

## Status review (as of 2026-11-01)

**Where the project actually is:** solid physics foundation, Player entity with two resources, one ability (Time Dilation), three levels. Not yet a game — no enemies, no combat, no win/lose loop.

| Area | State |
|---|---|
| Module 1 Physics (4 gravity orientations, coyote, variable jump, 60hz timestep) | Done |
| Module 2 Level architecture (JSON levels, moving platforms, 3 levels, boundary system) | Done |
| Module 3 Camera (follow, bounds, shake, re-centre on rotate) | Done |
| Stability infra (crash handler, 3 logs, watchdog, level fallback, entity caps) | Done |
| src/entities/player.py (Player dataclass, chrono_reserve, serialisable) | Done |
| Time Dilation ability (E key, freezes platforms 3s, costs 25 CR) | Done |
| Module 13 Sprite/animation (~70%) | 3 player sprites. Helmet sprites absent. No `EXOSKELETON_GLOW_PATH` |
| Modules 4-12, 14-19 | Not started |
| Tests | 289 passing (2026-11-01) |

## Strategy
Stop building by layer. Build **thin vertical slices**, each ending in something playable, and put a go/no-go "is the loop fun?" gate after the first full run (M4). Content breadth (items, enemies, procgen, polish) comes only after that gate.

## Current milestone
**M4: First Run** (next)

## Milestones

**M0. Re-baseline** ✅ Done 2026-10-31

**M1. Feel** ✅ Done 2026-11-01
- Fixed 60hz timestep with accumulator ✅
- C2: unified bounds into collision system via boundary_rects() ✅
- C3: fixed fallback rect swap for horizontal gravity ✅
- Rotation flash overlay ✅
- animation.py split under 300 lines (helmet.py extracted) ✅
- levels 02 and 03 require rotation to solve ✅
- TAB level cycling ✅
- QA checklist updated and ticked ✅

**M2. First Toy** ✅ Done 2026-11-01
- Player dataclass refactor, serialisable to dict ✅
- `chrono_reserve` resource with movement-driven regen (15/s moving, 0/s idle) ✅
- Time Dilation ability — E key, 3s platform freeze, 25 CR cost, 2s cooldown ✅
- Amber glow overlay driven by `chrono_reserve` — deferred to art update (needs `EXOSKELETON_GLOW_PATH`)
- level_04 "Frozen Gate": 640px gap + speed-10 moving platform — unsolvable without Time Dilation ✅
Done when: a level exists that cannot be solved without dilating something. ✅

**M3. First Fight** ✅ Done 2026-11-01
- Temporal Echo patrol placeholder ✅
- `anchor_integrity` 3-hit pool, fall damage ✅
- Hit detection, knockback, i-frames (`src/systems/combat.py`) ✅
- Integrity 0 → level resets (winnable + losable) ✅
- Time Dilation freezes enemy ✅
Done when: an arena room is winnable and losable, and dilation changes how you fight. ✅

**M4. First Run** (8-12 sessions): the make-or-break slice
- M4a — fold_stability resource + RunState + start screen (in progress)
  - [x] `RunState` dataclass (fold_stability, node, seed, is_active) ✅
  - [x] `fold_stability` depletes 20/death; run ends at 0 ✅
  - [x] Fold tint: red overlay, alpha scales 0→110 as stability drops below 80 ✅
  - [x] Start screen ("THE FOLD / Press ENTER to begin") ✅
  - [x] `game_state` machine: "start" / "playing" ✅
- M4b — node map, hole encounters, death/win screens
  - [x] 5-node run: combat → hole → combat → hole → singularity ✅
  - [x] Node map screen (text list, current node highlighted) ✅
  - [x] Hole encounter resolve screen (phase 1 neutral, phase 2 reveals black/white) ✅
  - [x] White hole: +5 fold_stability, restore anchor_integrity ✅
  - [x] Black hole: -15 fold_stability, -1 anchor_integrity ✅
  - [x] Death screen with nodes/deaths/stability stats ✅
  - [x] Win screen (singularity reached) ✅
Done when: a ~10 min run from start to singularity or death is completable. **Gate:** external playtest. Is it fun? Go / redesign / cut.

**M5. Content Alpha** (in progress)
- M5a — Run Build System ✅ Done 2026-11-01
  - [x] EventBus + AbilitySlot framework (zero behaviour change) ✅
  - [x] 6 modifiers, 3 artifacts, 3 resonances in JSON ✅
  - [x] ItemManager — subscribes owned items to event bus, internal cooldowns, resonance detection ✅
  - [x] Reward flow — pick-1-of-3 after combat rooms and white holes, seeded offers, Paradox artifacts ✅
  - [x] Session 4 tuning pass ✅ — white hole no longer gives reward screen (resource restore is the reward); PARADOX_OFFER_CHANCE 25% → 15%
- M5b — Fold Predator enemy ✅ Done 2026-11-01
- M5c — Anomaly rooms ✅ Done 2026-11-02 — 3 hand-authored rooms (physics gate, RIGHT-gravity navigation, UP-gravity overhead), seeded picker, wired into hole node flow; expanded to 6 rooms post-M8 (3 added in commit 47d360d)
- M5d — HUD ✅ Done 2026-11-01 — integrity pips + chrono bar + dilation status; gravity label removed from production HUD
- M5e — The Anchored enemy ✅ Done 2026-11-01 — wander/stutter AI, frozen by Time Dilation, no-op on gravity rotate
- Audio v1 — deferred

**M6. Polish Beta** ✅ Done 2026-11-02
- Variable gravity: singularity pressure + per-level multiplier ✅
- Gravity zones: local fields that snap direction or scale strength ✅
- Gravity drain + snap-back: chrono drains off-default gravity, snaps back at 0 ✅
- Hard landing damage: impact above threshold costs 1 integrity ✅
- VFX pass: rotation burst, hit spark, landing dust (visual tuning deferred — see Needs revisit) ✅
- Rotation cinematic: zoom-in → hold → zoom-out (1.08× / 0.18s) ✅

**M7. Ship prep** ✅ Done 2026-11-02
- M7a: Save + meta-progression — `SaveManager`, `MetaProgress` dataclass, atomic write, corruption recovery ✅
- M7b: Second character (The Archivist) — deferred to backlog
- M7c: Mac + Windows PyInstaller builds — `build/the_fold.spec`, `build/build_mac.sh`, `build/build_windows.bat` ✅

## Current milestone
**M8 — Playtest Pass** ✅ Done 2026-11-02
- M8a: Stability rebalance — death cost 20→15, black hole 15→10, white hole restore 5→15 ✅
- M8b: Enemy data pass — EnemyDef in level JSON; Temporal Echo back in combat rooms; varies by node ✅
- M8c: Extend run to 9 nodes — 4 combat + 4 hole + singularity; 4 new level files (05-08); pressure curve validated ✅

**M8-post. Bug fixes + audit (between M8 and M9)** ✅ Done 2026-11-05
- Adversarial game-dev audit — 12 bugs fixed (AbilitySlot chrono floor, knockback gravity-aware, animation walk/land fixes, moving platform float precision, rotation cooldown constant). Tests in `tests/test_audit_fixes.py`. ✅
- AIR_DECEL increased 0.1 → 0.25 — reduces floaty lateral drift ✅
- Hard landing visual feedback — directional camera punch + red impact flash on HARD_LAND_VELOCITY hit ✅
- Death cause tracked and shown on death screen ✅
- 3 additional anomaly rooms added (now 6 total) ✅
- Test suite refactored — `test_core.py` split into 6 focused domain files; 2 redundant duplicate test classes removed ✅
- `JUMP_ANTICIPATION` dead animation state deleted — enum value and sprite loading removed (closes adversarial audit item 6) ✅
- `TIME_DILATION_COOLDOWN` renamed to `TIME_DILATION_POST_EFFECT_WAIT` + `total_recharge` property added to `AbilitySlot` (closes adversarial audit item 12) ✅
- Ability combination test coverage filled — 7 new tests in `TestAbilitySlotCombinations` (closes adversarial audit item 13) ✅

## Current milestone
**TA — Tech Art Pipeline** (in progress)

## This sprint (max 3 tasks)
- [x] TA-0: GPU backend foundation — ModernGL context alongside Pygame, software fallback flag, triangle smoke test ✅
- [x] TA-1: Sprite batch + atlas loader — player and level geometry via GPU sprite batch, atlas packer tool ✅
- [x] TA-2: Parallax layer system — 5 FBOs with per-layer scroll factors, background split across sky/far/mid layers ✅
- [x] TA-3: 2D light buffer — ambient + up to 10 point/spot lights per level + player light, multiplied over mid/play ✅
- [x] TA-4: Post-processing stack v1 — bloom, LUT grade, vignette, grain, CRT stub; live toggles with F3 open ✅
- [x] TA-5: Fold distortion + gravity-flip bend — ripple on Time Dilation, frame bend on rotation, chromatic aberration ✅
- [x] GPU rotation-cinematic zoom: frame scales about the centre at composite time (lighting and ripples follow) ✅
- [ ] Vertical-slice review (Matt): play level_01 on the GPU renderer and judge it against the acceptance list below

## TA milestone track (tech art pipeline)

Full plan in `docs/tech-art-plan.md`. Runs alongside the M-series. Each TA module is one autonomous session.

| Module | Description | Status |
|---|---|---|
| TA-0 | GPU backend foundation (ModernGL context, software fallback, triangle) | ✅ Done |
| TA-1 | Sprite batch + atlas loader | ✅ Done |
| TA-2 | Parallax layer system (5 FBOs, per-layer scroll) | ✅ Done |
| TA-3 | 2D light buffer (ambient + point/spot lights per level) | ✅ Done |
| TA-4 | Post-processing stack v1 (bloom, vignette, grain, LUT) | ✅ Done |
| TA-5 | Fold distortion + gravity flip (screen-space warp, rotation bend) | ✅ Done |
| TA-6 | Feel framework (hitstop, sprite flash, squash/stretch, accessibility toggle) | — |
| TA-7 | GPU particles (instanced quad draw, visual upgrade) | — |
| TA-8 | Normal maps + emissive mask (optional, post-launch candidate) | — |

**Vertical slice acceptance (end of TA-5):** level_01 renders with 5 parallax layers, 3 point lights, bloom, vignette, grain, Fold distortion on rotation. 60fps on dev Mac. Software fallback passes all existing tests unchanged.
**Status 2026-11-05:** all items built. GPU frame ≈3ms on the dev Mac; 723 tests pass. Deviations: bloom is threshold-based (no emissive mask until TA-8); foreground layer empty (no art). Rotation-cinematic zoom now works on the GPU path. Awaiting Matt's in-game review.

**Open decisions (see `docs/tech-art-plan.md` §5):**
- Q3: Is the software renderer CI-only or a user-facing option for older/no-GPU machines?
- Q4: Normal map authoring — hand-painted or algorithmically generated from sprites?
- ~~Q5: CRT/halation pass~~ — decided: toggle wired in TA-4, shader is a pass-through stub
- ~~Q6: Parallax art for TA-2 testing~~ — decided: procedural split (see Decisions log)

## Needs revisit
- VFX particles (rotation burst, hit spark, landing dust) — mechanic is wired, visual execution needs tuning. Particle sizes, speeds, colours, and counts all open. Will be addressed in TA-7 (GPU particles).

## Known bugs / open items
- Up/W doubles as move and jump in horizontal gravity | annoying, may cause unintended jumps | deliberately left as is for now (see Decisions log)
- Helmet sprite files referenced in constants.py do not exist | cosmetic (placeholder renders)
- Amber glow overlay not implemented | deferred — needs `EXOSKELETON_GLOW_PATH` art asset (glow reference image showing exoskeleton path on black background)
- level_06 RIGHT gravity zone has no enemies — enemy patrol is x-axis only so wall-crawl placement isn't viable without y-patrol support. Deferred; fix when enemy AI supports directional patrol.
- ~~`JUMP_ANTICIPATION` dead animation state~~ — deleted (commit e8ca580; closes adversarial audit item 6)
- ~~`AbilitySlot.cooldown` naming confusion~~ — resolved: constant renamed `TIME_DILATION_POST_EFFECT_WAIT`, `total_recharge` property added (commit 9aa35f6; closes adversarial audit item 12)
- ~~Ability combination test coverage incomplete~~ — 7 new tests added in `TestAbilitySlotCombinations` (commit 63c331d; closes adversarial audit item 13)
- ~~level_01.json and anomaly_01.json both named "The Dividing Wall"~~ fixed: anomaly_03 renamed to "The Overhang"
- ~~No controls hint on start screen~~ fixed — first-time players see no key mapping
- ~~Death screen shows stats but not cause of death~~ fixed (commit 0a01be2 — death cause tracked and displayed)
- ~~Hard landing damage (HARD_LAND_VELOCITY = 13.0) has no visual feedback~~ fixed (commit 47ae69c — directional camera punch + red impact flash)
- ~~AIR_DECEL = 0.1 may read as floaty~~ fixed (commit b031882 — increased to 0.25)

## Risks
1. **Cadence.** 19 modules at 3 hr/week is multi-year. The M4 gate exists to avoid sinking that time into an unproven loop.
2. **Art pipeline.** AI-generated painterly sprites must stay consistent across animation frames. Use placeholders for everything non-player until M4.
3. **Determinism.** Time dilation and the Closed Loop rewind need a fixed-step, snapshot-able simulation. Locked in at M1/M2.
4. **Procgen.** "Valid in 2+ gravity orientations" is the hardest algorithmic piece. Hand-authored templates first.

## Backlog (parked, not commitments)
Cult enemies (Witness, Ordained, Architect); Archivist and Diplomat characters; Closed Loop rewind ultimate; spatial audio; controller rumble; Steam integration; Codex; amber glow overlay (needs `EXOSKELETON_GLOW_PATH` art asset); node map visual upgrade (star chart glyphs instead of text list); more anomaly rooms (currently 6); **level pathfinding validator** — BFS/flood-fill that simulates player movement (all 4 gravity orientations, jump arcs, moving platform positions) from spawn to goal for each level file; currently we use geometry-only checks (option 2, `tests/test_level_navigability.py`) which verify reachable positions exist but do not trace the navigation path — needed when procedural level generation (M11) ships.

### Pre-ship platform work (native Mac + Windows from one codebase)
Decided 2026-11-05: develop on Mac in a single codebase and defer packaging. Keep code portable meanwhile (`os.path.join` paths, no Mac-only libraries, GLSL 3.30 core shaders, software renderer kept green).
- **Save/log location:** frozen builds write `save.json` and `logs/` next to the executable, which on Mac is inside the `.app`. That breaks with code signing or a read-only app location. Move them to `~/Library/Application Support/The Fold` (Mac) and `%APPDATA%\The Fold` (Windows). About 15 lines, isolated.
- **Packaging session:** native arm64 Python environment (current Anaconda is Intel, so builds are x86_64 and macOS shows an "Intel support ending" warning; update CLAUDE.md's environment rule to match). GitHub Actions builds for Windows x64 + macOS arm64 (optionally Intel Mac). Switch the Windows build from a single `.exe` to a folder for Steam. Mac code signing.
- **Checkpoint:** one Windows smoke test (CI-built `.exe` on a real PC) before the M4 external playtest, so Windows-only issues surface early.

### Design ideas parking lot (unscoped, not committed)
- **Chrono degradation across levels** — cumulative chrono use degrades the reserve cap or regen rate across subsequent levels, making runs harder as the player burns more resource. Creates a "spend now vs. protect for later" arc across the run, not just within a level.
- **Environmental black holes / disrupted pixels** — levels seeded with small black holes that visually corrupt nearby pixels and geometry, creating additional hazard layers. Thematically grounded (singularity proximity warps space). Could be cosmetic-only at first, then gain gameplay consequences (disrupted platforms, suppressed abilities in radius).

## Decisions needed from Matt
1. ~~Re-order to vertical slices?~~ Decided: yes.
2. ~~Launch scope.~~ Decided: lean v1.0.
3. ~~Horizontal-gravity controls.~~ Decided: no change for now.
4. ~~Art strategy through M4.~~ Decided: placeholders for everything except the player sprite and existing background.
5. **TA Q3 — Software renderer scope:** CI-only fallback, or exposed as a user option for older/no-GPU machines? (Recommendation: CI-only now, revisit on a compatibility report.)
6. **TA Q4 — Normal map authoring:** Hand-painted per sprite, or algorithmically generated from painted surface? (Recommendation: generated via SpriteIlluminator or similar; upgrade hero sprites if quality is insufficient.)
7. ~~**TA Q5 — CRT/halation pass:**~~ Decided 2026-11-05: stub toggle in TA-4. In scope for TA-4, or stub and defer post-vertical-slice? (Recommendation: stub the toggle in TA-4, leave shader empty; decide after seeing full post stack on real art.)
8. ~~**TA Q6 — TA-2 parallax art:**~~ Decided 2026-11-05: procedural split. Does TA-2 need painted layered backgrounds, or test with procedural tinted copies of `background.png`? (Recommendation: procedural split for TA-2 testing; real layers when art pipeline produces them.)

## Decisions log
- 2026-10-31: roadmap drafted.
- 2026-10-31: re-ordered around vertical slices; Audio, UI, Save and most Phase 2/3 work sit behind the M4 go/no-go gate.
- 2026-10-31: v1.0 scope is lean: 1 character, 3 enemy types, 3 abilities, 3 modifiers, 3 artifacts. Cult enemies, extra characters and the rewind ultimate are post-launch.
- 2026-10-31: art through M4 is placeholders (colored shapes) for enemies, platforms, holes and UI; real art only for the player and the existing background.
- 2026-10-31: controls unchanged for now (Space/Up/W jump in every orientation). Option on the table if revisited: Space always jumps plus an orientation-aware arrow jump (Down gravity: Up/W; Up: Down/S; Right: Left/A; Left: Right/D), built as a switchable constant and A/B tested.
- 2026-11-01: amber glow overlay deferred — requires `EXOSKELETON_GLOW_PATH` (a reference image showing the exoskeleton lit against black, used to define glow coordinates). Will be implemented in a dedicated art-update session once the asset exists.
- 2026-11-01: fold_stability cost per integrity-0 death = 20 (5 deaths end a run). Leaves budget for hole encounters and node timers in M4b.
- 2026-11-01: fold tint starts at stability 80, max alpha 110 at stability 0. Red overlay only — shader distortion deferred to M6.
- 2026-11-01: M3 anchored state simplified — integrity 0 = immediate level reset. No anchored timer. Fold stability cost paid on reset.
- 2026-11-02: The Archivist (second character) deferred to backlog. M7b skipped; game ships with one character (The Navigator) in v1.0.
- 2026-11-02: fold-playtester built as a sibling project (../fold-playtester/), never shipped in the binary. Visual agent using Claude computer-use. Run with `python run_playtest.py` from that directory.
- 2026-11-02: 28-item design assessment via code review. Core finding: hole uncertainty non-functional, enemies identical every run, 5-node run too short for build system or pressure curve to land. M8 sprint pivoted to playtest fixes. Steam deferred indefinitely — game needs art before Steam is relevant.
- 2026-11-02: Proposed stability rebalance: death cost 20→15, black hole 15→10, white hole restore 5→15. Makes holes feel like calculated risk rather than a penalty worse than dying twice. Pending implementation in M8a.
- 2026-11-05: Tech art plan approved (`docs/tech-art-plan.md`). Resolution strategy: stay at 800×600 world units, upscale to display (TA Q1). Art pipeline first, art second — build TA-0 through TA-5 with current placeholders, swap real art later (TA Q2).
- 2026-11-05: Adversarial game-dev audit completed. 12 bugs fixed across GPU, physics, resources, combat, animation, and input systems. All 3 remaining open items closed same session: JUMP_ANTICIPATION deleted, cooldown rename + total_recharge property, ability combination tests added.
- 2026-11-05: TA-2 parallax: placeholder layers are procedural splits of `background.png` (TA Q6). Painted art drops in as `assets/backgrounds/layers/{sky,far,mid}.png` with no code change. Foreground layer allocated but left empty until there is art for it. Per-level scroll overrides via optional `"layers"` key in level JSON; the play layer is locked to 1.0.
- 2026-11-05: TA-3 lighting: only levels with a `"lights"` key are lit (level_01 for now; others render as after TA-2). Lit layers are mid + play; sky/far stay self-lit. Player carries a warm amber point light in lit levels. Light buffer is half-float, capped at 2.0 for mild overbright.
- 2026-11-05: TA-4 post stack. Bloom keys off a brightness threshold, not an emissive mask (masks are TA-8). Grade contrast pivots at 0.18, not 0.5, because the art is mostly below 0.1 luminance and a 0.5 pivot crushed it. Grain is scaled down in shadows for the same reason. HUD and fold tint skip post. Build fix: numpy un-excluded and `shaders/` bundled in the PyInstaller spec (a full build has not been run to confirm).
- 2026-11-05: TA-5 Fold distortion. The ripple fires on the rising edge of Time Dilation (so Kerr Ring's free activation ripples too), not on the E key. The bend fires on every `_do_gravity_rotation` (R key, gravity zones, chrono snap-back). Distortion runs after bloom and before grade/vignette/grain, so the glow warps but the screen-fixed effects don't.
- 2026-11-05: 28-item design assessment (separate from adversarial audit) drove the M8 sprint: hole uncertainty non-functional, enemies identical every run, 5-node run too short. All three addressed in M8a-c.

## Last session
Date: 2026-11-05
Did: TA-2 parallax, debug overlay → F3, TA-3 lighting, TA-4 post stack, TA-5 Fold distortion + gravity bend (Feel class; distortion post pass with ripple, bend, chromatic aberration). PyInstaller spec fixed (numpy, shaders/). The GPU vertical slice is feature-complete.
State of tests: 723 passing
Next up: Matt's vertical-slice review in game (GPU renderer, level_01). Also: run build/build_mac.sh once to confirm a frozen GPU build launches. GPU rotation zoom fixed after the TA-5 review. Then TA-6 (feel framework).
