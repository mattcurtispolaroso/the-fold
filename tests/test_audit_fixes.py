"""Tests covering all fixes from the antagonistic game-developer audit."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("FOLD_RENDERER", "software")


class TestAbilitySlotFixes(unittest.TestCase):
    """AbilitySlot: chrono_reserve floor, time_scale_factor as parameter."""

    def _make_slot(self, cost: float = 25.0, time_scale_factor: float = 0.0):
        from src.systems.spacetime import AbilitySlot
        return AbilitySlot(
            name="test", duration=1.0, cost=cost, cooldown=1.0,
            time_scale_factor=time_scale_factor,
        )

    def test_activate_does_not_go_negative(self) -> None:
        """chrono_reserve must never go below 0 after activate()."""
        slot = self._make_slot(cost=50.0)
        result = slot.activate(10.0)  # reserve < cost
        self.assertGreaterEqual(result, 0.0)

    def test_activate_exact_cost(self) -> None:
        """Activating with exactly cost leaves reserve at 0."""
        slot = self._make_slot(cost=25.0)
        result = slot.activate(25.0)
        self.assertAlmostEqual(result, 0.0)

    def test_time_scale_uses_factor_not_hardcoded(self) -> None:
        """time_scale() must return time_scale_factor, not a hardcoded constant."""
        from src.systems.events import EventBus, GameEvent
        slot = self._make_slot(time_scale_factor=0.5)
        slot.activate(100.0)
        self.assertAlmostEqual(slot.time_scale(), 0.5)

    def test_time_scale_inactive_returns_one(self) -> None:
        """time_scale() returns 1.0 when ability is not active."""
        slot = self._make_slot(time_scale_factor=0.0)
        self.assertAlmostEqual(slot.time_scale(), 1.0)

    def test_make_time_dilation_uses_dilation_factor(self) -> None:
        """make_time_dilation must configure time_scale_factor from TIME_DILATION_FACTOR."""
        from constants import TIME_DILATION_FACTOR
        from src.systems.spacetime import make_time_dilation
        td = make_time_dilation()
        self.assertAlmostEqual(td.time_scale_factor, TIME_DILATION_FACTOR)


class TestCombatFixes(unittest.TestCase):
    """compute_knockback: vertical component against gravity."""

    def test_knockback_vertical_component_down_gravity(self) -> None:
        """With DOWN gravity, knockback must have a negative vy (upward kick)."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(100, 100, 50, 100, (0, 1))
        self.assertLess(vy, 0.0, "vy should be negative (upward) with DOWN gravity")
        self.assertNotAlmostEqual(vx, 0.0, msg="vx lateral component should be non-zero")

    def test_knockback_vertical_component_up_gravity(self) -> None:
        """With UP gravity, knockback must have a positive vy (downward = anti-gravity kick)."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(100, 100, 50, 100, (0, -1))
        self.assertGreater(vy, 0.0, "vy should be positive (downward = anti-gravity) with UP gravity")

    def test_knockback_vertical_component_horizontal_gravity(self) -> None:
        """With horizontal gravity, knockback must have a non-zero vx anti-gravity kick."""
        from src.systems.combat import compute_knockback
        vx, vy = compute_knockback(100, 100, 100, 50, (1, 0))  # RIGHT gravity
        self.assertLess(vx, 0.0, "vx should be negative (anti-gravity = LEFT) with RIGHT gravity")
        self.assertNotAlmostEqual(vy, 0.0, msg="vy lateral component should be non-zero")


class TestAnimationFixes(unittest.TestCase):
    """determine_player_state: IDLE/WALK uses lateral speed, LAND state fires."""

    def test_walk_returned_on_lateral_speed_with_no_input(self) -> None:
        """WALK must be returned when lateral speed > min even if move_input == 0."""
        from src.rendering.animation import PlayerState, determine_player_state
        from constants import WALK_ANIM_MIN_SPEED
        state = determine_player_state(
            on_ground=True, vx=WALK_ANIM_MIN_SPEED + 1.0, vy=0.0,
            gravity_dir=(0, 1), move_input=0,
        )
        self.assertEqual(state, PlayerState.WALK)

    def test_idle_returned_when_stopped_and_no_input(self) -> None:
        """IDLE must be returned when both lateral speed and move_input are zero."""
        from src.rendering.animation import PlayerState, determine_player_state
        state = determine_player_state(
            on_ground=True, vx=0.0, vy=0.0,
            gravity_dir=(0, 1), move_input=0,
        )
        self.assertEqual(state, PlayerState.IDLE)

    def test_land_returned_when_land_timer_active(self) -> None:
        """LAND must be returned when land_timer > 0."""
        from src.rendering.animation import PlayerState, determine_player_state
        state = determine_player_state(
            on_ground=True, vx=0.0, vy=0.0,
            gravity_dir=(0, 1), move_input=0, land_timer=0.05,
        )
        self.assertEqual(state, PlayerState.LAND)

    def test_land_timer_zero_does_not_trigger_land(self) -> None:
        """land_timer=0 must not trigger LAND state."""
        from src.rendering.animation import PlayerState, determine_player_state
        state = determine_player_state(
            on_ground=True, vx=0.0, vy=0.0,
            gravity_dir=(0, 1), move_input=0, land_timer=0.0,
        )
        self.assertNotEqual(state, PlayerState.LAND)

    def test_notify_landed_sets_land_timer(self) -> None:
        """notify_landed() must set _land_timer to LAND_ANIM_DURATION."""
        import pygame
        pygame.init()
        from constants import LAND_ANIM_DURATION
        from src.rendering.animation import PlayerAnimator
        animator = PlayerAnimator()
        self.assertAlmostEqual(animator._land_timer, 0.0)
        animator.notify_landed()
        self.assertAlmostEqual(animator._land_timer, LAND_ANIM_DURATION)

    def test_land_timer_decrements_on_update(self) -> None:
        """_land_timer must decrease during update() calls."""
        import pygame
        pygame.init()
        from src.rendering.animation import PlayerAnimator, PlayerState
        animator = PlayerAnimator()
        animator.notify_landed()
        before = animator._land_timer
        animator.update(0.05, PlayerState.IDLE)
        self.assertLess(animator._land_timer, before)


class TestMovingPlatformFixes(unittest.TestCase):
    """MovingPlatform: float position tracking prevents int truncation."""

    def _make_platform(self, speed: int, axis: str = "x"):
        import pygame
        from src.levels.level_renderer import MovingPlatform
        from src.levels.level_data import MovingPlatformDef
        defn = MovingPlatformDef(x=100, y=200, w=60, h=20,
                                  axis=axis, min_val=50, max_val=200, speed=speed)
        return MovingPlatform(defn)

    def test_slow_platform_moves_at_fractional_time_scale(self) -> None:
        """speed=1, time_scale=0.5 must still accumulate movement (no int truncation)."""
        mp = self._make_platform(speed=1)
        initial_fx = mp._fx
        for _ in range(4):
            mp.update(time_scale=0.5)
        # 4 steps × 0.5 = 2.0px accumulated
        self.assertAlmostEqual(mp._fx, initial_fx + 2.0)

    def test_rect_matches_float_position(self) -> None:
        """rect.x must always equal int(_fx)."""
        mp = self._make_platform(speed=1)
        for _ in range(10):
            mp.update(time_scale=0.7)
        self.assertEqual(mp.rect.x, int(mp._fx))

    def test_riding_velocity_uses_epsilon_not_equality(self) -> None:
        """riding_velocity must handle near-zero time_scale without float equality."""
        import pygame
        from src.levels.level_renderer import LevelRenderer
        from src.levels.level_data import LevelData, MovingPlatformDef, PlatformDef, GoalDef
        # Build a minimal level with one moving platform
        from constants import EPSILON
        level = LevelRenderer()
        defn = MovingPlatformDef(x=50, y=200, w=60, h=20, axis="x",
                                  min_val=50, max_val=300, speed=3)
        from dataclasses import replace
        # Create a bare-minimum LevelData
        from src.levels.level_data import GravityZoneDef, EnemyDef
        data = LevelData(
            name="test_level",
            static_platforms=[PlatformDef(x=0, y=400, w=800, h=20)],
            moving_platforms=[defn],
            goal=GoalDef(x=750, y=360, w=30, h=30),
            spawn=(100.0, 350.0),
            gravity_start=(0, 1),
            gravity_multiplier=1.0,
            gravity_zones=[],
            enemies=[],
            level_width=800,
            level_height=600,
        )
        level.load_from_data(data)
        # near-zero but nonzero time_scale — should NOT crash with float-equality EPSILON check
        result = level.riding_velocity(80.0, 220.0, 20.0, 20.0, (0, 1), time_scale=EPSILON * 0.5)
        self.assertIsInstance(result, tuple)


class TestRotationCooldownConstant(unittest.TestCase):
    """ROTATION_COOLDOWN constant exists and is positive."""

    def test_rotation_cooldown_exists_and_positive(self) -> None:
        from constants import ROTATION_COOLDOWN
        self.assertGreater(ROTATION_COOLDOWN, 0.0)

    def test_epsilon_defined(self) -> None:
        from constants import EPSILON
        self.assertGreater(EPSILON, 0.0)
        self.assertLess(EPSILON, 0.1)


class TestAbilitySlotCombinations(unittest.TestCase):
    """Gaps from adversarial audit item 13: activation-while-active, fractional
    time scale, total_recharge property, modifier stacking with real slot."""

    def _make_slot(self, duration: float = 3.0, cost: float = 10.0,
                   cooldown: float = 2.0, tsf: float = 0.0) -> object:
        from src.systems.spacetime import AbilitySlot
        return AbilitySlot(
            name="time_dilation", duration=duration, cost=cost,
            cooldown=cooldown, time_scale_factor=tsf,
        )

    def _bus(self) -> object:
        from src.systems.events import EventBus
        return EventBus()

    def test_activate_while_active_resets_timer_to_full_duration(self) -> None:
        """Re-activating mid-effect resets active_timer to full duration."""
        slot = self._make_slot(duration=3.0)
        slot.activate(100.0)
        slot.tick(1.0, self._bus())  # 1s into effect → timer=2.0
        slot.activate(100.0)        # re-activate
        self.assertAlmostEqual(slot.active_timer, 3.0)

    def test_activate_while_active_deducts_cost_again(self) -> None:
        """Re-activating while active still deducts chrono cost."""
        slot = self._make_slot(cost=10.0)
        remaining = slot.activate(100.0)   # → 90
        remaining = slot.activate(remaining)  # → 80
        self.assertAlmostEqual(remaining, 80.0)

    def test_total_recharge_equals_duration_plus_cooldown(self) -> None:
        """total_recharge property returns duration + post-effect wait."""
        slot = self._make_slot(duration=3.0, cooldown=2.0)
        self.assertAlmostEqual(slot.total_recharge, 5.0)

    def test_cooldown_timer_set_to_total_recharge_on_activate(self) -> None:
        """cooldown_timer is initialised to duration + cooldown on activate."""
        slot = self._make_slot(duration=3.0, cooldown=2.0)
        slot.activate(100.0)
        self.assertAlmostEqual(slot.cooldown_timer, 5.0)

    def test_fractional_time_scale_factor_returned_while_active(self) -> None:
        """time_scale_factor of 0.3 (partial slow) is returned correctly."""
        slot = self._make_slot(tsf=0.3)
        slot.activate(100.0)
        self.assertAlmostEqual(slot.time_scale(), 0.3)

    def test_ability_ready_after_full_cooldown_elapsed(self) -> None:
        """Ability becomes ready exactly after duration + cooldown has ticked down."""
        slot = self._make_slot(duration=1.0, cooldown=1.0)
        bus = self._bus()
        slot.activate(100.0)
        slot.tick(2.0, bus)  # exactly duration + cooldown
        self.assertTrue(slot.is_ready)
        self.assertFalse(slot.is_active)

    def test_extend_active_ability_works_with_real_slot(self) -> None:
        """extend_active_ability effect integrates with a real AbilitySlot, not a stub."""
        import random
        from src.systems.items.effects import EFFECT_REGISTRY, EffectContext
        from src.systems.events import EventResult
        slot = self._make_slot(duration=3.0)
        slot.activate(100.0)
        slot.tick(1.0, self._bus())  # 1s in → active_timer = 2.0
        ctx = EffectContext(
            player=None, enemies=[], run_state=None,
            ability_slot=slot, rng=random.Random(0),
        )
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 0.5},
        )
        self.assertAlmostEqual(slot.active_timer, 2.5)


if __name__ == "__main__":
    unittest.main()
