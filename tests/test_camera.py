"""Unit tests for the Camera system.

Run: python test_game.py
Tests run headless — no game window is opened.
"""
import unittest

import tests.conftest  # noqa: F401
import constants
from src.rendering.camera import Camera


class TestCameraInit(unittest.TestCase):
    """Camera initialisation defaults."""

    def test_starts_at_origin(self):
        cam = Camera(800, 600)
        self.assertEqual(cam.x, 0.0)
        self.assertEqual(cam.y, 0.0)

    def test_zoom_default(self):
        cam = Camera(800, 600)
        self.assertEqual(cam.zoom, 1.0)

    def test_screen_dimensions(self):
        cam = Camera(800, 600)
        self.assertEqual(cam.screen_w, 800)
        self.assertEqual(cam.screen_h, 600)


class TestSmoothFollow(unittest.TestCase):
    """Smooth lerp follow behaviour."""

    def test_follows_target(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 0.0, 0.0
        # Target far from camera — should move toward it
        for _ in range(300):
            cam.update(500.0, 300.0, 1 / 60)
        # Dead zone means camera stops within DEAD_ZONE distance of target
        self.assertAlmostEqual(cam.x, 500.0, delta=constants.CAMERA_DEAD_ZONE_X + 1)
        self.assertAlmostEqual(cam.y, 300.0, delta=constants.CAMERA_DEAD_ZONE_Y + 1)

    def test_converges_over_time(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 0.0, 0.0
        d1 = abs(cam.x - 400)
        cam.update(400, 0, 1 / 60)
        d2 = abs(cam.x - 400)
        self.assertLess(d2, d1)

    def test_does_not_overshoot(self):
        cam = Camera(800, 600)
        cam.x = 0.0
        cam.update(100, 0, 1 / 60)
        self.assertGreaterEqual(cam.x, 0.0)
        self.assertLessEqual(cam.x, 100.0)


class TestDeadZone(unittest.TestCase):
    """Dead zone suppresses camera movement for small target offsets."""

    def test_no_movement_inside_dead_zone(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 100.0, 100.0
        # Target within dead zone
        small_dx = constants.CAMERA_DEAD_ZONE_X * 0.5
        small_dy = constants.CAMERA_DEAD_ZONE_Y * 0.5
        cam.update(100 + small_dx, 100 + small_dy, 1 / 60)
        self.assertEqual(cam.x, 100.0)
        self.assertEqual(cam.y, 100.0)

    def test_movement_outside_dead_zone(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 100.0, 100.0
        big_dx = constants.CAMERA_DEAD_ZONE_X * 3
        cam.update(100 + big_dx, 100, 1 / 60)
        self.assertGreater(cam.x, 100.0)


class TestBounds(unittest.TestCase):
    """Camera bounds clamping."""

    def test_clamps_to_left_edge(self):
        cam = Camera(800, 600)
        cam.set_bounds(1200, 900)
        cam.x, cam.y = 0.0, 450.0
        cam.update(0, 450, 1 / 60)
        # Camera can't go below half-screen from left edge
        self.assertGreaterEqual(cam.x, 400.0)

    def test_clamps_to_right_edge(self):
        cam = Camera(800, 600)
        cam.set_bounds(1200, 900)
        cam.x, cam.y = 1200.0, 450.0
        cam.update(1200, 450, 1 / 60)
        self.assertLessEqual(cam.x, 800.0)

    def test_clamps_to_top_edge(self):
        cam = Camera(800, 600)
        cam.set_bounds(1200, 900)
        cam.x, cam.y = 600.0, 0.0
        cam.update(600, 0, 1 / 60)
        self.assertGreaterEqual(cam.y, 300.0)

    def test_clamps_to_bottom_edge(self):
        cam = Camera(800, 600)
        cam.set_bounds(1200, 900)
        cam.x, cam.y = 600.0, 900.0
        cam.update(600, 900, 1 / 60)
        self.assertLessEqual(cam.y, 600.0)

    def test_no_bounds_allows_any_position(self):
        cam = Camera(800, 600)
        cam.x, cam.y = -9999.0, -9999.0
        cam.update(-9999, -9999, 1 / 60)
        # Without bounds set, should stay near target
        self.assertLess(cam.x, 0)


class TestScreenShake(unittest.TestCase):
    """Screen shake behaviour."""

    def test_shake_produces_offset(self):
        cam = Camera(800, 600)
        cam.shake(10.0, 0.5)
        cam.update(0, 0, 1 / 60)
        # Offset should be non-zero (very unlikely to be exactly 0)
        has_offset = (cam._shake_offset_x != 0 or cam._shake_offset_y != 0)
        self.assertTrue(has_offset)

    def test_shake_decays_to_zero(self):
        cam = Camera(800, 600)
        cam.shake(10.0, 0.1)
        # Run for 1 second — well past duration
        for _ in range(60):
            cam.update(0, 0, 1 / 60)
        self.assertAlmostEqual(cam._shake_offset_x, 0.0)
        self.assertAlmostEqual(cam._shake_offset_y, 0.0)

    def test_shakes_stack(self):
        cam = Camera(800, 600)
        cam.shake(10.0, 1.0)
        cam.shake(10.0, 1.0)
        # Two active shakes
        self.assertEqual(len(cam._shakes), 2)

    def test_shake_disabled_produces_no_shakes(self):
        original = constants.SCREEN_SHAKE_ENABLED
        try:
            constants.SCREEN_SHAKE_ENABLED = False
            cam = Camera(800, 600)
            cam.shake(10.0, 0.5)
            self.assertEqual(len(cam._shakes), 0)
        finally:
            constants.SCREEN_SHAKE_ENABLED = original


class TestZoom(unittest.TestCase):
    """Zoom transform behaviour."""

    def test_default_zoom_is_one(self):
        cam = Camera(800, 600)
        self.assertEqual(cam.zoom, 1.0)

    def test_zoom_lerps_toward_target(self):
        cam = Camera(800, 600)
        cam.zoom = 2.0
        cam.update(0, 0, 1 / 60)
        self.assertGreater(cam.zoom, 1.0)
        self.assertLess(cam.zoom, 2.0)

    def test_zoom_reaches_target(self):
        cam = Camera(800, 600)
        cam.zoom = 2.0
        for _ in range(300):
            cam.update(0, 0, 1 / 60)
        self.assertAlmostEqual(cam.zoom, 2.0, delta=0.01)

    def test_world_to_screen_at_zoom_1(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 400.0, 300.0
        sx, sy = cam.world_to_screen(400, 300)
        self.assertAlmostEqual(sx, 400.0, delta=1.0)
        self.assertAlmostEqual(sy, 300.0, delta=1.0)

    def test_world_to_screen_at_zoom_2(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 400.0, 300.0
        cam._zoom = 2.0  # set directly for test precision
        sx, sy = cam.world_to_screen(400, 300)
        # At camera centre, zoom shouldn't shift position
        self.assertAlmostEqual(sx, 400.0, delta=1.0)
        self.assertAlmostEqual(sy, 300.0, delta=1.0)

    def test_world_to_screen_offset_scales_with_zoom(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 400.0, 300.0
        cam._zoom = 2.0
        sx, sy = cam.world_to_screen(450, 300)
        # 50px offset * zoom 2 = 100px on screen from centre
        self.assertAlmostEqual(sx, 500.0, delta=1.0)

    def test_zoom_minimum_clamped(self):
        cam = Camera(800, 600)
        cam.zoom = 0.01
        self.assertEqual(cam._target_zoom, 0.1)

    def test_world_rect_to_screen(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 400.0, 300.0
        cam._zoom = 2.0
        sx, sy, sw, sh = cam.world_rect_to_screen(400, 300, 50, 30)
        self.assertAlmostEqual(sw, 100.0)
        self.assertAlmostEqual(sh, 60.0)


class TestGravityRotationRecentre(unittest.TestCase):
    """Gravity rotation re-centre behaviour."""

    def test_recentre_timer_starts(self):
        cam = Camera(800, 600)
        cam.on_gravity_rotate()
        self.assertGreater(cam._recentre_timer, 0)

    def test_recentre_timer_counts_down(self):
        cam = Camera(800, 600)
        cam.on_gravity_rotate()
        initial = cam._recentre_timer
        cam.update(0, 0, 0.1)
        self.assertLess(cam._recentre_timer, initial)

    def test_recentre_timer_reaches_zero(self):
        cam = Camera(800, 600)
        cam.on_gravity_rotate()
        for _ in range(60):
            cam.update(0, 0, 1 / 60)
        self.assertEqual(cam._recentre_timer, 0.0)

    def test_recentre_uses_boosted_speed(self):
        """Camera converges faster during re-centre than normal."""
        cam_normal = Camera(800, 600)
        cam_normal.x = 0.0
        cam_normal.update(200, 0, 1 / 60)
        normal_dist = abs(cam_normal.x - 200)

        cam_boost = Camera(800, 600)
        cam_boost.x = 0.0
        cam_boost.on_gravity_rotate()
        cam_boost.update(200, 0, 1 / 60)
        boost_dist = abs(cam_boost.x - 200)

        # Boosted camera should be closer to target
        self.assertLess(boost_dist, normal_dist)

    def test_recentre_reaches_position_within_duration(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 0.0, 0.0
        cam.on_gravity_rotate()
        # Simulate for recentre duration
        for _ in range(120):
            cam.update(300, 200, 1 / 60)
        self.assertAlmostEqual(cam.x, 300, delta=30)
        self.assertAlmostEqual(cam.y, 200, delta=30)


class TestOffset(unittest.TestCase):
    """Camera offset property for simple rendering."""

    def test_offset_centres_camera(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 400.0, 300.0
        ox, oy = cam.offset
        self.assertAlmostEqual(ox, 0.0, delta=1.0)
        self.assertAlmostEqual(oy, 0.0, delta=1.0)

    def test_offset_shifts_with_camera(self):
        cam = Camera(800, 600)
        cam.x, cam.y = 500.0, 400.0
        ox, oy = cam.offset
        self.assertAlmostEqual(ox, -100.0, delta=1.0)
        self.assertAlmostEqual(oy, -100.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
