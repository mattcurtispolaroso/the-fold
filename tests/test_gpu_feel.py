"""Tests for TA-5: Feel (Fold ripples, gravity bend) and the distortion pass.

Feel is pure Python and always tested. Distortion rendering tests use a
standalone ModernGL context and skip without a GPU.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np

import constants as C
from src.rendering.gpu.feel import (
    DistortionParams, Feel, bend_envelope, ripple_envelope,
)

_SIZE = (200, 160)
_DT = 1.0 / 60.0


class TestFeelQueue(unittest.TestCase):
    """Queueing, clamping and expiry of feel effects."""

    def setUp(self) -> None:
        """Fresh Feel per test."""
        self.feel = Feel()

    def test_zero_duration_is_noop(self) -> None:
        """feel.distortion(..., dur=0) queues nothing (spec)."""
        self.feel.distortion(10, 10, dur=0.0)
        self.feel.distortion(10, 10, dur=-1.0)
        self.assertEqual(self.feel.ripples, [])

    def test_zero_strength_is_noop(self) -> None:
        """A ripple with no strength would be invisible, so it is not queued."""
        self.feel.distortion(10, 10, strength=0.0)
        self.assertEqual(self.feel.ripples, [])

    def test_strength_clamped(self) -> None:
        """Strength above DISTORTION_STRENGTH_MAX is clamped."""
        self.feel.distortion(0, 0, strength=999.0)
        self.assertEqual(self.feel.ripples[0].strength, C.DISTORTION_STRENGTH_MAX)

    def test_ripple_cap_recycles_oldest(self) -> None:
        """Beyond DISTORTION_MAX_RIPPLES the oldest ripple is dropped."""
        for i in range(C.DISTORTION_MAX_RIPPLES + 2):
            self.feel.distortion(float(i), 0.0)
        self.assertEqual(len(self.feel.ripples), C.DISTORTION_MAX_RIPPLES)
        self.assertEqual(self.feel.ripples[0].x, 2.0)

    def test_ripple_expires(self) -> None:
        """A ripple is removed once its duration has elapsed."""
        self.feel.distortion(0, 0, dur=0.1)
        self.feel.update(0.05)
        self.assertEqual(len(self.feel.ripples), 1)
        self.feel.update(0.06)
        self.assertEqual(self.feel.ripples, [])

    def test_bend_expires(self) -> None:
        """The bend ends after BEND_DURATION."""
        self.feel.gravity_bend((1, 0))
        self.feel.update(C.BEND_DURATION + _DT)
        self.assertIsNone(self.feel.bend_age)
        self.assertFalse(self.feel.distortion_params((0, 0), _SIZE).active)

    def test_dilation_ripples_once_per_activation(self) -> None:
        """track_dilation fires on the rising edge only (covers E and Kerr Ring)."""
        for active in (False, True, True, True, False, True):
            self.feel.track_dilation(active, 5.0, 6.0)
        self.assertEqual(len(self.feel.ripples), 2)
        self.assertEqual((self.feel.ripples[0].x, self.feel.ripples[0].y), (5.0, 6.0))

    def test_reset_clears_everything(self) -> None:
        """reset() drops ripples and any bend in progress."""
        self.feel.distortion(0, 0)
        self.feel.gravity_bend((0, -1))
        self.feel.reset()
        self.assertFalse(self.feel.distortion_params((0, 0), _SIZE).active)


class TestDistortionParams(unittest.TestCase):
    """Envelope shapes and conversion to shader parameters."""

    def test_idle_is_inactive(self) -> None:
        """No effects → inactive params (the post pass is skipped)."""
        self.assertFalse(Feel().distortion_params((0, 0), _SIZE).active)

    def test_ripple_envelope(self) -> None:
        """Ring starts at radius 0 / full amplitude and ends at full radius / zero amplitude."""
        self.assertEqual(ripple_envelope(0.0), (0.0, 1.0))
        self.assertEqual(ripple_envelope(1.0), (1.0, 0.0))

    def test_bend_envelope_arches(self) -> None:
        """Bend is zero at both ends and peaks in the middle."""
        self.assertAlmostEqual(bend_envelope(0.0), 0.0)
        self.assertAlmostEqual(bend_envelope(0.5), 1.0)
        self.assertAlmostEqual(bend_envelope(1.0), 0.0, places=6)

    def test_ripple_converted_to_gl_pixels(self) -> None:
        """World position + camera offset → screen, then Y flipped for GL."""
        feel = Feel()
        feel.distortion(300.0, 250.0)
        cx, cy, radius, amp = feel.distortion_params((-200.0, -100.0), _SIZE).ripples[0]
        self.assertEqual((cx, cy), (100.0, _SIZE[1] - 150.0))
        self.assertEqual(radius, 0.0)
        self.assertAlmostEqual(amp, C.RIPPLE_AMPLITUDE_PX)

    def test_amplitude_clamped_to_max_offset(self) -> None:
        """Even at max strength a ripple never exceeds DISTORTION_MAX_OFFSET_PX."""
        feel = Feel()
        feel.distortion(0, 0, strength=C.DISTORTION_STRENGTH_MAX)
        amp = feel.distortion_params((0, 0), _SIZE).ripples[0][3]
        self.assertLessEqual(amp, C.DISTORTION_MAX_OFFSET_PX)

    def test_bend_direction_flipped_for_gl(self) -> None:
        """Gravity DOWN on screen (0, 1) bends toward GL -Y."""
        feel = Feel()
        feel.gravity_bend((0, 1))
        feel.update(C.BEND_DURATION / 2)
        dx, dy, amount = feel.distortion_params((0, 0), _SIZE).bend
        self.assertEqual((dx, dy), (0.0, -1.0))
        self.assertAlmostEqual(amount, C.BEND_AMPLITUDE_PX)

    def test_aberration_tracks_strongest_effect(self) -> None:
        """Aberration peaks with the effect and is zero when idle."""
        feel = Feel()
        feel.gravity_bend((1, 0))
        feel.update(C.BEND_DURATION / 2)
        self.assertAlmostEqual(feel.distortion_params((0, 0), _SIZE).aberration,
                               C.ABERRATION_MAX_PX)

    def test_ripple_follows_camera_zoom(self) -> None:
        """Under zoom the ripple centre scales about the screen centre and its radius scales."""
        feel = Feel()
        feel.distortion(150.0, 80.0)        # 50px right of the 200×160 centre, on the centre row
        feel.update(C.RIPPLE_DURATION / 2)  # non-zero radius
        plain = feel.distortion_params((0, 0), _SIZE)
        zoomed = feel.distortion_params((0, 0), _SIZE, zoom=2.0)
        self.assertEqual(zoomed.ripples[0][0], 200.0)                # 100 + 50×2
        self.assertEqual(zoomed.ripples[0][1], plain.ripples[0][1])  # centre row unchanged
        self.assertAlmostEqual(zoomed.ripples[0][2], plain.ripples[0][2] * 2.0)

    def test_zoom_one_matches_unzoomed(self) -> None:
        """zoom=1.0 (the default) gives exactly the pre-zoom result."""
        feel = Feel()
        feel.distortion(37.0, 91.0)
        self.assertEqual(feel.distortion_params((-5, 3), _SIZE, zoom=1.0).ripples,
                         feel.distortion_params((-5, 3), _SIZE).ripples)


class TestDistortionPassGPU(unittest.TestCase):
    """Rendered distortion via a standalone context (skipped without a GPU)."""

    def setUp(self) -> None:
        """Post stack with only distortion enabled and a striped test scene."""
        try:
            import moderngl
            self.ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        from src.rendering.gpu.lut import identity_lut
        from src.rendering.gpu.post_stack import PostStack
        self.post = PostStack(self.ctx, _SIZE, identity_lut(C.LUT_SIZE))
        for name in C.POST_PASS_ORDER:
            self.post.enabled[name] = name == "distortion"
        self.out = self.ctx.simple_framebuffer(_SIZE, components=4)

    def tearDown(self) -> None:
        """Release GPU resources."""
        if getattr(self, "ctx", None) is None:
            return
        self.out.release()
        self.post.release()
        self.ctx.release()

    def _render(self, params: DistortionParams) -> np.ndarray:
        """Render a scene with a white horizontal band (GL rows 70-89); return RGB rows bottom-up."""
        scene = self.post.begin_scene()
        scene.scissor = (0, 70, _SIZE[0], 20)
        scene.clear(1.0, 1.0, 1.0, 1.0)
        scene.scissor = None
        self.post.set_distortion(params)
        self.post.render(self.out)
        w, h = _SIZE
        return np.frombuffer(self.out.read(components=3), dtype=np.uint8).reshape(h, w, 3)

    def _band_rows(self, img: np.ndarray, col: int) -> tuple[int, int]:
        """Return (first, last) GL row of the white band in a column."""
        rows = np.where(img[:, col, 1] > 128)[0]
        return int(rows.min()), int(rows.max())

    def test_inactive_params_leave_scene_unchanged(self) -> None:
        """With no active effect the band stays exactly where it was drawn."""
        img = self._render(DistortionParams())
        self.assertEqual(self._band_rows(img, 100), (70, 89))

    def test_bend_bows_centre_not_edges(self) -> None:
        """A downward bend moves the band down at the centre column and not at the edges."""
        img = self._render(DistortionParams(bend=(0.0, -1.0, 10.0)))
        centre_low, _ = self._band_rows(img, _SIZE[0] // 2)
        edge_low, _ = self._band_rows(img, 0)
        self.assertLessEqual(centre_low, 61)  # ~10 px lower at the centre
        self.assertGreaterEqual(edge_low, 69)  # unmoved at the edge

    def test_ripple_displaces_only_near_ring(self) -> None:
        """A ring crossing the band pushes it outward there; far columns stay put."""
        ripple = (100.0, 40.0, 40.0, 8.0)  # centre below the band, ring reaches it at x=100
        img = self._render(DistortionParams(ripples=[ripple]))
        low_near, _ = self._band_rows(img, 100)
        self.assertGreater(low_near, 72)      # pushed up (away from centre)
        self.assertEqual(self._band_rows(img, 5), (70, 89))

    def test_aberration_splits_channels(self) -> None:
        """At the band edge near a screen corner red and blue disagree."""
        img = self._render(DistortionParams(aberration=4.0))
        col = 2  # far left, where the radial split is largest
        red_rows = np.where(img[:, col, 0] > 128)[0]
        blue_rows = np.where(img[:, col, 2] > 128)[0]
        self.assertNotEqual((red_rows.min(), red_rows.max()), (blue_rows.min(), blue_rows.max()))

    def test_offset_never_exceeds_cap(self) -> None:
        """A huge bend is clamped to DISTORTION_MAX_OFFSET_PX by the shader."""
        img = self._render(DistortionParams(bend=(0.0, -1.0, 500.0)))
        centre_low, _ = self._band_rows(img, _SIZE[0] // 2)
        self.assertGreaterEqual(centre_low, 70 - C.DISTORTION_MAX_OFFSET_PX - 1)
