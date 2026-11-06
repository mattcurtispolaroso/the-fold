"""Builds the sky / far / mid parallax layer images at startup (TA-2).

Real art is a pure asset drop: if assets/backgrounds/layers/<name>.png exists it
is used for that layer. Otherwise a placeholder is derived from background.png:
  sky — the whole image, blurred, dimmed and cooled, fully opaque
  far — only the bright features (stars, nebula, hull rim), luminance-keyed
  mid — the lower band (pipework), darkened to a silhouette with a soft top edge
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pygame

import constants as C

logger = logging.getLogger(__name__)

# Rec. 601 luma weights for the far-layer luminance key
_LUMA_WEIGHTS = np.array([0.299, 0.587, 0.114], dtype=np.float32)
_MAX_CHANNEL: float = 255.0


def build_layer_images(
    base_dir: str,
    background: pygame.Surface | None,
    size: tuple[int, int],
) -> dict[str, pygame.Surface]:
    """Return one RGBA Surface per image layer; layers with no source are omitted."""
    makers = {"sky": make_sky_layer, "far": make_far_layer, "mid": make_mid_layer}
    images: dict[str, pygame.Surface] = {}
    for name in C.PARALLAX_IMAGE_LAYERS:
        art = _load_layer_art(base_dir, name, size)
        if art is not None:
            images[name] = art
        elif background is not None:
            images[name] = makers[name](pygame.transform.smoothscale(background, size))
    if background is None and not images:
        logger.warning("No background art found — parallax image layers are empty")
    return images


def _load_layer_art(base_dir: str, name: str, size: tuple[int, int]) -> pygame.Surface | None:
    """Load painted art for one layer if present; log and return None on failure."""
    path = os.path.join(base_dir, C.PARALLAX_LAYER_ART_DIR, f"{name}.png")
    if not os.path.isfile(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
    except pygame.error as e:
        logger.warning("Layer art failed to load (%s): %s — using placeholder", path, e)
        return None
    return pygame.transform.smoothscale(img, size)


def make_sky_layer(background: pygame.Surface) -> pygame.Surface:
    """Blurred, dimmed, cool-tinted, fully opaque copy — a distant haze behind far."""
    rgb = _rgb_floats(_blur(background, C.PARALLAX_SKY_BLUR_DIVISOR))
    rgb *= np.array(C.PARALLAX_SKY_TINT, dtype=np.float32)
    alpha = np.ones(rgb.shape[:2], dtype=np.float32)
    return _to_surface(rgb, alpha)


def make_far_layer(background: pygame.Surface) -> pygame.Surface:
    """Bright features only — alpha ramps up with luminance."""
    rgb = _rgb_floats(background)
    luma = rgb @ _LUMA_WEIGHTS
    alpha = _ramp(luma, C.PARALLAX_FAR_LUMA_LOW, C.PARALLAX_FAR_LUMA_HIGH)
    return _to_surface(rgb * np.array(C.PARALLAX_FAR_TINT, dtype=np.float32), alpha)


def make_mid_layer(background: pygame.Surface) -> pygame.Surface:
    """Darkened lower band — alpha ramps in from the band's top edge."""
    rgb = _rgb_floats(background) * np.array(C.PARALLAX_MID_TINT, dtype=np.float32)
    w, h = background.get_size()
    # surfarray is indexed [x, y]; build a per-row ramp and broadcast across x
    row_frac = np.linspace(0.0, 1.0, h, dtype=np.float32)
    row_alpha = _ramp(row_frac, C.PARALLAX_MID_BAND_START, C.PARALLAX_MID_BAND_FULL)
    alpha = np.broadcast_to(row_alpha, (w, h))
    return _to_surface(rgb, alpha)


def _blur(surf: pygame.Surface, divisor: int) -> pygame.Surface:
    """Cheap blur: smoothscale down by `divisor` and back up."""
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // divisor), max(1, h // divisor)))
    return pygame.transform.smoothscale(small, (w, h))


def _ramp(values: np.ndarray, low: float, high: float) -> np.ndarray:
    """Linear 0→1 ramp between low and high, clamped outside that range."""
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def _rgb_floats(surf: pygame.Surface) -> np.ndarray:
    """Return the surface's RGB as float32 in [0, 1], shape (w, h, 3)."""
    return pygame.surfarray.array3d(surf).astype(np.float32) / _MAX_CHANNEL


def _to_surface(rgb: np.ndarray, alpha: np.ndarray) -> pygame.Surface:
    """Pack float RGB (w, h, 3) and alpha (w, h) in [0, 1] into an SRCALPHA Surface."""
    w, h = alpha.shape
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.pixels3d(surf)[:] = (np.clip(rgb, 0.0, 1.0) * _MAX_CHANNEL).astype(np.uint8)
    pygame.surfarray.pixels_alpha(surf)[:] = (np.clip(alpha, 0.0, 1.0) * _MAX_CHANNEL).astype(np.uint8)
    return surf
