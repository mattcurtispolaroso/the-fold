# Decisions Needed — Module 1: Physics Extraction

## main.py line count
**Target:** 150 lines. **Actual:** 190 lines.
**Why:** main.py still contains load_player_sprite(), load_background() (rendering), input-to-move_input mapping (event handling), and draw code. These belong in future modules (rendering, entity system). Removing them now would require Module 5 (Entity) or Module 13 (Sprite/Animation) which are Phase 1, not Phase 0. Conservative decision: leave at 190 lines until those modules are built.
