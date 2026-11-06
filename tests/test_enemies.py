"""Tests for enemy entities: TemporalEcho, FoldPredator, TheAnchored."""
from __future__ import annotations

import unittest

import tests.conftest  # noqa: F401
import constants as C


# ---------------------------------------------------------------------------
# TemporalEcho tests
# ---------------------------------------------------------------------------

class TestTemporalEcho(unittest.TestCase):
    """TemporalEcho patrols horizontally, freezes on time_scale=0."""

    def _make(self) -> object:
        from src.entities.enemy import TemporalEcho
        return TemporalEcho(px=100.0, py=50.0, min_x=50.0, max_x=200.0, speed=C.TEMPORAL_ECHO_SPEED)

    def test_moves_right_by_speed(self) -> None:
        e = self._make()
        e.update(1.0)
        self.assertAlmostEqual(e.px, 100.0 + C.TEMPORAL_ECHO_SPEED)

    def test_reverses_at_max_x(self) -> None:
        e = self._make()
        e.px = 200.0
        e.update(1.0)
        self.assertEqual(e.direction, -1)
        self.assertLessEqual(e.px, 200.0)

    def test_reverses_at_min_x(self) -> None:
        e = self._make()
        e.direction = -1
        e.px = 50.0
        e.update(1.0)
        self.assertEqual(e.direction, 1)
        self.assertGreaterEqual(e.px, 50.0)

    def test_time_scale_zero_freezes(self) -> None:
        e = self._make()
        before = e.px
        e.update(0.0)
        self.assertAlmostEqual(e.px, before)

    def test_time_scale_half_slows(self) -> None:
        e = self._make()
        e.update(0.5)
        self.assertAlmostEqual(e.px, 100.0 + C.TEMPORAL_ECHO_SPEED * 0.5)

    def test_reset_restores_position(self) -> None:
        e = self._make()
        e.px = 190.0
        e.direction = -1
        e.reset()
        self.assertAlmostEqual(e.px, 100.0)
        self.assertEqual(e.direction, 1)

    def test_rect_covers_centre(self) -> None:
        e = self._make()
        r = e.rect
        self.assertEqual(r.centerx, int(e.px))
        self.assertEqual(r.centery, int(e.py))
        self.assertEqual(r.width, C.TEMPORAL_ECHO_W)
        self.assertEqual(r.height, C.TEMPORAL_ECHO_H)


# ---------------------------------------------------------------------------
# Frozen timer tests (shared behaviour across enemy types)
# ---------------------------------------------------------------------------

class TestEnemyFrozenTimer(unittest.TestCase):
    def test_frozen_timer_initialises_to_zero(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        self.assertAlmostEqual(e.frozen_timer, 0.0)

    def test_frozen_enemy_does_not_move(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 1.0
        start = e.px
        e.update(time_scale=1.0, dt=1.0 / 60)
        self.assertAlmostEqual(e.px, start)

    def test_frozen_timer_decrements(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 1.0
        e.update(time_scale=1.0, dt=0.5)
        self.assertAlmostEqual(e.frozen_timer, 0.5)

    def test_reset_clears_frozen_timer(self):
        from src.entities.enemy import TemporalEcho
        e = TemporalEcho(px=100.0, py=100.0, min_x=0.0, max_x=200.0, speed=2.0)
        e.frozen_timer = 2.0
        e.reset()
        self.assertAlmostEqual(e.frozen_timer, 0.0)


# ---------------------------------------------------------------------------
# FoldPredator tests
# ---------------------------------------------------------------------------

def _make_predator(px=400.0, py=400.0, level_min=0.0, level_max=800.0):
    from src.entities.fold_predator import FoldPredator
    return FoldPredator(px=px, py=py, level_min=level_min, level_max=level_max)


class TestFoldPredatorPatrol(unittest.TestCase):
    def test_patrol_moves_laterally(self):
        p = _make_predator(px=400.0)
        start = p.px
        p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertNotAlmostEqual(p.px, start)

    def test_patrol_bounces_at_max(self):
        p = _make_predator(px=799.0, level_max=800.0)
        p._direction = 1
        for _ in range(20):
            p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertLessEqual(p.px, 800.0)

    def test_patrol_bounces_at_min(self):
        p = _make_predator(px=1.0, level_min=0.0)
        p._direction = -1
        for _ in range(20):
            p.update(dt=1.0, player_px=10000.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreaterEqual(p.px, 0.0)


class TestFoldPredatorChase(unittest.TestCase):
    def test_enters_chase_when_player_in_range(self):
        from src.entities.fold_predator import _State
        p = _make_predator(px=400.0)
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)

    def test_stays_patrol_when_player_out_of_range(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_CHASE_RANGE
        p = _make_predator(px=400.0)
        far = 400.0 + FOLD_PREDATOR_CHASE_RANGE + 50.0
        p.update(dt=1.0, player_px=far, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PATROL)

    def test_chase_moves_toward_player(self):
        p = _make_predator(px=400.0)
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        start = p.px
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreater(p.px, start)

    def test_chase_moves_left_when_player_left(self):
        p = _make_predator(px=400.0)
        p.update(dt=1.0, player_px=300.0, player_py=400.0, gravity_dir=(0, 1))
        start = p.px
        p.update(dt=1.0, player_px=300.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertLess(p.px, start)

    def test_exits_chase_when_player_leaves_range(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_CHASE_RANGE
        p = _make_predator(px=400.0)
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)
        far = 400.0 + FOLD_PREDATOR_CHASE_RANGE + 200.0
        p.update(dt=1.0, player_px=far, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PATROL)


class TestFoldPredatorPhase(unittest.TestCase):
    def test_phase_fires_after_interval(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_PHASE_INTERVAL
        p = _make_predator(px=400.0)
        p._state = _State.CHASE
        p._phase_cooldown = 0.01
        p.update(dt=0.02, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.PHASE)

    def test_phase_moves_faster_than_chase(self):
        from src.entities.fold_predator import _State
        p_chase = _make_predator(px=400.0)
        p_phase = _make_predator(px=400.0)
        p_chase._state = _State.CHASE
        p_phase._state = _State.PHASE
        p_phase._phase_timer = 10.0  # won't expire this tick
        p_chase.update(dt=0.1, player_px=600.0, player_py=400.0, gravity_dir=(0, 1))
        p_phase.update(dt=0.1, player_px=600.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertGreater(p_phase.px, p_chase.px)

    def test_phase_returns_to_chase_after_duration(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_PHASE_DURATION
        p = _make_predator(px=400.0)
        p._state = _State.PHASE
        p._phase_timer = 0.01
        p.update(dt=0.02, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)


class TestFoldPredatorStun(unittest.TestCase):
    def test_on_gravity_rotate_stuns(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p.on_gravity_rotate()
        self.assertEqual(p._state, _State.STUNNED)

    def test_stun_from_any_state(self):
        from src.entities.fold_predator import _State
        for initial in (_State.PATROL, _State.CHASE, _State.PHASE):
            p = _make_predator()
            p._state = initial
            p.on_gravity_rotate()
            self.assertEqual(p._state, _State.STUNNED, f"from {initial}")

    def test_stun_preserves_pre_stun_state(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p._state = _State.CHASE
        p.on_gravity_rotate()
        self.assertEqual(p._pre_stun_state, _State.CHASE)

    def test_stunned_enemy_does_not_move(self):
        p = _make_predator(px=400.0)
        p.on_gravity_rotate()
        start = p.px
        p.update(dt=0.5, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.px, start)

    def test_stun_expires_and_resumes(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_STUN_DURATION
        p = _make_predator(px=400.0)
        p._state = _State.CHASE
        p.on_gravity_rotate()
        p.update(dt=FOLD_PREDATOR_STUN_DURATION + 0.1,
                 player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertEqual(p._state, _State.CHASE)

    def test_repeated_rotation_refreshes_stun(self):
        from src.entities.fold_predator import _State
        from constants import FOLD_PREDATOR_STUN_DURATION
        p = _make_predator()
        p.on_gravity_rotate()
        p.update(dt=FOLD_PREDATOR_STUN_DURATION * 0.5,
                 player_px=400.0, player_py=400.0, gravity_dir=(0, 1))
        p.on_gravity_rotate()  # rotate again while stunned
        self.assertAlmostEqual(p._stun_timer, FOLD_PREDATOR_STUN_DURATION)


class TestFoldPredatorGravityAware(unittest.TestCase):
    def test_moves_on_y_axis_in_horizontal_gravity(self):
        p = _make_predator(px=400.0, py=400.0)
        from src.entities.fold_predator import _State
        p._state = _State.CHASE
        start_px = p.px
        start_py = p.py
        p.update(dt=1.0, player_px=400.0, player_py=300.0, gravity_dir=(-1, 0))
        self.assertAlmostEqual(p.px, start_px, msg="X should not change in horizontal gravity")
        self.assertNotAlmostEqual(p.py, start_py, msg="Y should change in horizontal gravity")

    def test_moves_on_x_axis_in_vertical_gravity(self):
        p = _make_predator(px=400.0, py=400.0)
        from src.entities.fold_predator import _State
        p._state = _State.CHASE
        start_py = p.py
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.py, start_py, msg="Y should not change in vertical gravity")


class TestFoldPredatorReset(unittest.TestCase):
    def test_reset_returns_to_spawn(self):
        p = _make_predator(px=400.0, py=400.0)
        p.update(dt=1.0, player_px=450.0, player_py=400.0, gravity_dir=(0, 1))
        p.on_gravity_rotate()
        p.reset()
        self.assertAlmostEqual(p.px, 400.0)
        self.assertAlmostEqual(p.py, 400.0)

    def test_reset_clears_stun(self):
        from src.entities.fold_predator import _State
        p = _make_predator()
        p.on_gravity_rotate()
        p.reset()
        self.assertEqual(p._state, _State.PATROL)
        self.assertAlmostEqual(p._stun_timer, 0.0)

    def test_reset_clears_frozen_timer(self):
        p = _make_predator()
        p.frozen_timer = 2.0
        p.reset()
        self.assertAlmostEqual(p.frozen_timer, 0.0)


class TestFoldPredatorFrozenTimerCompat(unittest.TestCase):
    """frozen_timer must work the same as on TemporalEcho (Hawking Emitter compat)."""

    def test_frozen_timer_initialises_zero(self):
        p = _make_predator()
        self.assertAlmostEqual(p.frozen_timer, 0.0)

    def test_frozen_pauses_movement(self):
        p = _make_predator(px=400.0)
        p.frozen_timer = 1.0
        start = p.px
        p.update(dt=1.0, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.px, start)

    def test_frozen_timer_decrements(self):
        p = _make_predator()
        p.frozen_timer = 1.0
        p.update(dt=0.5, player_px=500.0, player_py=400.0, gravity_dir=(0, 1))
        self.assertAlmostEqual(p.frozen_timer, 0.5)


# ---------------------------------------------------------------------------
# TheAnchored tests
# ---------------------------------------------------------------------------

class TestTheAnchored(unittest.TestCase):
    """Tests for TheAnchored enemy — broken-timeline wander/stutter AI."""

    def _make(self, px=200.0, py=400.0, seed=42):
        from src.entities.anchored import TheAnchored
        return TheAnchored(px=px, py=py, level_min=0.0, level_max=800.0, seed=seed)

    def test_initial_state_is_wander(self):
        a = self._make()
        self.assertFalse(a.is_stuttering)

    def test_rect_centred_on_position(self):
        from src.entities.anchored import TheAnchored
        a = self._make(px=200.0, py=400.0)
        r = a.rect
        self.assertEqual(r.centerx, 200)
        self.assertEqual(r.centery, 400)
        self.assertEqual(r.width, a.w)
        self.assertEqual(r.height, a.h)

    def test_moves_laterally_each_tick(self):
        a = self._make()
        px_before = a.px
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertNotEqual(a.px, px_before)

    def test_time_dilation_freezes_movement(self):
        a = self._make()
        px_before = a.px
        a.update(time_scale=0.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a.px, px_before, places=5)

    def test_time_dilation_freezes_stutter_timer(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=200.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.05
        before = a._stutter_cooldown
        a.update(time_scale=0.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a._stutter_cooldown, before, places=5)

    def test_stutter_triggers_after_interval(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        a._wander_timer = 999.0
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)

    def test_stutter_ends_after_duration(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)
        a._stutter_timer = 0.001
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertFalse(a.is_stuttering)

    def test_clamped_to_level_bounds(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=5.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._direction = -1
        for _ in range(200):
            a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertGreaterEqual(a.px, 0.0)
        self.assertLessEqual(a.px, 800.0)

    def test_gravity_rotate_is_noop(self):
        a = self._make()
        px_before = a.px
        py_before = a.py
        a.on_gravity_rotate()
        self.assertEqual(a.px, px_before)
        self.assertEqual(a.py, py_before)

    def test_reset_returns_to_spawn(self):
        a = self._make(px=200.0, py=400.0)
        a.update(time_scale=1.0, dt=1.0, gravity_dir=(0, 1))
        a.reset()
        self.assertAlmostEqual(a.px, 200.0, places=5)
        self.assertAlmostEqual(a.py, 400.0, places=5)
        self.assertFalse(a.is_stuttering)

    def test_frozen_timer_blocks_movement(self):
        a = self._make()
        a.frozen_timer = 2.0
        px_before = a.px
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertAlmostEqual(a.px, px_before, places=5)
        self.assertAlmostEqual(a.frozen_timer, 1.9, places=5)

    def test_frozen_timer_decrements_and_resumes(self):
        a = self._make()
        a.frozen_timer = 0.05
        px_before = a.px
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertEqual(a.frozen_timer, 0.0)
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(0, 1))
        self.assertNotEqual(a.px, px_before)

    def test_horizontal_gravity_moves_y(self):
        from src.entities.anchored import TheAnchored
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        py_before = a.py
        a.update(time_scale=1.0, dt=0.1, gravity_dir=(1, 0))
        self.assertNotEqual(a.py, py_before)

    def test_draw_does_not_crash(self):
        import pygame
        surface = pygame.Surface((800, 600))
        a = self._make()
        a.draw(surface, (0.0, 0.0))

    def test_stutter_draw_color_differs(self):
        from src.entities.anchored import TheAnchored
        import constants as C
        a = TheAnchored(px=400.0, py=400.0, level_min=0.0, level_max=800.0, seed=0)
        a._stutter_cooldown = 0.0
        a.update(time_scale=1.0, dt=0.001, gravity_dir=(0, 1))
        self.assertTrue(a.is_stuttering)
        self.assertNotEqual(C.ANCHORED_COLOR, C.ANCHORED_STUTTER_COLOR)


if __name__ == "__main__":
    unittest.main()
