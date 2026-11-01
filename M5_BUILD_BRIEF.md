# M5 Brief — Run Build System (Replayability)

**For:** Claude Code autonomous sessions
**Read first:** `CLAUDE.md`, `ROADMAP.md`. Where this brief conflicts with the Game Design Bible, the bible wins: log the conflict in `DECISIONS_NEEDED.md` and take the conservative option.
**Milestone:** M5 Content Alpha, the "data-driven item system" line item. Nothing else in M5.

---

## 0. Decisions for Matt (answer before Session 1)

Once these are answered, this brief counts as the approved plan for the files listed in each session. Still copy each session's plan into `DECISIONS_NEEDED.md` per the >3-file rule.

1. **v1 pool size.** The roadmap says 3 abilities / 3 modifiers / 3 artifacts. Pick-1-of-3 needs a pool well above 3 to feel different run to run. **Recommend: 1 ability (Time Dilation) + 6 modifiers + 3 artifacts for this slice.** Modifiers are mostly JSON, so they're cheap. New abilities wait for their own spec (§7).
2. **Domain names.** Recommend **Gravity / Time / Horizon** (§2).
3. **Paradox offers cost.** Recommend 15 `fold_stability` per Paradox artifact (§4).
4. **Skip reward.** Recommend skip gives nothing (StS-style). Fold Stability must not be restorable here, per the bible.

---

## 1. Goal

Make runs feel different through **player choice**, not raw randomness. Borrow the principles that make Hades / Slay the Spire replayable, expressed only through systems the bible already defines.

| Principle | Fold implementation |
|---|---|
| Pick 1 of 3, see it before you commit | Reward screen after combat rooms and white holes |
| Families give builds identity | 3 domains, each with a signature verb |
| Limited slots force tradeoffs | Bible's 3 abilities + 1 ultimate cap; modifier cap per run (§3) |
| Commitment pays off | **Resonances**: cross-domain combos defined in data (Module 9's "combination effect system") |
| Power costs something | **Paradox offers**: artifacts paid for with `fold_stability` (the bible's MTG tension) |
| Upgrades without bloat | Owning a modifier → it's offered as a rank-up (max rank 3) |

**Hard constraint (non-negotiable):** no item may alter physics constants: gravity strength, jump, movement, rotation behaviour, collision. Items modify **resources, timers, damage, i-frames, ability parameters, rewards, and hole consequences only**, always clamped to the existing sandbox bounds in `constants.py`. Add a test that enforces this (§6).

**Done when:**
- Two runs diverge visibly because of what the player picked.
- At least one Resonance is reachable in a normal 5-node run.
- 352+ tests pass.

---

## 2. Domains

| Domain | Signature verb | Content (from planned lists) |
|---|---|---|
| **TIME** | slow, extend, rewind | Time Dilation (exists), Redshift, Closed Timelike Curve |
| **GRAVITY** | rotate, pin, launch | Tidal Coupling, Geodesic *(new name, placeholder)* |
| **HORIZON** | risk, phase, holes | Event Horizon, Quantum Foam |
| *(none)* | run-defining | Artifacts: Kerr Ring, Hawking Emitter, Penrose Diagram |

---

## 3. v1 content (illustrative; all numbers are constants, tune freely)

Every effect only uses verbs that exist today: dilate, rotate, move, take hits, hit integrity 0, clear rooms, enter holes.

**Modifiers** (rank 1 / 2 / 3)
| Name | Domain | Trigger | Effect |
|---|---|---|---|
| Redshift | Time | `ability_used(time_dilation)` | Dilation lasts +0.5 / +1.0 / +1.5 s |
| Closed Timelike Curve | Time | `integrity_zero` (cancellable) | Once per room: cancel, restore 1 integrity, return to last safe position. Rank 2/3: once per room + once more per run / twice per room |
| Tidal Coupling | Gravity | `gravity_rotated` | +8 / 12 / 16 `chrono_reserve` (internal cooldown 1.5 s) |
| Geodesic | Gravity | `gravity_rotated` | 0.3 / 0.5 / 0.7 s of i-frames |
| Event Horizon | Horizon | `hole_resolved` | Black hole costs −5 / −8 / −10 less stability; white hole adds +1 extra reward option |
| Quantum Foam | Horizon | `player_hit` (cancellable) | 15 / 25 / 35% chance to phase through a hit (seeded RNG) |

**Resonances** (auto-activate when both parts are owned; shown on the reward screen as "completes resonance")
| Name | Requires | Effect |
|---|---|---|
| Spaghettification | Tidal Coupling + Redshift | Rotating gravity during dilation extends dilation +1 s (once per activation) |
| Ergosphere | Geodesic + Quantum Foam | Hits phased by Quantum Foam also grant Geodesic i-frames |
| Information Paradox | Closed Timelike Curve + Event Horizon | A black hole's integrity loss is undone by CTC without spending its charge |

**Artifacts** (offered rarely; always via Paradox offers or white holes)
| Name | Effect |
|---|---|
| Kerr Ring | Every 4th gravity rotation (full revolution) triggers a free Time Dilation |
| Hawking Emitter | When integrity drops, freeze all enemies within `HAWKING_RADIUS` for 1 s |
| Penrose Diagram | Every reward screen shows 4 options instead of 3 |

**Slot rules:** max 3 abilities + 1 ultimate (bible). Max `MODIFIER_CAP = 6` owned modifiers per run. When at cap, taking a new one requires dropping one (shown on the reward screen). Artifacts are uncapped but rare.

---

## 4. Reward flow

- New `game_state = "reward"`.
  - After a combat room clears: `playing → reward → node_map`.
  - After a **white** hole resolves: `hole_encounter → reward → node_map`.
  - Black holes give no reward.
- **Offers:** 3 options (4 with Penrose), generated from `RandomGenerator(run_seed, node_idx)` so they're deterministic per run.
  - If the player owns items from a domain, guarantee ≥1 offer from an owned domain. This is a light keepsake-style pull that lets builds cohere.
  - An owned modifier below max rank appears as **rank-up** instead of a duplicate.
  - **Paradox offer:** at most one per screen, appearing with probability `PARADOX_OFFER_CHANCE`. It's an artifact with a `fold_stability` cost shown in red. It can't be taken if it would drop stability to ≤ 0.
  - **Skip** is always available.
- Text-only UI is fine (match the node map style). Show name, domain, rank, one-line effect, and "completes resonance" when applicable.

**Out of scope:** door/branch previews on the node map. That's Module 10, its own slice. Leave a `reward_type` field on nodes so it can slot in later.

---

## 5. Architecture

Follow the CLAUDE.md dependency rules (data imports nothing; main imports systems only).

**Event bus:** `src/systems/events.py`
- Simple synchronous pub/sub, `GameEvent` enum.
- Cancellable events return a result object that listeners can mark `cancelled`.
- Events for v1:
  - `GRAVITY_ROTATED`
  - `ABILITY_USED`
  - `ABILITY_ENDED`
  - `PLAYER_HIT` (cancellable)
  - `INTEGRITY_ZERO` (cancellable)
  - `ROOM_ENTERED`
  - `ROOM_CLEARED`
  - `HOLE_RESOLVED`

**Ability framework:** `src/systems/spacetime.py`
- Start of Module 4.
- `AbilitySlot` dataclass, with Time Dilation's `dilation_timer` / `dilation_cooldown` moved **out of `main.py`** into it.
- Ability params (`duration`, `cost`, `cooldown`) are read from the slot so modifiers can adjust them, clamped to existing bounds.

**Item data**
- `assets/data/items/*.json`, one file per tier: `modifiers.json`, `artifacts.json`, `resonances.json`.
- `src/data/items.py`: dataclasses `ItemDef`, `OwnedItem(id, rank)`, `ResonanceDef`.
- `src/systems/items/registry.py`: load and validate all JSON at startup. An invalid entry gets logged to `game_log.txt` and skipped. A test asserts every shipped file is valid.
- `src/systems/items/effects.py`: a small library of **effect primitives**, each one a function registered by name.
  - Primitives: `add_chrono`, `grant_iframes`, `extend_active_ability`, `cancel_event`, `restore_integrity`, `modify_hole_outcome`, `add_reward_option`, `freeze_enemies_in_radius`, `trigger_ability`.
  - Each item is JSON naming a trigger, a primitive, and per-rank params.
  - **New items = JSON. New primitives = code.**
- `src/systems/items/manager.py`: subscribes owned items to the bus, tracks internal cooldowns and per-room/per-run charges, detects resonances.

**Run state:** `RunState` gains `owned_items: list[dict]` and `paradox_spent: float`, both serialisable.

**Example JSON**
```json
{
  "id": "tidal_coupling",
  "name": "Tidal Coupling",
  "tier": "modifier",
  "domain": "gravity",
  "trigger": "GRAVITY_ROTATED",
  "effect": "add_chrono",
  "params_by_rank": [{"amount": 8}, {"amount": 12}, {"amount": 16}],
  "internal_cooldown": 1.5,
  "description": "Rotating gravity restores Chrono Reserve.",
  "unlocked_by": null
}
```
`unlocked_by` stays null for now. It exists so M7 meta-progression can add items to the pool **horizontally** (new options, never permanent stat boosts).

---

## 6. Sessions

Per CLAUDE.md: never refactor and add features in the same session; write `SESSION_PLAN.md` first; run `python test_game.py` after every change; commit after each session.

**Session 1: refactor only, zero behaviour change**
- Add the event bus.
- Extract Time Dilation into `spacetime.py` / `AbilitySlot`.
- Emit the 8 events from the existing code paths in `main.py`.
- Remove the `CHRONO_DRAIN_TEST` Q key.
- Files: `events.py` (new), `spacetime.py` (new), `main.py`, `constants.py`, tests.
- **Accept:** all 352 existing tests pass unchanged; new tests cover event dispatch and cancellation; Time Dilation behaves identically in play.

**Session 2: item system, no UI**
- Add item dataclasses, registry and validation, effect primitives, manager, resonance detection, and `RunState.owned_items`.
- Add the 6 modifiers, 3 artifacts and 3 resonances as JSON.
- Add a debug key (F-key, behind a `DEBUG_ITEMS` constant) to grant items for playtesting.
- **Accept:**
  - Each item has a unit test of its effect at every rank.
  - The resonance activation test passes.
  - The **physics-invariance test** passes: with every item owned at max rank, run the existing fuzz and rotation-stress tests and assert all physics constants and gravity/movement outputs are identical to a no-item baseline.
  - The bible's ability-combination test passes: no combination produces values outside sandbox bounds.

**Session 3: reward flow**
- Add the `"reward"` game state, seeded offer generation, domain pull, rank-ups, Paradox offers, skip, modifier-cap swap, and HUD draw function(s).
- Show owned items on the node map screen.
- **Accept:**
  - Same seed produces the same offers.
  - A Paradox offer is never takeable at a cost that would end the run.
  - A full 5-node run is playable with picks.
  - `qa_checklist.md` gets a "Build system" section.

**Session 4: tuning pass (only after Matt plays Session 3)**
- Adjust constants from his notes. No new systems.

---

## 7. Parked: do not build, but don't block

- **Abilities 2–3** (Gravity Anchor, Horizon Shift, etc.) need a mechanics spec from Matt first. The slot framework must support them.
- **Branching node map with reward previews** (Module 10). Nodes carry a `reward_type` field now.
- **Gravity-bound loadouts** (an ability slot per gravity orientation). This is an interesting Fold-only idea, but it conflicts with rotation as traversal because every navigation rotation would swap your combat kit. If it's revisited, prototype it as a single artifact, not a core system.
- **Meta-progression unlocks** (M7). Horizontal only, via `unlocked_by`.
- **Heat-style difficulty ladder.** Post-launch. Must use rule modifiers that don't touch physics (enemy behaviour, resource costs, node composition).
- **Domain flavour fiction** (e.g., powers as echoes of other timelines). Text only, Matt's call; bible says archetypes, no named characters.
