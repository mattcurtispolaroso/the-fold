"""Tests for the TA-2 parallax layer system.

Pure-math and schema tests always run. GPU tests use a standalone ModernGL
context (no window) and skip when no GPU is available, e.g. in CI.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np
import pygame

import constants as C
from src.levels.level_data import LevelData, parse_layer_scrolls
from src.rendering.gpu.layer import parallax_offset, resolve_scroll_factors

_SIZE = (200, 100)
_MARKER_X = 100        # x of the 1px white column in the synthetic sky image
_CAM_STEP_X = -80.0    # camera moves right by 80px → additive offset drops by 80


def _standalone_ctx():
    """Return a standalone ModernGL context, or None when no GPU is available."""
    try:
        import moderngl
        return moderngl.create_standalone_context()
    except Exception:
        return None


def _marker_column(fbo, threshold: int = 128) -> int:
    """Return the x of the brightest column in the middle row of an FBO."""
    w, h = fbo.size
    pixels = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(h, w, 4)
    row = pixels[h // 2, :, 0].astype(int)
    if row.max() < threshold:
        return -1
    return int(row.argmax())


class TestParallaxMath(unittest.TestCase):
    """Scroll-factor math — no GPU needed."""

    def test_play_layer_matches_camera(self) -> None:
        """Factor 1.0 must reproduce the camera offset exactly (locked to physics)."""
        self.assertEqual(parallax_offset((-120.0, 35.0), 1.0), (-120.0, 35.0))

    def test_zero_factor_pins_to_screen(self) -> None:
        """Factor 0.0 must ignore camera movement entirely."""
        self.assertEqual(parallax_offset((-500.0, -300.0), 0.0), (0.0, 0.0))

    def test_sky_scrolls_slower_than_play(self) -> None:
        """For any camera movement the sky moves less than the playfield."""
        factors = resolve_scroll_factors()
        sky_x, _ = parallax_offset((_CAM_STEP_X, 0.0), factors["sky"])
        play_x, _ = parallax_offset((_CAM_STEP_X, 0.0), factors["play"])
        self.assertLess(abs(sky_x), abs(play_x))
        self.assertAlmostEqual(sky_x, _CAM_STEP_X * C.PARALLAX_SCROLL_FACTORS["sky"])

    def test_default_factors_increase_back_to_front(self) -> None:
        """Layers further back must scroll slower than layers in front of them."""
        factors = [C.PARALLAX_SCROLL_FACTORS[n] for n in C.PARALLAX_LAYER_NAMES]
        self.assertEqual(factors, sorted(factors))
        self.assertEqual(len(C.PARALLAX_LAYER_NAMES), 5)

    def test_overrides_cannot_unlock_play_layer(self) -> None:
        """A play-layer override is ignored; play stays at 1.0."""
        self.assertEqual(resolve_scroll_factors({"play": 0.3})["play"], 1.0)

    def test_overrides_are_clamped(self) -> None:
        """Out-of-range overrides are clamped to the allowed scroll range."""
        factors = resolve_scroll_factors({"sky": -1.0, "fore": 99.0})
        self.assertEqual(factors["sky"], C.PARALLAX_SCROLL_MIN)
        self.assertEqual(factors["fore"], C.PARALLAX_SCROLL_MAX)


class TestLevelLayerSchema(unittest.TestCase):
    """The optional "layers" key in level JSON."""

    _BASE = {"name": "t", "gravity_start": [0, 1], "spawn": [0, 0],
             "goal": {"x": 0, "y": 0, "w": 10, "h": 10}}

    def test_levels_without_layers_load(self) -> None:
        """Existing levels have no "layers" key and get no overrides."""
        self.assertEqual(LevelData.from_dict(dict(self._BASE)).layer_scrolls, {})

    def test_layers_round_trip(self) -> None:
        """Overrides survive to_dict → from_dict."""
        d = dict(self._BASE, layers={"sky": {"scroll": 0.1}, "mid": {"scroll": 0.4}})
        level = LevelData.from_dict(d)
        self.assertEqual(LevelData.from_dict(level.to_dict()).layer_scrolls,
                         {"sky": 0.1, "mid": 0.4})

    def test_to_dict_omits_empty_layers(self) -> None:
        """Levels without overrides serialise exactly as before TA-2."""
        self.assertNotIn("layers", LevelData.from_dict(dict(self._BASE)).to_dict())

    def test_unknown_and_play_layers_dropped(self) -> None:
        """Unknown names and the locked play layer are discarded."""
        scrolls = parse_layer_scrolls({"bogus": {"scroll": 0.3}, "play": {"scroll": 0.3}})
        self.assertEqual(scrolls, {})

    def test_malformed_layers_falls_back(self) -> None:
        """A non-object "layers" value makes load() use the fallback level."""
        import json
        import tempfile
        d = dict(self._BASE, layers=["sky"])
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(d, f)
        try:
            self.assertEqual(LevelData.load(f.name).name, "Fallback Level")
        finally:
            os.unlink(f.name)

    def test_shipped_levels_still_load(self) -> None:
        """Every level file in levels/ still parses without falling back."""
        level_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "levels")
        for fname in sorted(os.listdir(level_dir)):
            if fname.endswith(".json"):
                level = LevelData.load(os.path.join(level_dir, fname))
                self.assertNotEqual(level.name, "Fallback Level", fname)


class TestPlaceholderLayerImages(unittest.TestCase):
    """Procedural split of background.png into sky / far / mid (Q6)."""

    def setUp(self) -> None:
        """Build a small gradient background surface."""
        pygame.init()
        self.bg = pygame.Surface(_SIZE)
        for x in range(_SIZE[0]):
            shade = int(255 * x / (_SIZE[0] - 1))
            pygame.draw.line(self.bg, (shade, shade, shade), (x, 0), (x, _SIZE[1] - 1))

    def test_builds_all_three_image_layers(self) -> None:
        """With a background and no layer art, sky/far/mid are all generated."""
        from src.rendering.gpu.layer_images import build_layer_images
        images = build_layer_images("/nonexistent", self.bg, _SIZE)
        self.assertEqual(set(images), set(C.PARALLAX_IMAGE_LAYERS))
        for surf in images.values():
            self.assertEqual(surf.get_size(), _SIZE)

    def test_no_background_gives_no_images(self) -> None:
        """Missing background art must not crash — layers are simply empty."""
        from src.rendering.gpu.layer_images import build_layer_images
        self.assertEqual(build_layer_images("/nonexistent", None, _SIZE), {})

    def test_sky_is_opaque(self) -> None:
        """The sky is the backstop layer and must be fully opaque."""
        from src.rendering.gpu.layer_images import make_sky_layer
        alpha = pygame.surfarray.array_alpha(make_sky_layer(self.bg))
        self.assertTrue((alpha == 255).all())

    def test_far_keeps_only_bright_pixels(self) -> None:
        """Far-layer alpha is zero on dark pixels and full on bright ones."""
        from src.rendering.gpu.layer_images import make_far_layer
        alpha = pygame.surfarray.array_alpha(make_far_layer(self.bg))
        self.assertEqual(alpha[0, 50], 0)
        self.assertEqual(alpha[-1, 50], 255)

    def test_mid_is_a_lower_band(self) -> None:
        """Mid-layer alpha is zero at the top and full at the bottom."""
        from src.rendering.gpu.layer_images import make_mid_layer
        alpha = pygame.surfarray.array_alpha(make_mid_layer(self.bg))
        self.assertEqual(alpha[50, 0], 0)
        self.assertEqual(alpha[50, -1], 255)


class TestDebugOverlayTimings(unittest.TestCase):
    """Per-layer timing text for the debug overlay."""

    def test_one_line_per_layer_plus_light_composite_and_total(self) -> None:
        """Every layer is listed, even with no samples yet."""
        from src.rendering.gpu.debug_overlay import format_layer_timings
        lines = format_layer_timings({"sky": 0.25, "play": 1.0})
        self.assertEqual(len(lines), len(C.PARALLAX_LAYER_NAMES) + 3)
        self.assertIn("1.25", lines[-1])


class TestParallaxStackGPU(unittest.TestCase):
    """Real FBO rendering through a standalone context (skipped without a GPU)."""

    def setUp(self) -> None:
        """Create a context, a stack with a marker-line sky, and a sprite batch."""
        self.ctx = _standalone_ctx()
        if self.ctx is None:
            self.skipTest("No GPU available")
        pygame.init()
        from src.rendering.gpu.atlas import RuntimeAtlas
        from src.rendering.gpu.layer import ParallaxStack
        from src.rendering.gpu.sprite_batch import SpriteBatch
        sky = pygame.Surface(_SIZE, pygame.SRCALPHA)
        sky.fill((0, 0, 0, 255))
        pygame.draw.line(sky, (255, 255, 255, 255), (_MARKER_X, 0), (_MARKER_X, _SIZE[1]))
        self.stack = ParallaxStack(self.ctx, _SIZE, {"sky": sky})
        self.atlas = RuntimeAtlas(self.ctx, {})
        self.batch = SpriteBatch(self.ctx, self.atlas, _SIZE)

    def tearDown(self) -> None:
        """Release GPU resources."""
        if getattr(self, "ctx", None) is None:
            return
        self.stack.release()
        self.batch.release()
        self.atlas.release()
        self.ctx.release()

    def _render(self, cam_offset: tuple[float, float]) -> tuple[int, int]:
        """Render one frame; return (sky marker x, play marker x)."""
        self.stack.begin_frame()
        self.stack.draw_image_layers(cam_offset)
        with self.stack.target("play"):
            self.batch.begin()
            # 1px-wide world-space marker at x = _MARKER_X
            self.batch.draw_rect(_MARKER_X + cam_offset[0], 0, 1, _SIZE[1], (1, 1, 1, 1))
            self.batch.flush()
        return (_marker_column(self.stack.layers["sky"].fbo),
                _marker_column(self.stack.layers["play"].fbo))

    def test_sky_visibly_scrolls_slower_than_playfield(self) -> None:
        """TA-2 done-when: horizontal camera movement shifts sky 0.05× as far as play."""
        sky0, play0 = self._render((0.0, 0.0))
        sky1, play1 = self._render((_CAM_STEP_X, 0.0))
        play_shift = play1 - play0
        sky_shift = sky1 - sky0
        self.assertEqual(play_shift, int(_CAM_STEP_X))
        expected_sky = _CAM_STEP_X * C.PARALLAX_SCROLL_FACTORS["sky"]
        self.assertAlmostEqual(sky_shift, expected_sky, delta=1.0)
        self.assertLess(abs(sky_shift), abs(play_shift))
        self.assertNotEqual(sky_shift, 0)  # it does move — just slower

    def test_composite_blends_translucent_layer_once(self) -> None:
        """A 50% layer over an opaque sky gives a 50/50 mix (no double darkening)."""
        target = self.ctx.simple_framebuffer(_SIZE, components=4)
        self.stack.begin_frame()
        self.stack.layers["sky"].fbo.clear(0.0, 0.0, 1.0, 1.0)
        with self.stack.target("far"):
            self.batch.begin()
            self.batch.draw_rect(0, 0, _SIZE[0], _SIZE[1], (1.0, 0.0, 0.0, 0.5))
            self.batch.flush()
        target.clear(0.0, 0.0, 0.0, 1.0)
        self.stack.composite(target)
        r, g, b, _ = target.read(components=4)[:4]
        self.assertAlmostEqual(r, 128, delta=3)
        self.assertEqual(g, 0)
        self.assertAlmostEqual(b, 128, delta=3)
        target.release()

    def test_resize_reallocates_every_layer(self) -> None:
        """resize() changes every FBO; resizing to the same size is a no-op."""
        new_size = (320, 180)
        self.stack.resize(new_size)
        for layer in self.stack.layers.values():
            self.assertEqual(layer.size, new_size)
        tex_before = self.stack.layers["sky"].texture
        self.stack.resize(new_size)
        self.assertIs(self.stack.layers["sky"].texture, tex_before)

    def test_profiling_records_every_layer(self) -> None:
        """With profiling on, image, play and composite timings are all recorded."""
        self.stack.profiling = True
        self._render((0.0, 0.0))
        self.stack.composite(self.ctx.simple_framebuffer(_SIZE, components=4))
        for key in ("sky", "play", "composite"):
            self.assertIn(key, self.stack.layer_ms)
            self.assertGreaterEqual(self.stack.layer_ms[key], 0.0)
