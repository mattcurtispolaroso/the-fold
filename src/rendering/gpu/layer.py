"""Parallax layer system (TA-2) — five offscreen FBOs composited back-to-front.

Each layer renders at the internal game resolution with its own scroll factor:
sky 0.05×, far 0.20×, mid 0.50×, play 1.00×, fore 1.30× (see constants.py).
The sky/far/mid layers are drawn from screen-sized images; the play layer is
drawn by the sprite batch. composite() blends every layer onto a target
framebuffer using the upscale shader, so the target may be any size.

Blend convention: layers store premultiplied colour so partially transparent
layers composite correctly (straight alpha would darken them twice).
"""
from __future__ import annotations

import array
from contextlib import contextmanager
from typing import Iterator

import moderngl
import pygame

import constants as C
from src.rendering.gpu.sprite_batch import _load_shader

# Sprite/image draws INTO a layer: straight-alpha colour, accumulate alpha correctly
_LAYER_BLEND = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA,
                moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
# Layer textures onto the target: they already hold premultiplied colour
_COMPOSITE_BLEND = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
# What the sprite batch and HUD overlay expect everywhere else
_DEFAULT_BLEND = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

COMPOSITE_TIMING_KEY: str = "composite"
_NS_PER_MS: float = 1_000_000.0
_FULLSCREEN_QUAD = (-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)  # triangle strip, NDC


def parallax_offset(cam_offset: tuple[float, float], factor: float) -> tuple[float, float]:
    """Return the screen offset for a layer that scrolls at `factor` × the camera.

    cam_offset is the additive camera offset (screen = world + offset). A factor
    of 1.0 locks the layer to the playfield; 0.0 pins it to the screen.
    """
    ox, oy = cam_offset
    return (ox * factor, oy * factor)


def resolve_scroll_factors(overrides: dict[str, float] | None = None) -> dict[str, float]:
    """Merge per-level overrides onto the default factors; play is always 1.0."""
    factors = dict(C.PARALLAX_SCROLL_FACTORS)
    for name, value in (overrides or {}).items():
        if name in factors and name != C.PARALLAX_PLAY_LAYER:
            factors[name] = max(C.PARALLAX_SCROLL_MIN, min(C.PARALLAX_SCROLL_MAX, value))
    factors[C.PARALLAX_PLAY_LAYER] = 1.0
    return factors


class LayerFBO:
    """One offscreen colour target (texture + framebuffer) for a single parallax layer."""

    def __init__(self, ctx: moderngl.Context, name: str, size: tuple[int, int]) -> None:
        """Allocate the layer's texture and framebuffer at `size`."""
        self._ctx = ctx
        self.name = name
        self.texture: moderngl.Texture
        self.fbo: moderngl.Framebuffer
        self._allocate(size)

    def _allocate(self, size: tuple[int, int]) -> None:
        """Create the GPU texture and framebuffer, then clear them to transparent."""
        self.texture = self._ctx.texture(size, 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.fbo = self._ctx.framebuffer(color_attachments=[self.texture])
        self.fbo.clear(0.0, 0.0, 0.0, 0.0)

    @property
    def size(self) -> tuple[int, int]:
        """Pixel size of this layer's framebuffer."""
        return self.fbo.size

    def resize(self, size: tuple[int, int]) -> None:
        """Reallocate at a new size; a no-op when the size is unchanged."""
        if tuple(size) == self.size:
            return
        self.release()
        self._allocate(size)

    def release(self) -> None:
        """Free the framebuffer and texture."""
        self.fbo.release()
        self.texture.release()


class ParallaxStack:
    """Owns the five layer FBOs, draws image layers, and composites to a target.

    Per frame: begin_frame() → draw_image_layers() → `with target("play"):` sprite
    batch draws → composite(screen). Set `profiling = True` to fill `layer_ms`
    with GPU times (this stalls the pipeline, so only enable it for debugging).
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        size: tuple[int, int],
        images: dict[str, pygame.Surface],
    ) -> None:
        """Create the FBOs, the fullscreen-quad program, and the image textures."""
        self._ctx = ctx
        self.layers: dict[str, LayerFBO] = {
            name: LayerFBO(ctx, name, size) for name in C.PARALLAX_LAYER_NAMES
        }
        self._prog = ctx.program(
            vertex_shader=_load_shader("upscale.vert"),
            fragment_shader=_load_shader("upscale.frag"),
        )
        self._prog["u_texture"] = 0
        self._quad_vbo = ctx.buffer(array.array("f", _FULLSCREEN_QUAD).tobytes())
        self._quad_vao = ctx.vertex_array(self._prog, [(self._quad_vbo, "2f", "a_pos")])
        self._images = {
            name: _upload_image(ctx, surf)
            for name, surf in images.items() if name in C.PARALLAX_IMAGE_LAYERS
        }
        self._queries: dict[str, moderngl.Query] = {}
        self.profiling: bool = False
        self.layer_ms: dict[str, float] = {}
        ctx.enable(moderngl.BLEND)

    @property
    def size(self) -> tuple[int, int]:
        """Internal resolution shared by every layer."""
        return self.layers[C.PARALLAX_PLAY_LAYER].size

    def begin_frame(self) -> None:
        """Clear every layer to transparent and reset per-frame timings."""
        self.layer_ms = {}
        for layer in self.layers.values():
            layer.fbo.clear(0.0, 0.0, 0.0, 0.0)

    def draw_image_layers(
        self,
        cam_offset: tuple[float, float],
        overrides: dict[str, float] | None = None,
    ) -> None:
        """Draw each image layer into its FBO, scrolled by its parallax factor."""
        factors = resolve_scroll_factors(overrides)
        w, h = self.size
        for name, texture in self._images.items():
            sx, sy = parallax_offset(cam_offset, factors[name])
            with self.target(name):
                texture.use(0)
                self._prog["u_uv_offset"].value = (-sx / w, -sy / h)
                self._quad_vao.render(moderngl.TRIANGLE_STRIP)

    @contextmanager
    def target(self, name: str) -> Iterator[LayerFBO]:
        """Bind a layer FBO with layer blending for the duration of the block."""
        layer = self.layers[name]
        layer.fbo.use()
        self._ctx.blend_func = _LAYER_BLEND
        with self._timed(name):
            yield layer
        self._ctx.blend_func = _DEFAULT_BLEND

    def composite(self, target: moderngl.Framebuffer) -> None:
        """Blend every layer back-to-front onto `target`, scaling to its viewport."""
        target.use()
        self._ctx.blend_func = _COMPOSITE_BLEND
        self._prog["u_uv_offset"].value = (0.0, 0.0)
        with self._timed(COMPOSITE_TIMING_KEY):
            for name in C.PARALLAX_LAYER_NAMES:
                self.layers[name].texture.use(0)
                self._quad_vao.render(moderngl.TRIANGLE_STRIP)
        self._ctx.blend_func = _DEFAULT_BLEND

    def resize(self, size: tuple[int, int]) -> None:
        """Reallocate every layer FBO at a new internal resolution."""
        for layer in self.layers.values():
            layer.resize(size)

    @contextmanager
    def _timed(self, key: str) -> Iterator[None]:
        """Accumulate GPU ms for `key` into layer_ms when profiling is on."""
        if not self.profiling:
            yield
            return
        query = self._queries.get(key) or self._ctx.query(time=True)
        self._queries[key] = query
        with query:
            yield
        self.layer_ms[key] = self.layer_ms.get(key, 0.0) + query.elapsed / _NS_PER_MS

    def release(self) -> None:
        """Free all GPU resources owned by the stack."""
        for layer in self.layers.values():
            layer.release()
        for texture in self._images.values():
            texture.release()
        # moderngl 5.x Query objects have no release(); they die with the context
        self._queries.clear()
        self._quad_vao.release()
        self._quad_vbo.release()
        self._prog.release()


def _upload_image(ctx: moderngl.Context, surf: pygame.Surface) -> moderngl.Texture:
    """Upload a layer image as an RGBA texture with smooth (sub-pixel) sampling."""
    raw = pygame.image.tostring(surf, "RGBA", True)
    texture = ctx.texture(surf.get_size(), 4, data=raw)
    texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
    texture.repeat_x = False
    texture.repeat_y = False
    return texture
