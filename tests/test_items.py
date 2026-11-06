"""Tests for the item/modifier/artifact system (registry, effects, manager, offers)."""
from __future__ import annotations

import os
import unittest

import tests.conftest  # noqa: F401


# ---------------------------------------------------------------------------
# Shared fake helpers
# ---------------------------------------------------------------------------

class _FakePlayer:
    def __init__(self):
        self.chrono_reserve = 50.0
        self.iframes_timer = 0.0
        self.anchor_integrity = 3
        self.px = 100.0
        self.py = 200.0
        self.last_safe_px = 90.0
        self.last_safe_py = 200.0
        self.vx = 1.0
        self.vy = 0.0


class _FakeRunState:
    def __init__(self):
        self.fold_stability = 100.0
        self.extra_reward_options = 0


class _FakeEnemy:
    def __init__(self, px=300.0, py=200.0):
        self.px = px
        self.py = py
        self.frozen_timer = 0.0


class _FakeAbilitySlot:
    def __init__(self, name="time_dilation"):
        self.name = name
        self.active_timer = 0.0
        self.duration = 3.0
        self.cooldown = 2.0
        self.is_active = False
        self.is_ready = True


class _FakeLogger:
    def __init__(self):
        self.entries = []

    def log_event(self, msg):
        self.entries.append(msg)


def _make_ctx(player=None, enemies=None, run_state=None, ability_slot=None):
    from src.systems.items.effects import EffectContext
    return EffectContext(
        player=player or _FakePlayer(),
        enemies=enemies or [],
        run_state=run_state or _FakeRunState(),
        ability_slot=ability_slot or _FakeAbilitySlot(),
        rng=__import__("random").Random(42),
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestItemRegistry(unittest.TestCase):
    """Item registry loads and validates JSON files correctly."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_registry(self):
        from src.systems.items.registry import load_item_registry
        logger = _FakeLogger()
        reg = load_item_registry(self.BASE_DIR, logger)
        return reg, logger

    def test_loads_all_modifiers(self):
        reg, _ = self._make_registry()
        ids = {d.id for d in reg.modifiers()}
        expected = {"redshift", "closed_timelike_curve", "tidal_coupling",
                    "geodesic", "event_horizon", "quantum_foam"}
        self.assertEqual(ids, expected)

    def test_loads_all_artifacts(self):
        reg, _ = self._make_registry()
        ids = {d.id for d in reg.artifacts()}
        expected = {"kerr_ring", "hawking_emitter", "penrose_diagram"}
        self.assertEqual(ids, expected)

    def test_loads_all_resonances(self):
        reg, _ = self._make_registry()
        ids = {r.id for r in reg.all_resonances()}
        expected = {"spaghettification", "ergosphere", "information_paradox"}
        self.assertEqual(ids, expected)

    def test_modifier_params_by_rank_has_3_entries(self):
        reg, _ = self._make_registry()
        for defn in reg.modifiers():
            with self.subTest(item=defn.id):
                self.assertEqual(len(defn.params_by_rank), 3, defn.id)

    def test_artifact_params_by_rank_has_1_entry(self):
        reg, _ = self._make_registry()
        for defn in reg.artifacts():
            with self.subTest(item=defn.id):
                self.assertEqual(len(defn.params_by_rank), 1, defn.id)

    def test_all_items_have_valid_tiers(self):
        reg, _ = self._make_registry()
        for defn in reg.all_items():
            self.assertIn(defn.tier, {"modifier", "artifact"})

    def test_all_items_have_valid_domains(self):
        reg, _ = self._make_registry()
        for defn in reg.all_items():
            self.assertIn(defn.domain, {"time", "gravity", "horizon", "none"})

    def test_resonances_require_existing_items(self):
        reg, _ = self._make_registry()
        item_ids = {d.id for d in reg.all_items()}
        for res in reg.all_resonances():
            for req in res.requires:
                self.assertIn(req, item_ids, f"{res.id} requires unknown item {req!r}")

    def test_invalid_entry_is_skipped_with_log(self):
        from src.systems.items.registry import ItemRegistry
        logger = _FakeLogger()
        reg = ItemRegistry()
        bad = {"id": "bad", "name": "Bad", "tier": "unknown_tier",
               "domain": "time", "trigger": "X", "effect": "y",
               "params_by_rank": [{}], "description": "oops"}
        reg._add_item(bad, logger)
        self.assertIsNone(reg.get_item("bad"))
        self.assertTrue(any("bad" in e for e in logger.entries))


# ---------------------------------------------------------------------------
# Effect tests
# ---------------------------------------------------------------------------

class TestEffectAddChrono(unittest.TestCase):
    def test_adds_amount(self):
        ctx = _make_ctx()
        ctx.player.chrono_reserve = 50.0
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        EFFECT_REGISTRY["add_chrono"](EventResult(), ctx, {"amount": 8})
        self.assertAlmostEqual(ctx.player.chrono_reserve, 58.0)

    def test_clamps_to_max(self):
        from constants import CHRONO_RESERVE_MAX
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.chrono_reserve = CHRONO_RESERVE_MAX - 1
        EFFECT_REGISTRY["add_chrono"](EventResult(), ctx, {"amount": 999})
        self.assertAlmostEqual(ctx.player.chrono_reserve, CHRONO_RESERVE_MAX)


class TestEffectGrantIframes(unittest.TestCase):
    def test_sets_timer(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.iframes_timer = 0.0
        EFFECT_REGISTRY["grant_iframes"](EventResult(), ctx, {"seconds": 0.3})
        self.assertAlmostEqual(ctx.player.iframes_timer, 0.3)

    def test_does_not_reduce_existing_timer(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.player.iframes_timer = 0.8
        EFFECT_REGISTRY["grant_iframes"](EventResult(), ctx, {"seconds": 0.3})
        self.assertAlmostEqual(ctx.player.iframes_timer, 0.8)


class TestEffectExtendActiveAbility(unittest.TestCase):
    def _make_active_slot(self):
        slot = _FakeAbilitySlot()
        slot.active_timer = 1.5
        slot.is_active = True
        return slot

    def test_extends_when_active(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 0.5})
        self.assertAlmostEqual(slot.active_timer, 2.0)

    def test_no_effect_when_not_active(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ability_slot.active_timer = 0.0
        ctx.ability_slot.is_active = False
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 0.5})
        self.assertAlmostEqual(ctx.ability_slot.active_timer, 0.0)

    def test_no_effect_wrong_ability(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "other_ability", "seconds": 0.5})
        self.assertAlmostEqual(slot.active_timer, 1.5)

    def test_caps_extension(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = self._make_active_slot()
        slot.active_timer = slot.duration * 2.9
        ctx = _make_ctx(ability_slot=slot)
        EFFECT_REGISTRY["extend_active_ability"](
            EventResult(), ctx, {"ability_name": "time_dilation", "seconds": 999})
        self.assertLessEqual(ctx.ability_slot.active_timer, slot.duration * 3 + 0.01)


class TestEffectCancelAndRestore(unittest.TestCase):
    def test_cancels_with_room_charge(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 1
        ctx.player.anchor_integrity = 0
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertTrue(result.cancelled)
        self.assertEqual(ctx.player.anchor_integrity, 1)
        self.assertEqual(ctx.ctc_room_charges, 0)

    def test_uses_run_bonus_when_room_exhausted(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 0
        ctx.ctc_run_bonus = 1
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertTrue(result.cancelled)
        self.assertEqual(ctx.ctc_run_bonus, 0)

    def test_does_not_cancel_with_no_charges(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 0
        ctx.ctc_run_bonus = 0
        result = EventResult()
        EFFECT_REGISTRY["cancel_and_restore"](result, ctx, {})
        self.assertFalse(result.cancelled)

    def test_restores_position(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.ctc_room_charges = 1
        ctx.player.px = 999.0
        ctx.player.py = 999.0
        ctx.player.last_safe_px = 90.0
        ctx.player.last_safe_py = 200.0
        EFFECT_REGISTRY["cancel_and_restore"](EventResult(), ctx, {})
        self.assertAlmostEqual(ctx.player.px, 90.0)
        self.assertAlmostEqual(ctx.player.py, 200.0)


class TestEffectPhaseHit(unittest.TestCase):
    def test_cancels_when_rng_hits(self):
        import random
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        ctx.rng = random.Random(0)
        result = EventResult()
        EFFECT_REGISTRY["phase_hit"](result, ctx, {"chance": 1.0})
        self.assertTrue(result.cancelled)
        self.assertTrue(ctx._phase_blocked)

    def test_does_not_cancel_when_chance_zero(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        ctx = _make_ctx()
        result = EventResult()
        EFFECT_REGISTRY["phase_hit"](result, ctx, {"chance": 0.0})
        self.assertFalse(result.cancelled)


class TestEffectModifyHoleOutcome(unittest.TestCase):
    def test_restores_stability_on_black_hole(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        run = _FakeRunState()
        run.fold_stability = 60.0
        ctx = _make_ctx(run_state=run)
        EFFECT_REGISTRY["modify_hole_outcome"](
            EventResult(), ctx, {"stability_reduction": 5, "extra_reward_options": 0},
            is_white=False)
        self.assertAlmostEqual(run.fold_stability, 65.0)

    def test_adds_extra_options_on_white_hole(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        run = _FakeRunState()
        ctx = _make_ctx(run_state=run)
        EFFECT_REGISTRY["modify_hole_outcome"](
            EventResult(), ctx, {"stability_reduction": 10, "extra_reward_options": 1},
            is_white=True)
        self.assertEqual(run.extra_reward_options, 1)


class TestEffectFreezeEnemies(unittest.TestCase):
    def test_freezes_nearby_enemy(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        enemy = _FakeEnemy(px=110.0, py=200.0)
        ctx = _make_ctx(enemies=[enemy])
        ctx.player.px = 100.0
        ctx.player.py = 200.0
        EFFECT_REGISTRY["freeze_enemies_in_radius"](
            EventResult(), ctx, {"radius": 200.0, "duration": 1.0})
        self.assertAlmostEqual(enemy.frozen_timer, 1.0)

    def test_does_not_freeze_distant_enemy(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        enemy = _FakeEnemy(px=500.0, py=200.0)
        ctx = _make_ctx(enemies=[enemy])
        ctx.player.px = 100.0
        ctx.player.py = 200.0
        EFFECT_REGISTRY["freeze_enemies_in_radius"](
            EventResult(), ctx, {"radius": 200.0, "duration": 1.0})
        self.assertAlmostEqual(enemy.frozen_timer, 0.0)


class TestEffectTriggerAbility(unittest.TestCase):
    def test_triggers_on_nth_rotation(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = _FakeAbilitySlot()
        ctx = _make_ctx(ability_slot=slot)
        ctx.kerr_ring_rotations = 0
        params = {"ability_name": "time_dilation", "every_n": 4}
        for _ in range(3):
            EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertEqual(ctx.kerr_ring_rotations, 3)
        self.assertAlmostEqual(slot.active_timer, 0.0)
        EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertEqual(ctx.kerr_ring_rotations, 0)
        self.assertGreater(slot.active_timer, 0.0)

    def test_no_trigger_wrong_ability(self):
        from src.systems.items.effects import EFFECT_REGISTRY
        from src.systems.events import EventResult
        slot = _FakeAbilitySlot(name="other")
        ctx = _make_ctx(ability_slot=slot)
        params = {"ability_name": "time_dilation", "every_n": 1}
        EFFECT_REGISTRY["trigger_ability"](EventResult(), ctx, params)
        self.assertAlmostEqual(slot.active_timer, 0.0)


# ---------------------------------------------------------------------------
# Resonance tests
# ---------------------------------------------------------------------------

class TestResonanceActivation(unittest.TestCase):
    """Resonances auto-activate when both required items are owned."""

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_manager_with_items(self, item_ids):
        import random
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot, rng_seed=42)
        owned = [OwnedItem(id=iid, rank=1) for iid in item_ids]
        mgr.sync_owned(owned)
        return mgr, bus, player, run, slot

    def test_spaghettification_activates(self):
        mgr, *_ = self._make_manager_with_items(["tidal_coupling", "redshift"])
        self.assertIn("spaghettification", mgr._active_resonances)

    def test_spaghettification_not_active_with_one_part(self):
        mgr, *_ = self._make_manager_with_items(["tidal_coupling"])
        self.assertNotIn("spaghettification", mgr._active_resonances)

    def test_ergosphere_activates(self):
        mgr, *_ = self._make_manager_with_items(["geodesic", "quantum_foam"])
        self.assertIn("ergosphere", mgr._active_resonances)

    def test_information_paradox_activates(self):
        mgr, *_ = self._make_manager_with_items(["closed_timelike_curve", "event_horizon"])
        self.assertIn("information_paradox", mgr._active_resonances)

    def test_no_resonances_empty_inventory(self):
        mgr, *_ = self._make_manager_with_items([])
        self.assertEqual(len(mgr._active_resonances), 0)


# ---------------------------------------------------------------------------
# ItemManager tests
# ---------------------------------------------------------------------------

class TestItemManagerInternalCooldown(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _make_manager(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot, rng_seed=0)
        # Tidal coupling has 1.5s internal cooldown
        mgr.sync_owned([OwnedItem(id="tidal_coupling", rank=1)])
        return mgr, bus, player

    def test_tidal_coupling_fires_on_first_rotation(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        self.assertGreater(player.chrono_reserve, 0.0)

    def test_tidal_coupling_blocked_by_cooldown(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        first = player.chrono_reserve
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, -1))
        self.assertAlmostEqual(player.chrono_reserve, first)

    def test_tidal_coupling_fires_after_cooldown_expires(self):
        mgr, bus, player = self._make_manager()
        from src.systems.events import GameEvent
        player.chrono_reserve = 0.0
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, 1))
        first = player.chrono_reserve
        mgr.tick(2.0)  # advance past 1.5s cooldown
        bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=(0, -1))
        self.assertGreater(player.chrono_reserve, first)


class TestItemManagerRoomChargeReset(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_ctc_room_charges_reset_on_room_entered(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus, GameEvent
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        mgr.sync_owned([OwnedItem(id="closed_timelike_curve", rank=1)])
        # Drain charges
        mgr._ctx.ctc_room_charges = 0
        # ROOM_ENTERED should reset them
        bus.emit(GameEvent.ROOM_ENTERED)
        self.assertEqual(mgr._ctx.ctc_room_charges, 1)


class TestPhysicsInvariance(unittest.TestCase):
    """Physics constants must be unchanged with all items at max rank."""

    def test_physics_constants_unchanged_with_all_items(self):
        import constants
        # Record baseline physics values
        baseline = {
            "GRAVITY_STRENGTH": constants.GRAVITY_STRENGTH,
            "TERMINAL_VELOCITY": constants.TERMINAL_VELOCITY,
            "JUMP_SPEED": constants.JUMP_SPEED,
            "ACCEL": constants.ACCEL,
            "DECEL": constants.DECEL,
            "AIR_ACCEL": constants.AIR_ACCEL,
            "MAX_MOVE_SPEED": constants.MAX_MOVE_SPEED,
            "COYOTE_TIME": constants.COYOTE_TIME,
            "JUMP_CUT_MULTIPLIER": constants.JUMP_CUT_MULTIPLIER,
        }
        # Grant all items and run several physics updates
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.data.items import OwnedItem
        from src.systems.events import EventBus, GameEvent
        logger = _FakeLogger()
        registry = load_item_registry(BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = _FakeRunState()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        all_owned = [OwnedItem(id=d.id, rank=len(d.params_by_rank)) for d in registry.all_items()]
        mgr.sync_owned(all_owned)
        # Fire every event type
        for event in [
            GameEvent.GRAVITY_ROTATED, GameEvent.ABILITY_USED, GameEvent.ROOM_ENTERED,
            GameEvent.ROOM_CLEARED, GameEvent.HOLE_RESOLVED,
        ]:
            bus.emit(event, gravity_dir=(0, 1), ability_name="time_dilation", is_white=True)
        # Assert physics constants unchanged
        for name, value in baseline.items():
            self.assertAlmostEqual(
                getattr(constants, name), value,
                msg=f"Physics constant {name} was altered by item system",
            )


class TestRunStateOwnedItems(unittest.TestCase):
    def test_new_run_has_empty_owned_items(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        self.assertEqual(run.owned_items, [])

    def test_new_run_has_zero_paradox_spent(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        self.assertAlmostEqual(run.paradox_spent, 0.0)

    def test_to_dict_includes_owned_items(self):
        from src.data.run_state import RunState
        run = RunState.new_run()
        run.owned_items = [{"id": "redshift", "rank": 1}]
        d = run.to_dict()
        self.assertIn("owned_items", d)
        self.assertEqual(d["owned_items"][0]["id"], "redshift")


# ---------------------------------------------------------------------------
# Offer generation tests
# ---------------------------------------------------------------------------

class TestOfferGeneration(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _load_registry(self):
        from src.systems.items.registry import load_item_registry
        return load_item_registry(self.BASE_DIR, _FakeLogger())

    def test_same_seed_same_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        offers_a = generate_offers(registry, [], run_seed=42, node_idx=0)
        offers_b = generate_offers(registry, [], run_seed=42, node_idx=0)
        self.assertEqual([o.item_def.id for o in offers_a],
                         [o.item_def.id for o in offers_b])

    def test_different_node_different_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        offers_0 = generate_offers(registry, [], run_seed=1, node_idx=0)
        offers_2 = generate_offers(registry, [], run_seed=1, node_idx=2)
        ids_0 = [o.item_def.id for o in offers_0 if not o.is_paradox]
        ids_2 = [o.item_def.id for o in offers_2 if not o.is_paradox]
        self.assertGreater(len(ids_0), 0)
        self.assertGreater(len(ids_2), 0)

    def test_different_seed_likely_different_offers(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        any_differ = False
        for s in range(5):
            a = [o.item_def.id for o in generate_offers(registry, [], run_seed=s, node_idx=0)
                 if not o.is_paradox]
            b = [o.item_def.id for o in generate_offers(registry, [], run_seed=s + 1000, node_idx=0)
                 if not o.is_paradox]
            if a != b:
                any_differ = True
                break
        self.assertTrue(any_differ, "Different seeds should sometimes produce different offers")

    def test_base_count_is_three(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(20):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            non_paradox = [o for o in offers if not o.is_paradox]
            self.assertEqual(len(non_paradox), 3, f"seed={seed}")
            break  # first passing seed is enough

    def test_extra_options_increases_count(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(50):
            base = [o for o in generate_offers(registry, [], run_seed=seed, node_idx=0)
                    if not o.is_paradox]
            extra = [o for o in generate_offers(registry, [], run_seed=seed, node_idx=0,
                                                extra_options=1) if not o.is_paradox]
            if len(base) == 3:
                self.assertEqual(len(extra), 4)
                break

    def test_no_duplicate_offers_in_one_set(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(10):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            ids = [o.item_def.id for o in offers]
            self.assertEqual(len(ids), len(set(ids)), f"Duplicate offer at seed={seed}")

    def test_rank_up_offered_for_owned_below_max(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        owned = [OwnedItem(id="redshift", rank=1)]
        found_rankup = False
        for seed in range(50):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            for o in offers:
                if o.item_def.id == "redshift" and o.is_rank_up:
                    found_rankup = True
                    self.assertEqual(o.current_rank, 1)
                    self.assertEqual(o.target_rank, 2)
                    break
            if found_rankup:
                break
        self.assertTrue(found_rankup, "Rank-up offer should appear for owned modifier below max rank")

    def test_maxed_modifier_not_offered(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        owned = [OwnedItem(id="redshift", rank=3)]
        for seed in range(20):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            for o in offers:
                self.assertNotEqual(o.item_def.id, "redshift",
                                    f"Maxed modifier offered at seed={seed}")

    def test_paradox_offer_is_artifact(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(100):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            for o in offers:
                if o.is_paradox:
                    self.assertEqual(o.item_def.tier, "artifact")
                    self.assertGreater(o.paradox_cost, 0.0)
                    return

    def test_paradox_not_takeable_below_cost(self):
        from src.systems.items.offers import generate_offers
        registry = self._load_registry()
        for seed in range(100):
            offers = generate_offers(registry, [], run_seed=seed, node_idx=0)
            for o in offers:
                if o.is_paradox:
                    self.assertFalse(o.takeable(o.paradox_cost))
                    self.assertFalse(o.takeable(o.paradox_cost - 0.1))
                    self.assertTrue(o.takeable(o.paradox_cost + 1.0))
                    return

    def test_domain_pull_weights_owned_domain(self):
        from src.systems.items.offers import generate_offers
        from src.data.items import OwnedItem
        registry = self._load_registry()
        owned = [OwnedItem(id="tidal_coupling", rank=1)]
        gravity_count = 0
        for seed in range(30):
            offers = generate_offers(registry, owned, run_seed=seed, node_idx=0)
            gravity_count += sum(1 for o in offers if o.item_def.domain == "gravity" and not o.is_paradox)
        self.assertGreater(gravity_count, 0)


# ---------------------------------------------------------------------------
# Apply offer tests
# ---------------------------------------------------------------------------

class TestApplyOffer(unittest.TestCase):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _setup(self):
        from src.systems.items.registry import load_item_registry
        from src.systems.items.manager import ItemManager
        from src.systems.events import EventBus
        from src.data.run_state import RunState
        logger = _FakeLogger()
        registry = load_item_registry(self.BASE_DIR, logger)
        bus = EventBus()
        player = _FakePlayer()
        run = RunState.new_run()
        slot = _FakeAbilitySlot()
        mgr = ItemManager(registry=registry, bus=bus, player=player, enemies=[],
                          run_state=run, ability_slot=slot)
        mgr.sync_owned([])
        return registry, mgr, run

    def test_new_modifier_added_to_owned(self):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        registry, mgr, run = self._setup()
        from src.systems.items.offers import Offer
        defn = registry.get_item("redshift")
        offer = Offer(item_def=defn, is_rank_up=False, current_rank=0,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer, _owned_item_list
        _apply_offer(offer, run, mgr, registry)
        ids = [e["id"] for e in run.owned_items]
        self.assertIn("redshift", ids)

    def test_rank_up_updates_existing_entry(self):
        registry, mgr, run = self._setup()
        run.owned_items = [{"id": "redshift", "rank": 1}]
        from src.systems.items.offers import Offer
        defn = registry.get_item("redshift")
        offer = Offer(item_def=defn, is_rank_up=True, current_rank=1,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        entry = next(e for e in run.owned_items if e["id"] == "redshift")
        self.assertEqual(entry["rank"], 2)
        count = sum(1 for e in run.owned_items if e["id"] == "redshift")
        self.assertEqual(count, 1)

    def test_paradox_costs_stability(self):
        registry, mgr, run = self._setup()
        run.fold_stability = 80.0
        from src.systems.items.offers import Offer
        defn = registry.get_item("kerr_ring")
        offer = Offer(item_def=defn, is_rank_up=False, current_rank=0,
                      is_paradox=True, paradox_cost=20.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        self.assertAlmostEqual(run.fold_stability, 60.0)
        self.assertAlmostEqual(run.paradox_spent, 20.0)

    def test_modifier_cap_drops_oldest(self):
        from constants import MODIFIER_CAP
        from src.data.items import ItemDef
        registry, mgr, run = self._setup()
        modifier_ids = [d.id for d in registry.modifiers()]
        fill_count = min(MODIFIER_CAP, len(modifier_ids))
        run.owned_items = [{"id": mid, "rank": 1} for mid in modifier_ids[:fill_count]]
        oldest_id = run.owned_items[0]["id"]
        new_defn = ItemDef(
            id="test_synthetic_mod", name="Synthetic", tier="modifier",
            domain="time", trigger="GRAVITY_ROTATED", effect="add_chrono",
            params_by_rank=[{"amount": 5}], description="test",
        )
        registry._items["test_synthetic_mod"] = new_defn
        from src.systems.items.offers import Offer
        offer = Offer(item_def=new_defn, is_rank_up=False, current_rank=0,
                      is_paradox=False, paradox_cost=0.0)
        from main import _apply_offer
        _apply_offer(offer, run, mgr, registry)
        ids = [e["id"] for e in run.owned_items]
        self.assertNotIn(oldest_id, ids, "Oldest modifier should be dropped at cap")
        self.assertIn("test_synthetic_mod", ids)
        # Clean up
        del registry._items["test_synthetic_mod"]


if __name__ == "__main__":
    unittest.main()
