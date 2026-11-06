"""Tests for the TA-4 post-processing stack.

LUT maths, toggles and key mapping always run. GPU tests render through a
standalone ModernGL context and read pixels back; they skip without a GPU.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np
import pygame

import constants as C
from src.rendering.gpu.lut import build_grade_lut, identity_lut, load_lut, lut_from_strip
from src.rendering.gpu.post_stack import vignette_factor

_SIZE = (160, 120)
_GREY = 0.5
_LUMA_TOL = 5.0 / 255.0   # spec: golden-image tolerance ±5 luma


def _ctx_or_none():
    """Return a standalone ModernGL context, or None when no GPU is available."""
    try:
        import moderngl
        return moderngl.create_standalone_context()
    except Exception:
        return None


class TestLut(unittest.TestCase):
    """LUT construction — pure numpy."""

    def test_identity_maps_colour_to_itself(self) -> None:
        """identity_lut[b, g, r] == (r, g, b) at every grid point."""
        lut = identity_lut(4)
        ramp = np.linspace(0, 1, 4)
        np.testing.assert_allclose(lut[1, 2, 3], [ramp[3], ramp[2], ramp[1]])

    def test_grade_stays_in_range_and_is_not_identity(self) -> None:
        """The procedural grade is a real (but bounded) change."""
        grade = build_grade_lut(C.LUT_SIZE)
        self.assertGreaterEqual(float(grade.min()), 0.0)
        self.assertLessEqual(float(grade.max()), 1.0)
        self.assertGreater(float(np.abs(grade - identity_lut(C.LUT_SIZE)).max()), 0.01)

    def test_grade_tints_shadows_cool_and_highlights_warm(self) -> None:
        """Dark greys lean blue, light greys lean red (retrofuturist split tone)."""
        grade = build_grade_lut(C.LUT_SIZE)
        dark, light = grade[2, 2, 2], grade[-3, -3, -3]
        self.assertGreater(dark[2], dark[0])
        self.assertGreater(light[0], light[2])

    def test_strip_round_trip(self) -> None:
        """An identity strip image parses back to the identity LUT."""
        n = 4
        strip = pygame.Surface((n * n, n))
        for b in range(n):
            for g in range(n):
                for r in range(n):
                    c = [round(v * 255 / (n - 1)) for v in (r, g, b)]
                    strip.set_at((b * n + r, g), c)
        np.testing.assert_allclose(lut_from_strip(strip, n), identity_lut(n), atol=1 / 255)

    def test_wrong_strip_size_rejected(self) -> None:
        """A strip with the wrong dimensions raises instead of mis-grading."""
        with self.assertRaises(ValueError):
            lut_from_strip(pygame.Surface((10, 10)), 4)

    def test_missing_strip_falls_back_to_procedural(self) -> None:
        """With no LUT art on disk the procedural grade is used."""
        np.testing.assert_allclose(load_lut("/nonexistent", C.LUT_SIZE),
                                   build_grade_lut(C.LUT_SIZE))


class TestPostConfig(unittest.TestCase):
    """Pass order, defaults and key mapping."""

    def test_every_pass_has_a_default(self) -> None:
        """Each pass in the order has a default state; CRT starts off (TA Q5)."""
        self.assertEqual(set(C.POST_PASS_ORDER), set(C.POST_PASS_DEFAULTS))
        self.assertFalse(C.POST_PASS_DEFAULTS["crt"])

    def test_keys_map_to_passes_in_order(self) -> None:
        """Keys 1-6 toggle the passes in POST_PASS_ORDER; other keys map to nothing."""
        from src.rendering.gpu.debug_overlay import post_pass_for_key
        self.assertEqual(post_pass_for_key(pygame.K_1), C.POST_PASS_ORDER[0])
        self.assertEqual(post_pass_for_key(pygame.K_6), C.POST_PASS_ORDER[5])
        self.assertEqual(len(C.POST_PASS_ORDER), 6)
        self.assertIsNone(post_pass_for_key(pygame.K_r))

    def test_overlay_lists_pass_states(self) -> None:
        """The timing block shows each pass with its key and ON/off state."""
        from src.rendering.gpu.debug_overlay import format_layer_timings
        enabled = dict(C.POST_PASS_DEFAULTS)
        lines = format_layer_timings({}, enabled)
        self.assertTrue(any(l.startswith("[1] bloom") and "ON" in l for l in lines))
        self.assertTrue(any(l.startswith("[6] crt") and "off" in l for l in lines))

    def test_vignette_reference_shape(self) -> None:
        """Centre is untouched, corners darkened by exactly VIGNETTE_STRENGTH."""
        self.assertAlmostEqual(vignette_factor(0.5, 0.5, *_SIZE), 1.0)
        self.assertAlmostEqual(vignette_factor(0.0, 0.0, *_SIZE), 1.0 - C.VIGNETTE_STRENGTH)


class TestPostStackGPU(unittest.TestCase):
    """Real post passes on a standalone context (skipped without a GPU)."""

    def setUp(self) -> None:
        """Create a context, a post stack with an identity LUT, and an output target."""
        self.ctx = _ctx_or_none()
        if self.ctx is None:
            self.skipTest("No GPU available")
        from src.rendering.gpu.post_stack import PostStack
        self.post = PostStack(self.ctx, _SIZE, identity_lut(C.LUT_SIZE))
        self.out = self.ctx.simple_framebuffer(_SIZE, components=4)

    def tearDown(self) -> None:
        """Release GPU resources."""
        if getattr(self, "ctx", None) is None:
            return
        self.out.release()
        self.post.release()
        self.ctx.release()

    def _only(self, *names: str) -> None:
        """Enable exactly the given passes."""
        for name in C.POST_PASS_ORDER:
            self.post.enabled[name] = name in names

    def _run(self, fill: tuple[float, float, float], draw=None) -> np.ndarray:
        """Fill the scene, optionally draw into it, render, return float RGB (h, w, 3), row 0 = top."""
        scene = self.post.begin_scene()
        scene.clear(*fill, 1.0)
        if draw:
            draw(scene)
        self.post.render(self.out)
        w, h = _SIZE
        px = np.frombuffer(self.out.read(components=3), dtype=np.uint8).reshape(h, w, 3)
        return px[::-1].astype(np.float32) / 255.0

    def test_all_off_is_identity(self) -> None:
        """With every pass disabled the scene reaches the target unchanged."""
        self._only()
        img = self._run((0.2, 0.4, 0.6))
        np.testing.assert_allclose(img[10, 10], [0.2, 0.4, 0.6], atol=_LUMA_TOL)

    def test_toggle_flips_state(self) -> None:
        """toggle() flips a pass and returns the new state."""
        before = self.post.enabled["vignette"]
        self.assertEqual(self.post.toggle("vignette"), not before)
        self.assertEqual(self.post.enabled["vignette"], not before)

    def test_vignette_matches_reference(self) -> None:
        """Golden check: vignette on flat grey matches vignette_factor() within ±5 luma."""
        self._only("vignette")
        img = self._run((_GREY, _GREY, _GREY))
        w, h = _SIZE
        for row in range(0, h, 15):
            for col in range(0, w, 20):
                u, v = (col + 0.5) / w, 1.0 - (row + 0.5) / h
                expected = _GREY * vignette_factor(u, v, w, h)
                self.assertAlmostEqual(float(img[row, col, 0]), expected, delta=_LUMA_TOL,
                                       msg=f"pixel ({col}, {row})")

    def test_grain_varies_per_frame(self) -> None:
        """Two consecutive frames of the same scene differ only by grain."""
        self._only("grain")
        first = self._run((_GREY, _GREY, _GREY))
        second = self._run((_GREY, _GREY, _GREY))
        self.assertGreater(float(np.abs(first - second).mean()), 0.002)
        self.assertLessEqual(float(np.abs(first - _GREY).max()), C.GRAIN_AMOUNT + _LUMA_TOL)

    def test_bloom_spreads_bright_pixels_only(self) -> None:
        """A bright block glows into its dark surroundings; a dim scene gets no glow."""
        self._only("bloom")

        def bright_block(scene) -> None:
            scene.scissor = (70, 50, 20, 20)
            scene.clear(1.0, 1.0, 1.0, 1.0)
            scene.scissor = None

        img = self._run((0.0, 0.0, 0.0), bright_block)
        self.assertGreater(float(img[60, 65].sum()), 0.02)   # just outside the block: glow
        dim = self._run((0.3, 0.3, 0.3))
        np.testing.assert_allclose(dim[60, 80], [0.3, 0.3, 0.3], atol=_LUMA_TOL)

    def test_lut_identity_is_neutral(self) -> None:
        """An identity LUT leaves colours unchanged (texel-centre sampling is right)."""
        self._only("lut")
        img = self._run((0.1, 0.5, 0.9))
        np.testing.assert_allclose(img[30, 30], [0.1, 0.5, 0.9], atol=_LUMA_TOL)

    def test_crt_stub_is_passthrough(self) -> None:
        """The CRT stub changes nothing even when enabled."""
        self._only("crt")
        img = self._run((0.25, 0.5, 0.75))
        np.testing.assert_allclose(img[5, 5], [0.25, 0.5, 0.75], atol=_LUMA_TOL)

    def test_timed_callback_receives_enabled_passes(self) -> None:
        """The timing hook is called once per enabled pass, in order; idle distortion is skipped."""
        from contextlib import nullcontext
        from src.rendering.gpu.feel import DistortionParams
        from src.rendering.gpu.post_stack import PostStack
        seen: list[str] = []
        post = PostStack(self.ctx, _SIZE, identity_lut(C.LUT_SIZE),
                         timed=lambda key: seen.append(key) or nullcontext())
        for name in C.POST_PASS_ORDER:
            post.enabled[name] = name != "lut"
        post.begin_scene()
        post.render(self.out)  # no distortion params set → distortion pass skipped
        self.assertEqual(seen, [n for n in C.POST_PASS_ORDER if n not in ("lut", "distortion")])
        seen.clear()
        post.set_distortion(DistortionParams(aberration=1.0))
        post.render(self.out)
        post.release()
        self.assertEqual(seen, [n for n in C.POST_PASS_ORDER if n != "lut"])

    def test_resize(self) -> None:
        """resize() reallocates the scene buffer; rendering still works afterwards."""
        self.post.resize((80, 60))
        self.assertEqual(self.post.size, (80, 60))
        self.post.begin_scene()
        self.post.render(self.out)  # must not raise


class TestShaderWatchCompilesAll(unittest.TestCase):
    """Every shader in shaders/ compiles and links with its runtime vertex shader."""

    def test_all_shaders_compile(self) -> None:
        """tools/shader_watch.compile_all() reports no errors."""
        ctx = _ctx_or_none()
        if ctx is None:
            self.skipTest("No GPU available")
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "shader_watch.py")
        spec = importlib.util.spec_from_file_location("shader_watch", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            self.assertEqual(module.compile_all(ctx), [])
        finally:
            ctx.release()
