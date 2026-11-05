"""GPU context management — initialises ModernGL alongside Pygame.

use_gpu_renderer() checks the USE_GPU_RENDERER constant and the FOLD_RENDERER
environment variable so CI can force the software path without code changes.
"""
from __future__ import annotations

import os

import moderngl

from constants import USE_GPU_RENDERER


def use_gpu_renderer() -> bool:
    """Return True when the GPU renderer should be active.

    Set FOLD_RENDERER=software to force the software fallback regardless of the
    USE_GPU_RENDERER constant (CI always uses this to skip the GPU path).
    """
    if os.environ.get("FOLD_RENDERER", "").lower() == "software":
        return False
    return USE_GPU_RENDERER


class GPUContext:
    """Thin wrapper around a ModernGL context created from a Pygame OPENGL window.

    Call clear() each frame before submitting draw calls, and release() on shutdown.
    """

    def __init__(self) -> None:
        """Create the ModernGL context from the current Pygame OPENGL window."""
        self.ctx: moderngl.Context = moderngl.create_context()

    def clear(self, r: float = 0.0, g: float = 0.0, b: float = 0.0, a: float = 1.0) -> None:
        """Clear the colour and depth buffers to the given colour."""
        self.ctx.clear(r, g, b, a)

    def release(self) -> None:
        """Release all GPU resources owned by this context."""
        self.ctx.release()

    @staticmethod
    def is_available() -> bool:
        """Return True if moderngl can open a standalone context (GPU exists)."""
        try:
            ctx = moderngl.create_standalone_context()
            ctx.release()
            return True
        except Exception:
            return False
