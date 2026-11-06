"""Tests for the pooled particle VFX system."""
from __future__ import annotations

import unittest

import tests.conftest  # noqa: F401
import constants as C


class TestParticlePool(unittest.TestCase):
    """Tests for the pooled particle VFX system."""

    def _make_pool(self, size: int = 200) -> object:
        from src.rendering.vfx import ParticlePool
        return ParticlePool(size)

    def test_pool_pre_allocates_capacity(self) -> None:
        pool = self._make_pool(50)
        self.assertEqual(len(pool._pool), 50)

    def test_emit_rotation_burst_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_ROTATION_BURST_COUNT)

    def test_emit_hit_spark_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_hit_spark(0.0, 0.0)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_HIT_SPARK_COUNT)

    def test_emit_landing_dust_activates_correct_count(self) -> None:
        pool = self._make_pool(200)
        pool.emit_landing_dust(0.0, 0.0, 64.0, 96.0, (0, 1))
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, C.VFX_LANDING_DUST_COUNT)

    def test_update_decrements_lifetime(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        first = next(p for p in pool._pool if p.active)
        before = first.lifetime
        pool.update(0.1)
        self.assertAlmostEqual(first.lifetime, before - 0.1, places=5)

    def test_update_deactivates_expired_particles(self) -> None:
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        for _ in range(100):
            pool.update(0.1)
        active = sum(1 for p in pool._pool if p.active)
        self.assertEqual(active, 0)

    def test_pool_recycles_when_full(self) -> None:
        pool = self._make_pool(5)
        for _ in range(10):
            pool.emit_rotation_burst(0.0, 0.0)
        self.assertEqual(len(pool._pool), 5)

    def test_landing_dust_moves_against_down_gravity(self) -> None:
        """Dust from a down-gravity landing should on average move upward."""
        pool = self._make_pool(200)
        pool.emit_landing_dust(400.0, 400.0, 64.0, 96.0, (0, 1))
        active = [p for p in pool._pool if p.active]
        avg_vy = sum(p.vy for p in active) / len(active)
        self.assertLess(avg_vy, 0.0)

    def test_landing_dust_moves_against_right_gravity(self) -> None:
        """Dust from a right-gravity landing should on average move leftward."""
        pool = self._make_pool(200)
        pool.emit_landing_dust(400.0, 400.0, 96.0, 64.0, (1, 0))
        active = [p for p in pool._pool if p.active]
        avg_vx = sum(p.vx for p in active) / len(active)
        self.assertLess(avg_vx, 0.0)

    def test_rotation_burst_particles_have_varied_directions(self) -> None:
        """Burst particles should spread in multiple directions."""
        pool = self._make_pool(200)
        pool.emit_rotation_burst(0.0, 0.0)
        active = [p for p in pool._pool if p.active]
        vx_signs = {1 if p.vx >= 0 else -1 for p in active}
        vy_signs = {1 if p.vy >= 0 else -1 for p in active}
        self.assertEqual(len(vx_signs), 2)
        self.assertEqual(len(vy_signs), 2)


if __name__ == "__main__":
    unittest.main()
