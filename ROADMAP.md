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
- M5c — Anomaly rooms ✅ Done 2026-11-02 — 3 hand-authored rooms (physics gate, RIGHT-gravity navigation, UP-gravity overhead), seeded picker, wired into hole node flow
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
**M8 — Playtest Pass**

## This sprint (max 3 tasks)
- [x] M8a: Stability rebalance — death cost 20→15, black hole 15→10, white hole restore 5→15 ✅
- [x] M8b: Enemy data pass — EnemyDef in level JSON; Temporal Echo back in combat rooms; varies by node ✅
- [x] M8c: Extend run to 9 nodes — 4 combat + 4 hole + singularity; 4 new level files (05-08); pressure curve validated ✅

## Needs revisit
- VFX particles (rotation burst, hit spark, landing dust) — mechanic is wired, visual execution needs tuning. Particle sizes, speeds, colours, and counts all open. Revisit once we have a clearer feel for the visual language.

## Known bugs / open items
- Up/W doubles as move and jump in horizontal gravity | annoying, may cause unintended jumps | deliberately left as is for now (see Decisions log)
- Helmet sprite files referenced in constants.py do not exist | cosmetic (placeholder renders)
- Amber glow overlay not implemented | deferred — needs `EXOSKELETON_GLOW_PATH` art asset (glow reference image showing exoskeleton path on black background)
- Enemies in levels 05-08 placed in DOWN-gravity starting section only — incoherent once player enters gravity zone. Deferred; needs level-specific enemy y-coordinates for ceiling/wall gravity areas.
- AIR_DECEL = 0.1 may read as floaty — lateral momentum persists ~50 frames airborne. Needs live playtest to confirm.
- level_01.json and anomaly_01.json both named "The Dividing Wall" — duplicate name on node map display
- No controls hint on start screen — first-time players see no key mapping
- Death screen shows stats but not cause of death — players can't learn from runs
- Hard landing damage (HARD_LAND_VELOCITY = 13.0) has no visual feedback — damage source is opaque to player

## Risks
1. **Cadence.** 19 modules at 3 hr/week is multi-year. The M4 gate exists to avoid sinking that time into an unproven loop.
2. **Art pipeline.** AI-generated painterly sprites must stay consistent across animation frames. Use placeholders for everything non-player until M4.
3. **Determinism.** Time dilation and the Closed Loop rewind need a fixed-step, snapshot-able simulation. Locked in at M1/M2.
4. **Procgen.** "Valid in 2+ gravity orientations" is the hardest algorithmic piece. Hand-authored templates first.

## Backlog (parked, not commitments)
Cult enemies (Witness, Ordained, Architect); Archivist and Diplomat characters; Closed Loop rewind ultimate; spatial audio; controller rumble; Steam integration; Codex; amber glow overlay (needs `EXOSKELETON_GLOW_PATH` art asset); jump buffer (8–10 frame input queue); node map visual upgrade (star chart glyphs instead of text list); 6+ anomaly rooms (currently 3); controls hint on start screen; death cause on death screen; **level pathfinding validator** — BFS/flood-fill that simulates player movement (all 4 gravity orientations, jump arcs, moving platform positions) from spawn to goal for each level file; currently we use geometry-only checks (option 2, `tests/test_level_navigability.py`) which verify reachable positions exist but do not trace the navigation path — needed when procedural level generation (M11) ships.

### Design ideas parking lot (unscoped, not committed)
- **Chrono degradation across levels** — cumulative chrono use degrades the reserve cap or regen rate across subsequent levels, making runs harder as the player burns more resource. Creates a "spend now vs. protect for later" arc across the run, not just within a level.
- **Environmental black holes / disrupted pixels** — levels seeded with small black holes that visually corrupt nearby pixels and geometry, creating additional hazard layers. Thematically grounded (singularity proximity warps space). Could be cosmetic-only at first, then gain gameplay consequences (disrupted platforms, suppressed abilities in radius).

## Decisions needed from Matt
1. ~~Re-order to vertical slices?~~ Decided: yes.
2. ~~Launch scope.~~ Decided: lean v1.0.
3. ~~Horizontal-gravity controls.~~ Decided: no change for now.
4. ~~Art strategy through M4.~~ Decided: placeholders for everything except the player sprite and existing background.

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

## Last session
Date: 2026-11-02
Did: Completed M8 sprint — M8a stability rebalance (death/black hole/white hole costs rebalanced), M8b enemy data pass (EnemyDef dataclass, all 4 combat levels now have varied enemy compositions driven by JSON, Temporal Echo back in rotation), M8c 9-node run (NODE_SEQUENCE extended to 4 combat + 4 hole + singularity, 4 new level files 05-08 with gravity zone complexity scaling). Node map now shows 8 playable nodes before singularity. Singularity pressure curve validated across all 8 nodes.
State of tests: 579 passing
Next up: Playtest the 9-node run; assess whether the pressure curve lands; consider M9 (audio v1, anomaly room variety, or jump buffer)
