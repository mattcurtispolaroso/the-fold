"""Tests for the TA-6 feel framework: hitstop, sprite flash, squash/stretch,
camera routing, and the reduced-effects (accessibility) intensity multiplier.

Everything except the final GPU class runs headless with no GL context,
which is how the software renderer and CI use Feel.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np

import constants as C
from src.rendering.camera import Camera
from src.rendering.gpu.feel import Feel
from src.rendering.gpu.feel_effects import Hitstop, squash_scale

_DT = 1.0 / 60.0
_SIZE = (200, 160)


class _RecordingCamera:
    """Minimal camera stand-in that records what Feel forwards to it."""

    def __init__(self) -> None:
        """Start with empty call logs."""
        self.shakes: list[tuple[float, float]] = []
        self.punches: list[tuple[float, float, float]] = []
        self.cinematics: int = 0

    def shake(self, intensity: float, duration: float) -> None:
        """Record a shake."""
        self.shakes.append((intensity, duration))

    def punch(self, dx: float, dy: float, duration: float) -> None:
        """Record a punch."""
        self.punches.append((dx, dy, duration))

    def start_rotation_cinematic(self) -> None:
        """Record a cinematic start."""
        self.cinematics += 1


class TestHitstop(unittest.TestCase):
    """feel.hitstop freezes the physics accumulator for exactly its duration."""

    def test_freezes_physics_time_for_duration(self) -> None:
        """0.06s hitstop at 60fps: physics_time is 0 for the frozen frames, then resumes."""
        feel = Feel()
        feel.hitstop(0.06)
        frozen = [feel.physics_time(_DT) for _ in range(3)]
        self.assertEqual(frozen, [0.0, 0.0, 0.0])
        resumed = feel.physics_time(_DT)
        self.assertAlmostEqual(resumed, 4 * _DT - 0.06, places=9)
        self.assertAlmostEqual(feel.physics_time(_DT), _DT)

    def test_accumulator_loses_exactly_the_hitstop(self) -> None:
        """Over a second, total simulated time = real time − hitstop (no drift, no double-count)."""
        feel = Feel()
        feel.hitstop(0.06)
        total = sum(feel.physics_time(_DT) for _ in range(60))
        self.assertAlmostEqual(total, 1.0 - 0.06, places=9)

    def test_overlapping_hitstops_take_longest(self) -> None:
        """Two hits in one frame freeze for the longer one, not the sum."""
        h = Hitstop()
        h.trigger(0.04)
        h.trigger(0.06)
        self.assertAlmostEqual(h.remaining, 0.06)

    def test_hitstop_clamped(self) -> None:
        """A huge hitstop is clamped to HITSTOP_MAX; negative is ignored."""
        h = Hitstop()
        h.trigger(5.0)
        self.assertEqual(h.remaining, C.HITSTOP_MAX)
        h2 = Hitstop()
        h2.trigger(-1.0)
        self.assertFalse(h2.active)

    def test_no_hitstop_passes_time_through(self) -> None:
        """Without a hitstop, physics_time is identity."""
        self.assertEqual(Feel().physics_time(0.0123), 0.0123)


class TestSpriteFlashAndSquash(unittest.TestCase):
    """Flash fades out; squash springs back and roughly preserves area."""

    def test_flash_fades_to_zero(self) -> None:
        """A flash starts at SPRITE_FLASH_MAX and is gone after its duration."""
        feel = Feel()
        feel.flash((1.0, 0.0, 0.0), 0.1)
        r, g, b, amount = feel.sprite_flash()
        self.assertEqual((r, g, b), (1.0, 0.0, 0.0))
        self.assertAlmostEqual(amount, C.SPRITE_FLASH_MAX)
        feel.update(0.11)
        self.assertEqual(feel.sprite_flash()[3], 0.0)

    def test_dilation_start_flashes_amber(self) -> None:
        """Time Dilation switching on gives the amber exosuit flash plus a ripple."""
        feel = Feel()
        feel.track_dilation(True, 0.0, 0.0)
        self.assertEqual(feel.sprite_flash()[:3], C.DILATION_FLASH_COLOR)
        self.assertEqual(len(feel.ripples), 1)

    def test_squash_shortens_along_gravity_and_springs_back(self) -> None:
        """Landing squash: shorter along gravity, wider across; back to 1 afterwards."""
        feel = Feel()
        feel.squash(C.LAND_SQUASH)
        along, across = feel.sprite_scale()
        self.assertLess(along, 1.0)
        self.assertGreater(across, 1.0)
        feel.update(C.SQUASH_DURATION)
        self.assertEqual(feel.sprite_scale(), (1.0, 1.0))

    def test_stretch_lengthens_along_gravity(self) -> None:
        """Jump stretch: longer along gravity, narrower across."""
        feel = Feel()
        feel.squash(C.JUMP_STRETCH)
        along, across = feel.sprite_scale()
        self.assertGreater(along, 1.0)
        self.assertLess(across, 1.0)

    def test_squash_partially_compensates_area(self) -> None:
        """Across moves opposite to along, compensating half-way (area = sqrt(along))."""
        for amount in (-C.SQUASH_MAX, -0.1, 0.1, C.SQUASH_MAX):
            along, across = squash_scale(amount)
            self.assertEqual(along < 1.0, across > 1.0)
            self.assertAlmostEqual(along * across, along ** 0.5)

    def test_squash_amount_clamped(self) -> None:
        """Extreme squash requests are clamped to SQUASH_MAX."""
        feel = Feel()
        feel.squash(10.0)
        along, _ = feel.sprite_scale()
        self.assertAlmostEqual(along, 1.0 - C.SQUASH_MAX)


class TestIntensityMultiplier(unittest.TestCase):
    """Reduced-effects mode visibly reduces every effect."""

    def setUp(self) -> None:
        """A normal and a reduced Feel, each with a recording camera."""
        self.cam_normal, self.cam_reduced = _RecordingCamera(), _RecordingCamera()
        self.normal = Feel(self.cam_normal)
        self.reduced = Feel(self.cam_reduced)
        self.reduced.reduced_effects = True

    def test_intensity_values(self) -> None:
        """Intensity is DEFAULT normally and REDUCED in accessibility mode."""
        self.assertEqual(self.normal.intensity, C.FEEL_INTENSITY_DEFAULT)
        self.assertEqual(self.reduced.intensity, C.FEEL_INTENSITY_REDUCED)
        self.assertLess(C.FEEL_INTENSITY_REDUCED, C.FEEL_INTENSITY_DEFAULT)

    def test_toggle(self) -> None:
        """toggle_reduced_effects flips the mode and returns it."""
        self.assertTrue(self.normal.toggle_reduced_effects())
        self.assertEqual(self.normal.intensity, C.FEEL_INTENSITY_REDUCED)

    def test_shake_and_punch_scaled(self) -> None:
        """Camera shake and punch are multiplied by intensity; durations unchanged."""
        for feel in (self.normal, self.reduced):
            feel.shake(10.0, 0.2)
            feel.punch(10.0, -10.0, 0.1)
        k = C.FEEL_INTENSITY_REDUCED
        self.assertEqual(self.cam_normal.shakes, [(10.0, 0.2)])
        self.assertEqual(self.cam_reduced.shakes, [(10.0 * k, 0.2)])
        self.assertEqual(self.cam_reduced.punches, [(10.0 * k, -10.0 * k, 0.1)])

    def test_rotation_zoom_skipped_when_reduced(self) -> None:
        """The rotation cinematic zoom runs normally and is skipped in reduced mode."""
        self.normal.rotation_cinematic()
        self.reduced.rotation_cinematic()
        self.assertEqual((self.cam_normal.cinematics, self.cam_reduced.cinematics), (1, 0))

    def test_hitstop_scaled(self) -> None:
        """Reduced mode shortens hitstop by the intensity factor."""
        self.reduced.hitstop(0.06)
        self.assertAlmostEqual(self.reduced._hitstop.remaining, 0.06 * C.FEEL_INTENSITY_REDUCED)

    def test_flash_and_squash_scaled(self) -> None:
        """Sprite flash amount and squash deformation shrink in reduced mode."""
        for feel in (self.normal, self.reduced):
            feel.flash((1, 1, 1), 0.1)
            feel.squash(0.3)
        self.assertAlmostEqual(self.reduced.sprite_flash()[3],
                               self.normal.sprite_flash()[3] * C.FEEL_INTENSITY_REDUCED)
        self.assertGreater(self.reduced.sprite_scale()[0], self.normal.sprite_scale()[0])

    def test_distortion_scaled(self) -> None:
        """Ripple amplitude, bend and aberration all scale by intensity."""
        for feel in (self.normal, self.reduced):
            feel.distortion(50.0, 50.0)
            feel.gravity_bend((1, 0))
            feel.update(C.BEND_DURATION / 2)
        n = self.normal.distortion_params((0, 0), _SIZE)
        r = self.reduced.distortion_params((0, 0), _SIZE)
        k = C.FEEL_INTENSITY_REDUCED
        self.assertAlmostEqual(r.ripples[0][3], n.ripples[0][3] * k)
        self.assertAlmostEqual(r.bend[2], n.bend[2] * k)
        self.assertAlmostEqual(r.aberration, n.aberration * k)

    def test_screen_flash_scaled(self) -> None:
        """Full-screen rotation/impact flash multiplier follows intensity."""
        self.assertEqual(self.reduced.screen_flash_scale(), C.FEEL_INTENSITY_REDUCED)


class TestHeadless(unittest.TestCase):
    """The whole feel API works with no GPU and with the software renderer's Camera."""

    def test_no_camera_is_safe(self) -> None:
        """Every call is a no-op-safe without a camera (headless/CI)."""
        feel = Feel()
        feel.shake(5, 0.1)
        feel.punch(1, 1, 0.1)
        feel.rotation_cinematic()
        feel.hitstop(0.05)
        feel.flash((1, 1, 1), 0.1)
        feel.squash(0.2)
        feel.update(_DT)
        self.assertEqual(feel.physics_time(_DT), 0.0)  # still inside the hitstop

    def test_real_camera_receives_shake(self) -> None:
        """With the real (software-path) Camera, feel.shake produces a camera offset."""
        cam = Camera(800, 600)
        feel = Feel(cam)
        feel.shake(20.0, 0.5)
        moved = False
        for _ in range(10):
            cam.update(cam.x, cam.y, _DT)
            if cam._shake_offset_x != 0.0 or cam._shake_offset_y != 0.0:
                moved = True
        self.assertTrue(moved)

    def test_reset_clears_hitstop_flash_squash(self) -> None:
        """reset() (on death/level change) unfreezes physics and clears sprite effects."""
        feel = Feel()
        feel.hitstop(0.1)
        feel.flash((1, 1, 1), 0.1)
        feel.squash(0.3)
        feel.reset()
        self.assertEqual(feel.physics_time(_DT), _DT)
        self.assertEqual(feel.sprite_flash()[3], 0.0)
        self.assertEqual(feel.sprite_scale(), (1.0, 1.0))


class TestSpriteFlashGPU(unittest.TestCase):
    """The sprite shader flashes a silhouette (skipped without a GPU)."""

    def test_flash_whitens_opaque_pixels_only(self) -> None:
        """A red sprite at flash 1.0 renders white where opaque, transparent elsewhere."""
        try:
            import moderngl
            ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        import pygame
        from src.rendering.gpu.atlas import RuntimeAtlas
        from src.rendering.gpu.sprite_batch import SpriteBatch
        pygame.init()
        sprite = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.rect(sprite, (255, 0, 0, 255), (0, 0, 5, 10))  # left half opaque red
        atlas = RuntimeAtlas(ctx, {"s": sprite})
        batch = SpriteBatch(ctx, atlas, (40, 40))
        fbo = ctx.simple_framebuffer((40, 40), components=4)
        fbo.use()
        fbo.clear(0, 0, 0, 0)
        batch.begin()
        batch.draw_sprite("s", 20, 20, 20, 20, flash=(1.0, 1.0, 1.0, 1.0))
        batch.flush()
        px = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape(40, 40, 4)[::-1]
        self.assertEqual(tuple(px[20, 13]), (255, 255, 255, 255))  # opaque half → white
        self.assertEqual(int(px[20, 27, 3]), 0)                    # transparent half stays clear
        for res in (fbo, batch, atlas, ctx):
            res.release()
