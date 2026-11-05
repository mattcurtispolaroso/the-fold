"""Tests for the GPU atlas and sprite batch (TA-1).

All tests are headless — they use pygame software surfaces and verify math
rather than actual GL output. GPU-dependent tests are skipped if no context
is available.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")


class TestRuntimeAtlasUVs(unittest.TestCase):
    """Verify atlas UV math without a real GL context."""

    def _make_atlas_offline(self, frames: dict):
        """Build a RuntimeAtlas using a standalone context if available."""
        try:
            import moderngl
            ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        import pygame
        from src.rendering.gpu.atlas import RuntimeAtlas
        pygame.init()
        atlas = RuntimeAtlas(ctx, frames)
        ctx.release()
        return atlas

    def test_white_frame_always_present(self) -> None:
        """White frame must exist even with an empty frames dict."""
        atlas = self._make_atlas_offline({})
        uvs = atlas.get_uvs("__white__")
        self.assertEqual(len(uvs), 4)

    def test_uvs_are_normalized(self) -> None:
        """All UV values must be in [0, 1]."""
        import pygame
        pygame.init()
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        surf.fill((255, 0, 0, 255))
        atlas = self._make_atlas_offline({"test": surf})
        for uv in atlas.get_uvs("test"):
            self.assertGreaterEqual(uv, 0.0)
            self.assertLessEqual(uv, 1.0)

    def test_v_top_greater_than_v_bot(self) -> None:
        """v_top must be greater than v_bot (GL V increases toward top of frame)."""
        import pygame
        pygame.init()
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        atlas = self._make_atlas_offline({"frame": surf})
        u_l, v_top, u_r, v_bot = atlas.get_uvs("frame")
        self.assertGreater(v_top, v_bot)

    def test_u_right_greater_than_u_left(self) -> None:
        """u_right must be greater than u_left for a non-zero-width frame."""
        import pygame
        pygame.init()
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        atlas = self._make_atlas_offline({"f": surf})
        u_l, v_top, u_r, v_bot = atlas.get_uvs("f")
        self.assertGreater(u_r, u_l)

    def test_missing_frame_falls_back_to_white(self) -> None:
        """get_uvs for a missing frame must not raise and return valid UVs."""
        atlas = self._make_atlas_offline({})
        uvs = atlas.get_uvs("does_not_exist")
        self.assertEqual(len(uvs), 4)


class TestSpriteBatchRotation(unittest.TestCase):
    """Verify the rotation math in _rotated_corners (no GPU needed)."""

    def _corners(self, cx, cy, hw, hh, angle):
        from src.rendering.gpu.sprite_batch import _rotated_corners
        return _rotated_corners(cx, cy, hw, hh, angle)

    def test_zero_rotation_identity(self) -> None:
        """0° rotation must return unrotated corners."""
        import math
        corners = self._corners(100, 100, 30, 50, 0.0)
        # TL at (70, 50), TR at (130, 50), BR at (130, 150), BL at (70, 150)
        self.assertAlmostEqual(corners[0][0], 70, places=5)   # TL x
        self.assertAlmostEqual(corners[0][1], 50, places=5)   # TL y
        self.assertAlmostEqual(corners[2][0], 130, places=5)  # BR x
        self.assertAlmostEqual(corners[2][1], 150, places=5)  # BR y

    def test_90_ccw_feet_point_right(self) -> None:
        """90° CCW rotation (RIGHT gravity): original feet (+y) must go to +x (right)."""
        import math
        cx, cy, hw, hh = 0, 0, 20, 40
        corners = self._corners(cx, cy, hw, hh, 90.0)
        # Original bottom center (0, +hh) should rotate to (+hh, 0) = right side
        # BL (originally -hw, +hh) → after 90° CCW: (+hh, +hw)
        # BR (originally +hw, +hh) → after 90° CCW: (+hh, -hw) = right side, up
        # Check that the rightmost corners are the original "bottom" (feet) corners
        # i.e., BR and BL are to the right
        br_x = corners[2][0]  # BR x after rotation
        bl_x = corners[3][0]  # BL x after rotation
        # BR was originally (hw, hh); after 90° CCW screen: (hh*cos(90)+hw*sin(90)...)
        # Using formula: x' = x*cos+y*sin, y' = -x*sin+y*cos → (hw*0+hh*1, -hw*1+hh*0) = (hh, -hw)
        self.assertAlmostEqual(corners[2][0], cy + hh, places=5)   # BR → right
        self.assertAlmostEqual(corners[2][1], cx - hw, places=5)   # BR → up

    def test_180_flips_top_to_bottom(self) -> None:
        """180° rotation (UP gravity): original TL must end up at BR."""
        cx, cy, hw, hh = 0, 0, 20, 40
        corners = self._corners(cx, cy, hw, hh, 180.0)
        # Original TL (-hw, -hh) → after 180°: (hw, hh)
        self.assertAlmostEqual(corners[0][0], cx + hw, places=5)
        self.assertAlmostEqual(corners[0][1], cy + hh, places=5)


if __name__ == "__main__":
    unittest.main()
