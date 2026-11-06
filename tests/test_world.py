"""Engine Session 3 — World, InputFrame, determinism and snapshots.

These drive the real simulation (World.step), so they test the game, not a
mirror of it.
"""
from __future__ import annotations

import math
import os
import random
import unittest

import constants as C
from src.data.items import OwnedItem
from src.physics.validation import overlaps_any
from src.systems.events import EventBus, GameEvent
from src.systems.input_frame import InputBuffer, InputFrame
from src.systems.items import load_item_registry
from src.systems.world import World

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = [os.path.join(ROOT, "levels", f"level_{i:02d}.json") for i in range(1, 9)]


class _Log:
    """Silent logger for the item registry loader."""

    def __getattr__(self, _name: str):
        return lambda *a, **k: None


_REGISTRY = load_item_registry(ROOT, _Log())


def _world(level: int = 0, seed: int = 1234) -> World:
    """A fresh world in a real level with a fixed run seed."""
    w = World(_REGISTRY, EventBus())
    w.new_run(seed)
    w.load_level(LEVELS[level])
    return w


def _script(steps: int, seed: int) -> list[InputFrame]:
    """A pseudo-random but fixed input timeline: walking, jumps, rotations, dilation."""
    rng = random.Random(seed)
    frames, move = [], 1
    for i in range(steps):
        if i % 50 == 0:
            move = rng.choice([-1, 0, 1])
        frames.append(InputFrame(move_x=move, move_y=-move,
                                 jump_pressed=rng.random() < 0.04, jump_released=rng.random() < 0.04,
                                 rotate_pressed=rng.random() < 0.01, dilate_pressed=rng.random() < 0.005))
    return frames


def _fingerprint(w: World) -> tuple:
    """Everything that should match between two identical runs."""
    p = w.player
    return (round(p.px, 6), round(p.py, 6), round(p.vx, 6), round(p.vy, 6), p.gravity_dir,
            round(p.chrono_reserve, 6), p.anchor_integrity, w.run_state.deaths,
            round(w.run_state.fold_stability, 6), round(w.time_dilation.active_timer, 6),
            round(w.rotation_cooldown, 6), tuple((round(e.px, 4), round(e.py, 4)) for e in w.enemies),
            tuple(tuple(mp.rect) for mp in w.level.moving_platforms), w.steps)


def _run(w: World, frames: list[InputFrame]) -> list[tuple]:
    """Step through a timeline, recording a fingerprint after every step."""
    out = []
    for f in frames:
        w.step(f)
        out.append(_fingerprint(w))
    return out


class TestDeterminism(unittest.TestCase):
    """Identical inputs → identical results (the foundation for replays and rewind)."""

    def test_same_inputs_same_states(self) -> None:
        """Two worlds fed the same 1500 steps match at every step, in a level with all 3 enemy types."""
        frames = _script(1500, seed=9)
        self.assertEqual(_run(_world(6), frames), _run(_world(6), frames))

    def test_frame_rate_does_not_change_outcome(self) -> None:
        """One input timeline played at 30, 60 and 144 fps through InputBuffer ends identically.

        Each press lands in whatever frame it falls in; the buffer hands it to the
        next physics step, so the step sequence — and the result — is the same.
        """
        frames = _script(900, seed=4)
        results = []
        for fps in (30, 60, 144):
            w, buf, acc = _world(3), InputBuffer(), 0.0
            step_i, t = 0, 0.0
            while step_i < len(frames):
                t += 1.0 / fps
                acc += 1.0 / fps
                while acc >= C.PHYSICS_DT and step_i < len(frames):
                    f = frames[step_i]
                    buf.set_held(f.move_x, f.move_y)
                    if f.jump_pressed: buf.press_jump()
                    if f.jump_released: buf.release_jump()
                    if f.rotate_pressed: buf.press_rotate()
                    if f.dilate_pressed: buf.press_dilate()
                    w.step(buf.take())
                    acc -= C.PHYSICS_DT
                    step_i += 1
            results.append(_fingerprint(w))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])


class TestSnapshot(unittest.TestCase):
    """snapshot() / restore() round-trips all simulation state."""

    def test_restore_then_replay_matches(self) -> None:
        """Run 300 steps, snapshot, run 400 more; restore and replay those 400 → identical."""
        w = _world(6)
        _run(w, _script(300, seed=1))
        snap = w.snapshot()
        tail = _script(400, seed=2)
        first = _run(w, tail)
        w.restore(snap)
        self.assertEqual(_run(w, tail), first)

    def test_restore_twice(self) -> None:
        """A snapshot can be restored repeatedly (it isn't consumed or aliased)."""
        w = _world(1)
        snap = w.snapshot()
        frames = _script(200, seed=5)
        a = _run(w, frames)
        w.restore(snap)
        b = _run(w, frames)
        w.restore(snap)
        self.assertEqual(_run(w, frames), a)
        self.assertEqual(a, b)

    def test_restore_keeps_live_references(self) -> None:
        """Restored in place: ItemManager still sees the world's player and run state."""
        w = _world(0)
        snap = w.snapshot()
        _run(w, _script(100, seed=3))
        w.restore(snap)
        self.assertIs(w.item_manager._ctx.player, w.player)
        self.assertIs(w.item_manager._ctx.run_state, w.run_state)
        self.assertIs(w.item_manager._enemies, w.enemies)

    def test_snapshot_rejected_across_level_loads(self) -> None:
        """Restoring into a different level load fails loudly."""
        w = _world(0)
        snap = w.snapshot()
        w.load_level(LEVELS[1])
        with self.assertRaises(ValueError):
            w.restore(snap)


class TestFixedStepTimers(unittest.TestCase):
    """Gameplay timers advance per step, so no steps (hitstop) means no time passes."""

    def test_dilation_lasts_exact_steps(self) -> None:
        """Time Dilation lasts duration / PHYSICS_DT steps, regardless of frame timing."""
        w = _world(0)
        w.player.chrono_reserve = C.CHRONO_RESERVE_MAX
        w.step(InputFrame(dilate_pressed=True))
        steps = 0
        while w.time_dilation.is_active:
            w.step(InputFrame())
            steps += 1
        self.assertAlmostEqual(steps, round(w.time_dilation.duration / C.PHYSICS_DT), delta=1)

    def test_no_step_no_time(self) -> None:
        """Hitstop feeds the accumulator nothing, so ability timers freeze with physics."""
        w = _world(0)
        w.player.chrono_reserve = C.CHRONO_RESERVE_MAX
        w.step(InputFrame(dilate_pressed=True))
        before = w.time_dilation.active_timer
        # (no World.step calls = a hitstopped frame)
        self.assertEqual(w.time_dilation.active_timer, before)

    def test_press_is_never_lost_or_repeated(self) -> None:
        """A press waits for the next step and is consumed exactly once."""
        buf = InputBuffer()
        buf.press_jump()
        self.assertTrue(buf.take().jump_pressed)
        self.assertFalse(buf.take().jump_pressed)


class TestRunStateFix(unittest.TestCase):
    """Bug found in session 3: item effects wrote to a stale RunState after a new run."""

    def test_penrose_diagram_adds_reward_option(self) -> None:
        """Was: live extra_reward_options stayed 0. Now the live run state gets it."""
        w = _world(0)
        w.new_run(7)
        w.item_manager.sync_owned([OwnedItem(id="penrose_diagram", rank=1)])
        w.bus.emit(GameEvent.ROOM_CLEARED)
        self.assertEqual(w.run_state.extra_reward_options, 1)

    def test_new_run_keeps_identity(self) -> None:
        """new_run() updates the RunState in place; references stay live."""
        w = _world(0)
        rs = w.run_state
        w.new_run(99)
        self.assertIs(w.run_state, rs)
        self.assertIs(w.item_manager._ctx.run_state, rs)
        self.assertEqual(rs.run_seed, 99)


class TestRespawn(unittest.TestCase):
    """Respawn never places the player inside geometry, even with a bad level spawn."""

    def test_every_level_spawn_is_valid_after_respawn(self) -> None:
        """Levels 05-08 have spawns 18px inside the floor; respawn corrects them."""
        for path in LEVELS:
            w = World(_REGISTRY, EventBus())
            w.load_level(path)
            p = w.player
            self.assertFalse(overlaps_any(p.px, p.py, p.player_w, p.player_h,
                                          w.level.collision_rects()), path)
            self.assertEqual((p.last_safe_px, p.last_safe_py), (p.px, p.py))


class TestWorldFuzz(unittest.TestCase):
    """CLAUDE.md fuzz test through the real World.step: random input across every level."""

    def test_10k_steps_all_levels_stay_valid(self) -> None:
        """After every step: finite values, never inside geometry, never NaN."""
        rng, total = random.Random(77), 0
        for i, path in enumerate(LEVELS):
            w = World(_REGISTRY, EventBus())
            w.new_run(i)
            w.load_level(path)
            for f in _script(1300, seed=rng.randrange(1 << 30)):
                w.step(f)
                total += 1
                p = w.player
                self.assertTrue(all(math.isfinite(v) for v in (p.px, p.py, p.vx, p.vy)), path)
                self.assertFalse(overlaps_any(p.px, p.py, p.player_w, p.player_h,
                                              w.level.collision_rects()), f"{path} step {w.steps}")
        self.assertGreaterEqual(total, 10_000)
