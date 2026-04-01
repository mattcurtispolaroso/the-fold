# Decisions Needed — Module 2: Level Architecture

## Resolved — MovingPlatform class location
**Question:** The MovingPlatform class exists in both main.py and level_renderer.py. Where should the canonical version live?
**Decision (conservative):** Move it to level_renderer.py since it's level geometry. main.py imports from there. The old class in main.py is removed.
