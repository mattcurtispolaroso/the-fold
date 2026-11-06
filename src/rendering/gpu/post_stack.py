"""Post-processing stack (TA-4/TA-5) — bloom, Fold distortion, LUT grade, vignette, grain, CRT stub.

Per frame: begin_scene() returns a cleared half-float scene buffer for the
parallax composite; render(target) runs each enabled pass in POST_PASS_ORDER,
ping-ponging between two buffers, then copies the result to `target`. The HUD
is drawn after render(), so it is never post-processed.
"""
from __future__ import annotations

import array
import math
from contextlib import AbstractContextManager, nullcontext
from typing import Callable

import moderngl
import numpy as np

import constants as C
from src.rendering.gpu.feel import DistortionParams
from src.rendering.gpu.layer import FULLSCREEN_QUAD
from src.rendering.gpu.lut import upload_lut
from src.rendering.gpu.sprite_batch import _load_shader

TimedFn = Callable[[str], AbstractContextManager]

_PASS_SHADERS: dict[str, str] = {
    "bloom_extract": "bloom_extract.frag", "blur": "blur.frag",
    "bloom_combine": "bloom_combine.frag", "lut": "lut.frag",
    "vignette": "vignette.frag", "grain": "grain.frag", "crt": "crt.frag",
    "copy": "copy.frag", "distortion": "distortion.frag",
}
# Compile-time array sizes rewritten from constants: file → (placeholder, replacement)
_SHADER_DEFINES: dict[str, tuple[str, str]] = {
    "distortion.frag": ("#define MAX_RIPPLES 4",
                        f"#define MAX_RIPPLES {C.DISTORTION_MAX_RIPPLES}"),
}
_BLOOM_UNIT: int = 1
_LUT_UNIT: int = 2
_GRAIN_SEED_PERIOD: int = 997  # frame counter wraps here to keep float seeds precise


def _load_pass_shader(filename: str) -> str:
    """Load a pass shader, applying any compile-time define rewrite."""
    source = _load_shader(filename)
    if filename in _SHADER_DEFINES:
        placeholder, replacement = _SHADER_DEFINES[filename]
        if placeholder not in source:
            raise RuntimeError(f"{filename} is missing '{placeholder}'")
        source = source.replace(placeholder, replacement)
    return source


def vignette_factor(u: float, v: float, width: int, height: int) -> float:
    """Python reference of vignette.frag: brightness multiplier at UV (u, v)."""
    dx, dy = (u - 0.5) * width, (v - 0.5) * height
    dist = math.hypot(dx, dy) / math.hypot(0.5 * width, 0.5 * height)
    t = min(max((dist - C.VIGNETTE_INNER) / (C.VIGNETTE_OUTER - C.VIGNETTE_INNER), 0.0), 1.0)
    return 1.0 - C.VIGNETTE_STRENGTH * (t * t * (3.0 - 2.0 * t))


class _Target:
    """A half-float colour texture plus its framebuffer."""

    def __init__(self, ctx: moderngl.Context, size: tuple[int, int]) -> None:
        """Allocate a linearly filtered, edge-clamped RGBA16F target."""
        self.texture = ctx.texture(size, 4, dtype="f2")
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.texture.repeat_x = self.texture.repeat_y = False
        self.fbo = ctx.framebuffer(color_attachments=[self.texture])

    def release(self) -> None:
        """Free the framebuffer and texture."""
        self.fbo.release()
        self.texture.release()


class PostStack:
    """Runs the toggleable post passes between the scene composite and the screen."""

    def __init__(
        self,
        ctx: moderngl.Context,
        size: tuple[int, int],
        lut: np.ndarray,
        timed: TimedFn | None = None,
    ) -> None:
        """Compile every pass, upload the LUT, and allocate the buffers."""
        self._ctx = ctx
        self._timed: TimedFn = timed or (lambda _key: nullcontext())
        self.enabled: dict[str, bool] = {n: C.POST_PASS_DEFAULTS[n] for n in C.POST_PASS_ORDER}
        self._frame: int = 0
        vert = _load_shader("post.vert")
        self._progs = {name: ctx.program(vertex_shader=vert, fragment_shader=_load_pass_shader(f))
                       for name, f in _PASS_SHADERS.items()}
        self._quad_vbo = ctx.buffer(array.array("f", FULLSCREEN_QUAD).tobytes())
        self._vaos = {name: ctx.vertex_array(prog, [(self._quad_vbo, "2f", "a_pos")])
                      for name, prog in self._progs.items()}
        self._lut_texture = upload_lut(ctx, lut)
        self._distortion = DistortionParams()
        self._set_static_uniforms(lut.shape[0])
        self._targets: dict[str, _Target] = {}
        self._allocate(size)

    def _set_static_uniforms(self, lut_size: int) -> None:
        """Write uniforms that never change after startup."""
        p = self._progs
        p["bloom_extract"]["u_threshold"].value = C.BLOOM_THRESHOLD
        p["bloom_extract"]["u_knee"].value = C.BLOOM_KNEE
        p["bloom_combine"]["u_bloom"].value = _BLOOM_UNIT
        p["bloom_combine"]["u_intensity"].value = C.BLOOM_INTENSITY
        p["lut"]["u_lut"].value = _LUT_UNIT
        p["lut"]["u_lut_size"].value = float(lut_size)
        p["lut"]["u_strength"].value = C.LUT_STRENGTH
        p["vignette"]["u_strength"].value = C.VIGNETTE_STRENGTH
        p["vignette"]["u_inner"].value = C.VIGNETTE_INNER
        p["vignette"]["u_outer"].value = C.VIGNETTE_OUTER
        p["grain"]["u_amount"].value = C.GRAIN_AMOUNT
        p["distortion"]["u_ripple_width"].value = C.RIPPLE_WIDTH_PX
        p["distortion"]["u_max_offset"].value = C.DISTORTION_MAX_OFFSET_PX
        p["grain"]["u_shadow_scale"].value = C.GRAIN_SHADOW_SCALE
        p["grain"]["u_full_luma"].value = C.GRAIN_FULL_LUMA

    def _allocate(self, size: tuple[int, int]) -> None:
        """Create full-res scene/ping/pong targets and downsampled bloom targets."""
        bloom_size = (max(1, size[0] // C.BLOOM_DOWNSAMPLE), max(1, size[1] // C.BLOOM_DOWNSAMPLE))
        for name in ("scene", "ping", "pong"):
            self._targets[name] = _Target(self._ctx, size)
        for name in ("bloom_a", "bloom_b"):
            self._targets[name] = _Target(self._ctx, bloom_size)
        resolution = (float(size[0]), float(size[1]))
        self._progs["vignette"]["u_resolution"].value = resolution
        self._progs["grain"]["u_resolution"].value = resolution
        self._progs["distortion"]["u_resolution"].value = resolution

    @property
    def size(self) -> tuple[int, int]:
        """Internal resolution of the scene buffer."""
        return self._targets["scene"].fbo.size

    def begin_scene(self) -> moderngl.Framebuffer:
        """Clear the scene buffer to opaque black and return it as a composite target."""
        scene = self._targets["scene"].fbo
        scene.clear(0.0, 0.0, 0.0, 1.0)
        return scene

    def toggle(self, name: str) -> bool:
        """Flip one pass on/off and return its new state."""
        self.enabled[name] = not self.enabled[name]
        return self.enabled[name]

    def set_distortion(self, params: DistortionParams) -> None:
        """Set this frame's Fold ripples / bend / aberration (from Feel.distortion_params)."""
        self._distortion = params

    def render(self, target: moderngl.Framebuffer) -> None:
        """Run every enabled pass on the scene buffer, then copy to `target`."""
        self._frame = (self._frame + 1) % _GRAIN_SEED_PERIOD
        self._progs["grain"]["u_seed"].value = float(self._frame)
        src = self._targets["scene"]
        outputs = [self._targets["ping"], self._targets["pong"]]
        self._ctx.disable(moderngl.BLEND)  # every pass overwrites its target
        for name in C.POST_PASS_ORDER:
            if not self.enabled[name] or (name == "distortion" and not self._distortion.active):
                continue
            dst = outputs[0]
            with self._timed(name):
                self._run_pass(name, src, dst)
            src, outputs = dst, outputs[::-1]
        self._draw("copy", src.texture, target)
        self._ctx.enable(moderngl.BLEND)  # HUD and overlays drawn next need it

    def _run_pass(self, name: str, src: _Target, dst: _Target) -> None:
        """Dispatch one named pass from src into dst."""
        if name == "bloom":
            self._bloom(src, dst)
            return
        if name == "lut":
            self._lut_texture.use(_LUT_UNIT)
        if name == "distortion":
            self._upload_distortion()
        self._draw(name, src.texture, dst.fbo)

    def _upload_distortion(self) -> None:
        """Write the current DistortionParams into the distortion shader."""
        prog, params = self._progs["distortion"], self._distortion
        ripples = params.ripples[:C.DISTORTION_MAX_RIPPLES]
        padded = list(ripples) + [(0.0, 0.0, 0.0, 0.0)] * (C.DISTORTION_MAX_RIPPLES - len(ripples))
        prog["u_ripples"].write(array.array("f", [v for r in padded for v in r]).tobytes())
        prog["u_ripple_count"].value = len(ripples)
        prog["u_bend"].value = params.bend
        prog["u_aberration"].value = params.aberration

    def _bloom(self, src: _Target, dst: _Target) -> None:
        """Bright-pass at low res, blur it, then add it back onto the scene."""
        a, b = self._targets["bloom_a"], self._targets["bloom_b"]
        self._draw("bloom_extract", src.texture, a.fbo)
        bw, bh = a.fbo.size
        blur = self._progs["blur"]
        for _ in range(C.BLOOM_BLUR_PASSES):
            blur["u_direction"].value = (1.0 / bw, 0.0)
            self._draw("blur", a.texture, b.fbo)
            blur["u_direction"].value = (0.0, 1.0 / bh)
            self._draw("blur", b.texture, a.fbo)
        a.texture.use(_BLOOM_UNIT)
        self._draw("bloom_combine", src.texture, dst.fbo)

    def _draw(self, prog_name: str, source: moderngl.Texture, fbo: moderngl.Framebuffer) -> None:
        """Render one fullscreen quad with `prog_name`, sampling `source` on unit 0."""
        fbo.use()
        source.use(0)
        self._vaos[prog_name].render(moderngl.TRIANGLE_STRIP)

    def resize(self, size: tuple[int, int]) -> None:
        """Reallocate every buffer at a new internal resolution."""
        if tuple(size) == self.size:
            return
        for target in self._targets.values():
            target.release()
        self._allocate(size)

    def release(self) -> None:
        """Free all GPU resources owned by the stack."""
        for target in self._targets.values():
            target.release()
        self._lut_texture.release()
        for vao in self._vaos.values():
            vao.release()
        self._quad_vbo.release()
        for prog in self._progs.values():
            prog.release()
