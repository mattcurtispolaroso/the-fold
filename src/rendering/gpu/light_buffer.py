"""2D light buffer (TA-3) — ambient + point/spot lights rendered to a half-float FBO.

The buffer holds a per-pixel light multiplier (1.0 = unlit look, >1.0 = mild
overbright). ParallaxStack.composite() multiplies the lit layers (mid, play)
by it. Levels without a "lights" key are not lit at all: render() returns None
and the composite runs unchanged.
"""
from __future__ import annotations

import array
import math
from dataclasses import dataclass, field

import moderngl

import constants as C
from src.levels.light_data import LightDef, LightKind
from src.rendering.gpu.layer import FULLSCREEN_QUAD
from src.rendering.gpu.sprite_batch import _load_shader

# Cone bounds that make smoothstep() return 1 for every direction (point lights)
POINT_LIGHT_CONE: tuple[float, float] = (-2.0, -1.0)
_MAX_LIGHTS_DEFINE: str = "#define MAX_LIGHTS 11"


@dataclass
class PackedLights:
    """Uniform-ready light arrays, padded to LIGHT_SHADER_SLOTS entries."""

    ambient: tuple[float, float, float]
    count: int
    positions: list[float] = field(default_factory=list)  # 2 floats per slot
    colors: list[float] = field(default_factory=list)     # 3 floats per slot
    radii: list[float] = field(default_factory=list)      # 1 float per slot
    dirs: list[float] = field(default_factory=list)       # 2 floats per slot
    cones: list[float] = field(default_factory=list)      # 2 floats per slot


def make_player_light(x: float, y: float) -> LightDef:
    """Return the warm point light that follows the player (world coords)."""
    return LightDef(kind=LightKind.POINT, x=x, y=y, radius=C.PLAYER_LIGHT_RADIUS,
                    color=C.PLAYER_LIGHT_COLOR, intensity=C.PLAYER_LIGHT_INTENSITY)


def spot_direction(angle_deg: float) -> tuple[float, float]:
    """Unit vector for a spot angle (CCW from +x) in Y-down screen space."""
    rad = math.radians(angle_deg)
    return (math.cos(rad), -math.sin(rad))


def spot_cone(spread_deg: float) -> tuple[float, float]:
    """(cos outer, cos inner) for a cone of full width spread_deg."""
    half = math.radians(spread_deg / 2.0)
    return (math.cos(half), math.cos(half * C.LIGHT_SPOT_INNER_FRAC))


def pack_lights(lights: list[LightDef], cam_offset: tuple[float, float]) -> PackedLights:
    """Convert world-space lights to padded screen-space uniform arrays.

    The first ambient light sets the ambient term (LIGHT_DEFAULT_AMBIENT if
    none). At most LIGHT_SHADER_SLOTS point/spot lights are packed.
    """
    ambients = [l for l in lights if l.kind is LightKind.AMBIENT]
    emitters = [l for l in lights if l.kind is not LightKind.AMBIENT][:C.LIGHT_SHADER_SLOTS]
    ambient = C.LIGHT_DEFAULT_AMBIENT
    if ambients:
        a = ambients[0]
        ambient = tuple(c * a.intensity for c in a.color)
    packed = PackedLights(ambient=ambient, count=len(emitters))
    ox, oy = cam_offset
    for light in emitters:
        is_spot = light.kind is LightKind.SPOT
        packed.positions += [light.x + ox, light.y + oy]
        packed.colors += [c * light.intensity for c in light.color]
        packed.radii.append(light.radius)
        packed.dirs += list(spot_direction(light.angle)) if is_spot else [1.0, 0.0]
        packed.cones += list(spot_cone(light.spread)) if is_spot else list(POINT_LIGHT_CONE)
    _pad(packed, C.LIGHT_SHADER_SLOTS - packed.count)
    return packed


def _pad(packed: PackedLights, slots: int) -> None:
    """Append `slots` inert entries so every array matches the shader's size."""
    packed.positions += [0.0, 0.0] * slots
    packed.colors += [0.0, 0.0, 0.0] * slots
    packed.radii += [1.0] * slots
    packed.dirs += [1.0, 0.0] * slots
    packed.cones += list(POINT_LIGHT_CONE) * slots


class LightBuffer:
    """Owns the light FBO and the accumulation shader; one fullscreen draw per frame."""

    def __init__(self, ctx: moderngl.Context, size: tuple[int, int]) -> None:
        """Compile the light shader and allocate the half-float light FBO."""
        self._ctx = ctx
        frag = _load_shader("light.frag")
        if _MAX_LIGHTS_DEFINE not in frag:
            raise RuntimeError("light.frag is missing its MAX_LIGHTS define")
        frag = frag.replace(_MAX_LIGHTS_DEFINE, f"#define MAX_LIGHTS {C.LIGHT_SHADER_SLOTS}")
        self._prog = ctx.program(vertex_shader=_load_shader("upscale.vert"), fragment_shader=frag)
        self._prog["u_max_brightness"].value = C.LIGHT_BUFFER_MAX_BRIGHTNESS
        self._quad_vbo = ctx.buffer(array.array("f", FULLSCREEN_QUAD).tobytes())
        self._quad_vao = ctx.vertex_array(self._prog, [(self._quad_vbo, "2f", "a_pos")])
        self.texture: moderngl.Texture
        self.fbo: moderngl.Framebuffer
        self._allocate(size)

    def _allocate(self, size: tuple[int, int]) -> None:
        """Create the half-float texture (allows values above 1.0) and its FBO."""
        self.texture = self._ctx.texture(size, 4, dtype="f2")
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo = self._ctx.framebuffer(color_attachments=[self.texture])
        self._prog["u_resolution"].value = (float(size[0]), float(size[1]))

    @property
    def size(self) -> tuple[int, int]:
        """Pixel size of the light buffer."""
        return self.fbo.size

    def render(
        self,
        level_lights: list[LightDef],
        player_pos: tuple[float, float],
        cam_offset: tuple[float, float],
    ) -> moderngl.Texture | None:
        """Render this frame's light buffer; return None when the level is unlit."""
        if not level_lights:
            return None
        packed = pack_lights(level_lights + [make_player_light(*player_pos)], cam_offset)
        self._upload(packed)
        self.fbo.use()
        self._quad_vao.render(moderngl.TRIANGLE_STRIP)
        return self.texture

    def _upload(self, packed: PackedLights) -> None:
        """Write the packed arrays into the shader uniforms."""
        self._prog["u_ambient"].value = packed.ambient
        self._prog["u_light_count"].value = packed.count
        for name, values in (("u_light_pos", packed.positions), ("u_light_color", packed.colors),
                             ("u_light_radius", packed.radii), ("u_light_dir", packed.dirs),
                             ("u_light_cone", packed.cones)):
            self._prog[name].write(array.array("f", values).tobytes())

    def resize(self, size: tuple[int, int]) -> None:
        """Reallocate at a new size; a no-op when the size is unchanged."""
        if tuple(size) == self.size:
            return
        self.fbo.release()
        self.texture.release()
        self._allocate(size)

    def release(self) -> None:
        """Free all GPU resources owned by the light buffer."""
        self.fbo.release()
        self.texture.release()
        self._quad_vao.release()
        self._quad_vbo.release()
        self._prog.release()
