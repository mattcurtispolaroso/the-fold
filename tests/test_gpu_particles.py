"""Tests for TA-7: frame-rate-independent particles and the instanced GPU renderer.

Pool/physics tests are pure Python. GPU tests use a standalone ModernGL
context and skip when no GPU is available.
"""
from __future__ import annotations

import array
import math
import os
import random
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np

import constants as C
from src.rendering.vfx import INSTANCE_FLOATS, ParticlePool

_SIZE = (200, 160)


def _simulate(pool: ParticlePool, seconds: float, fps: int) -> None:
    """Advance a pool for `seconds` at a fixed frame rate."""
    dt = 1.0 / fps
    for _ in range(round(seconds * fps)):
        pool.update(dt)


def _single(vx: float, vy: float, ax: float = 0.0, ay: float = 0.0, drag: float = 0.0) -> ParticlePool:
    """A one-slot pool holding one hand-configured particle at the origin."""
    pool = ParticlePool(1)
    p = pool._acquire()
    p.px = p.py = 0.0
    p.vx, p.vy, p.ax, p.ay, p.drag = vx, vy, ax, ay, drag
    p.lifetime = p.max_lifetime = 10.0
    p.active = True
    return pool


class TestFrameRateIndependence(unittest.TestCase):
    """Particles move per second, not per frame (CLAUDE.md delta-time rule)."""

    def test_constant_velocity_same_at_30_and_120_fps(self) -> None:
        """100 px/s for 0.5 s lands at 50 px regardless of frame rate."""
        for fps in (30, 60, 120):
            pool = _single(100.0, 0.0)
            _simulate(pool, 0.5, fps)
            self.assertAlmostEqual(pool._pool[0].px, 50.0, places=6, msg=f"{fps} fps")

    def test_acceleration_exact_at_any_frame_rate(self) -> None:
        """Under gravity alone, position is ½·a·t² at 30, 60 and 120 fps."""
        for fps in (30, 60, 120):
            pool = _single(0.0, 0.0, ay=900.0)
            _simulate(pool, 0.3, fps)
            self.assertAlmostEqual(pool._pool[0].py, 0.5 * 900.0 * 0.3 ** 2, places=6,
                                   msg=f"{fps} fps")

    def test_drag_exact_at_any_frame_rate(self) -> None:
        """Drag alone decays speed as e^(−drag·t) whatever the frame rate."""
        for fps in (30, 120):
            pool = _single(200.0, 0.0, drag=3.0)
            _simulate(pool, 0.2, fps)
            self.assertAlmostEqual(pool._pool[0].vx, 200.0 * math.exp(-3.0 * 0.2), places=6)

    def test_drag_plus_gravity_close_across_frame_rates(self) -> None:
        """Combined drag and gravity (real spark settings) agree within 3% at 30 vs 120 fps."""
        spark = C.VFX_HIT_SPARK
        a = _single(300.0, 0.0, ay=spark["gravity"], drag=spark["drag"])
        b = _single(300.0, 0.0, ay=spark["gravity"], drag=spark["drag"])
        _simulate(a, 0.3, 30)
        _simulate(b, 0.3, 120)
        self.assertAlmostEqual(a._pool[0].px, b._pool[0].px, delta=0.03 * b._pool[0].px)
        self.assertAlmostEqual(a._pool[0].py, b._pool[0].py, delta=0.03 * b._pool[0].py)


class TestEffectShapes(unittest.TestCase):
    """Visual-upgrade behaviour from the TA-7 spec."""

    def setUp(self) -> None:
        """Deterministic randomness per test."""
        random.seed(1234)

    def test_rotation_burst_is_a_ring(self) -> None:
        """Burst particles stay in a tight radial band (a ring, not a blob)."""
        pool = ParticlePool(100)
        pool.emit_rotation_burst(0.0, 0.0)
        _simulate(pool, 0.15, 60)
        dists = [math.hypot(p.px, p.py) for p in pool._pool if p.active]
        mean = sum(dists) / len(dists)
        self.assertGreater(mean, 10.0)
        self.assertLess(max(dists) - min(dists), 0.25 * mean)

    def test_rotation_burst_is_amber_and_glows(self) -> None:
        """Burst colours are amber (red > blue) and additive."""
        pool = ParticlePool(100)
        pool.emit_rotation_burst(0.0, 0.0)
        for p in (p for p in pool._pool if p.active):
            self.assertGreater(p.r, p.b)
            self.assertEqual(p.glow, 1.0)

    def test_hit_sparks_fall_with_player_gravity(self) -> None:
        """With gravity RIGHT, sparks drift +x on average."""
        pool = ParticlePool(100)
        pool.emit_hit_spark(0.0, 0.0, (1, 0))
        _simulate(pool, 0.2, 60)
        live = [p for p in pool._pool if p.active]
        self.assertGreater(sum(p.vx for p in live) / len(live), 50.0)

    def test_hit_spark_is_red_orange(self) -> None:
        """Spark colours are red-orange: red dominant, little blue."""
        pool = ParticlePool(100)
        pool.emit_hit_spark(0.0, 0.0)
        for p in (p for p in pool._pool if p.active):
            self.assertEqual(p.r, 1.0)
            self.assertLess(p.b, 0.4)

    def test_dust_puffs_grow_and_burst_shrinks(self) -> None:
        """Dust gets bigger over its life; burst particles get smaller."""
        pool = ParticlePool(100)
        pool.emit_landing_dust(0.0, 0.0, 64, 96, (0, 1))
        dust = next(p for p in pool._pool if p.active)
        start = dust.size
        pool.update(0.1)
        self.assertGreater(dust.size, start)
        burst = ParticlePool(100)
        burst.emit_rotation_burst(0.0, 0.0)
        ring = next(p for p in burst._pool if p.active)
        start = ring.size
        burst.update(0.1)
        self.assertLess(ring.size, start)


class TestPoolAndInstances(unittest.TestCase):
    """Fixed-size pool and the GPU instance packing."""

    def test_pool_never_grows(self) -> None:
        """Emitting far more than capacity recycles slots; the pool size is constant."""
        pool = ParticlePool(C.VFX_POOL_SIZE)
        for _ in range(100):
            pool.emit_rotation_burst(0.0, 0.0)
            pool.emit_hit_spark(0.0, 0.0)
            pool.emit_landing_dust(0.0, 0.0, 64, 96, (0, 1))
        self.assertEqual(len(pool._pool), C.VFX_POOL_SIZE)
        self.assertEqual(pool.active_count(), C.VFX_POOL_SIZE)

    def test_pool_size_matches_entity_limit(self) -> None:
        """The pool is sized to the MAX_PARTICLES entity limit."""
        self.assertEqual(C.VFX_POOL_SIZE, C.MAX_PARTICLES)

    def test_write_instances_packs_active_only(self) -> None:
        """Only live particles are written, in screen space, with life as alpha."""
        pool = ParticlePool(10)
        pool.emit_hit_spark(100.0, 50.0)   # 14 > 10 → all 10 slots live
        pool._pool[3].active = False
        buf = array.array("f", [0.0] * (10 * INSTANCE_FLOATS))
        count = pool.write_instances(buf, (5.0, -5.0))
        self.assertEqual(count, 9)
        self.assertAlmostEqual(buf[0], 105.0, places=4)
        self.assertAlmostEqual(buf[1], 45.0, places=4)
        self.assertAlmostEqual(buf[6], 1.0, places=4)   # just born: full life


class TestParticleRendererGPU(unittest.TestCase):
    """Instanced draw via a standalone context (skipped without a GPU)."""

    def setUp(self) -> None:
        """Context, renderer at pool capacity, and a target framebuffer."""
        try:
            import moderngl
            self.ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        import moderngl
        from src.rendering.gpu.particles import ParticleRenderer
        self.ctx.enable(moderngl.BLEND)
        self.renderer = ParticleRenderer(self.ctx, _SIZE, C.VFX_POOL_SIZE)
        self.fbo = self.ctx.simple_framebuffer(_SIZE, components=4)
        self.fbo.use()
        self.fbo.clear(0.0, 0.0, 0.0, 0.0)

    def tearDown(self) -> None:
        """Release GPU resources."""
        if getattr(self, "ctx", None) is None:
            return
        self.fbo.release()
        self.renderer.release()
        self.ctx.release()

    def _pixels(self) -> np.ndarray:
        """RGBA pixels, row 0 = top."""
        w, h = _SIZE
        return np.frombuffer(self.fbo.read(components=4), dtype=np.uint8).reshape(h, w, 4)[::-1]

    def test_500_particles_one_draw_call(self) -> None:
        """A full pool of MAX_PARTICLES renders in exactly one instanced draw call."""
        pool = ParticlePool(C.VFX_POOL_SIZE)
        while pool.active_count() < C.VFX_POOL_SIZE:
            pool.emit_hit_spark(100.0, 80.0)
        self.assertEqual(self.renderer.draw(pool, (0.0, 0.0)), C.VFX_POOL_SIZE)
        self.assertEqual(self.renderer.draw_calls, 1)

    def test_empty_pool_issues_no_draw_call(self) -> None:
        """Nothing alive → no GL draw call at all."""
        self.renderer.draw(ParticlePool(C.VFX_POOL_SIZE), (0.0, 0.0))
        self.assertEqual(self.renderer.draw_calls, 0)

    def test_particle_lands_at_its_screen_position(self) -> None:
        """A dust particle is drawn at world position + camera offset."""
        pool = ParticlePool(1)
        p = pool._acquire()
        p.px, p.py = 60.0, 40.0
        p.size0 = p.size1 = 6.0
        p.r = p.g = p.b = 1.0
        p.glow = 0.0
        p.lifetime = p.max_lifetime = 1.0
        p.active = True
        self.renderer.draw(pool, (20.0, 10.0))
        px = self._pixels()
        self.assertGreater(int(px[50, 80, 3]), 200)   # centre at (80, 50): opaque
        self.assertEqual(int(px[10, 10, 3]), 0)        # elsewhere: untouched

    def test_glow_particles_are_additive(self) -> None:
        """Glow particles add colour without writing alpha (premultiplied additive)."""
        pool = ParticlePool(1)
        p = pool._acquire()
        p.px, p.py = 100.0, 80.0
        p.size0 = p.size1 = 6.0
        p.r, p.g, p.b = 1.0, 0.5, 0.0
        p.glow = 1.0
        p.lifetime = p.max_lifetime = 1.0
        p.active = True
        self.renderer.draw(pool, (0.0, 0.0))
        r, g, b, a = (int(v) for v in self._pixels()[80, 100])
        self.assertGreater(r, 150)   # hot core; sampled half a pixel off exact centre
        self.assertLess(b, 10)       # colour preserved (orange, no blue)
        self.assertEqual(a, 0)       # additive: alpha untouched

    def test_oversized_pool_rejected(self) -> None:
        """A pool bigger than the instance buffer fails loudly instead of overflowing."""
        with self.assertRaises(ValueError):
            self.renderer.draw(ParticlePool(C.VFX_POOL_SIZE + 1), (0.0, 0.0))


class TestNestedTimingSafe(unittest.TestCase):
    """ParallaxStack.timed() inside another timed() block must not raise a GL error."""

    def test_nested_timed_is_untimed_and_error_free(self) -> None:
        """Inner block runs untimed (counted in the outer key); GL reports no error."""
        try:
            import moderngl
            ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        from src.rendering.gpu.layer import ParallaxStack
        stack = ParallaxStack(ctx, _SIZE, {})
        stack.profiling = True
        stack.begin_frame()
        with stack.target("play"):          # opens the "play" query
            with stack.timed("particles"):  # nested: must not open a second query
                stack.layers["play"].fbo.clear(1.0, 0.0, 0.0, 1.0)
        self.assertEqual(ctx.error, "GL_NO_ERROR")
        self.assertIn("play", stack.layer_ms)
        self.assertNotIn("particles", stack.layer_ms)
        stack.release()
        ctx.release()
