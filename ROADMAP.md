# The Fold: Roadmap

Written 2026-10-31 after a repo review. Estimates are rough and assume one ~3 hr session per week. Overnight Claude Code runs can compress them.

## Vision
A retrofuturistic 1962 roguelite platformer where you bend gravity and time, and every black/white hole is a committed gamble. Powers weaken as you near the singularity. Physics never changes, so players can master it.

## Status review (as of 2026-10-31)

**Where the project actually is:** a solid, well-tested foundation, but not yet a game. There is one test level, no enemies, no abilities, no resources, no win/lose loop.

| Area | State |
|---|---|
| Module 1 Physics (4 gravity orientations, coyote, variable jump) | Done |
| Module 2 Level architecture (JSON levels, moving platforms, ASCII helper) | Done, one test level only |
| Module 3 Camera (follow, bounds, shake) | Done |
| Stability infra (crash handler, 3 logs, watchdog, level fallback, entity caps) | Done |
| Module 13 Sprite/animation | ~70%. Uncommitted. 3 player sprites exist (idle, jump_rising, 1 walk frame). Helmet sprites referenced in constants but absent. No `EXOSKELETON_GLOW_PATH` |
| Modules 4-12, 14-19 (abilities, entities, enemies, combat, run state, items, node map, level gen, audio, VFX, UI, save, juice, cinematic, Steam) | Not started. `src/entities/` and `src/data/` are empty |
| Tests | 253 passing per last recorded session (2026-04-10). **Not re-run during this review** (no pygame in the review sandbox). Run `python test_game.py` on your Mac first |

**Findings**
1. **Idle ~6.5 months.** Last commit 2026-04-02, last session 2026-04-10.
2. **Uncommitted work at risk:** ~365 changed lines in `animation.py`/`constants.py`/`main.py`, plus untracked `sprite_sheet.py` and `tests/test_sprite_sheet.py`.
3. **Manual QA checklist is entirely unchecked.** Phase 0's goal ("movement and rotation feel great") has never been formally validated.
4. **Plan is horizontal, not vertical.** 19 modules built layer by layer means no playable "game" for a long time. At this cadence that is years.
5. **Gaps vs your own CLAUDE.md rules:** variable (capped) dt instead of fixed 60hz timestep; `animation.py` is 424 lines (limit 300); player state appears to live as locals in `main()` rather than an entity/dataclass; open item C2 (bounds clamping uses a separate code path from collision); swept collision not verified in this review.
6. **Doc drift:** CLAUDE.md still says "single-file game" and "Phase 0" while Modules 1-3 and stability are done; mixes `python` / `python3`.

## Strategy
Stop building by layer. Build **thin vertical slices**, each ending in something playable, and put a go/no-go "is the loop fun?" gate after the first full run (M4). Content breadth (items, enemies, procgen, polish) comes only after that gate.

## Current milestone
**M0: Re-baseline, then M1: Feel** (Phase 0 exit)

## Milestones

**M0. Re-baseline** (1-2 sessions)
Done when: WIP committed, 253 tests confirmed green on your Mac, QA checklist ticked, CLAUDE.md phase/overview corrected, `/pm` workflow in place.

**M1. Feel** (5-7 sessions): finishes Phase 0
- Fixed 60hz timestep with accumulator (do now: time dilation and rewind depend on deterministic steps)
- Resolve C2 (unify bounds into collision)
- Horizontal-gravity controls: **no change for now** (decided 2026-10-31); revisit after M1 playtests
- Simple rotation transition (~0.3-0.5s) so rotation reads as an event; full cinematic stays in M6
- Finish Module 13 minimally: working idle/walk/jump with placeholders for missing frames, split `animation.py` under 300 lines
- 2 more levels that require rotation to solve
Done when: QA checklist fully ticked; 2 people who are not you play 5 minutes and understand rotation without being told.

**M2. First Toy** (6-8 sessions)
- Refactor-only session first: player into an entity/dataclass with serialisable state (no features in that session)
- `chrono_reserve` resource with regen rules
- One ability: Time Dilation, affecting a moving platform and a hazard independently of the player
- Amber glow overlay driven by resource (needs `EXOSKELETON_GLOW_PATH`, from the glow reference image)
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
- [ ] Commit WIP and run `python test_game.py` on your Mac | done when: clean `git status`, 253+ tests green
- [ ] Play `level_01` for 20 min and tick `qa_checklist.md` | done when: every box checked or turned into a Known bug
- [ ] Add `ROADMAP.md` + `/pm` command to the repo and fix CLAUDE.md phase/overview text | done when: `/pm start` runs and reports accurately

## Known bugs / open items
- C2: bounds clamping separate from collision | severity: annoying (edge cases only) | see DECISIONS_NEEDED.md
- Rotating against a screen edge can briefly clip the player before clamp corrects | annoying
- Up/W doubles as move and jump in horizontal gravity | annoying, may cause unintended jumps | deliberately left as is for now (see Decisions log)
- `animation.py` 424 lines, over the 300-line limit | cosmetic/process
- Helmet sprite files referenced in constants.py do not exist | cosmetic (placeholder renders)

## Risks
1. **Cadence.** 19 modules at 3 hr/week is multi-year. The M4 gate exists to avoid sinking that time into an unproven loop.
2. **Art pipeline.** AI-generated painterly sprites must stay consistent across animation frames. Use placeholders for everything non-player until M4.
3. **Determinism.** Time dilation and the Closed Loop rewind need a fixed-step, snapshot-able simulation. Locked in at M1/M2.
4. **Procgen.** "Valid in 2+ gravity orientations" is the hardest algorithmic piece. Hand-authored templates first.

## Backlog (parked, not commitments)
Cult enemies (Witness, Ordained, Architect); Archivist and Diplomat characters; Closed Loop rewind ultimate; spatial audio; controller rumble; Steam cloud and trading cards; Codex.

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

## Last session
Date: 2026-04-10
Did: helmet overlay gravity-aware positioning fix; stability infrastructure complete
State of tests: 253 passing (not re-run 2026-10-31)
Next up: see "This sprint"
