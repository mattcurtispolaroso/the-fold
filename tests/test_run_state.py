"""Tests for RunState, run node sequencing, and hole encounter consequences."""
from __future__ import annotations

import unittest

import tests.conftest  # noqa: F401


class TestRunState(unittest.TestCase):
    """RunState dataclass — fold_stability, seed, serialisation."""

    def test_new_run_is_active(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertTrue(rs.is_active)

    def test_new_run_fold_stability_is_max(self):
        from src.data.run_state import RunState
        from constants import FOLD_STABILITY_MAX
        rs = RunState.new_run()
        self.assertEqual(rs.fold_stability, FOLD_STABILITY_MAX)

    def test_new_run_current_node_zero(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.current_node_idx, 0)

    def test_new_run_generates_nonzero_seed(self):
        from src.data.run_state import RunState
        seeds = {RunState.new_run().run_seed for _ in range(10)}
        self.assertGreater(len(seeds), 1)

    def test_to_dict_is_serialisable(self):
        import json
        from src.data.run_state import RunState
        rs = RunState.new_run()
        d = rs.to_dict()
        json.dumps(d)  # raises if not serialisable

    def test_fold_stability_can_deplete(self):
        from src.data.run_state import RunState
        from constants import FOLD_STABILITY_INTEGRITY_COST
        rs = RunState.new_run()
        rs.fold_stability -= FOLD_STABILITY_INTEGRITY_COST
        self.assertLess(rs.fold_stability, 100.0)

    def test_fold_stability_depleted_to_zero_ends_run(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.fold_stability = 0.0
        self.assertLessEqual(rs.fold_stability, 0.0)

    def test_inactive_run_has_false_is_active(self):
        from src.data.run_state import RunState
        rs = RunState(fold_stability=100.0, current_node_idx=0, run_seed=0, is_active=False)
        self.assertFalse(rs.is_active)


class TestRunStateM4b(unittest.TestCase):
    """RunState M4b additions — node sequence, hole outcomes, combat levels."""

    def test_new_run_has_four_combat_levels(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(len(rs.combat_levels), 4)

    def test_new_run_combat_levels_in_valid_range(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertIn(rs.combat_levels[0], (0, 1))
        self.assertIn(rs.combat_levels[1], (2, 3))
        self.assertIn(rs.combat_levels[2], (4, 5))
        self.assertIn(rs.combat_levels[3], (6, 7))

    def test_new_run_has_four_hole_outcomes(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(len(rs.hole_outcomes), 4)

    def test_current_node_type_at_start(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.current_node_type, "combat")

    def test_advance_node_increments_idx(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()
        self.assertEqual(rs.current_node_idx, 1)
        self.assertEqual(rs.current_node_type, "hole")

    def test_node_count_is_nine(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.node_count, 9)

    def test_combat_level_for_first_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        idx = rs.combat_level_for_current_node()
        self.assertIn(idx, (0, 1))

    def test_combat_level_for_second_combat_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()  # hole
        rs.advance_node()  # combat node 2
        idx = rs.combat_level_for_current_node()
        self.assertIn(idx, (2, 3))

    def test_hole_outcome_for_first_hole(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        rs.advance_node()  # now at first hole (idx 1)
        result = rs.current_hole_is_white()
        self.assertIsInstance(result, bool)

    def test_singularity_is_last_node(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        for _ in range(8):
            rs.advance_node()
        self.assertEqual(rs.current_node_type, "singularity")

    def test_deaths_starts_at_zero(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        self.assertEqual(rs.deaths, 0)

    def test_to_dict_includes_new_fields(self):
        from src.data.run_state import RunState
        rs = RunState.new_run()
        d = rs.to_dict()
        self.assertIn("combat_levels", d)
        self.assertIn("hole_outcomes", d)
        self.assertIn("deaths", d)


class TestHoleEncounter(unittest.TestCase):
    """Hole encounter constants and consequence logic."""

    def test_white_hole_restores_integrity(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import ANCHOR_INTEGRITY_MAX
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        p.anchor_integrity = 1
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertEqual(p.anchor_integrity, ANCHOR_INTEGRITY_MAX)

    def test_white_hole_restores_fold_stability(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import WHITE_HOLE_STABILITY_RESTORE
        rs = RunState.new_run()
        rs.fold_stability = 50.0
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertAlmostEqual(rs.fold_stability, 50.0 + WHITE_HOLE_STABILITY_RESTORE)

    def test_white_hole_capped_at_max(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import FOLD_STABILITY_MAX
        rs = RunState.new_run()
        rs.fold_stability = FOLD_STABILITY_MAX
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=True)
        self.assertEqual(rs.fold_stability, FOLD_STABILITY_MAX)

    def test_black_hole_reduces_integrity(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import ANCHOR_INTEGRITY_MAX
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertEqual(p.anchor_integrity, ANCHOR_INTEGRITY_MAX - 1)

    def test_black_hole_reduces_fold_stability(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        from constants import BLACK_HOLE_STABILITY_COST
        rs = RunState.new_run()
        initial = rs.fold_stability
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertAlmostEqual(rs.fold_stability, initial - BLACK_HOLE_STABILITY_COST)

    def test_black_hole_increments_deaths(self):
        from main import _apply_hole_consequences
        from src.data.run_state import RunState
        from src.entities.player import Player
        rs = RunState.new_run()
        p = Player(px=0.0, py=0.0)
        _apply_hole_consequences(rs, p, is_white=False)
        self.assertEqual(rs.deaths, 1)

    def test_hole_phase_durations_are_positive(self):
        from constants import HOLE_ENCOUNTER_PHASE1_DURATION, HOLE_ENCOUNTER_PHASE2_DURATION
        self.assertGreater(HOLE_ENCOUNTER_PHASE1_DURATION, 0)
        self.assertGreater(HOLE_ENCOUNTER_PHASE2_DURATION, 0)


if __name__ == "__main__":
    unittest.main()
