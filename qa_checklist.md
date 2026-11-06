# The Fold — Manual QA Checklist

Run through this after each coding session. Launch the game with `python main.py`.

---

## Basic Movement

- [ ] Left/right movement responds immediately and feels snappy
- [ ] Player accelerates smoothly (not instant max speed)
- [ ] Player decelerates to a stop when keys are released (no ice-skating)
- [ ] Movement works with both Arrow keys and WASD

## Jumping

- [ ] Spacebar triggers a jump from the ground
- [ ] Up arrow / W also trigger a jump
- [ ] Tap-jump produces a noticeably shorter hop than a held jump
- [ ] Jump arc feels weighty — fast through the peak, not floaty
- [ ] Player cannot jump while airborne (no double jump)
- [ ] Coyote time: walk off the floor edge, then immediately press jump — should still work within ~0.1s

## Gravity / World Rotation

- [ ] Pressing R rotates gravity counter-clockwise (Down → Right → Up → Left → Down)
- [ ] HUD label updates to show the current gravity direction
- [ ] Player falls toward the correct edge after each rotation
- [ ] Floor visually appears on the correct edge for each orientation
- [ ] White dot on the player points away from gravity (toward "up")
- [ ] All 4 orientations reachable by pressing R four times, returning to the start
- [ ] Pressing R triggers a brief white screen flash — gravity change reads as an event, not a silent shift

## Movement Under Each Orientation

- [ ] **Gravity Down:** left/right to move, space to jump upward
- [ ] **Gravity Right:** up/down to move, space to jump leftward
- [ ] **Gravity Up:** left/right to move, space to jump downward
- [ ] **Gravity Left:** up/down to move, space to jump rightward

## Edge Cases

- [ ] Rotate mid-jump — player should change fall direction immediately
- [ ] Rotate rapidly (mash R) — no crash, player falls to correct wall each time
- [ ] Rotate while standing on floor — player detaches and falls to the new floor
- [ ] Player cannot leave the screen boundaries (clamped to window)
- [ ] Long free-fall (rotate to give maximum drop) — speed caps at terminal velocity, no visual glitch
- [ ] Jump immediately after landing (buffering) — should feel responsive

## Performance / Stability

- [ ] Steady 60 FPS with no hitches
- [ ] No crash on window close (X button)
- [ ] No crash on Escape key
- [ ] No visual artifacts or flickering

## Known Issues to Watch For

- Movement keys overlap with jump keys in horizontal gravity orientations (Up/W is both "move up" and "jump") — may cause unintended jumps when moving. Deliberate for now — revisit after M1 playtests.

## Level Loading and Cycling

- [ ] Game loads level_01.json on startup without errors
- [ ] All 7 static platforms render in correct positions
- [ ] Both moving platforms animate correctly (horizontal oscillation)
- [ ] Spawn point places player at correct start position (above first platform)
- [ ] Goal rect renders as green rectangle in upper-left area
- [ ] "GOAL REACHED!" text appears when player touches goal area
- [ ] Deleting level_01.json produces a clear error (not silent failure)
- [ ] TAB cycles to level_02 — camera resets, player spawns at new start position, gravity resets to DOWN
- [ ] TAB cycles to level_03 — same reset behaviour
- [ ] TAB cycles to level_04 — same reset behaviour, Chrono Reserve resets to full
- [ ] TAB from level_04 wraps back to level_01

## Rotation-Required Levels

- [ ] **level_02 "Flip Up":** floor ends at x≈600 — player cannot reach goal (ceiling, right side) by jumping. Rotating gravity to UP and walking the ceiling reaches it.
- [ ] **level_03 "Side Step":** floor ends at x≈600 — player cannot reach goal (right wall, mid-height) by jumping. Rotating gravity to RIGHT and walking the right wall reaches it.
- [ ] Player cannot accidentally trigger the goal in either level while gravity is DOWN
- [ ] Camera scrolls correctly across the full 2400px width on levels 02 and 03

## Time Dilation — level_04 "Frozen Gate"

- [ ] Level loads without error — player spawns on start floor (left side, y≈720)
- [ ] Gap between start floor and exit ledge is visually uncrossable by jumping (640px gap)
- [ ] Moving platform oscillates horizontally at full speed before Time Dilation
- [ ] Player cannot ride moving platform to exit: falls short before reaching ledge
- [ ] Pressing E when Chrono Reserve ≥ 25 activates Time Dilation — "TIME DILATION" HUD appears
- [ ] Moving platform freezes immediately on activation
- [ ] Player can jump onto frozen platform and walk to its right edge
- [ ] Jump from right edge of frozen platform reaches exit ledge (x≥900)
- [ ] Goal reached when player steps into green goal rect on exit ledge
- [ ] E key does nothing when Chrono Reserve < 25 (insufficient CR)
- [ ] E key does nothing during cooldown period (2s after duration ends)
- [ ] Chrono Reserve refills visibly when player moves (debug overlay shows bar filling)

## Level Architecture Edge Cases

- [ ] Moving platforms carry correct collision — player can stand on them
- [ ] Gravity rotation works correctly with multi-platform level (not just single floor)
- [ ] Player doesn't clip through thin platforms (ceiling platforms are 20px)
- [ ] Moving platform at ceiling gap is reachable with gravity=up
- [ ] Player cannot escape level bounds in any gravity orientation (boundary platform system)

## Camera System

- [ ] Camera smoothly follows the player — no snapping or jitter
- [ ] Camera dead zone — small player movements near centre don't move camera
- [ ] Camera stops at level edges — never shows beyond level bounds
- [ ] Gravity rotation triggers smooth camera re-centre (no jump/snap)
- [ ] Landing from a jump produces a subtle screen shake
- [ ] Gravity rotation produces a noticeable screen shake
- [ ] Screen shake decays smoothly — no lingering vibration
- [ ] HUD text stays fixed on screen — does not move with camera
- [ ] "GOAL REACHED!" text stays centred on screen, not in world space
- [ ] Level is larger than screen (1200x900) — camera reveals area as player moves

## Camera Edge Cases

- [ ] Rapid gravity rotation (mash R) — camera handles multiple re-centres without glitching
- [ ] Player at corner of level — camera clamps to both edges simultaneously
- [ ] Landing immediately after rotation — both shakes should stack visually
- [ ] Background image stays full-screen (not offset by camera) — intentional parallax-free for now

## Debug Overlay

- [ ] Press backtick (`` ` ``) to toggle debug overlay — red physics rect outline + green centre dot
- [ ] Debug overlay visible in all four gravity orientations
- [ ] Debug overlay does not affect gameplay or physics

## Physics Module (post-extraction)

- [ ] Jump works in all 4 gravity orientations (down, left, up, right)
- [ ] Variable jump height (tap vs hold) works in all orientations
- [ ] Coyote time works after walking off any platform edge
- [ ] Gravity rotation (R) correctly changes physics direction immediately
- [ ] Terminal velocity caps fall speed in all orientations
- [ ] Lateral movement accel/decel feels identical to pre-refactor
- [ ] No physics logic remains in main.py — all in src/physics/

## Build System (M5a)

### Offer Screen
- [ ] After clearing a combat room — reward screen appears before node map
- [ ] After a white hole — reward screen appears before node map
- [ ] After a black hole — NO reward screen (go directly to node map)
- [ ] Press 1/2/3 to pick an offer — item appears in ITEMS list on node map
- [ ] Press S to skip — no item granted, node map resumes correctly
- [ ] Rank-up offer shows "R1 → R2" and only appears when item is owned below max rank
- [ ] Maxed modifier (rank 3) never appears as an offer
- [ ] Paradox offer shown in red with stability cost
- [ ] Paradox offer NOT pickable if cost would drop stability to ≤ 0
- [ ] Picking a Paradox offer reduces fold_stability by the shown cost
- [ ] With Penrose Diagram owned — reward screen shows 4 options instead of 3

### Modifier Cap
- [ ] ITEMS line on node map shows all owned items with rank
- [ ] When 6 modifiers owned and a 7th is picked — oldest is dropped, new one added
- [ ] "MODIFIER CAP REACHED" warning shown on reward screen when at cap

### Debug
- [ ] F key (in game) grants all items at rank 1 for playtesting
- [ ] After F grant — ITEMS line on node map shows all items

### Item Effects (verify via F-key grant + play)
- [ ] Tidal Coupling — chrono reserve increases on gravity rotation (with 1.5s cooldown)
- [ ] Geodesic — brief i-frames on gravity rotation (can walk through enemy hit)
- [ ] Redshift — Time Dilation duration extended when active
- [ ] Closed Timelike Curve — integrity-zero cancelled once per room, position restored
- [ ] Event Horizon — black hole costs less stability
- [ ] Quantum Foam — occasional hit cancellation
- [ ] Kerr Ring — every 4th rotation triggers free Time Dilation
- [ ] Hawking Emitter — enemy freezes briefly when player integrity drops
- [ ] Penrose Diagram — 4 options on reward screen

### Parallax layers (TA-2, GPU renderer only)
- [ ] Walk right across level_01: the sky haze/nebula drifts slowly, the ship rim (far) faster, the pipework band (mid) faster still, and platforms move 1:1 with the player
- [ ] Vertical camera movement (taller levels, UP/DOWN gravity) also shows parallax with no visible seams; image layers mirror-wrap at their edges
- [ ] Gravity rotation and screen shake: background layers shake less than the playfield (expected; shake is part of the camera offset)
- [ ] F3 toggles the debug overlay in both renderers (backquote no longer does anything)
- [ ] Debug overlay (F3) on the GPU path shows the collision rect plus per-layer ms (sky/far/mid/play/fore/composite/total) top-right
- [ ] Total layer time stays well under the 4ms scene budget (measured ~0.7ms on the dev Mac)
- [ ] `FOLD_RENDERER=software python main.py` looks exactly as before TA-2 (flat background, no parallax)
- [ ] Dropping `assets/backgrounds/layers/sky.png` (or far/mid) replaces that layer's placeholder on next launch
- [ ] Known placeholder artefact: the ✦ watermark in background.png repeats in the mid band. It goes away when painted layers land
- [ ] Rotation cinematic zoom (R): GPU path zooms in ~8% and back out over ~0.18s, matching the software renderer; lighting and the player's light pool stay aligned with geometry; HUD, vignette and grain do not zoom

### 2D lighting (TA-3, GPU renderer only)
- [ ] level_01: room corners far from lights are visibly darker than areas near the 3 point lights
- [ ] level_01: a warm amber pool follows the player everywhere, including after gravity rotation
- [ ] Sky and far background layers are NOT darkened by lighting; mid pipework band and playfield are
- [ ] Levels other than level_01 look exactly as after TA-2 (unlit, no player light)
- [ ] F3 overlay shows a `light` line; with level_01 it stays well under 2ms (measured ~0.5ms with 10 lights)
- [ ] Brightness tuning: level_01 ambient raised 0.30-0.42 → 0.72-0.82 and player light 0.7 → 0.85 after first look was too dark. Re-check in play; tune in levels/level_01.json and PLAYER_LIGHT_* in constants.py
- [ ] A level JSON with a malformed "lights" value loads the fallback level instead of crashing

### Post-processing (TA-4, GPU renderer only)
- [ ] With F3 open, keys 1-6 toggle bloom / distortion / lut / vignette / grain / crt; overlay shows ON/off in grey and per-pass ms
- [ ] Keys 1-6 do nothing to post passes when F3 is closed (and still work on the reward screen as before)
- [ ] Bloom: goal block and cyan moving platform have a soft glow; dark areas do not
- [ ] Grain is visible as fine shifting noise in mid-tones and is not obvious in near-black areas
- [ ] Vignette darkens corners; HUD pips/chrono bar and the fold tint are NOT vignetted or grained
- [ ] LUT: pipework band in level_01 stays readable with the grade on (regression: a 0.5 contrast pivot crushed it)
- [ ] CRT toggle (key 6) changes nothing. It is a stub (TA Q5)
- [ ] Dropping a 256×16 strip at assets/luts/grade.png replaces the procedural grade on next launch; a wrong-size strip logs a warning and falls back
- [ ] Post stack total stays under 4ms in the F3 overlay (measured ≈1.1ms)
- [ ] Frozen build (build/build_mac.sh) launches in GPU mode: numpy is no longer excluded and shaders/ is now bundled. Not yet verified

### Fold distortion + gravity bend (TA-5, GPU renderer only)
- [ ] E (Time Dilation): a ring ripples outward from the player and fades in ~0.6s, with a brief red/blue fringe
- [ ] Kerr Ring free Time Dilation (every 4th rotation) also ripples
- [ ] R (rotate): the frame bows toward the NEW gravity direction and springs back in ~0.35s; edges stay pinned
- [ ] Entering a gravity zone and chrono snap-back also bend
- [ ] Ripple stays anchored to the world spot where it fired as the camera moves
- [ ] Spamming E/R never warps the frame more than ~32px (hard cap) and never tears
- [ ] HUD is never warped (drawn after post)
- [ ] Distortion toggle (key 2 with F3 open) disables ripple and bend
- [ ] Ripple strength reads well in motion (looked subtle in stills). Tune RIPPLE_AMPLITUDE_PX / RIPPLE_WIDTH_PX

### Feel framework (TA-6)
- [ ] Enemy hit: a brief freeze (~0.06s), the player flashes white, small screen shake; knockback still applies after the freeze
- [ ] Hard landing: short freeze, strong squash with feet planted, camera punch along gravity
- [ ] Normal landing: subtle squash; jumping: subtle stretch along gravity (check all 4 gravity directions, GPU renderer)
- [ ] Time Dilation (E or Kerr Ring): amber sprite flash alongside the ripple
- [ ] F3 + 0 toggles "reduced fx": shake, punch, flashes (sprite and full-screen), squash, ripple, bend and aberration all visibly weaker; rotation zoom skipped; hitstop shorter
- [ ] Death mid-hitstop: respawn is not frozen (feel.reset on level reset)
- [ ] Software renderer (FOLD_RENDERER=software): hitstop, shake and punch work; no sprite flash or squash (expected, GPU-only)
- [ ] Tuning pass: are HIT_HITSTOP / squash amounts / flash durations right in play?

### GPU particles (TA-7)
- [ ] R (rotate): an amber ring expands from the player and fades in ~0.4s (GPU renderer: these were invisible before TA-7)
- [ ] Enemy hit and hard landing: red-orange sparks burst and fall in the player's current gravity direction (check a sideways gravity zone)
- [ ] Any landing: grey dust fans out from the feet against gravity and puffs up as it slows
- [ ] Particles stay in place in the world as the camera moves and zoom with the rotation cinematic
- [ ] Spamming R + landings: never more than 500 particles; no stutter (F3 `play` ms includes particles)
- [ ] Software renderer: same effects (simpler circles), same speeds as GPU (both frame-rate independent now)
- [ ] Tuning: are ring size, spark count and dust puff right in play? (`VFX_*` specs in constants.py)

### Physics hardening (Engine Session 1)
- [ ] Ride a horizontal moving platform end to end: the player stays put on it through the turnarounds (used to slip ~8px)
- [ ] Stand beside a horizontal moving platform's path: it shoves you sideways (used to teleport you on top)
- [ ] Rotate (R) in a narrow vertical gap: either nudged to fit, or refused with a tiny shake and NO chrono spent / no cooldown
- [ ] Get pinned between a moving platform and a wall: you reappear at your last safe ground spot (no damage). Design decision pending, see DECISIONS_NEEDED
- [ ] logs/crash_log.txt shows no "PHYSICS VIOLATION" lines after a normal run (any line there = a geometry/ability bug worth reporting)

### Smoothness (Engine Session 2)
- [ ] Walk and fall at a steady speed: no periodic hitch/stutter of the player or the background (used to judder ~2-3×/s)
- [ ] Ride a moving platform: platform and player move together smoothly, no shimmer between them
- [ ] Respawn after a death / TAB to a new level: the player appears at spawn instantly, no streak across the screen
- [ ] Camera: starts following smoothly when you walk out of the small dead zone (no jolt); after R it re-centres on you
- [ ] Screen shake (rotation, hits) reads as a shake, not as random jitter
- [ ] No screen tearing (vsync on). On a 120/144 Hz external display the game should run at that rate; on the MacBook's own screen it's 60 Hz (macOS limit for OpenGL)
