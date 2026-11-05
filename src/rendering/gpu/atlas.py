"""Runtime texture atlas — packs pygame Surfaces into a single GL texture at startup.

All named frames are shelf-packed into a 2048×2048 RGBA atlas and uploaded once.
A built-in 1×1 white pixel ('__white__') is always present for solid-color quads.
"""
from __future__ import annotations

import pygame
import moderngl

WHITE_FRAME: str = "__white__"
ATLAS_SIZE: int = 2048
_PADDING: int = 1   # pixel gap between packed frames to avoid bleeding


class RuntimeAtlas:
    """Packs named pygame Surfaces into one GL texture.

    UV lookups return (u_left, v_top, u_right, v_bot) in OpenGL texture space
    where v_top > v_bot (V increases upward in GL). The white frame is always
    available as a fallback for untextured colored quads.
    """

    def __init__(self, ctx: moderngl.Context, frames: dict[str, pygame.Surface]) -> None:
        """Pack all frames and upload to GPU."""
        self._rects: dict[str, pygame.Rect] = {}

        atlas_surf = pygame.Surface((ATLAS_SIZE, ATLAS_SIZE), pygame.SRCALPHA)
        atlas_surf.fill((0, 0, 0, 0))

        all_frames: dict[str, pygame.Surface] = {WHITE_FRAME: _white_pixel()}
        all_frames.update(frames)

        # Shelf packing: sort tallest first, place left-to-right, start new row on overflow
        sorted_items = sorted(all_frames.items(), key=lambda kv: kv[1].get_height(), reverse=True)
        cx, cy, row_h = _PADDING, _PADDING, 0
        for name, surf in sorted_items:
            fw, fh = surf.get_size()
            if cx + fw + _PADDING > ATLAS_SIZE:
                cx = _PADDING
                cy += row_h + _PADDING
                row_h = 0
            if cy + fh + _PADDING > ATLAS_SIZE:
                print(f"[Atlas] Warning: frame '{name}' doesn't fit — using white fallback")
                continue
            atlas_surf.blit(surf, (cx, cy))
            self._rects[name] = pygame.Rect(cx, cy, fw, fh)
            row_h = max(row_h, fh)
            cx += fw + _PADDING

        # Upload with flipped=True so GL V=0=bottom, V=1=top (matches screen-space quad math)
        raw = pygame.image.tostring(atlas_surf, "RGBA", True)
        self._texture: moderngl.Texture = ctx.texture((ATLAS_SIZE, ATLAS_SIZE), 4, data=raw)
        self._texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def get_uvs(self, name: str) -> tuple[float, float, float, float]:
        """Return (u_left, v_top, u_right, v_bot) for the named frame.

        v_top > v_bot: in GL texture space, V increases toward the top of the
        image (which corresponds to pygame Y=0 after the flipped upload).
        Half-pixel insets (texel-centre convention) prevent nearest-neighbour
        filtering from sampling the transparent padding at frame boundaries.
        Falls back to the white frame if the name is missing.
        """
        r = self._rects.get(name) or self._rects[WHITE_FRAME]
        # 0.5-pixel inset: sample texel centres, not edges
        u_l = (r.x + 0.5) / ATLAS_SIZE
        u_r = (r.x + r.width - 0.5) / ATLAS_SIZE
        # After flipped=True upload: GL V = 1 - (pygame_y + 0.5)/H at texel centre
        v_top = 1.0 - (r.y + 0.5) / ATLAS_SIZE
        v_bot = 1.0 - (r.y + r.height - 0.5) / ATLAS_SIZE
        return (u_l, v_top, u_r, v_bot)

    def has_frame(self, name: str) -> bool:
        """Return True if the frame is in the atlas."""
        return name in self._rects

    def use(self, unit: int = 0) -> None:
        """Bind atlas texture to the given texture unit."""
        self._texture.use(unit)

    def release(self) -> None:
        """Free GPU texture memory."""
        self._texture.release()

    @property
    def white_uvs(self) -> tuple[float, float, float, float]:
        """UVs for the 1×1 white pixel — use as a solid-color quad source."""
        return self.get_uvs(WHITE_FRAME)


def _white_pixel() -> pygame.Surface:
    """Return a 1×1 fully opaque white Surface."""
    s = pygame.Surface((1, 1), pygame.SRCALPHA)
    s.fill((255, 255, 255, 255))
    return s
