"""Colour-grading lookup tables for the post stack's LUT pass (TA-4).

A LUT is a float32 array of shape (N, N, N, 3) indexed [b, g, r] — the memory
order a GL 3D texture expects (x = red fastest, z = blue slowest).

Sources, in priority order:
  1. assets/luts/grade.png — a standard 256×16 strip: 16 slices of 16×16 laid
     left-to-right by blue; within a slice x = red, y = green (top row = 0).
  2. The procedural grade built from the GRADE_* constants.
"""
from __future__ import annotations

import logging
import os

import moderngl
import numpy as np
import pygame

import constants as C

logger = logging.getLogger(__name__)

_LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
_MAX_CHANNEL: float = 255.0


def identity_lut(size: int) -> np.ndarray:
    """Return a LUT that maps every colour to itself."""
    ramp = np.linspace(0.0, 1.0, size, dtype=np.float32)
    b, g, r = np.meshgrid(ramp, ramp, ramp, indexing="ij")
    return np.stack([r, g, b], axis=-1)


def build_grade_lut(size: int) -> np.ndarray:
    """Bake the procedural grade: contrast, saturation, split-tone shadows/highlights."""
    color = identity_lut(size)
    color = (color - C.GRADE_CONTRAST_PIVOT) * C.GRADE_CONTRAST + C.GRADE_CONTRAST_PIVOT
    luma = (color @ _LUMA_WEIGHTS)[..., None]
    color = luma + (color - luma) * C.GRADE_SATURATION
    color = (color
             + np.array(C.GRADE_SHADOW_TINT, dtype=np.float32) * (1.0 - luma)
             + np.array(C.GRADE_HIGHLIGHT_TINT, dtype=np.float32) * luma)
    return np.clip(color, 0.0, 1.0).astype(np.float32)


def lut_from_strip(strip: pygame.Surface, size: int) -> np.ndarray:
    """Convert a (size² × size) strip image into a LUT array."""
    w, h = strip.get_size()
    if (w, h) != (size * size, size):
        raise ValueError(f"LUT strip must be {size * size}x{size}, got {w}x{h}")
    pixels = pygame.surfarray.array3d(strip).astype(np.float32) / _MAX_CHANNEL  # [x, y, c]
    # x = blue_slice * size + red, y = green  →  reshape to [blue, red, green, c]
    cube = pixels.reshape(size, size, size, 3)
    return np.ascontiguousarray(cube.transpose(0, 2, 1, 3))  # → [blue, green, red, c]


def load_lut(base_dir: str, size: int) -> np.ndarray:
    """Return the strip LUT from LUT_ART_PATH if valid, else the procedural grade."""
    path = os.path.join(base_dir, C.LUT_ART_PATH)
    if os.path.isfile(path):
        try:
            return lut_from_strip(pygame.image.load(path), size)
        except (pygame.error, ValueError) as e:
            logger.warning("LUT strip failed to load (%s): %s — using procedural grade", path, e)
    return build_grade_lut(size)


def upload_lut(ctx: moderngl.Context, lut: np.ndarray) -> moderngl.Texture3D:
    """Upload a LUT array as a linearly filtered, edge-clamped 3D texture."""
    size = lut.shape[0]
    texture = ctx.texture3d((size, size, size), 3, data=lut.astype("f4").tobytes(), dtype="f4")
    texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
    texture.repeat_x = texture.repeat_y = texture.repeat_z = False
    return texture
