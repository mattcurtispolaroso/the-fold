# CLAUDE.md — The Fold

## Project Overview

2D platformer prototype built with Python/Pygame. Single-file game (`main.py`) with a gravity rotation mechanic.

## Key Files

- `main.py` — game source (all logic in one file)
- `test_game.py` — automated unit tests (unittest framework, runs headless)
- `qa_checklist.md` — manual QA checklist for playtesting
- `requirements.txt` — Python dependencies (pygame)

## Automated QA Rules

Follow these after every code change:

1. After every change to `main.py`, automatically run `python3 test_game.py` and show the results before considering the task complete.
2. If any tests fail, fix them before moving on — do not ask whether to fix them, just fix them.
3. After fixing failing tests, run the test suite again to confirm everything passes.
4. If you add a new mechanic or change existing game logic, add the corresponding unit tests to `test_game.py` at the same time.
5. At the end of every session, update `qa_checklist.md` with any new edge cases or issues discovered.

**Never consider a coding task done until the full test suite passes.**

## Game Design Bible

Read this to understand what we are building before making any suggestions or changes.

**GAME:** The Fold
**GENRE:** Roguelite 2D platformer / side-scroller
**TONE:** Retrofuturistic 1962+. Optimistic technology meeting cosmic indifference. Inspired by Carlo Rovelli's writings on black holes and the nature of time. Not post-apocalyptic, not Fallout. Sleek, strange, alive.

### Core Mechanics

**CORE MECHANIC 1 — SPACETIME MANIPULATION:** Player can locally warp gravity and time around a point on screen, independently of themselves or applied to themselves. Maximum 3 active abilities + 1 ultimate per character. Abilities use a Fold Energy resource with cooldowns.

**CORE MECHANIC 2 — GRAVITY ROTATION:** The entire map rotates 90 degrees at a time, changing which direction gravity pulls. Player controls this. Cycles through all 4 orientations. Eventually will have a zoom in / rotate / zoom out animation. Player navigates in 2 directions at a time.

**CORE MECHANIC 3 — BLACK/WHITE HOLE UNCERTAINTY:** Holes look identical from outside the event horizon. Entering is a committed risk. Black hole = power suppression and danger. White hole = explosive reward and power surge. Players can learn to read subtle environmental hints but never know for certain.

### Difficulty Curve

Powers weaken as player approaches the singularity. Early game feels expansive and powerful. Late game feels desperate and constrained. This is physically grounded — near a singularity spacetime is already so warped that adding your own distortion becomes harder.

### Run Structure

Node map styled as a star chart. Start → navigate nodes → reach singularity. Node types include combat, anomaly puzzles, hole encounters, merchants, and rest points. Each run is procedurally generated.

### Buildout System — Three Tiers

**Abilities** (active powers, max 3 + ultimate) — examples: Time Dilation, Gravity Anchor, Fold Burst, Horizon Shift, Temporal Echo, Causality Lance

**Modifiers** (passive augments to abilities) — examples: Event Horizon, Tidal Coupling, Redshift, Quantum Foam, Closed Timelike Curve

**Artifacts** (rare run-defining items) — examples: Kerr Ring, Penrose Diagram, Hawking Emitter, Chronometer, Rovelli Stone

### Stakes

Civilizational not personal. Humanity's timeline, Fold stability, singularity collapse. Tracked visually on screen via the Fold Watch. No named characters who age or die.

### Characters

Archetypes not people. Distinct ultimates that express their philosophical relationship with spacetime. Unlocked progressively across runs. Examples:

- **The Navigator:** ultimate is Dead Reckoning — freeze time globally for 3 seconds except for yourself
- **The Archivist:** ultimate is White Hole — emit everything absorbed this run in one catastrophic release
- **The Diplomat:** ultimate is Closed Loop — rewind the last 10 seconds of world state but not your own position

### Replayability Levers

Randomized node maps, black/white hole uncertainty, build combinatorics, character variety, permanent meta-unlocks across runs, civilizational stakes tracker.

### Physics Rule

The physics of spacetime in this world never change and are never randomized. Players can learn and master them completely. **This is non-negotiable.**

### Platform

Mac + Windows, shipping on Steam. One time purchase.

### Development Approach

Solo developer, 3 hours per week. Prototype first, always. Never build what isn't needed yet. Every session must produce something playable. Run `python3 test_game.py` after every change.

### Current Phase

**Phase 0 — Foundation.** Focus is exclusively on making movement and gravity rotation feel great. Do not suggest or implement features beyond this scope until instructed.
