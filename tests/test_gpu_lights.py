"""Tests for the TA-3 2D light buffer.

Schema and packing tests always run. GPU tests render through a standalone
ModernGL context and read pixels back; they skip when no GPU is available.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")

import numpy as np
import pygame

import constants as C
from src.levels.level_data import LevelData
from src.levels.light_data import LightDef, LightKind, parse_lights
from src.rendering.gpu.light_buffer import (
    POINT_LIGHT_CONE, make_player_light, pack_lights, spot_cone, spot_direction,
)

_SIZE = (200, 100)
_CENTER = (100.0, 50.0)
_AMBIENT = [0.2, 0.3, 0.4]
_TOL = 0.01  # half-float precision is ~0.001 near 1.0


def _point(x: float, y: float, radius: float = 40.0,
           color=(1.0, 0.5, 0.25), intensity: float = 1.0) -> dict:
    """Return a point-light JSON entry."""
    return {"type": "point", "x": x, "y": y, "radius": radius,
            "color": list(color), "intensity": intensity}


def _ambient_entry(color=_AMBIENT) -> dict:
    """Return an ambient-light JSON entry."""
    return {"type": "ambient", "color": list(color)}


class TestLightSchema(unittest.TestCase):
    """The optional "lights" key in level JSON."""

    _BASE = {"name": "t", "gravity_start": [0, 1], "spawn": [0, 0],
             "goal": {"x": 0, "y": 0, "w": 10, "h": 10}}

    def test_levels_without_lights_are_unlit(self) -> None:
        """No "lights" key means an empty list (the level renders unlit)."""
        level = LevelData.from_dict(dict(self._BASE))
        self.assertEqual(level.lights, [])
        self.assertNotIn("lights", level.to_dict())

    def test_round_trip(self) -> None:
        """Ambient, point and spot lights survive to_dict → from_dict."""
        spot = {"type": "spot", "x": 5, "y": 6, "radius": 300, "angle": 270,
                "spread": 40, "color": [0.8, 0.5, 0.2], "intensity": 0.9}
        level = LevelData.from_dict(dict(self._BASE, lights=[_ambient_entry(), _point(1, 2), spot]))
        again = LevelData.from_dict(level.to_dict())
        self.assertEqual(again.lights, level.lights)
        self.assertEqual([l.kind for l in again.lights],
                         [LightKind.AMBIENT, LightKind.POINT, LightKind.SPOT])

    def test_values_are_clamped(self) -> None:
        """Radius, intensity, colour and spread are clamped to safe ranges."""
        light = parse_lights([{"type": "spot", "radius": 1e9, "intensity": 99,
                               "color": [2.0, -1.0, 0.5], "spread": 999}])[0]
        self.assertEqual(light.radius, C.LIGHT_RADIUS_MAX)
        self.assertEqual(light.intensity, C.LIGHT_INTENSITY_MAX)
        self.assertEqual(light.color, (1.0, 0.0, 0.5))
        self.assertEqual(light.spread, C.LIGHT_SPREAD_MAX)

    def test_unknown_types_dropped(self) -> None:
        """Unknown, missing or non-object entries are skipped, not fatal."""
        lights = parse_lights([{"type": "laser"}, {}, "point", _point(0, 0)])
        self.assertEqual(len(lights), 1)

    def test_light_count_capped(self) -> None:
        """At most LIGHT_MAX_PER_LEVEL emitters and one ambient survive parsing."""
        raw = [_ambient_entry(), _ambient_entry()] + [_point(i, 0) for i in range(15)]
        lights = parse_lights(raw)
        self.assertEqual(sum(l.kind is LightKind.AMBIENT for l in lights), 1)
        self.assertEqual(len(lights) - 1, C.LIGHT_MAX_PER_LEVEL)

    def test_malformed_lights_falls_back(self) -> None:
        """A non-list "lights" value makes load() use the fallback level."""
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(dict(self._BASE, lights={"type": "point"}), f)
        try:
            self.assertEqual(LevelData.load(f.name).name, "Fallback Level")
        finally:
            os.unlink(f.name)

    def test_level_01_is_lit_for_vertical_slice(self) -> None:
        """level_01 has an ambient light and 3 point lights (vertical-slice target)."""
        lights = LevelData.load("levels/level_01.json").lights
        self.assertEqual(sum(l.kind is LightKind.AMBIENT for l in lights), 1)
        self.assertEqual(sum(l.kind is LightKind.POINT for l in lights), 3)


class TestLightPacking(unittest.TestCase):
    """World → screen conversion and padded uniform arrays (no GPU)."""

    def test_arrays_padded_to_shader_slots(self) -> None:
        """Every array has exactly LIGHT_SHADER_SLOTS entries regardless of count."""
        packed = pack_lights([LightDef(LightKind.POINT)], (0.0, 0.0))
        n = C.LIGHT_SHADER_SLOTS
        self.assertEqual(packed.count, 1)
        self.assertEqual((len(packed.positions), len(packed.colors), len(packed.radii),
                          len(packed.dirs), len(packed.cones)), (2 * n, 3 * n, n, 2 * n, 2 * n))

    def test_positions_follow_camera(self) -> None:
        """Light positions are shifted into screen space by the camera offset."""
        packed = pack_lights([LightDef(LightKind.POINT, x=500, y=400)], (-300.0, -100.0))
        self.assertEqual(packed.positions[:2], [200.0, 300.0])

    def test_color_premultiplied_by_intensity(self) -> None:
        """The shader receives colour × intensity."""
        packed = pack_lights([LightDef(LightKind.POINT, color=(1.0, 0.5, 0.0), intensity=2.0)],
                             (0.0, 0.0))
        self.assertEqual(packed.colors[:3], [2.0, 1.0, 0.0])

    def test_default_ambient_when_none_declared(self) -> None:
        """A lit level with no ambient entry gets LIGHT_DEFAULT_AMBIENT."""
        self.assertEqual(pack_lights([LightDef(LightKind.POINT)], (0, 0)).ambient,
                         C.LIGHT_DEFAULT_AMBIENT)

    def test_point_lights_use_full_cone(self) -> None:
        """Point lights get the cone bounds that light every direction."""
        packed = pack_lights([LightDef(LightKind.POINT)], (0, 0))
        self.assertEqual(tuple(packed.cones[:2]), POINT_LIGHT_CONE)

    def test_spot_angle_270_points_down_screen(self) -> None:
        """Angle 270° is straight down in Y-down screen space."""
        dx, dy = spot_direction(270.0)
        self.assertAlmostEqual(dx, 0.0)
        self.assertAlmostEqual(dy, 1.0)

    def test_spot_cone_inner_inside_outer(self) -> None:
        """The full-strength inner cone is narrower than the outer cone."""
        outer, inner = spot_cone(40.0)
        self.assertGreater(inner, outer)

    def test_player_light_tracks_position(self) -> None:
        """The player light sits exactly at the given world position."""
        light = make_player_light(123.0, 456.0)
        self.assertEqual((light.x, light.y, light.kind), (123.0, 456.0, LightKind.POINT))


class TestLightBufferGPU(unittest.TestCase):
    """Real light accumulation via a standalone context (skipped without a GPU)."""

    def setUp(self) -> None:
        """Create a context and a light buffer."""
        try:
            import moderngl
            self.ctx = moderngl.create_standalone_context()
        except Exception:
            self.skipTest("No GPU available")
        from src.rendering.gpu.light_buffer import LightBuffer
        self.buffer = LightBuffer(self.ctx, _SIZE)
        self.far_player = (-10_000.0, -10_000.0)  # keeps the player light off-screen

    def tearDown(self) -> None:
        """Release GPU resources."""
        if getattr(self, "ctx", None) is None:
            return
        self.buffer.release()
        self.ctx.release()

    def _render(self, raw_lights: list[dict], player=None) -> np.ndarray:
        """Render and return the light buffer as float RGB, shape (h, w, 3), row 0 = top."""
        tex = self.buffer.render(parse_lights(raw_lights), player or self.far_player, (0.0, 0.0))
        w, h = _SIZE
        data = np.frombuffer(tex.read(), dtype=np.float16).reshape(h, w, 4)
        return data[::-1, :, :3].astype(np.float32)

    def test_unlit_level_returns_none(self) -> None:
        """No level lights → no light buffer, so the composite stays unlit."""
        self.assertIsNone(self.buffer.render([], (0.0, 0.0), (0.0, 0.0)))

    def test_ambient_only_is_uniform(self) -> None:
        """With only ambient light every pixel equals the ambient colour."""
        img = self._render([_ambient_entry()])
        np.testing.assert_allclose(img[0, 0], _AMBIENT, atol=_TOL)
        np.testing.assert_allclose(img[-1, -1], _AMBIENT, atol=_TOL)

    def test_point_light_adds_to_ambient(self) -> None:
        """At a point light's centre: ambient + colour × intensity; beyond its radius: ambient."""
        img = self._render([_ambient_entry(), _point(*_CENTER, color=(0.5, 0.25, 0.125))])
        cx, cy = int(_CENTER[0]), int(_CENTER[1])
        np.testing.assert_allclose(img[cy, cx], [0.7, 0.55, 0.525], atol=0.03)
        np.testing.assert_allclose(img[0, 0], _AMBIENT, atol=_TOL)  # 100+ px from a 40 px light

    def test_overlapping_lights_are_additive(self) -> None:
        """Two identical lights at one spot add exactly twice one light's contribution."""
        one = self._render([_ambient_entry(), _point(*_CENTER, color=(0.2, 0.2, 0.2))])
        two = self._render([_ambient_entry(), _point(*_CENTER, color=(0.2, 0.2, 0.2)),
                            _point(*_CENTER, color=(0.2, 0.2, 0.2))])
        ambient = np.array(_AMBIENT, dtype=np.float32)
        np.testing.assert_allclose(two - ambient, 2 * (one - ambient), atol=_TOL)

    def test_brightness_is_capped(self) -> None:
        """Stacked lights never exceed LIGHT_BUFFER_MAX_BRIGHTNESS."""
        img = self._render([_point(*_CENTER, color=(1, 1, 1), intensity=C.LIGHT_INTENSITY_MAX)
                            for _ in range(3)])
        self.assertLessEqual(float(img.max()), C.LIGHT_BUFFER_MAX_BRIGHTNESS + _TOL)

    def test_player_light_follows_player(self) -> None:
        """The player light brightens the area around the given player position."""
        left = self._render([_ambient_entry()], player=(30.0, 50.0))
        right = self._render([_ambient_entry()], player=(170.0, 50.0))
        self.assertGreater(left[50, 30].sum(), right[50, 30].sum())
        self.assertGreater(right[50, 170].sum(), left[50, 170].sum())

    def test_spot_light_only_lights_its_cone(self) -> None:
        """A downward spot lights pixels below it and not pixels above it."""
        spot = {"type": "spot", "x": 100, "y": 50, "radius": 60, "angle": 270,
                "spread": 60, "color": [1, 1, 1]}
        img = self._render([_ambient_entry(), spot])
        self.assertGreater(img[70, 100].sum(), sum(_AMBIENT) + 0.1)   # below: lit
        np.testing.assert_allclose(img[30, 100], _AMBIENT, atol=_TOL)  # above: ambient only

    def test_resize(self) -> None:
        """resize() reallocates the buffer; the same size is a no-op."""
        self.buffer.resize((64, 32))
        self.assertEqual(self.buffer.size, (64, 32))
        tex = self.buffer.texture
        self.buffer.resize((64, 32))
        self.assertIs(self.buffer.texture, tex)

    def test_composite_multiplies_only_lit_layers(self) -> None:
        """Light 0.5 halves the play layer but leaves the sky layer untouched."""
        from src.rendering.gpu.layer import ParallaxStack
        pygame.init()
        stack = ParallaxStack(self.ctx, _SIZE, {})
        light = self.buffer.render(parse_lights([_ambient_entry([0.5, 0.5, 0.5])]),
                                   self.far_player, (0.0, 0.0))
        target = self.ctx.simple_framebuffer(_SIZE, components=4)
        results = []
        for layer in ("sky", "play"):
            stack.begin_frame()
            stack.layers[layer].fbo.clear(1.0, 1.0, 1.0, 1.0)
            target.clear(0.0, 0.0, 0.0, 1.0)
            stack.composite(target, light)
            results.append(target.read(components=4)[0])
        target.release()
        stack.release()
        self.assertEqual(results[0], 255)                 # sky: unlit
        self.assertAlmostEqual(results[1], 128, delta=2)  # play: × 0.5
