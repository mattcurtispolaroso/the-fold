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
**M2: First Toy** (in progress)

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

**M2. First Toy** (in progress)
- Player dataclass refactor, serialisable to dict ✅
- `chrono_reserve` resource with movement-driven regen (15/s moving, 0/s idle) ✅
- Time Dilation ability — E key, 3s platform freeze, 25 CR cost, 2s cooldown ✅
- Amber glow overlay driven by `chrono_reserve` — deferred to art update (needs `EXOSKELETON_GLOW_PATH`)
- level_04: level that cannot be solved without Time Dilation
Done when: a level exists that cannot be solved without dilating something.

**M3. First Fight** (6-8 sessions)
- Minimal Entity system (physics/render/health components)
- Enemy: Temporal Echo only, reacts to time dilation
- Combat: hit detection, knockback, i-frames
- `anchor_integrity`, Anchored death state, respawn, fall-off-screen cost
Done when: an arena room is winnable and losable, and dilation changes how you fight.

**M4. First Run** (8-12 sessions): the make-or-break slice
- Run state manager (serialisable)
- 5-node run on a simple node screen, rooms from hand-authored templates (no procgen yet)
- Hole encounter: black/white, identical outside, with the resource consequences from the design bible
- `fold_stability` shown via environment tint/distortion
- Start screen, death/win screen
Done when: a ~10 min run from start to singularity or death is completable. **Gate:** external playtest. Is it fun? Go / redesign / cut.

**M5. Content Alpha** (post-gate)
Data-driven item system; 3 abilities, 3 modifiers, 3 artifacts; Fold Predator and The Anchored enemies; procedural room generation (valid in 2+ gravity orientations); real node map UI; HUD; audio v1.

**M6. Polish Beta**
VFX (pooled particles), juice, full rotation cinematic, singularity difficulty curve tuning, art pass.

**M7. Ship**
Save/meta-progression, second character, Mac/Windows PyInstaller builds, Steam integration.

## This sprint (max 3 tasks)
- [ ] level_04 "Frozen Gate": level requiring Time Dilation to solve | done when: gap is uncrossable without freezing the platform, level added to TAB cycle, 289+ tests pass
- [ ] `anchor_integrity` on Player (3-hit pool, visual TBD) | done when: field exists, serialisable, resets on spawn, falls off screen costs 1 hit
- [ ] First enemy placeholder — Temporal Echo patrol rect | done when: enemy rect spawns in level, moves back and forth, stops when Time Dilation is active

## Known bugs / open items
- Up/W doubles as move and jump in horizontal gravity | annoying, may cause unintended jumps | deliberately left as is for now (see Decisions log)
- Helmet sprite files referenced in constants.py do not exist | cosmetic (placeholder renders)
- `main.py` slightly over 300 lines | process/cosmetic — extract draw helpers if it grows further
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

## Last session
Date: 2026-11-01
Did: M2 sprint complete — Player dataclass refactor (11 new tests), chrono_reserve resource with movement-driven regen (7 new tests), Time Dilation ability E-key (5 new tests). Amber glow deferred to art update.
State of tests: 289 passing
Next up: level_04 "Frozen Gate" — first required-dilation level
