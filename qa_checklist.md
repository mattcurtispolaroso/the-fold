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
