"""Headless smoke tests for the GPU context — no display required.

Creates a standalone ModernGL context (no Pygame window) to verify the
driver is available and the context wrapper works. CI always sets
FOLD_RENDERER=software so the game path is exercised without a GPU.
"""
from __future__ import annotations

import os
import unittest


class TestGPUContextHeadless(unittest.TestCase):
    """Verify GPUContext helpers work correctly without a display."""

    def test_software_override_via_env(self) -> None:
        """FOLD_RENDERER=software must disable GPU regardless of the constant."""
        os.environ["FOLD_RENDERER"] = "software"
        try:
            from src.rendering.gpu.context import use_gpu_renderer
            self.assertFalse(use_gpu_renderer())
        finally:
            del os.environ["FOLD_RENDERER"]

    def test_gpu_enabled_without_env_override(self) -> None:
        """With no env override, use_gpu_renderer() reflects USE_GPU_RENDERER."""
        os.environ.pop("FOLD_RENDERER", None)
        from constants import USE_GPU_RENDERER
        from src.rendering.gpu.context import use_gpu_renderer
        self.assertEqual(use_gpu_renderer(), USE_GPU_RENDERER)

    def test_standalone_context_smoke(self) -> None:
        """Creating a standalone ModernGL context and clearing must not raise."""
        try:
            import moderngl
            ctx = moderngl.create_standalone_context()
            ctx.clear(0.0, 0.0, 0.0, 1.0)
            ctx.release()
        except Exception as exc:
            self.skipTest(f"No GPU available in this environment: {exc}")

    def test_is_available_returns_bool(self) -> None:
        """GPUContext.is_available() must return a bool without raising."""
        from src.rendering.gpu.context import GPUContext
        result = GPUContext.is_available()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
