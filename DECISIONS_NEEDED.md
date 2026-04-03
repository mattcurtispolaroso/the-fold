# Decisions Needed — Code Quality Audit

## Category C — Dangerous Interactions (deferred)

### C1: Stale on_ground after gravity rotation
- **File:** main.py:101
- **Risk:** `on_ground` from previous frame is used to skip gravity on current frame. If gravity rotates mid-frame, player may briefly skip gravity in the new direction.
- **Recommended fix:** Recompute on_ground via adjacency probe after gravity rotation, before physics step. Low priority — only affects single frame after rotation.

### C2: Level bounds clamping precision
- **File:** main.py:173-189
- **Risk:** Uses `round()` comparison which could miss sub-pixel edge cases. Different code path from platform collision.
- **Recommended fix:** Unify bounds clamping into resolve_collisions by adding virtual boundary platforms. Moderate effort — defer to physics refactor session.

### C3: Sprite/physics rect size mismatch in horizontal gravity
- **File:** src/rendering/animation.py:167
- **Risk:** 90/270 degree rotation swaps sprite width/height but physics rect stays PLAYER_SPRITE_WIDTH x PLAYER_SPRITE_HEIGHT. Visual and collision rects disagree in left/right gravity.
- **Recommended fix:** Either swap player_w/player_h in main.py when gravity is horizontal, or keep physics rect as the larger dimension always. Needs design decision — gameplay implications.

### C4: Camera shake applied to offset (safe)
- **File:** src/rendering/camera.py:186-187
- **Risk:** None — documented for clarity. Shake offset only affects rendering, never physics.

## Category D — Stability Risks (deferred)

### D1: No top-level exception handler
- **File:** main.py:110
- **Risk:** Any unhandled exception crashes to desktop. CLAUDE.md stability rules require crash_log.txt with player state.
- **Recommended fix:** Wrap game loop in try/except, write crash report. Dedicate a session to stability infrastructure.

### D2: No logging infrastructure
- **Risk:** No crash_log.txt, performance_log.txt, or game_log.txt exist. Required by CLAUDE.md.
- **Recommended fix:** Build logging module in dedicated session.

### D3: No physics watchdog
- **Risk:** No monitoring of physics update time. Required by CLAUDE.md.
- **Recommended fix:** Add timer around physics step, log warnings. Part of stability session.

### D4: No error handling on level load
- **File:** src/levels/level_data.py:142-143
- **Risk:** Malformed JSON crashes the game.
- **Recommended fix:** Add try/except with fallback level. Part of stability session.

### D5: No entity count limits
- **Risk:** No MAX_ENEMIES, MAX_PARTICLES, MAX_PROJECTILES defined.
- **Recommended fix:** Add to constants.py when entity system is built (Module 5).

### D6: System font dependency
- **File:** main.py:80
- **Risk:** `pygame.font.SysFont(None, 28)` may render differently across platforms.
- **Recommended fix:** Bundle a TTF font in assets/fonts/. Low priority.
