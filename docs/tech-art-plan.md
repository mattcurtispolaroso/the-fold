# Tech Art Pipeline — Plan v0.1
*Status: approved 2026-11-05. Decisions Q1 and Q2 locked in (see §5). Starting TA-0.*

---

## 1. Audit — what exists and what must change

### Current render pipeline (in order, every frame)

```
screen.fill(black)
background.png  →  flat blit, no parallax, no scale
level geometry  →  colored pygame.Rect fills (gray, cyan, green)
enemies         →  colored pygame.Rect fills
player          →  software-scaled sprite PNG, rotated per gravity dir
particles       →  CPU circles, pre-allocated pool
fold_tint_surf  →  alpha-filled Surface blit (red overlay)
flash_surf      →  alpha-filled Surface blit (blue-white)
impact_flash    →  alpha-filled Surface blit (red-orange)
HUD             →  font blits, pip rects
```

Pure Pygame software renderer. No GPU, no layers, no lighting, no post-processing. `world_surf` is 800×600; zoom is emulated by scaling it with `pygame.transform.scale` before the final blit (the rotation cinematic).

### What exists that is reusable

| Component | Verdict |
|---|---|
| Physics, collision, gravity | Keep as-is — zero rendering dependency |
| Camera (offset, shake, punch, zoom) | Keep — will feed GPU transform uniforms |
| `ParticlePool` | Keep data model; replace draw path |
| Rotation flash / fold tint / impact flash | Replace with post-processing passes |
| `PlayerAnimator` | Keep — produces the source surface; GPU path samples it as a texture |
| `LevelRenderer` | Keep data; replace draw calls |
| `draw_world` in hud.py | Gut and replace with GPU scene submission |
| Test suite | Must stay green — GPU path behind config flag |

### Key risks

1. **Resolution mismatch** (see Open Questions #1). The brief says 1920×1080; the entire physics and level geometry is authored at 800×600. These cannot coexist naively.
2. **macOS OpenGL cap at 4.1** — staying within OpenGL 3.3 core avoids this. No geometry shaders, no compute shaders, no SPIR-V. All fine for 2D.
3. **ModernGL not installed.** numpy is (1.26.4). One `pip install moderngl` needed; add to `requirements.txt`.
4. **Headless tests.** The existing test suite runs `pygame.init()` in a headless mode. ModernGL requires a valid OpenGL context. Tests must use a ModernGL standalone context (no window) or skip GPU tests via `pytest.mark.skipif(no_gpu)`.
5. **Sprite sheets are sparse.** Only 3 player PNGs exist (idle, walk_1, jump_rising). The GPU atlas system must handle missing frames gracefully (placeholder rect) so tests don't break.

---

## 2. Architecture

### Resolution strategy (recommended)

Keep all physics, levels, and game logic at **800×600 world units.** The GPU renderer draws to an internal framebuffer at that size, then upscales to the display resolution (1920×1080 or native window size) with a final blit shader. This is standard for pixel-art/hand-painted 2D games — it separates "game resolution" from "display resolution" cleanly. Art is authored at **2× game resolution (1600×1200 source)** and displayed at 2× by the upscale pass. No physics or level data changes required.

### Render graph

```
─────────────────── OFFSCREEN (800×600) ─────────────────────────
 Layer FBOs (rendered back-to-front, parallax scrolled)
   sky_fbo    (scroll 0.05×)   ─┐
   far_fbo    (scroll 0.20×)    │
   mid_fbo    (scroll 0.50×)    ├─ sprite batch draws
   play_fbo   (scroll 1.00×)    │  (geometry + enemies + player)
   fore_fbo   (scroll 1.30×)   ─┘

 light_fbo  — additive composition of ambient + N point lights
              (multiplied over play_fbo and mid_fbo)

 composite_fbo — merge all layers + light buffer

─────────────── POST STACK (each toggleable) ──────────────────────
 bloom_pass      — threshold + separable blur on emissive channel
 vignette_pass   — radial darkening
 grain_pass      — per-frame noise texture offset
 lut_pass        — 32-slot 1D or 16×16×16 3D LUT
 distortion_pass — fold warp / gravity flip bend (data-driven)
 crt_pass        — optional halation (off by default)

─────────────── DISPLAY UPSCALE ───────────────────────────────────
 final fullscreen quad  — 800×600 → native window, nearest/bilinear toggle

─────────────── HUD (draws direct to screen, skips post) ──────────
 HUD layer — pips, chrono bar, dilation status
```

### Sprite pipeline

```
Art source (1600×1200 PNGs, painted)
   ↓  atlas_packer.py  (tools/)
Texture atlas PNG + JSON manifest (frame rects, pivot, gravity variants)
   ↓  AtlasLoader (src/rendering/gpu/)
GPU Texture object  →  SpriteBatch.draw(atlas_id, frame, x, y, ...)
```

The atlas packer is a build-time tool (not runtime). It packs all frames into one or more 2048×2048 textures. The GPU path samples these; the software fallback scales individual PNGs as before.

### Light description (scene data)

Lights are described per-level in the level JSON under `"lights"`:

```json
"lights": [
  {"type": "ambient", "color": [0.05, 0.08, 0.12]},
  {"type": "point", "x": 400, "y": 200, "radius": 300, "color": [0.3, 0.6, 1.0], "intensity": 1.2},
  {"type": "spot",  "x": 800, "y": 0,   "radius": 400, "angle": 270, "spread": 40, "color": [0.8, 0.5, 0.2], "intensity": 0.9}
]
```

The light buffer is a separate FBO blended multiplicatively over the playfield. Normal maps are optional — lighting works without them using flat per-channel multiplication. With normal maps it upgrades to a standard `dot(N, L)` diffuse model.

### Fallback strategy

A single constant `USE_GPU_RENDERER: bool = True` in `constants.py` (overridable via env var `FOLD_RENDERER=software`) gates every GPU path. The existing Pygame software pipeline runs unchanged when it is `False`. CI always sets `FOLD_RENDERER=software`. No GPU tests run in CI unless a GPU is detected.

### File layout

```
shaders/
  sprite.vert / sprite.frag       — batched sprite draw
  light.vert / light.frag         — light accumulation
  bloom.frag / blur.frag
  vignette.frag
  grain.frag
  lut.frag
  distortion.frag                 — fold warp + gravity bend
  crt.frag
  upscale.frag
src/rendering/gpu/
  __init__.py
  context.py        — init, ctx singleton, fallback detection
  sprite_batch.py   — batched sprite renderer
  atlas.py          — atlas texture loader
  layer.py          — LayerFBO, parallax math
  light_buffer.py   — LightBuffer, point/spot accumulation
  post_stack.py     — PostStack, toggleable passes
  feel.py           — feel framework (hitstop, shake, flash — GPU-aware)
  debug_overlay.py  — in-game tuning panel
tools/
  atlas_packer.py   — offline atlas builder
  shader_watch.py   — hot-reload shaders in debug builds
```

### Feel framework API

```python
# Gameplay code calls these; rendering handles the rest:
feel.hitstop(0.06)              # freeze world for 60ms
feel.shake(trauma=0.4)          # trauma-based decaying shake
feel.flash(color=(1,1,1), dur=0.08)   # full-sprite white flash
feel.distortion(x, y, strength=1.0, dur=0.3)   # Fold warp from world pos
feel.gravity_bend(direction)    # gravity-flip frame bend
feel.squash(axis, amount=0.15)  # squash/stretch on player
```

The `feel` module wraps the camera's existing shake/punch and extends to GPU effects. The accessibility toggle sets a global `feel.intensity` multiplier (default 1.0, reduced to 0.3 for accessibility mode).

---

## 3. Module breakdown

Each module is sized for one autonomous overnight session. Dependencies listed; no module starts unless its dependency is merged and green.

### TA-0 — GPU backend foundation
**Goal:** ModernGL context initialises alongside Pygame. A single colored triangle draws to screen via OpenGL. Software fallback flag works. Zero gameplay change.
**Files:** `requirements.txt`, `constants.py`, `src/rendering/gpu/context.py`, `src/rendering/gpu/__init__.py`, `main.py` (init only, 3-line change)
**Acceptance:** `python main.py` runs with and without `FOLD_RENDERER=software`. Triangle visible in GPU mode.
**Tests:** headless context smoke test using `moderngl.create_standalone_context()`.
**Depends on:** nothing (first module)

### TA-1 — Sprite batch + atlas loader
**Goal:** Player and level geometry drawn via GPU sprite batch from a texture atlas. Visual output identical to software path.
**Files:** `src/rendering/gpu/sprite_batch.py`, `src/rendering/gpu/atlas.py`, `shaders/sprite.vert`, `shaders/sprite.frag`, `tools/atlas_packer.py`
**Acceptance:** all three player sprites draw correctly in all 4 gravity orientations; atlas packs cleanly; software path unaffected.
**Tests:** atlas packing unit tests (rect coverage, no overlap); sprite batch draw-call count test.
**Depends on:** TA-0

### TA-2 — Parallax layer system
**Goal:** 5 FBOs with per-layer scroll factors. Background art splits across sky/far/mid layers. Foreground silhouette layer added.
**Files:** `src/rendering/gpu/layer.py`, `shaders/upscale.frag`, level JSON schema (add `"layers"` key), `src/rendering/gpu/context.py` (FBO management)
**Acceptance:** sky layer visibly scrolls slower than playfield during camera movement; F3 overlay shows per-layer ms.
**Tests:** scroll factor math unit test; FBO resize test.
**Depends on:** TA-1

### TA-3 — 2D light buffer
**Goal:** Ambient light + up to 10 point/spot lights per level. Light buffer composited multiplicatively over playfield and mid layers.
**Files:** `src/rendering/gpu/light_buffer.py`, `shaders/light.vert`, `shaders/light.frag`, level JSON schema (`"lights"` key)
**Acceptance:** a point light follows the player position; room corners visibly darker with ambient-only; 10 lights at <2ms on dev Mac.
**Tests:** light data loading from JSON; additive blend math unit test.
**Depends on:** TA-2

### TA-4 — Post-processing stack v1 (bloom + vignette + grain + LUT)
**Goal:** Toggleable post passes. Bloom on emissive channel only. Vignette, grain, LUT hooked up with tunable params. Debug overlay lets you toggle each pass live.
**Files:** `src/rendering/gpu/post_stack.py`, `src/rendering/gpu/debug_overlay.py`, `shaders/bloom.frag`, `shaders/blur.frag`, `shaders/vignette.frag`, `shaders/grain.frag`, `shaders/lut.frag`, `tools/shader_watch.py`
**Acceptance:** toggling passes via debug overlay works; grain varies per frame; bloom visible on player helmet emissive. All passes combined <4ms.
**Tests:** pass toggle unit test; golden-image test for vignette (tolerance ±5 luma).
**Depends on:** TA-3

### TA-5 — Fold distortion + gravity flip
**Goal:** Screen-space warp from a world position (Fold ability use). Gravity-flip bend animation on rotation. Chromatic aberration split on activation.
**Files:** `shaders/distortion.frag`, `src/rendering/gpu/post_stack.py` (distortion pass), `src/rendering/gpu/feel.py`
**Acceptance:** pressing R (gravity rotate) triggers a visible frame-bend; E (time dilation) triggers a Fold ripple from player position; both are toggleable.
**Tests:** distortion param clamp tests; `feel.distortion()` queues correctly with zero-duration no-op.
**Depends on:** TA-4

### TA-6 — Feel framework
**Goal:** `feel.*` API replaces all direct camera shake calls. Hitstop, sprite flash (white/amber), squash/stretch hooks. Global intensity + accessibility toggle.
**Files:** `src/rendering/gpu/feel.py`, `main.py` (replace camera.shake/punch calls), `constants.py` (accessibility flag)
**Acceptance:** `feel.hitstop(0.06)` correctly freezes physics accumulator; sprite flash visible on hit; accessibility mode visibly reduces all effects.
**Tests:** hitstop duration unit test; intensity multiplier test; feel API works headlessly with software renderer.
**Depends on:** TA-5

### TA-7 — GPU particles
**Goal:** Particle system moved to GPU (instanced quad draw). Existing `ParticlePool` data model feeds GPU positions each frame. Visual upgrade to rotation burst, hit spark, landing dust.
**Files:** `src/rendering/gpu/sprite_batch.py` (instanced draw path), `src/rendering/vfx.py` (add GPU draw method), `shaders/sprite.vert`/`sprite.frag` (instancing variant)
**Acceptance:** 500 particles at 60fps; visually distinct rotation burst (amber ring), hit spark (red-orange), dust (gray fan).
**Tests:** instancing draw-call count test; particle recycle test (pool never grows).
**Depends on:** TA-6

### TA-8 — Normal maps + emissive mask (optional, post-launch candidate)
**Goal:** Optional normal map channel per sprite. Emissive mask so helmet visor and enemy threat elements glow without glowing the whole sprite. Lighting upgrades to `dot(N, L)` where normal maps exist.
**Files:** `src/rendering/gpu/light_buffer.py` (normal sample path), `shaders/light.frag`, atlas packer (add normal/emissive channels)
**Acceptance:** lighting visibly directional on agent sprite with normal map; emissive mask isolated on helmet visor; sprites without normal maps fall back gracefully to flat lighting.
**Tests:** fallback path unit test; atlas channel test.
**Depends on:** TA-4

---

## 4. Sequencing — vertical slice first

The first shipped milestone is one room that looks like a commercial title:

```
TA-0 → TA-1 → TA-2 → TA-3 → TA-4 → TA-5
```

That is: GPU backend → sprites → parallax → lights → post stack → Fold distortion.

**Vertical slice acceptance criteria** (end of TA-5):
- One combat room (level_01) renders with 5 parallax layers, 3 point lights, bloom on player emissives, vignette, grain, Fold distortion on gravity rotation, and gravity-flip bend.
- 60fps on dev Mac with full scene.
- Software fallback passes all 611 existing tests unchanged.
- F3 debug overlay shows per-pass ms.

Remaining modules (TA-6 feel, TA-7 GPU particles, TA-8 normal maps) ship after the vertical slice is reviewed and approved. TA-8 is explicitly marked optional/post-launch.

### Per-pass ms budget (800×600 internal, 60fps = 16.6ms total)

| Pass | Budget |
|---|---|
| Scene (5 layers + sprite batch) | 4ms |
| Light buffer | 2ms |
| Bloom (threshold + 2× blur) | 2ms |
| Vignette + grain + LUT | 1ms |
| Distortion | 1ms |
| Upscale | 0.5ms |
| HUD + swap | 1ms |
| **Total** | **11.5ms** (4.5ms headroom) |

---

## 5. Open questions — decisions needed

### Q1 — Resolution ✅ decided 2026-11-05
**Decision: Stay at 800×600 world units, upscale to display.** Moving to 1920×1080 would require reshaping every level JSON file, all physics constants (PPM, terminal velocity, boundary rects), and all existing test assertions. The upscale approach is standard for hand-painted 2D games (Cuphead, Hollow Knight use this pattern) and delivers the same visual output with no physics changes. Art is authored at 2× (1600×1200) and displayed pixel-perfect at 2× via the upscale shader.

### Q2 — Art state at vertical slice ✅ decided 2026-11-05
**Decision: Pipeline first, art second.** Build TA-0 through TA-5 with current placeholders. Swapping real art in is then a pure asset drop — no code change. This avoids blocking GPU work on the art pipeline and lets you test lighting and post-processing with real geometry before committing art direction.

### Q3 — Fallback: CI-only or runtime option?
**Question:** Is the Pygame software renderer a CI/test tool only, or should players be able to choose it (e.g., older/no-GPU machines)?
**Recommendation:** **CI-only for now.** Maintaining two render paths permanently doubles testing surface. Ship GPU-only; if a compatibility report comes in post-launch, revisit. The fallback flag stays in the codebase but is not exposed as a user setting.

### Q4 — Normal map authoring (non-blocking, informs TA-8 timing)
**Question:** Should normal maps be hand-painted by the artist, or generated algorithmically from the sprite's painted surface?
**Recommendation:** **Generated.** Tools like SpriteIlluminator or the open-source `spritesheet-to-normalmap` can produce plausible normal maps from painted sprites in minutes. Hand-painted is higher quality but adds significant art time per sprite. Start generated; upgrade specific hero sprites if the result is noticeably wrong.

### Q5 — CRT/halation pass (non-blocking)
**Question:** Is the CRT/halation effect in scope for the vertical slice, or is it a later optional pass?
**Recommendation:** **Defer to post-vertical-slice.** It is the most divisive aesthetic choice (players either love it or hate it) and adds no gameplay clarity. Wire the toggle in TA-4 but leave the shader as a stub. Decide after seeing the full post stack on real art.

### Q6 — Parallax art (non-blocking, informs TA-2 timeline)
**Question:** Does background art need to be painted and split into 5 layers before TA-2 can be meaningfully tested, or can it use a single image split procedurally?
**Recommendation:** **Procedural split for testing.** For TA-2, the single `background.png` can be split into tinted copies at different depths to verify the parallax math without new art. Real layered backgrounds land whenever the art pipeline produces them.
