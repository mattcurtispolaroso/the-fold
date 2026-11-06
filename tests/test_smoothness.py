"""Engine Session 2 — smoothness: render interpolation and frame-rate-independent camera.

The judder test replays a jittery frame-time sequence like the one measured on
the dev Mac (16–19 ms frames against a 60 Hz physics step) and compares
on-screen motion of a constant-speed object drawn raw vs interpolated.
"""
from __future__ import annotations

import random
import statistics
import unittest

import constants as C
from src.rendering.camera import Camera
from src.rendering.interpolation import RenderInterpolator, lerp, step_alpha

_SPEED = 4.0  # px per physics step


class _Body:
    """Anything with px/py, like the player or an enemy."""

    def __init__(self) -> None:
        """At the origin."""
        self.px, self.py = 0.0, 0.0


def _simulate(frame_ms: list[float], interpolate: bool) -> list[float]:
    """Run the game's accumulator loop; return the drawn x of a constant-speed body per frame."""
    body, interp = _Body(), RenderInterpolator()
    acc, drawn = 0.0, []
    for ms in frame_ms:
        acc += ms / 1000.0
        while acc >= C.PHYSICS_DT:
            interp.begin_step(body, [])
            body.px += _SPEED
            acc -= C.PHYSICS_DT
        if interpolate:
            drawn.append(interp.player_pos(body, step_alpha(acc, C.PHYSICS_DT))[0])
        else:
            drawn.append(body.px)
    return drawn


def _speed_jitter(drawn: list[float], frame_ms: list[float]) -> float:
    """Std-dev of on-screen speed (px/s) — 0 means perfectly even motion."""
    speeds = [(b - a) / (ms / 1000.0) for a, b, ms in zip(drawn, drawn[1:], frame_ms[1:])]
    return statistics.pstdev(speeds[10:])


class TestRenderInterpolation(unittest.TestCase):
    """Interpolation removes the 0-step / 2-step judder."""

    def setUp(self) -> None:
        """Frame times like the measured no-vsync run: mostly 16–17 ms, some 18–19."""
        rng = random.Random(3)
        self.frames = [rng.choice([16.0, 16.0, 17.0, 17.0, 17.0, 18.0, 19.0]) for _ in range(600)]

    def test_raw_rendering_judders(self) -> None:
        """Baseline: drawing raw physics state stutters (some frames move 0, some 2 steps)."""
        drawn = _simulate(self.frames, interpolate=False)
        steps = {round((b - a) / _SPEED) for a, b in zip(drawn, drawn[1:])}
        self.assertTrue({0, 2} & steps, "expected repeated or doubled steps")

    def test_interpolation_cuts_speed_jitter(self) -> None:
        """Interpolated on-screen speed is at least 5× steadier than raw."""
        raw = _speed_jitter(_simulate(self.frames, False), self.frames)
        smooth = _speed_jitter(_simulate(self.frames, True), self.frames)
        self.assertLess(smooth * 5, raw)

    def test_120hz_display_is_smooth(self) -> None:
        """At 120 fps (half the frames get no physics step) motion is still even."""
        frames = [8.33] * 600
        drawn = _simulate(frames, True)
        deltas = [b - a for a, b in zip(drawn, drawn[1:])][10:]
        self.assertLess(max(deltas) - min(deltas), 0.05 * _SPEED)

    def test_teleport_snaps_instead_of_streaking(self) -> None:
        """A move larger than TELEPORT_SNAP_PX draws at the destination immediately."""
        body, interp = _Body(), RenderInterpolator()
        interp.begin_step(body, [])
        body.px = C.TELEPORT_SNAP_PX + 50.0
        self.assertEqual(interp.player_pos(body, 0.1), (body.px, 0.0))

    def test_snap_forgets_previous(self) -> None:
        """After snap() (level reset) the current position is drawn."""
        body, interp = _Body(), RenderInterpolator()
        interp.begin_step(body, [])
        body.px = 10.0
        interp.snap()
        self.assertEqual(interp.player_pos(body, 0.0), (10.0, 0.0))

    def test_enemy_offset_and_unknown_enemy(self) -> None:
        """Recorded enemies interpolate; enemies spawned since the step draw at rest."""
        e, newcomer, interp = _Body(), _Body(), RenderInterpolator()
        interp.begin_step(_Body(), [e])
        e.px = 8.0
        self.assertEqual(interp.enemy_offset(e, 0.25), (-6.0, 0.0))
        self.assertEqual(interp.enemy_offset(newcomer, 0.25), (0.0, 0.0))

    def test_alpha_clamped(self) -> None:
        """Alpha stays in [0, 1] whatever the accumulator holds."""
        self.assertEqual(step_alpha(-1.0, C.PHYSICS_DT), 0.0)
        self.assertEqual(step_alpha(1.0, C.PHYSICS_DT), 1.0)
        self.assertEqual(lerp(2.0, 4.0, 0.5), 3.0)


class TestCameraFrameRateIndependence(unittest.TestCase):
    """The camera follows the same path at any frame rate."""

    def _follow(self, fps: int, seconds: float = 1.0) -> tuple[float, float]:
        """Camera chasing a target that jumps 400px right; returns position after `seconds`."""
        cam = Camera(800, 600)
        cam.x, cam.y = 0.0, 0.0
        for _ in range(round(seconds * fps)):
            cam.update(400.0, 0.0, 1.0 / fps)
        return cam.x, cam.y

    def test_same_path_at_30_60_120_fps(self) -> None:
        """Positions after 0.2 s and 1 s agree within 0.5px across frame rates.

        (Durations chosen so every frame rate runs a whole number of frames.)
        """
        for seconds in (0.2, 1.0):
            xs = [self._follow(fps, seconds)[0] for fps in (30, 60, 120)]
            self.assertLess(max(xs) - min(xs), 0.5, f"t={seconds}: {xs}")

    def test_dead_zone_edge_is_continuous(self) -> None:
        """Just outside the dead zone the camera barely moves (no jump at the edge)."""
        cam = Camera(800, 600)
        cam.x = 100.0
        cam.update(100.0 + C.CAMERA_DEAD_ZONE_X + 0.5, 0.0, 1 / 60)
        self.assertLess(cam.x - 100.0, 0.1)

    def test_shake_is_smooth_over_time(self) -> None:
        """Consecutive 120 fps shake samples change gradually (not white noise)."""
        cam = Camera(800, 600)
        cam.shake(10.0, 1.0)
        samples = []
        for _ in range(60):
            cam.update(cam.x, cam.y, 1 / 120)
            samples.append(cam._shake_offset_x)
        jumps = [abs(b - a) for a, b in zip(samples, samples[1:])]
        self.assertLess(max(jumps), 10.0 * 0.7)   # white noise jumps up to 2× intensity
