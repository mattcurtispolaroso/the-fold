# Session Plan — Fix C3: Physics Rect Swap in Horizontal Gravity

## Goal
Swap player physics rect dimensions when gravity is horizontal so physics rect matches rotated sprite. Pure fix — no new features.

## Steps
1. Add physics size constants to constants.py
2. Add get_player_physics_size() to src/physics/gravity.py
3. Export from src/physics/__init__.py
4. Update main.py: compute player_w/player_h from gravity_dir each frame, swap on rotation with centre preservation
5. Update debug overlay to use current physics dimensions
6. Add tests for get_player_physics_size() and rect swap behaviour
7. Run tests, verify, commit
