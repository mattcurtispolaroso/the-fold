"""Instanced GPU particle renderer (TA-7).

Draws every active particle in a ParticlePool with ONE instanced draw call:
a shared unit quad plus a per-instance buffer (position, radius, colour,
alpha, glow) that ParticlePool.write_instances() fills each frame. The
instance buffer is allocated once at pool capacity, so nothing grows.
"""
from __future__ import annotations

import array

import moderngl

import constants as C
from src.rendering.gpu.sprite_batch import _load_shader
from src.rendering.vfx import INSTANCE_FLOATS, ParticlePool

_UNIT_QUAD = (-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)  # triangle strip
_FLOAT_BYTES: int = 4
# Premultiplied blending: glow particles (alpha 0) add, normal ones cover
_PARTICLE_BLEND = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA,
                   moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)


class ParticleRenderer:
    """Uploads a pool's live particles and draws them in a single instanced call.

    `draw_calls` counts GL draw calls issued (for tests and the debug overlay).
    """

    def __init__(self, ctx: moderngl.Context, resolution: tuple[int, int], capacity: int) -> None:
        """Compile the particle program and allocate quad + instance buffers."""
        self._ctx = ctx
        self._capacity = capacity
        self._prog = ctx.program(vertex_shader=_load_shader("particle.vert"),
                                 fragment_shader=_load_shader("particle.frag"))
        self._prog["u_resolution"].value = (float(resolution[0]), float(resolution[1]))
        self._prog["u_soft_edge"].value = C.PARTICLE_SOFT_EDGE
        self._prog["u_glow_core"].value = C.PARTICLE_GLOW_CORE
        self._instances = array.array("f", [0.0] * (capacity * INSTANCE_FLOATS))
        self._quad_vbo = ctx.buffer(array.array("f", _UNIT_QUAD).tobytes())
        self._instance_vbo = ctx.buffer(reserve=capacity * INSTANCE_FLOATS * _FLOAT_BYTES)
        self._vao = ctx.vertex_array(self._prog, [
            (self._quad_vbo, "2f", "a_corner"),
            (self._instance_vbo, "2f 1f 3f 1f 1f/i",
             "i_pos", "i_radius", "i_color", "i_alpha", "i_glow"),
        ])
        self.draw_calls: int = 0
        self.last_count: int = 0

    def draw(self, pool: ParticlePool, cam_offset: tuple[float, float]) -> int:
        """Draw every live particle into the bound framebuffer; return how many.

        Must be called with the target (normally the play layer) already bound.
        Issues zero draw calls when nothing is alive.
        """
        if pool.capacity > self._capacity:
            raise ValueError(f"pool capacity {pool.capacity} exceeds renderer capacity "
                             f"{self._capacity}")
        count = pool.write_instances(self._instances, cam_offset)
        self.last_count = count
        if count == 0:
            return 0
        self._instance_vbo.write(
            memoryview(self._instances)[:count * INSTANCE_FLOATS].tobytes())
        self._ctx.blend_func = _PARTICLE_BLEND
        self._vao.render(moderngl.TRIANGLE_STRIP, instances=count)
        self.draw_calls += 1
        return count

    def release(self) -> None:
        """Free all GPU resources."""
        self._vao.release()
        self._instance_vbo.release()
        self._quad_vbo.release()
        self._prog.release()
