# Decisions Needed — Code Quality Audit

## Open Items

### C2: Level bounds clamping precision
- **File:** main.py (bounds clamping section)
- **Risk:** Uses `round()` comparison which could miss sub-pixel edge cases. Different code path from platform collision.
- **Recommended fix:** Unify bounds clamping into resolve_collisions by adding virtual boundary platforms. Moderate effort — defer to physics refactor session.

### C3: Sprite/physics rect size mismatch in horizontal gravity
- **File:** src/rendering/animation.py
- **Risk:** 90/270 degree rotation swaps sprite width/height but physics rect stays PLAYER_SPRITE_WIDTH x PLAYER_SPRITE_HEIGHT. Visual and collision rects disagree in left/right gravity.
- **Recommended fix:** Either swap player_w/player_h in main.py when gravity is horizontal, or keep physics rect as the larger dimension always. Needs design decision — gameplay implications.

## Resolved (removed from active list)

- **C1** — Stale on_ground after gravity rotation. Fixed: commit `426edb9`.
- **C4** — Camera shake applied to offset. Not a bug; documented for clarity only.
- **D1** — No top-level exception handler. Fixed: commit `b7f1ef2`.
- **D2** — No logging infrastructure. Fixed: commit `b7f1ef2`.
- **D3** — No physics watchdog. Fixed: commit `b7f1ef2`.
- **D4** — No error handling on level load. Fixed: commit `b7f1ef2`.
- **D5** — No entity count limits. Fixed: MAX_ENEMIES/MAX_PARTICLES/MAX_PROJECTILES added to constants.py.
- **D6** — System font dependency. Fixed: bundled TTF loaded first with SysFont fallback.
