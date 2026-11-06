"""GPU debug overlay text — per-layer render timings (TA-2).

Drawn onto the transparent HUD surface, so it composites over the world like
the rest of the HUD. TA-4 extends this module into the post-pass tuning panel.
"""
from __future__ import annotations

import pygame

import constants as C
from src.rendering.gpu.layer import COMPOSITE_TIMING_KEY

TIMING_TEXT_COLOR: tuple[int, int, int] = (180, 255, 180)
TIMING_LINE_HEIGHT: int = 18
TIMING_MARGIN: int = 10


def format_layer_timings(layer_ms: dict[str, float]) -> list[str]:
    """Return one 'name  0.00 ms' line per layer in draw order, then composite and total."""
    keys = list(C.PARALLAX_LAYER_NAMES) + [COMPOSITE_TIMING_KEY]
    lines = [f"{key:<9} {layer_ms.get(key, 0.0):5.2f} ms" for key in keys]
    lines.append(f"{'total':<9} {sum(layer_ms.values()):5.2f} ms")
    return lines


def draw_layer_timings(
    surf: pygame.Surface,
    font: pygame.font.Font,
    layer_ms: dict[str, float],
) -> None:
    """Draw the per-layer timing block in the top-right corner of `surf`."""
    lines = format_layer_timings(layer_ms)
    for i, line in enumerate(lines):
        text = font.render(line, True, TIMING_TEXT_COLOR)
        x = surf.get_width() - text.get_width() - TIMING_MARGIN
        surf.blit(text, (x, TIMING_MARGIN + i * TIMING_LINE_HEIGHT))
