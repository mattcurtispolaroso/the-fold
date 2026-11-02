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
- M5c — Anomaly rooms (procedural room generation, valid in 2+ gravity orientations)
- M5d — HUD ✅ Done 2026-11-01 — integrity pips + chrono bar + dilation status; gravity label removed from production HUD
- M5e — The Anchored enemy ✅ Done 2026-11-01 — wander/stutter AI, frozen by Time Dilation, no-op on gravity rotate
- Audio v1 — deferred

**M6. Polish Beta**
VFX (pooled particles), juice, full rotation cinematic, singularity difficulty curve tuning, art pass.

**M7. Ship**
Save/meta-progression, second character, Mac/Windows PyInstaller builds, Steam integration.

## Current milestone
**M5 — Content Alpha** (in progress)

## This sprint (max 3 tasks)
- [x] M5b — Fold Predator enemy ✅
- [x] M5d — HUD (always-visible resources) ✅
- [x] M5e — The Anchored enemy ✅
- [ ] M5c — Anomaly rooms (hand-authored templates, valid in 2+ gravity orientations)

## Known bugs / open items
- Up/W doubles as move and jump in horizontal gravity | annoying, may cause unintended jumps | deliberately left as is for now (see Decisions log)
- Helmet sprite files referenced in constants.py do not exist | cosmetic (placeholder renders)
- Amber glow overlay not implemented | deferred — needs `EXOSKELETON_GLOW_PATH` art asset (glow reference image showing exoskeleton path on black background)

## Risks
1. **Cadence.** 19 modules at 3 hr/week is multi-year. The M4 gate exists to avoid sinking that time into an unproven loop.
2. **Art pipeline.** AI-generated painterly sprites must stay consistent across animation frames. Use placeholders for everything non-player until M4.
3. **Determinism.** Time dilation and the Closed Loop rewind need a fixed-step, snapshot-able simulation. Locked in at M1/M2.
4. **Procgen.** "Valid in 2+ gravity orientations" is the hardest algorithmic piece. Hand-authored templates first.

## Backlog (parked, not commitments)
Cult enemies (Witness, Ordained, Architect); Archivist and Diplomat characters; Closed Loop rewind ultimate; spatial audio; controller rumble; Steam cloud and trading cards; Codex; amber glow overlay (needs `EXOSKELETON_GLOW_PATH` art asset).

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

## Last session
Date: 2026-11-01
Did: M5b (Fold Predator), M5d (HUD), M5e (The Anchored). Room now has both enemies — Fold Predator stunned by any gravity rotation, The Anchored frozen by Time Dilation. Always-visible HUD: 3 integrity pips, segmented chrono bar, dilation status. Single-enemy architecture expanded to enemies list.
State of tests: 483 passing
Next up: M5c — Anomaly rooms (hand-authored templates, valid in 2+ gravity orientations).
