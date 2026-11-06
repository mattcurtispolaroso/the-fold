"""GLSL source loading for the GPU renderer.

One shared, public loader so GPU modules don't reach into each other for it
(previously four modules imported a private helper from sprite_batch.py).
Shaders live in <project root>/shaders/; in a frozen build that folder is
bundled at the same relative location (see build/the_fold.spec).
"""
from __future__ import annotations

import os

SHADER_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "shaders",
)


def load_shader(name: str) -> str:
    """Return the source of shaders/<name>; raises FileNotFoundError if missing."""
    with open(os.path.join(SHADER_DIR, name)) as f:
        return f.read()
