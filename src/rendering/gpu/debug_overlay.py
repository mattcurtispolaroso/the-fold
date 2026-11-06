"""GPU debug overlay text — per-layer and per-post-pass timings (TA-2, TA-4).

Drawn onto the transparent HUD surface, so it composites over the world like
the rest of the HUD. With the overlay open, keys 1-5 toggle the post passes in
POST_PASS_ORDER; each line shows the key, the pass state and its GPU ms.
"""
from __future__ import annotations

import pygame

import constants as C
from src.rendering.gpu.layer import COMPOSITE_TIMING_KEY, LIGHT_TIMING_KEY

TIMING_TEXT_COLOR: tuple[int, int, int] = (180, 255, 180)
PASS_OFF_TEXT_COLOR: tuple[int, int, int] = (130, 130, 130)
TIMING_LINE_HEIGHT: int = 18
TIMING_MARGIN: int = 10
POST_TOGGLE_KEYS: tuple[int, ...] = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)


def post_pass_for_key(key: int) -> str | None:
    """Return the post pass toggled by `key` (1-5 → POST_PASS_ORDER), or None."""
    if key not in POST_TOGGLE_KEYS:
        return None
    index = POST_TOGGLE_KEYS.index(key)
    return C.POST_PASS_ORDER[index] if index < len(C.POST_PASS_ORDER) else None


def format_layer_timings(
    layer_ms: dict[str, float],
    post_enabled: dict[str, bool] | None = None,
) -> list[str]:
    """Return timing lines: layers, light, composite, post passes (if given), total."""
    keys = list(C.PARALLAX_LAYER_NAMES) + [LIGHT_TIMING_KEY, COMPOSITE_TIMING_KEY]
    lines = [f"{key:<9} {layer_ms.get(key, 0.0):5.2f} ms" for key in keys]
    for i, name in enumerate(C.POST_PASS_ORDER if post_enabled is not None else ()):
        state = "ON " if post_enabled[name] else "off"
        lines.append(f"[{i + 1}] {name:<8} {state} {layer_ms.get(name, 0.0):5.2f} ms")
    lines.append(f"{'total':<9} {sum(layer_ms.values()):5.2f} ms")
    return lines


def draw_layer_timings(
    surf: pygame.Surface,
    font: pygame.font.Font,
    layer_ms: dict[str, float],
    post_enabled: dict[str, bool] | None = None,
) -> None:
    """Draw the timing block in the top-right corner of `surf`; disabled passes in grey."""
    for i, line in enumerate(format_layer_timings(layer_ms, post_enabled)):
        color = PASS_OFF_TEXT_COLOR if " off " in line else TIMING_TEXT_COLOR
        text = font.render(line, True, color)
        x = surf.get_width() - text.get_width() - TIMING_MARGIN
        surf.blit(text, (x, TIMING_MARGIN + i * TIMING_LINE_HEIGHT))
