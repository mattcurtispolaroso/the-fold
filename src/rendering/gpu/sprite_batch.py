"""GPU sprite batch renderer for The Fold.

Collects quads each frame and flushes them to the GPU in one draw call.
Both textured sprites and solid-color rects share one shader and one VBO.

Camera convention: cam_offset is ADDITIVE — screen_pos = world_pos + cam_offset.
"""
from __future__ import annotations

import array
import math
import os

import pygame
import moderngl

import constants as C
from src.rendering.gpu.atlas import RuntimeAtlas, WHITE_FRAME

# Max quads before a forced mid-frame flush
MAX_QUADS: int = 4096
# Floats per vertex: pos(2) + uv(2) + tint(4)
_VFLOATS: int = 8
_VBYTES: int = _VFLOATS * 4  # float32

# Screen-space CCW rotation per gravity direction (degrees)
# Matches C.SPRITE_ROTATION — positive = visually CCW on screen
_GRAVITY_ANGLE: dict[tuple[int, int], float] = {
    (0, 1): 0.0,
    (0, -1): 180.0,
    (-1, 0): -90.0,
    (1, 0): 90.0,
}

_SHADER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), "shaders")


def _load_shader(name: str) -> str:
    """Read a GLSL source file from the shaders/ directory."""
    with open(os.path.join(_SHADER_DIR, name)) as f:
        return f.read()


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
        vert_src = _load_shader("sprite.vert")
        frag_src = _load_shader("sprite.frag")
        self._prog: moderngl.Program = ctx.program(
            vertex_shader=vert_src,
            fragment_shader=frag_src,
        )
        self._prog["u_resolution"].value = resolution
        self._prog["u_texture"] = 0

        # Pre-build static index buffer: two triangles per quad
        indices = array.array("I")
        for i in range(MAX_QUADS):
            b = i * 4
            indices.extend([b, b + 1, b + 2, b, b + 2, b + 3])

        self._vbo: moderngl.Buffer = ctx.buffer(
            reserve=MAX_QUADS * 4 * _VBYTES,
        )
        self._ibo: moderngl.Buffer = ctx.buffer(indices.tobytes())
        self._vao: moderngl.VertexArray = ctx.vertex_array(
            self._prog,
            [(self._vbo, "2f 2f 4f", "a_pos", "a_uv", "a_tint")],
            self._ibo,
        )

        # Enable alpha blending once — stays on for the session
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        # Persistent overlay texture — holds a software-rendered pygame Surface
        # each frame for game states not yet ported to the GPU path.
        w, h = resolution
        self._overlay_tex: moderngl.Texture = ctx.texture((w, h), 4)
        self._overlay_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

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
        self._push_quad(corners, uvs, (1.0, 1.0, 1.0, 1.0))

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
    ) -> None:
        """Write 4 vertices (TL, TR, BR, BL) into the CPU buffer."""
        base = self._quad_count * 4 * _VFLOATS
        r, g, b, a = tint
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


# ---------------------------------------------------------------------------
# World draw helper — called from main.py GPU path
# ---------------------------------------------------------------------------

def gpu_draw_world(
    batch: SpriteBatch,
    atlas: RuntimeAtlas,
    background: pygame.Surface | None,
    level: object,
    enemies: list,
    animator: object,
    player: object,
    player_state: object,
    cam_offset: tuple[float, float],
    width: int,
    height: int,
) -> None:
    """Draw the game world via the sprite batch (GPU path equivalent of draw_world).

    cam_offset is additive: screen_pos = world_pos + cam_offset.
    """
    ox, oy = cam_offset
    batch.begin()

    # Background — full screen, ignore camera offset
    if background is not None and atlas.has_frame("background"):
        batch.draw_sprite("background", width / 2, height / 2, width, height)
    else:
        batch.draw_rect(0, 0, width, height, (0.0, 0.0, 0.0, 1.0))

    # Gravity zones (outline — approximate with a thin filled rect)
    for zone in level.gravity_zones:
        col = _zone_color(zone)
        # Draw 4 edge rects to fake an outline (2px thick)
        zx, zy, zw, zh = zone.x + ox, zone.y + oy, zone.w, zone.h
        t = 2.0
        batch.draw_rect(zx, zy, zw, t, col)
        batch.draw_rect(zx, zy + zh - t, zw, t, col)
        batch.draw_rect(zx, zy, t, zh, col)
        batch.draw_rect(zx + zw - t, zy, t, zh, col)

    # Static platforms
    for plat in level.static_platforms:
        batch.draw_rect(plat.x + ox, plat.y + oy, plat.width, plat.height,
                        (0.392, 0.392, 0.392, 1.0))  # (100,100,100)/255

    # Moving platforms
    for mp in level.moving_platforms:
        r = mp.rect
        batch.draw_rect(r.x + ox, r.y + oy, r.width, r.height,
                        (0.196, 0.784, 0.784, 1.0))  # (50,200,200)/255

    # Goal rect
    gr = level.goal_rect
    batch.draw_rect(gr.x + ox, gr.y + oy, gr.width, gr.height,
                    (0.196, 0.863, 0.196, 1.0))  # (50,220,50)/255

    # Enemies
    for enemy in enemies:
        r = enemy.rect
        col = _enemy_color(enemy)
        batch.draw_rect(r.x + ox, r.y + oy, r.width, r.height, col)

    # Player sprite
    sw, sh = animator.width, animator.height
    px_screen = player.px + ox
    py_screen = player.py + oy
    frame_name = _player_frame_name(animator, player_state)
    if atlas.has_frame(frame_name):
        batch.draw_sprite(
            frame_name,
            px_screen, py_screen + C.SPRITE_PHYSICS_OFFSET_Y,
            sw, sh,
            gravity_dir=tuple(player.gravity_dir),
            flip_x=not player.facing_right,
        )
    else:
        # Fallback colored rect
        batch.draw_rect(px_screen - sw / 2, py_screen - sh / 2, sw, sh,
                        (0.863, 0.196, 0.196, 1.0))

    batch.flush()


def _player_frame_name(animator: object, player_state: object) -> str:
    """Map animator state + current walk frame to an atlas frame name."""
    state_name = player_state.name.lower()
    # Walk: pick the current walk frame index from the animator
    if state_name == "walk":
        frame_idx = getattr(animator, "_walk_frame", 0)
        name = f"player_walk_{frame_idx}"
        return name if animator._sprites.get(player_state) else "player_walk_0"
    return f"player_{state_name}_0"


def _zone_color(zone: object) -> tuple[float, float, float, float]:
    """Return RGBA float color for a gravity zone outline."""
    if zone.gravity_dir is not None:
        return (0.863, 0.627, 0.196, 1.0)  # amber
    if getattr(zone, "strength_mult", None) is not None and zone.strength_mult < 1.0:
        return (0.314, 0.549, 0.863, 1.0)  # blue
    return (0.863, 0.314, 0.196, 1.0)  # red-orange


def _enemy_color(enemy: object) -> tuple[float, float, float, float]:
    """Return RGBA float color for an enemy type."""
    cls = type(enemy).__name__
    if cls == "FoldPredator":
        return (0.706, 0.235, 0.863, 1.0)  # purple
    if cls == "TheAnchored":
        return (0.549, 0.824, 0.235, 1.0)  # yellow-green
    return (0.314, 0.863, 0.863, 1.0)  # cyan (TemporalEcho default)
