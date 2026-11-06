"""GPU sprite batch renderer for The Fold.

Collects quads each frame and flushes them to the GPU in one draw call.
Both textured sprites and solid-color rects share one shader and one VBO.

Camera convention: cam_offset is ADDITIVE — screen_pos = world_pos + cam_offset.
What to draw for the playfield lives in world_draw.py; this module is only
the batching mechanism.
"""
from __future__ import annotations

import array
import math

import pygame
import moderngl

from src.rendering.gpu.atlas import RuntimeAtlas
from src.rendering.gpu.shader_source import load_shader

# Max quads before a forced mid-frame flush
MAX_QUADS: int = 4096
# Floats per vertex: pos(2) + uv(2) + tint(4) + flash(4: rgb + amount)
_VFLOATS: int = 12
NO_FLASH: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
_VBYTES: int = _VFLOATS * 4  # float32

# Screen-space CCW rotation per gravity direction (degrees)
# Matches constants.SPRITE_ROTATION — positive = visually CCW on screen
_GRAVITY_ANGLE: dict[tuple[int, int], float] = {
    (0, 1): 0.0,
    (0, -1): 180.0,
    (-1, 0): -90.0,
    (1, 0): 90.0,
}

def _rotated_corners(
    cx: float, cy: float,
    half_w: float, half_h: float,
    angle_deg: float,
) -> list[tuple[float, float]]:
    """Return [TL, TR, BR, BL] screen-space corners after a screen-space CCW rotation."""
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    # Screen-space CCW rotation: x' = x*cos + y*sin; y' = -x*sin + y*cos
    base = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    result = []
    for lx, ly in base:
        rx = lx * cos_a + ly * sin_a
        ry = -lx * sin_a + ly * cos_a
        result.append((cx + rx, cy + ry))
    return result


def _quad_indices(quad_count: int) -> array.array:
    """Static index list: two triangles (TL-TR-BR, TL-BR-BL) per quad."""
    indices = array.array("I")
    for i in range(quad_count):
        b = i * 4
        indices.extend([b, b + 1, b + 2, b, b + 2, b + 3])
    return indices


def _overlay_texture(ctx: moderngl.Context, resolution: tuple[int, int]) -> moderngl.Texture:
    """Screen-sized texture for uploading a software-rendered Surface each frame."""
    texture = ctx.texture(resolution, 4)
    texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
    return texture


class SpriteBatch:
    """Batched 2D quad renderer — sprites and colored rects in one draw call.

    Usage: begin() → draw_sprite/draw_rect calls → flush().
    """

    def __init__(
        self,
        ctx: moderngl.Context,
        atlas: RuntimeAtlas,
        resolution: tuple[int, int],
    ) -> None:
        """Create GPU resources. Shaders are compiled once here."""
        self._ctx = ctx
        self._atlas = atlas
        self._resolution = resolution
        self._quad_count: int = 0
        self._vdata = array.array("f", [0.0] * (MAX_QUADS * 4 * _VFLOATS))

        # Compile shader program
        vert_src = load_shader("sprite.vert")
        frag_src = load_shader("sprite.frag")
        self._prog: moderngl.Program = ctx.program(
            vertex_shader=vert_src,
            fragment_shader=frag_src,
        )
        self._prog["u_resolution"].value = resolution
        self._prog["u_texture"] = 0

        self._vbo: moderngl.Buffer = ctx.buffer(
            reserve=MAX_QUADS * 4 * _VBYTES,
        )
        self._ibo: moderngl.Buffer = ctx.buffer(_quad_indices(MAX_QUADS).tobytes())
        self._vao: moderngl.VertexArray = ctx.vertex_array(
            self._prog,
            [(self._vbo, "2f 2f 4f 4f", "a_pos", "a_uv", "a_tint", "a_flash")],
            self._ibo,
        )

        # Enable alpha blending once — stays on for the session
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        # Persistent overlay texture — holds a software-rendered pygame Surface
        # each frame for game states not yet ported to the GPU path.
        self._overlay_tex: moderngl.Texture = _overlay_texture(ctx, resolution)

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def begin(self) -> None:
        """Reset quad counter for a new frame."""
        self._quad_count = 0

    def flush(self) -> None:
        """Upload buffered quads, issue the draw call, and reset the counter.

        Resetting here ensures that a second flush() call (e.g. from
        draw_fullscreen_surface) does not re-render the same batch.
        """
        if self._quad_count == 0:
            return
        byte_count = self._quad_count * 4 * _VBYTES
        self._vbo.write(self._vdata.tobytes()[:byte_count])
        self._atlas.use(0)
        self._vao.render(moderngl.TRIANGLES, vertices=self._quad_count * 6)
        self._quad_count = 0

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------

    def draw_sprite(
        self,
        frame: str,
        cx: float,
        cy: float,
        w: float,
        h: float,
        gravity_dir: tuple[int, int] = (0, 1),
        flip_x: bool = False,
        flash: tuple[float, float, float, float] = NO_FLASH,
    ) -> None:
        """Draw a named atlas frame centered at (cx, cy) with gravity rotation."""
        if self._quad_count >= MAX_QUADS:
            self.flush()
            self._quad_count = 0

        angle = _GRAVITY_ANGLE.get(gravity_dir, 0.0)
        corners = _rotated_corners(cx, cy, w / 2, h / 2, angle)

        ul, vt, ur, vb = self._atlas.get_uvs(frame)
        if flip_x:
            ul, ur = ur, ul

        # UVs per corner [TL, TR, BR, BL]
        uvs = [(ul, vt), (ur, vt), (ur, vb), (ul, vb)]
        self._push_quad(corners, uvs, (1.0, 1.0, 1.0, 1.0), flash)

    def draw_rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """Draw a solid-color rectangle using the white pixel frame."""
        if self._quad_count >= MAX_QUADS:
            self.flush()
            self._quad_count = 0

        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        uvs = self._atlas.white_uvs
        # All 4 corners share the same UV (1×1 white pixel)
        self._push_quad(corners, [(uvs[0], uvs[1])] * 4, color)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _push_quad(
        self,
        corners: list[tuple[float, float]],
        uvs: list[tuple[float, float]],
        tint: tuple[float, float, float, float],
        flash: tuple[float, float, float, float] = NO_FLASH,
    ) -> None:
        """Write 4 vertices (TL, TR, BR, BL) into the CPU buffer."""
        base = self._quad_count * 4 * _VFLOATS
        r, g, b, a = tint
        fr, fg, fb, fa = flash
        for i, ((px, py), (u, v)) in enumerate(zip(corners, uvs)):
            off = base + i * _VFLOATS
            self._vdata[off] = px
            self._vdata[off + 1] = py
            self._vdata[off + 2] = u
            self._vdata[off + 3] = v
            self._vdata[off + 4] = r
            self._vdata[off + 5] = g
            self._vdata[off + 6] = b
            self._vdata[off + 7] = a
            self._vdata[off + 8] = fr
            self._vdata[off + 9] = fg
            self._vdata[off + 10] = fb
            self._vdata[off + 11] = fa
        self._quad_count += 1

    def draw_fullscreen_surface(self, surf: pygame.Surface) -> None:
        """Upload a pygame Surface and render it as a fullscreen quad.

        Flushes any pending atlas draw calls first so the surface composites
        correctly. Used for game states (start screen, node map, etc.) that
        still run through the software rendering path.
        """
        self.flush()  # renders pending world quads and resets _quad_count to 0
        raw = pygame.image.tostring(surf, "RGBA", True)
        self._overlay_tex.write(raw)
        # Draw one fullscreen quad using the overlay texture instead of the atlas
        self._overlay_tex.use(0)
        w, h = self._resolution
        # UVs: TL(0,1), TR(1,1), BR(1,0), BL(0,0) — matches flipped=True upload
        corners = [(0.0, 0.0), (float(w), 0.0), (float(w), float(h)), (0.0, float(h))]
        uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
        self._push_quad(corners, uvs, (1.0, 1.0, 1.0, 1.0))
        byte_count = 1 * 4 * _VBYTES
        self._vbo.write(self._vdata.tobytes()[:byte_count])
        self._vao.render(moderngl.TRIANGLES, vertices=6)
        self._quad_count = 0  # overlay quad not managed by flush(); clear manually
        # Restore atlas binding for subsequent draw calls
        self._atlas.use(0)

    def release(self) -> None:
        """Free all GPU resources owned by this batch."""
        self._overlay_tex.release()
        self._vao.release()
        self._vbo.release()
        self._ibo.release()
        self._prog.release()

