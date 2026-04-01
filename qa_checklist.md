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

- Rotating while pressed against a screen edge can briefly clip the player into the boundary before clamping corrects it
- Movement keys overlap with jump keys in horizontal gravity orientations (Up/W is both "move up" and "jump") — may cause unintended jumps when moving
- No platforms yet — testing is limited to the single floor per orientation

## Level Loading

- [ ] Game loads level_01.json on startup without errors
- [ ] All 7 static platforms render in correct positions
- [ ] Both moving platforms animate correctly (horizontal oscillation)
- [ ] Spawn point places player at correct start position (above first platform)
- [ ] Goal rect renders as green rectangle in upper-left area
- [ ] "GOAL REACHED!" text appears when player touches goal area
- [ ] Deleting level_01.json produces a clear error (not silent failure)

## Level Architecture Edge Cases

- [ ] Moving platforms carry correct collision — player can stand on them
- [ ] Gravity rotation works correctly with multi-platform level (not just single floor)
- [ ] Player doesn't clip through thin platforms (ceiling platforms are 20px)
- [ ] Moving platform at ceiling gap is reachable with gravity=up

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

## Physics Module (post-extraction)

- [ ] Jump works in all 4 gravity orientations (down, left, up, right)
- [ ] Variable jump height (tap vs hold) works in all orientations
- [ ] Coyote time works after walking off any platform edge
- [ ] Gravity rotation (R) correctly changes physics direction immediately
- [ ] Terminal velocity caps fall speed in all orientations
- [ ] Lateral movement accel/decel feels identical to pre-refactor
- [ ] No physics logic remains in main.py — all in src/physics/
