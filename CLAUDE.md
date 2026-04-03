# CLAUDE.md — The Fold

## Environment

Always use the Conda base Python environment, never `/usr/bin/python3`. Run tests with `python test_game.py` not `python3 test_game.py`. If a `ModuleNotFoundError` occurs, the likely cause is wrong Python environment not a missing package.

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

## Resource Systems

Read this before making any design or implementation decisions about player health, abilities, or progression.

### Core Design Philosophy — Resources

The Fold uses a three-resource system where each resource operates on a different timescale and interacts with the others in meaningful ways. Inspired by Magic: The Gathering's life-as-resource mechanic — the player should face genuine decisions about spending precious resources to generate advantage. Names are placeholder and will be refined later.

### Resource 1 — Temporal Anchor Integrity (Personal Survival)

The player's personal health pool. Represented visually as the overall brightness of the amber exoskeleton glow — full health blazes, each hit noticeably dims it, critical state flickers. Small pool of 3-4 hits. Does not represent the player's body being damaged — it represents their personal timeline destabilising. At zero the player becomes momentarily Anchored — the death state — and loses one Fold Stability point before respawning at the last safe position with Integrity restored. Restored by: white hole encounters, rest nodes, certain artifacts. Depleted by: enemy hits, falling off screen, certain ability costs, black hole encounters.

### Resource 2 — Fold Stability (Run Survival)

The run's overall health. Represents how stable the Fold itself is — the civilizational stakes tracker. Starts at 100 each run, never fully restores, depletion is permanent within a run. Reaching zero ends the run entirely — the singularity wins. Displayed on screen as an environmental indicator — background distortion, redshift and warping increase as Fold Stability decreases. The world itself shows how close to collapse everything is. Not shown as a traditional health bar — the environment IS the indicator. Depleted by: Temporal Anchor Integrity hitting zero, black hole encounters, certain enemy abilities, taking too long at nodes. Slightly restored by: white hole encounters, specific rare artifacts only.

### Resource 3 — Chrono Reserve (Ability Power)

The player's time manipulation fuel. Powers all spacetime abilities — Time Dilation, Gravity Anchor, Fold Burst, all active abilities, and the ultimate. More powerful abilities cost more. The ultimate costs both Chrono Reserve AND Temporal Anchor Integrity simultaneously — Phyrexian mana style, world-stopping power at personal cost. Represented visually as the pulse speed along the exoskeleton — full reserve pulses slow and steady, depleting pulses faster and more erratic, empty goes still with only a faint flicker. Regenerates through active engagement and risk-taking — combat, fast movement, entering holes, proximity to enemies. Does NOT regenerate through hiding or passive play. The universe rewards those who engage with it.

### Proximity to Singularity Affects All Three

- **Far from singularity** — Chrono Reserve regenerates quickly, abilities are cheap, the universe has slack. Player feels powerful and expansive.
- **Mid run** — Chrono Reserve regenerates slower, adding distortions to already warped spacetime costs more. Harder choices about ability use.
- **Near singularity** — Chrono Reserve barely regenerates, every ability use is a significant decision, Temporal Anchor Integrity does not restore at rest nodes, Fold Stability is likely depleted. Maximum pressure, maximum stakes. This is intentional and thematic — near a singularity, time runs out.

### The MTG Tension

The interesting decisions come from resource interaction. Example: low on Temporal Anchor Integrity with an enemy approaching. Time Dilation would stop it but costs Chrono Reserve you are also low on. Do you spend Chrono Reserve to protect Integrity? Or take the hit, preserve the Reserve, and trust you can restore Integrity at the next rest node? This is the core decision loop — spend the thing that is killing you to survive longer.

### Falling Off Screen

Costs one Temporal Anchor Integrity hit. Player respawns at last safe ground position with Chrono Reserve intact. If Temporal Anchor Integrity is already at zero, costs one Fold Stability point instead. Gravity rotation should be used to avoid falls — this mechanic makes avoiding falls meaningful even when feeling invincible.

### Hole Encounters — Black vs White

- **Black hole** — depletes Temporal Anchor Integrity by one hit and reduces Fold Stability. Powers are suppressed inside. High risk.
- **White hole** — restores Temporal Anchor Integrity fully and provides a small Fold Stability restoration. Explosive reward and power surge on exit.
- Both look identical from outside the event horizon. The uncertainty is the mechanic.

### Visual Language — All Three Resources on One System

- **Temporal Anchor Integrity** — overall brightness of amber exoskeleton glow.
- **Chrono Reserve** — pulse speed along the exoskeleton. Full is slow and steady. Depleting is fast and erratic. Empty is near still with faint flicker.
- **Fold Stability** — the background and environment. Distortion, redshift and warping increase as stability decreases. No traditional health bar — the world itself is the indicator.

Goal: three resources readable at a glance with zero traditional UI required for moment-to-moment decisions. The suit and the world tell the complete story.

### Names Are Placeholder

Temporal Anchor Integrity, Fold Stability and Chrono Reserve are working names only. Final names to be decided later. Do not treat these as locked. When implementing refer to them in code as `anchor_integrity`, `fold_stability` and `chrono_reserve` until final names are confirmed.

### Exoskeleton Glow Implementation

The amber glow on the player exoskeleton is NOT baked into sprite art. Player sprites are generated with a dark unlit exoskeleton — cold carbon and titanium, no glow. The glow is added entirely by Pygame at runtime as a dynamic overlay layer drawn on top of the sprite each frame.

**Glow behaviour driven by resources:**

- `anchor_integrity` full — bright steady amber glow, slow pulse
- `anchor_integrity` damaged — noticeably dimmer amber, slightly faster pulse
- `anchor_integrity` critical — barely visible amber, fast erratic pulse
- `anchor_integrity` zero — glow extinguished, suit colour shifts sickly green via tint
- `chrono_reserve` full — slow steady pulse rhythm
- `chrono_reserve` depleting — pulse accelerates proportionally
- `chrono_reserve` empty — glow goes nearly still, faint flicker only

**Implementation:** draw player sprite first, then draw amber glow surface over exoskeleton path using `pygame.draw` with per-pixel alpha. Glow position defined as a list of rectangles or points tracing the exoskeleton path in sprite coordinates. This list lives in `constants.py` as `EXOSKELETON_GLOW_PATH`.

**Art pipeline:** all player sprites generated with dark unlit exoskeleton. One separate glow reference image generated showing exoskeleton path glowing amber against black — used by Claude Code to define `EXOSKELETON_GLOW_PATH` coordinates.

## Coding Standards and Best Practices

### General Principles

- **Readability over cleverness** — write code that is easy to understand at a glance. A future session of Claude Code or a human should be able to read any function and understand what it does within 30 seconds. Never sacrifice clarity for brevity.
- **Single responsibility** — every function does one thing. Every class has one job. If a function needs a long comment to explain what it does, it should be broken into smaller functions with descriptive names instead.
- **Fail loudly** — never silently swallow errors. If something goes wrong, log it clearly and crash early rather than continuing in a broken state. Silent failures in games cause bugs that are nearly impossible to trace.
- **No magic numbers** — every numeric constant that affects gameplay must be defined as a named constant at the top of its module. `JUMP_FORCE = 18` not just `18` scattered through the code. This makes tuning and balancing possible without hunting through files.
- **Composition over inheritance** — prefer building complex behaviour by combining simple components rather than deep inheritance chains. This game will grow — flat architectures are easier to modify than tall ones.

### Python Specific

- **Type hints on all function signatures** — `def move_player(velocity: Vector2, gravity: float) -> Vector2` not `def move_player(v, g)`. This makes the code self-documenting and catches errors early.
- **Dataclasses for game data** — use Python dataclasses for things like `PlayerState`, `LevelData`, `AbilityConfig`. Cleaner than dictionaries, safer than plain classes.
- **Constants in a dedicated `constants.py` file** — all tunable game values in one place. Screen size, gravity strength, jump force, platform speeds, ability cooldowns. Never buried in logic files.
- **Avoid global state** — pass state explicitly through function parameters or class instances. Global variables make autonomous sessions dangerous — a change in one place has invisible effects elsewhere.
- **Use enums for game states** — `GravityDirection.DOWN` not the integer `0`. `PlayerState.JUMPING` not the string `'jumping'`. Enums prevent entire classes of bugs from typos and wrong values.

### Pygame Specific

- **Separate update and draw** — never mix logic and rendering in the same function. `update()` changes state, `draw()` reads state and renders it. This separation is non-negotiable.
- **Delta time everywhere** — all movement and physics must be multiplied by delta time so the game runs identically at 30fps and 144fps. Never assume a fixed frame rate.
- **Sprite groups for everything** — use Pygame sprite groups not manual lists. They handle drawing order, collision detection and cleanup automatically.
- **Asset manager singleton** — one class responsible for loading and caching all images and sounds. Never load assets inside game loops. Load once, reference everywhere.
- **Fixed timestep for physics** — use a fixed physics timestep separate from the render loop. This makes physics deterministic and reproducible — essential for a game with precise spacetime mechanics.

### Architecture

- **Data-driven design** — game content like levels, abilities, enemies and artifacts should be defined in JSON or data files not hardcoded in Python. Adding a new ability should mean adding a JSON entry not writing new code.
- **Event system** — use a simple event bus for communication between systems. The combat system should not directly call the UI system — it should emit a `PLAYER_DAMAGED` event that anything can listen to. This keeps systems decoupled.
- **State machines for everything that has modes** — player movement, enemy AI, game screens, ability states. Explicit state machines prevent the impossible-to-debug `if is_jumping and not is_falling and was_on_ground` logic chains.
- **Component pattern for entities** — player, enemies and platforms should be built from reusable components like `PhysicsComponent`, `RenderComponent`, `HealthComponent` rather than monolithic classes. New entity types are just new combinations of existing components.
- **Clear module boundaries** — physics code never imports from UI code. Rendering never imports from game logic. Draw a dependency diagram — it should be a tree not a web.

### File and Project Structure

Keep the project organised as follows and never deviate:

```
/the-fold
├── main.py            — entry point only, minimal code
├── constants.py       — all tunable values
├── assets/            — images, sounds, fonts
├── levels/            — level data files
├── src/
│   ├── physics/       — gravity, collision, movement
│   ├── entities/      — player, enemies, platforms
│   ├── systems/       — ability, combat, audio, ui
│   ├── rendering/     — sprites, animation, vfx, camera
│   └── data/          — save, run state, meta progression
├── tests/             — all test files
└── tools/             — level editor helper, asset pipeline scripts
```

### Autonomous Session Specific

- **Never refactor and add features in the same session** — if refactoring is needed, do it in a dedicated session and confirm tests pass before the next session adds features on top.
- **Before touching any existing working system, read it fully first** — never modify code you haven't read in this session.
- **If a task would require changing more than 3 files simultaneously**, stop and write the plan to `DECISIONS_NEEDED.md` for human review first.
- **Prefer reversible changes** — if a significant change could break things, create a backup branch or copy before proceeding.
- **Every new class and function gets a docstring** — one sentence explaining what it does and why it exists.

### Code Review Checklist

Run through this before considering any task complete:

- [ ] All tests pass
- [ ] No magic numbers — everything is a named constant
- [ ] No functions longer than 40 lines
- [ ] No file longer than 300 lines — if approaching this, split it
- [ ] Type hints on all function signatures
- [ ] Every new class has a docstring
- [ ] Update and draw are separated
- [ ] Delta time used in all movement calculations
- [ ] No new global variables introduced
- [ ] Session log updated

## Stability, Performance and Crash Prevention

### Core Philosophy

The game must never crash to desktop under any circumstances during normal play. Physics complexity will increase significantly over time — the stability architecture must be built to handle this from the start. A bad frame should degrade gracefully, never crash. A physics edge case should be caught and corrected, never propagate into an unrecoverable state.

### Physics Stability Rules

- **Clamp everything** — every physics value must have a defined minimum and maximum. Velocity, acceleration, gravity strength, ability effect radius, time dilation factor. If a value can theoretically go infinite, it must be clamped before it is applied. Use a `clamp()` utility function everywhere, never raw arithmetic on physics values.
- **Delta time cap** — cap delta time at a maximum of 0.05 seconds regardless of actual frame time. If the game hitches and delta time spikes to 0.5 seconds, uncapped physics will teleport the player through walls. A cap of 0.05 means a bad frame causes a small physics stutter not a catastrophic position jump.
- **Tunneling prevention** — fast moving objects must use swept collision detection not point-in-time collision. A player moving fast enough can pass through a thin platform in one frame. Swept detection checks the entire path traveled not just the end position. This is non-negotiable for a game with gravity rotation and variable time dilation.
- **Physics validation** — after every physics update, validate the player state. If the player is inside a solid object, eject them to the nearest valid position and log the incident. Never leave the player in an invalid state.
- **Gravity rotation safety** — before executing a gravity rotation, check that the player's new position in the rotated orientation is valid. If the rotation would place the player inside geometry, find the nearest safe position first. Never rotate into an invalid state.
- **Spacetime ability bounds** — every spacetime ability effect must be sandboxed. Time dilation cannot reduce time scale below 0.05 or above 10.0. Gravity manipulation cannot exceed 5x normal gravity strength. These bounds are physics constants defined in `constants.py` and never exceeded regardless of ability combinations or modifier stacking.
- **Floating point safety** — never compare floating point numbers with equality. Always use an epsilon threshold. Replace all instances of `velocity == 0` with `abs(velocity) < EPSILON` where `EPSILON` is defined in `constants.py` as `0.001`.

### Performance Rules

- **60fps is non-negotiable** — the game must maintain 60fps on a mid-range Mac from 2020. Test this regularly not just at the end.
- **Profile before optimising** — never optimise code without profiling first to confirm it is actually the bottleneck. Premature optimisation creates complexity for no gain.
- **Spatial partitioning** — once the number of active entities exceeds 20, implement a simple spatial grid for collision detection. Never do O(n²) collision checks against all entities every frame.
- **Object pooling for particles and projectiles** — never instantiate or destroy particle objects during gameplay. Pre-allocate a pool at startup and recycle objects. Garbage collection spikes cause frame drops.
- **Asset loading** — all assets loaded at startup never during gameplay. Loading during a frame causes a hitch. Use a loading screen for initial asset loading.
- **Draw call batching** — group sprites by layer and draw them in batches. Never sort the full sprite list every frame — maintain sorted layers and only re-sort when the layer order changes.
- **Fixed physics timestep** — physics runs at a fixed 60hz regardless of render frame rate. If the render frame takes too long, physics still steps correctly. Use an accumulator pattern to decouple physics from rendering.

### Error Handling and Crash Prevention

- **Try-catch boundaries** — wrap the main game loop in a top-level exception handler that catches all unhandled exceptions, writes a full crash report to `crash_log.txt` with timestamp, player state, last 50 physics frames, and current level state, then attempts a graceful shutdown rather than a crash to desktop.
- **Asset loading fallbacks** — if any asset fails to load, substitute a coloured rectangle placeholder and log the failure. The game continues running. A missing sprite never crashes the game.
- **Level loading validation** — validate every level file on load before running it. If a level file is malformed, log the error and load the previous valid level. Never crash on a bad level file.
- **Save file corruption handling** — always validate save files on load. If the save file is corrupted, back it up as `save_corrupted_timestamp.json` and start fresh. Never crash on a bad save file. Never overwrite a save file in place — write to a temp file first then rename atomically.
- **Physics watchdog** — implement a watchdog timer that monitors physics update time every frame. If any single physics update takes longer than 16ms, log a warning with the current entity count and active effects. If it happens 3 frames in a row, disable the most expensive active spacetime effect and log it to `performance_log.txt`.
- **Entity count limits** — define maximum entity counts in `constants.py`. `MAX_ENEMIES = 20`, `MAX_PARTICLES = 500`, `MAX_PROJECTILES = 50`. Never exceed these limits — when the limit is reached, oldest entities are recycled not new ones created.

### Testing for Stability

- **Fuzz physics testing** — add a test in `test_game.py` that runs 10000 random physics updates with random inputs and confirms the game state remains valid throughout. No positions inside geometry, no infinite values, no NaN.
- **Gravity rotation stress test** — add a test that rotates gravity 1000 times in rapid succession and confirms the player state remains valid after every rotation.
- **Ability combination testing** — add tests for every possible combination of active abilities and modifiers to confirm no combination produces invalid physics values.
- **Memory leak detection** — run a 10 minute simulated play session in tests and confirm memory usage does not grow unboundedly. Object pooling and proper cleanup should keep memory flat after the initial load.
- **Frame time monitoring** — add a debug overlay toggled with F3 that shows current fps, physics update time, entity count, active effects count, and memory usage. Leave this in the game permanently — it is invaluable for spotting performance problems early.

### Logging

- Maintain three log files that persist across sessions: `game_log.txt` for general events, `performance_log.txt` for frame time warnings and entity count spikes, `crash_log.txt` for any unhandled exceptions and physics violations.
- **Log rotation** — when any log file exceeds 10MB, rename it to `log_archive_timestamp.txt` and start a fresh log. Never let logs grow unboundedly.
- **Physics violation log** — any time a physics value is clamped beyond its normal range, log it as a warning with the value, the source, and the current game state. These warnings are early indicators of ability combination bugs before they become crashes.

## Full Module Architecture

Read this before making any structural decisions to ensure all work is consistent with the intended final architecture.

### Architecture Philosophy

This is a long-term project being built incrementally over many sessions. Every module listed below will eventually be built. When making any structural decision — naming, file location, class design, data format — consider how it will fit into the complete architecture. Never make a local decision that solves today's problem but blocks a future module. When in doubt, build the more flexible version.

**CURRENT PHASE: Phase 0 — Foundation**
Active modules: Module 1 (Physics), Module 2 (Level Architecture), Module 3 (Camera)
Do not implement features from future modules — but do not make decisions that prevent them either.

### Complete Module Map

#### FOUNDATION LAYER — everything else depends on these

**Module 1 — Physics Engine (IN PROGRESS)**
Gravity vector system supporting all 4 orientations, collision detection with tunneling prevention, player movement with coyote time and variable jump, delta time with cap, fixed physics timestep, physics validation and clamping. Location: `src/physics/`

**Module 2 — Level Architecture (NEXT)**
Tile-based level system, JSON level format, LevelRenderer class, ASCII level editor helper, support for all platform types in all gravity orientations. Location: `src/levels/` and `levels/`

**Module 3 — Camera System (NEXT)**
Smooth follow camera, gravity rotation handling, zoom for rotation cinematic, screen shake, camera bounds. Location: `src/rendering/camera.py`

#### GAMEPLAY LAYER — the mechanics that make The Fold unique

**Module 4 — Spacetime Manipulation System (Phase 1)**
Fold Energy resource with regeneration, ability slot framework for 3 abilities plus ultimate, cooldown management, time dilation implementation affecting entities independently of player, gravity anchor implementation, local gravity inversion, ability visual effect triggers, spacetime ability bounds and sandboxing as defined in stability rules. Location: `src/systems/spacetime.py`

**Module 5 — Entity System (Phase 1)**
Base Entity class with PhysicsComponent, RenderComponent, HealthComponent, StateComponent. All moving objects in the game inherit from or compose this base. Supports all gravity orientations automatically by reading from the global gravity vector. Entity registry for spawn and despawn. Location: `src/entities/`

**Module 6 — Enemy AI Framework (Phase 1)**
Base EnemyAI class with patrol, detect, chase, attack state machine. Plugin architecture where each enemy type overrides specific behaviours. Three enemy types to implement: Temporal Echo (loop-based, affected by time dilation), Fold Predator (multi-temporal, countered by gravity rotation), The Anchored (broken timeline, unpredictable). Cult enemy types: Witness (human, patrol and attack), Ordained (temporal anchor removed, erratic), Architect (full spacetime counter-tactics). Location: `src/entities/enemies/`

**Module 7 — Combat System (Phase 1)**
Hit detection using swept collision, damage calculation, knockback physics, death states, invincibility frames. Spacetime interactions — enemies in time dilation take modified damage, enemies in gravity anchor are vulnerable. Location: `src/systems/combat.py`

#### PROGRESSION LAYER — the roguelite systems

**Module 8 — Run State Manager (Phase 2)**
Tracks complete current run state — active abilities, modifiers, artifacts, Fold Watch values, current node position, run seed, death and completion states. Serialisable to JSON for crash recovery. Single source of truth for everything run-specific. Location: `src/data/run_state.py`

**Module 9 — Ability/Modifier/Artifact System (Phase 2)**
Item definition format in JSON data files. Three tiers: Abilities (active, max 3 plus ultimate), Modifiers (passive augments), Artifacts (rare run-defining). Combination effect system — when two modifiers interact the result is defined in data not code. Pickup and equip logic. Starting item sets per character. Location: `src/systems/items/` and `assets/data/items/`

Planned abilities: Time Dilation, Gravity Anchor, Fold Burst, Horizon Shift, Temporal Echo, Causality Lance
Planned modifiers: Event Horizon, Tidal Coupling, Redshift, Quantum Foam, Closed Timelike Curve
Planned artifacts: Kerr Ring, Penrose Diagram, Hawking Emitter, Chronometer, Rovelli Stone

**Module 10 — Node Map System (Phase 2)**
Procedurally generated star chart run map. Node types: Combat, Anomaly Puzzle, Hole Encounter (black or white — identical appearance from outside), Merchant, Rest Point. Navigation and selection UI. Difficulty scaling by distance from start toward singularity. Convergence cult controlled nodes with distinct visual marker. Location: `src/systems/node_map.py`

**Module 11 — Procedural Level Generation (Phase 2)**
Rule-based level generation from room templates. Templates defined in JSON. Rooms connect based on gravity orientation compatibility. Difficulty parameters fed from node position. Cult territory rooms have distinct visual language. All generated levels guaranteed valid in at least 2 gravity orientations. Location: `src/systems/level_generator.py`

#### SYSTEMS LAYER — infrastructure supporting everything

**Module 12 — Audio Engine (Phase 3)**
Sound effect system with pooling, music playback and crossfading, audio zones — music shifts as player approaches singularity, spatial audio for spacetime effects, Fold Energy depletion audio cues. Location: `src/systems/audio.py`

**Module 13 — Sprite and Animation System (Phase 1 — unblocks art)**
Sprite sheet loading and slicing, animation state machine with defined states: Idle, Walk, Run, Jump Rising, Jump Peak, Jump Falling, Land, Gravity Rotation Trigger, Gravity Rotation Transition, Gravity Rotation Land, Ability 1-3 Active, Ultimate Charging, Ultimate Active (collar extended), Hit, Death. Smooth transitions between states, sprite flipping for direction. Location: `src/rendering/animation.py`

**Module 14 — Particle and VFX System (Phase 3)**
Object pooled particle system, defined effects: Time Dilation Ripple, Gravity Anchor Distortion, Rotation Zoom, Fold Burst, Hit Spark, Death Dissolve, White Hole Explosion, Black Hole Suppression Pulse, Convergence Symbol Flicker. Location: `src/rendering/vfx.py`

**Module 15 — UI and HUD System (Phase 2)**
Fold Energy bar styled as analogue gauge, ability slots display with cooldown indicators, Fold Watch civilizational tracker showing humanity timeline and Fold stability, node map overlay, pause menu, death screen with run summary, character select screen. All UI styled in Astounding Science Fiction aesthetic — painted, analogue, retrofuturistic. Location: `src/systems/ui/`

**Module 16 — Save and Meta-Progression System (Phase 3)**
Persistent data across runs — unlocked characters, Codex entries discovered, meta-upgrades earned, total runs completed, best run stats. Atomic save file writing with corruption recovery as defined in stability rules. Steam cloud save integration. Location: `src/data/save_manager.py`

#### POLISH LAYER — what separates good from great

**Module 17 — Juice System (Phase 3)**
Screen shake with configurable intensity and falloff, hit freeze frames configurable per hit type, camera punch on landing and ability use, controller rumble where available, particle bursts on every significant action. Tunable from `constants.py`. Location: `src/systems/juice.py`

**Module 18 — Gravity Rotation Cinematic (Phase 3)**
Full zoom-in rotate zoom-out sequence, duration and easing configurable, screen distortion shader during rotation, player brace animation trigger, environmental debris response, sound design integration. This is the signature visual moment of the game — it must feel extraordinary. Location: `src/rendering/rotation_cinematic.py`

**Module 19 — Steam Integration (Phase 4)**
Steamworks SDK integration via Python bindings, achievement definitions and triggers, Steam cloud save, trading cards, Steam overlay compatibility, Mac and Windows build pipeline via PyInstaller, Steam page assets pipeline. Location: `src/systems/steam.py` and `build/`

### Dependency Rules

These must never be violated:

- **Physics** never imports from UI, rendering, or systems
- **Rendering** never imports from systems or data
- **Entities** import from physics and rendering only
- **Systems** import from entities, physics, and data
- **UI** imports from systems and data only
- **Data** imports from nothing — pure data structures only
- **Main.py** imports from systems only — it is the orchestrator not the implementer

### Future Character Roster

Build entity system to support these:

- **The Navigator** — ultimate is Dead Reckoning, freeze time globally for 3 seconds except player
- **The Archivist** — ultimate is White Hole, emit everything absorbed this run in one release
- **The Diplomat** — ultimate is Closed Loop, rewind last 10 seconds of world state not player position
- Additional characters unlocked through meta-progression

### Platform Targets

- Mac and Windows via PyInstaller
- Steam distribution
- Target 60fps on mid-range 2020 Mac
- Resolution: 1920x1080 native with scaling support

## Autonomous Session Rules

When given a large multi-part task to complete overnight or over a long session:

1. Before starting, write a file called `SESSION_PLAN.md` listing every task, sub-task and acceptance criteria in order.
2. Work through tasks sequentially — fully complete and test each before moving to the next.
3. After each completed task write a one-line status update to `SESSION_LOG.md` with timestamp.
4. Run `python3 test_game.py` after every code change — fix failures before proceeding.
5. If you encounter a decision point requiring creative input, write the question to `DECISIONS_NEEDED.md` and continue with the most conservative option.
6. Never delete or significantly restructure working code without writing the reason to `SESSION_LOG.md` first.
7. At the end of the session write a `SUMMARY.md` with: what was completed, what was skipped and why, what needs human review, and what the next session should tackle.
8. Commit working code to git after each major module is complete with a descriptive commit message.
