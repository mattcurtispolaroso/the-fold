# Decisions Needed — Code Quality Audit

---

## M4b — Node Map, Hole Encounters, Death/Win Screens ✅ APPROVED 2026-11-01

**Touches 5 files. Requires review before coding.**

### What this sprint delivers

A completable run: 5 nodes, two platform rooms, two hole encounters, a singularity win. The loop that M4 is gating on.

| Task | Done when |
|---|---|
| Node sequence on `RunState` | 5-node list generated at run start from `run_seed`; `current_node_idx` advances on room clear |
| Node map screen | `game_state = "node_map"` — draws 5 node icons, current position, ENTER advances |
| Hole encounter screen | `game_state = "hole_encounter"` — black screen, 2s reveal, applies resource consequences, ENTER continues |
| Death screen | `game_state = "dead"` — run summary (nodes reached, deaths), ENTER → start screen |
| Win screen | `game_state = "win"` — singularity reached, ENTER → start screen |

---

### Node sequence

Fixed pattern, seeded-random combat level assignment:

```
Node 0: combat   → level picked from [level_01, level_02] via run_seed
Node 1: hole     → black or white (50/50 from run_seed, unknown until entered)
Node 2: combat   → level picked from [level_03, level_04] via run_seed
Node 3: hole     → black or white (50/50 from run_seed, unknown until entered)
Node 4: singularity → win condition, no room
```

Hole outcomes are fixed at run start (same run, same holes) but unknown to the player until entered. This is the core design bible mechanic.

`RunState` gains two new fields:
- `combat_levels: list[int]` — level indices for the two combat nodes (e.g. `[1, 3]`)
- `hole_outcomes: list[bool]` — `True` = white hole, one per hole node (e.g. `[True, False]`)

Both generated deterministically from `run_seed` in `new_run()`.

---

### game_state additions

Current states: `"start"`, `"playing"`

M4b adds: `"node_map"`, `"hole_encounter"`, `"dead"`, `"win"`

Flow:
```
"start" → ENTER → "node_map"
"node_map" → ENTER → "playing" (loads combat level) or "hole_encounter" or "win" (singularity)
"playing" → goal_reached → "node_map" (advance node_idx)
"playing" → fold_stability ≤ 0 → "dead"
"hole_encounter" → 2s timer → apply consequences → "node_map" (advance node_idx)
"dead" → ENTER → "start"
"win" → ENTER → "start"
```

---

### Node map visual

Text-only for M4b (styled UI is M5). One line per node:

```
  ● NODE 1 — COMBAT          [completed]
  ● NODE 2 — ANOMALY          ← current
  ○ NODE 3 — COMBAT
  ○ NODE 4 — ANOMALY
  ○ NODE 5 — SINGULARITY
```

Current node highlighted. Completed nodes dimmed. ENTER continues into the current node.

---

### Hole encounter screen

Black screen. Two phases, timed:

**Phase 1 (0.0–1.5s):** "ENTERING THE ANOMALY..." — no information, both outcomes look identical.

**Phase 2 (1.5–3.5s, auto-advance):** Reveal outcome and apply consequences immediately:
- White hole: "WHITE HOLE — TEMPORAL ANCHOR RESTORED" — restore `anchor_integrity` to max, `fold_stability += WHITE_HOLE_STABILITY_RESTORE`
- Black hole: "BLACK HOLE — ANCHOR DESTABILISED" — `anchor_integrity -= 1` (can trigger level reset if at 0), `fold_stability -= BLACK_HOLE_STABILITY_COST`

After phase 2 ends: return to `"node_map"` with node advanced.

If the black hole integrity hit triggers fold_stability ≤ 0: go to `"dead"` instead.

→ **Decision needed: white hole restores +5 or +10 fold_stability? Black hole costs 10 or 15?**
→ **Recommendation: white +5, black -15. Black holes should feel genuinely dangerous.**

---

### Death screen

```
RUN OVER

Nodes reached:  3 / 5
Deaths:         3
Fold stability: 0

Press ENTER
```

Stats read from `RunState`. No run history yet (M5+).

---

### Win screen

```
THE FOLD HOLDS

Nodes reached:  5 / 5
Deaths:         1
Fold stability: 60

Press ENTER
```

---

### Files to change

| File | Change |
|---|---|
| `constants.py` | `WHITE_HOLE_STABILITY_RESTORE`, `BLACK_HOLE_STABILITY_COST`, `HOLE_ENCOUNTER_PHASE1_DURATION`, `HOLE_ENCOUNTER_PHASE2_DURATION`, node map colors |
| `src/data/run_state.py` | Add `combat_levels`, `hole_outcomes`, `deaths` fields; update `new_run()`; add `current_node_type` property, `advance_node()`, `hole_index_for_current_node()` |
| `src/rendering/hud.py` | Add `draw_node_map()`, `draw_hole_screen()`, `draw_death_screen()`, `draw_win_screen()` |
| `main.py` | New `game_state` branches, hole timer, node advancement on goal_reached, death/win routing |
| `tests/test_core.py` | `TestRunStateM4b`, `TestHoleEncounter` classes |

---

### What this is NOT

- Star chart / branching node map (M5)
- Merchant or rest nodes (M5)
- Fold distortion shader (M6)
- Run history or meta-progression (M7)
- Hole encounter as a playable room (M5 — for M4b it's a resolve screen)

---

## M4a — fold_stability, RunState, Start Screen ✅ APPROVED 2026-11-01

**Touches 5 files (1 new). Requires review before coding.**

### What this sprint delivers

Foundation for M4. Nothing in the game loop changes until these three are in place.

| Task | Done when |
|---|---|
| `fold_stability` resource + tint | field on RunState, tint deepens as it depletes, integrity-0 death costs fold_stability |
| `RunState` dataclass | serialisable, holds fold_stability + node + seed, lives in `src/data/run_state.py` |
| Start screen | game shows black screen + text on launch, ENTER starts run, ESC quits |

---

### Design decisions — answers needed

**1. Where does `fold_stability` live?**

It is a run-level resource (permanent depletion across rooms), not a character stat. It belongs on `RunState`, not `Player`. When `anchor_integrity` hits 0, main.py pays the fold_stability cost from `run_state.fold_stability` before resetting the level.

→ **Recommendation: RunState. No question.**

**2. How much fold_stability does each integrity-0 death cost?**

`FOLD_STABILITY_MAX = 100`. With a cost of:
- 25 → run ends after 4 deaths
- 20 → run ends after 5 deaths
- 33 → run ends after 3 deaths

Hole encounters, enemy abilities, and node timers will also cost fold_stability in M4b, so deaths shouldn't eat the whole budget. **Recommendation: 20 (5 deaths). Leaves room for other drains.**

→ **Decision needed: 20, 25, or other?**

**3. Fold tint visual**

A full-screen red overlay. Alpha scales linearly:
- fold_stability ≥ 80 → alpha 0 (invisible)
- fold_stability = 50 → alpha 40 (subtle red)
- fold_stability = 0 → alpha 110 (strong red, world is visibly dying)

Drawn on top of the background but under level geometry + player. Later (M6) replaced by real shader distortion.

→ **Recommendation: tint starts at 80, max alpha 110. Confirm or adjust threshold.**

**4. Start screen**

Black screen, two lines of text:

```
THE FOLD

Press ENTER to begin
```

ENTER → starts a new run (new RunState, resets level to level_01, resets player).
ESC → quits.

No game world visible behind it. Styled UI is M5.

→ **Recommendation: yes. Any text changes?**

**5. Game state machine**

Add `game_state: str` variable in `main()` with two values for this sprint: `"start"` and `"playing"`. Sets up the pattern for `"dead"` and `"win"` screens in M4b.

When `game_state == "start"`: draw start screen, only ENTER/ESC handled.
When `game_state == "playing"`: current game loop runs as-is.

→ **No question — just noting the approach.**

**6. Run seed**

`RunState.run_seed` is generated with `random.randint(0, 2**32)` in `RunState.new_run()`. Stored but not consumed yet — procedural node map (M4b) will use it.

→ **No question — just noting it's there.**

---

### Files to change

| File | Change |
|---|---|
| `constants.py` | `FOLD_STABILITY_MAX`, `FOLD_STABILITY_INTEGRITY_COST` |
| `src/data/run_state.py` | **new** — `RunState` dataclass |
| `src/rendering/hud.py` | `draw_fold_tint()`, `draw_start_screen()` |
| `main.py` | `game_state`, `RunState` integration, fold_stability drain on death |
| `tests/test_core.py` | `TestRunState` class |

---

### Death flow change (M3 → M4a)

Currently: integrity 0 → `_reset_level_state()` immediately (free).

M4a: integrity 0 → `run_state.fold_stability -= FOLD_STABILITY_INTEGRITY_COST` → if fold_stability ≤ 0: `game_state = "dead"` (M4b will render death screen; for now just reset back to start screen) → else: `_reset_level_state()` as before.

---

### What this is NOT

- Node map UI or navigation (M4b)
- Hole encounter mechanics (M4b)
- Death screen with run summary (M4b)
- Win screen / singularity node (M4b)
- Fold distortion shader (M6)

---

## M3 Combat — Hit Detection, Knockback, I-frames ✅ APPROVED 2026-11-01

### Design decisions (resolved)

- **Anchored state**: no per-frame death timer. Integrity 0 → level resets immediately (same level, same as TAB but same index). Full anchored state with fold_stability cost is M4.
- **Knockback**: override velocity (not add) — predictable, testable.
- **Fall damage at integrity 0**: same level-reset path as combat death (unified).

### Files changed

| File | Change |
|---|---|
| `constants.py` | `IFRAMES_DURATION`, `KNOCKBACK_FORCE` |
| `src/entities/player.py` | `iframes_timer` field; `take_hit()` returns bool; `take_fall_damage()` returns bool |
| `src/systems/combat.py` | new — `check_hit()`, `compute_knockback()` |
| `main.py` | `_reset_level_state()` helper; hit detection; iframes tick |
| `tests/test_core.py` | `TestCombat` class |

### Signal convention

Both `take_hit()` and `take_fall_damage()` return `True` when integrity hits 0. Caller handles the level reset — Player has no reference to level/camera/enemy.

---

## Open Items

### C2: Level bounds clamping precision
- **File:** main.py (bounds clamping section)
- **Risk:** Uses `round()` comparison which could miss sub-pixel edge cases. Different code path from platform collision.
- **Recommended fix:** Unify bounds clamping into resolve_collisions by adding virtual boundary platforms. Moderate effort — defer to physics refactor session.

### C3: Sprite/physics rect size mismatch in horizontal gravity
- **File:** src/rendering/animation.py
- **Risk:** 90/270 degree rotation swaps sprite width/height but physics rect stays PLAYER_SPRITE_WIDTH x PLAYER_SPRITE_HEIGHT. Visual and collision rects disagree in left/right gravity.
- **Recommended fix:** Either swap player_w/player_h in main.py when gravity is horizontal, or keep physics rect as the larger dimension always. Needs design decision — gameplay implications.

---

## M5d — HUD ✅ APPROVED 2026-11-01

**Touches 4 files.**

### What this delivers

Always-visible resource readouts so the player can read integrity, chrono, and dilation state without the debug overlay. The exoskeleton glow design (CLAUDE.md) is deferred pending art — these are geometric placeholders with the same information.

### Layout

```
[top-left]                                        [top-right]
■ ■ ■   ← integrity pips (3 squares, amber/dark)

[game world]

[bottom-left]
━━━━━━░░░░  CHRONO   ← 10-segment bar
◀ TIME DILATION 2.1s ▶  ← only shown when active or cooling
```

Fold Stability: tint only (already done). Gravity label removed from production HUD (stays in debug overlay).

### Integrity pips
- 3 squares, 16×16px, 5px gap, top-left at (14, 14).
- Intact: amber `(210, 160, 50)`. Lost: dark `(40, 30, 15)`. All zero: pips go dark red `(150, 30, 30)`.

### Chrono bar
- 10 segments × 16px wide × 8px tall, 2px gap, bottom-left.
- Filled segments: amber when >50%, fading to dim orange below. Empty: near-black.
- Label "CHRONO" rendered in dim text to the right.

### Dilation status
- Active: `"◀ TIME DILATION X.Xs ▶"` in bright cyan, centred bottom.
- Cooling down (not active, timer > 0): dim version with remaining time.
- Ready and idle: nothing shown.

### Files
| File | Change |
|---|---|
| `constants.py` | HUD layout + colour constants |
| `src/rendering/hud.py` | rename `draw_hud_labels` → `draw_hud`; rewrite body |
| `main.py` | update import + call site |
| `tests/test_core.py` | smoke tests: no crash at boundaries (0 integrity, 100 chrono, active dilation) |

---

## M5b — Fold Predator Enemy ✅ APPROVED 2026-11-01

**Touches 4 files (1 new).**

### What this delivers

A second enemy that makes gravity rotation tactically meaningful in combat. Replaces the TemporalEcho placeholder in the active enemy slot. TemporalEcho class stays (available for future use).

### States

| State | Behaviour |
|---|---|
| PATROL | Oscillates laterally within level bounds |
| CHASE | Player within `FOLD_PREDATOR_CHASE_RANGE` px laterally — moves toward player |
| PHASE | Every `FOLD_PREDATOR_PHASE_INTERVAL`s during chase: burst at `FOLD_PREDATOR_PHASE_SPEED_MULT`× speed for `FOLD_PREDATOR_PHASE_DURATION`s |
| STUNNED | Any gravity rotation stuns for `FOLD_PREDATOR_STUN_DURATION`s; resumes previous state after |

### Decisions locked
- Stun triggers on **any** gravity rotation, regardless of distance to player.
- Movement is gravity-aware: lateral axis = X for vertical gravity, Y for horizontal.
- STUNNED color = pale blue-white (temporal disruption visual). PHASE color = brighter purple.

### Interface (matches TemporalEcho so main.py surgery is minimal)
- `update(time_scale, dt)` — same signature
- `reset()` — same
- `rect` property — same
- `draw(surface, offset)` — same
- `frozen_timer` field — same (Hawking Emitter compatible)
- `on_gravity_rotate()` — new; called from R-key handler in main.py

### Files
| File | Change |
|---|---|
| `constants.py` | 9 FOLD_PREDATOR_* constants |
| `src/entities/fold_predator.py` | new — FoldPredator class |
| `main.py` | swap TemporalEcho → FoldPredator; call `enemy.on_gravity_rotate()` from R key |
| `tests/test_core.py` | TestFoldPredator: patrol, chase entry/exit, phase burst, stun, gravity-aware movement, frozen_timer compat |

### Accept criteria
- Patrol oscillates and turns at bounds.
- CHASE entered when player within range, exited when player leaves range.
- PHASE burst fires after interval, speed doubles, returns to CHASE after duration.
- STUN freezes movement for full duration on any gravity rotation.
- After stun expires, resumes previous state.
- Gravity-aware: moves on Y axis when gravity is horizontal.
- frozen_timer field works (Hawking Emitter test passes unchanged).

---

## M5a Session 3 — Reward Flow ✅ APPROVED 2026-11-01

**Touches 5 files (1 new).**

### What this session delivers

The `"reward"` game state. After a combat room clears or a white hole resolves, the player sees a pick-1-of-3 offer screen before returning to the node map. Black holes give no reward.

### Flow

```
"playing" → goal_reached → generate offers → "reward" → pick → advance_node → "node_map"
"hole_encounter" (white) → timer ends → generate offers → "reward" → pick → advance_node → "node_map"
"hole_encounter" (black) → timer ends → advance_node → "node_map"  (unchanged)
```

`run_state.advance_node()` moves to the reward screen handler — called after pick or skip, not before. Two new flags in main.py locals: `reward_offers: list` and `pending_node_advance: bool`.

### Offer generation — `src/systems/items/offers.py` (new)

```python
@dataclass
class Offer:
    item_def: ItemDef
    is_rank_up: bool
    is_paradox: bool
    paradox_cost: float   # fold_stability; 0 if not paradox

def generate_offers(
    registry, run_state, node_idx, extra_options=0
) -> list[Offer]:
    ...
```

**Algorithm:**
1. Base count = 3 + `extra_options` (Penrose Diagram adds 1).
2. RNG seeded from `run_state.run_seed ^ (node_idx * 0x9e3779b9 & 0xFFFFFFFF)` — deterministic per run+node.
3. Build candidate pool:
   - Owned modifiers below max rank → rank-up offers (prioritised first).
   - Unowned modifiers — if player has ≥1 item in a domain, weight that domain × 3.
   - Filter out fully-maxed modifiers.
4. Fill base_count slots (no duplicates within a single offer set).
5. Paradox check: `rng.random() < PARADOX_OFFER_CHANCE` → append one artifact offer, cost from constants. Can only be taken if `fold_stability - cost > 0`.

### Modifier-cap handling

When MODIFIER_CAP (6) is reached and player picks a new modifier: auto-drop the oldest one in `run_state.owned_items`. Show a note on screen. No explicit drop screen in this session (Session 4 tuning pass can add it).

### Key bindings on reward screen

| Key | Action |
|---|---|
| `1` / `2` / `3` (`4` with Penrose) | Pick that offer |
| `S` or `0` | Skip — no item, advance |

### Node map update

Show owned items as a compact list below the node list:
```
ITEMS: Tidal Coupling R1, Redshift R2
```
One line, truncated if too many.

### Files

| File | Change |
|---|---|
| `src/systems/items/offers.py` | new — `Offer` dataclass, `generate_offers()` |
| `src/rendering/hud.py` | add `draw_reward_screen()`, update `draw_node_map()` |
| `main.py` | "reward" game_state branch, key handlers, transition logic |
| `tests/test_core.py` | `TestOfferGeneration`, `TestRewardFlow` |
| `qa_checklist.md` | add "Build system" section |

### Accept criteria (from brief §6 Session 3)

- Same seed + node index produces the same offers.
- A Paradox offer is never takeable if cost would drop stability to ≤ 0.
- A full 5-node run is playable with picks (at least one reward screen works end to end).
- `qa_checklist.md` gets a "Build system" section.
- 450+ tests pass (≥32 new).

---

## M5a Session 1 — Event Bus + Spacetime Refactor ✅ APPROVED 2026-11-01

**Touches 5+ files. Pure refactor — zero behaviour change.**

### Decisions locked (from M5_BUILD_BRIEF.md §0)

1. **Pool size:** Time Dilation is the only ability in this slice. No new abilities. 6 modifiers + 3 artifacts are Session 2.
2. **Domain names:** Time / Gravity / Horizon confirmed.
3. **Artifact costs:** Penrose Diagram 10 fold_stability, Kerr Ring 20, Hawking Emitter 25. Tunable later.
4. **Skip reward:** gives nothing.

### What Session 1 delivers

Infrastructure only. No gameplay change. All 352 existing tests pass unchanged.

| Task | File |
|---|---|
| `GameEvent` enum + `EventBus` pub/sub | `src/systems/events.py` (new) |
| `AbilitySlot` dataclass; `TimeDilationAbility` instance | `src/systems/spacetime.py` (new) |
| Wire `dilation_timer`/`dilation_cooldown` through `AbilitySlot` | `main.py` |
| Emit 8 events from existing code paths | `main.py` |
| Remove `CHRONO_DRAIN_TEST` Q key | `main.py`, `constants.py` |
| Tests: event dispatch, cancellation, AbilitySlot tick | `tests/test_core.py` |

### Event list (all emitted in Session 1, no handlers yet)

| Event | Emitted when |
|---|---|
| `GRAVITY_ROTATED` | R key handler |
| `ABILITY_USED` | Time Dilation activates (E key) |
| `ABILITY_ENDED` | `AbilitySlot.tick()` — active_timer hits 0 |
| `PLAYER_HIT` | cancellable — before `player.take_hit()` |
| `INTEGRITY_ZERO` | cancellable — when integrity hits 0 (hit or fall) |
| `ROOM_ENTERED` | game_state transitions to "playing" |
| `ROOM_CLEARED` | goal reached, before advance_node |
| `HOLE_RESOLVED` | inside `_apply_hole_consequences` |

### AbilitySlot interface

```python
@dataclass
class AbilitySlot:
    name: str
    duration: float   # reads from constants, modifiers can adjust later
    cost: float
    cooldown: float
    active_timer: float = 0.0
    cooldown_timer: float = 0.0

    @property
    def is_active(self) -> bool: ...
    @property
    def is_ready(self) -> bool: ...
    def activate(self, chrono_reserve: float) -> float: ...  # returns updated reserve
    def tick(self, dt: float, bus: EventBus) -> None: ...    # emits ABILITY_ENDED
    def reset(self) -> None: ...                             # clears both timers
    def time_scale(self) -> float: ...                       # TIME_DILATION_FACTOR or 1.0
```

### Accept criteria

- All 352 existing tests pass.
- New tests: EventBus dispatches to registered handlers; cancellable events respect cancelled flag; AbilitySlot.tick emits ABILITY_ENDED exactly once when active_timer reaches 0; time_scale() returns correct values.
- Time Dilation behaves identically in play (same duration, same cost, same cooldown).
- Q key removed; CHRONO_DRAIN_TEST removed from constants.py.

---

## Resolved (removed from active list)

- **C1** — Stale on_ground after gravity rotation. Fixed: commit `426edb9`.
- **C4** — Camera shake applied to offset. Not a bug; documented for clarity only.
- **D1** — No top-level exception handler. Fixed: commit `b7f1ef2`.
- **D2** — No logging infrastructure. Fixed: commit `b7f1ef2`.
- **D3** — No physics watchdog. Fixed: commit `b7f1ef2`.
- **D4** — No error handling on level load. Fixed: commit `b7f1ef2`.
- **D5** — No entity count limits. Fixed: MAX_ENEMIES/MAX_PARTICLES/MAX_PROJECTILES added to constants.py.
- **D6** — System font dependency. Fixed: bundled TTF loaded first with SysFont fallback.
