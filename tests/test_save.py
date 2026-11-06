"""Tests for SaveManager and MetaProgress."""
from __future__ import annotations

import os
import unittest

import tests.conftest  # noqa: F401


class TestSaveManager(unittest.TestCase):
    """Tests for SaveManager and MetaProgress."""

    def setUp(self) -> None:
        """Create a temp dir for save files."""
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self._save_path = os.path.join(self._tmpdir, "save.json")

    def tearDown(self) -> None:
        """Remove temp dir."""
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_manager(self):
        from src.data.save_manager import SaveManager
        return SaveManager(self._save_path)

    def test_load_returns_empty_progress_when_no_file(self) -> None:
        """Load on missing file returns zeroed MetaProgress."""
        meta = self._make_manager().load()
        self.assertEqual(meta.total_runs, 0)
        self.assertEqual(meta.runs_won, 0)

    def test_save_then_load_round_trips(self) -> None:
        """Saved MetaProgress round-trips through JSON correctly."""
        from src.data.save_manager import MetaProgress
        mgr = self._make_manager()
        m = MetaProgress(total_runs=5, runs_won=2, best_stability=75.0, best_nodes_reached=4)
        mgr.save(m)
        loaded = mgr.load()
        self.assertEqual(loaded.total_runs, 5)
        self.assertEqual(loaded.runs_won, 2)
        self.assertAlmostEqual(loaded.best_stability, 75.0)
        self.assertEqual(loaded.best_nodes_reached, 4)

    def test_save_writes_atomically_via_temp_file(self) -> None:
        """Save file appears at the correct path after save."""
        from src.data.save_manager import MetaProgress
        mgr = self._make_manager()
        mgr.save(MetaProgress(total_runs=1))
        self.assertTrue(os.path.exists(self._save_path))
        self.assertFalse(os.path.exists(self._save_path + ".tmp"))

    def test_corrupt_file_returns_empty_progress(self) -> None:
        """Corrupt save file is handled gracefully and returns empty progress."""
        with open(self._save_path, "w") as f:
            f.write("not valid json {{{")
        meta = self._make_manager().load()
        self.assertEqual(meta.total_runs, 0)

    def test_corrupt_file_is_backed_up(self) -> None:
        """Corrupt save file is renamed to a backup, not deleted."""
        with open(self._save_path, "w") as f:
            f.write("garbage")
        self._make_manager().load()
        backups = [f for f in os.listdir(self._tmpdir) if "corrupted" in f]
        self.assertEqual(len(backups), 1)

    def test_corrupt_file_original_removed(self) -> None:
        """After corruption backup, the original save.json no longer exists."""
        with open(self._save_path, "w") as f:
            f.write("garbage")
        self._make_manager().load()
        self.assertFalse(os.path.exists(self._save_path))

    def test_record_run_increments_total_runs(self) -> None:
        """record_run always increments total_runs."""
        from src.data.save_manager import MetaProgress
        m = MetaProgress()
        m.record_run(won=False, fold_stability=50.0, nodes_reached=2)
        self.assertEqual(m.total_runs, 1)

    def test_record_win_increments_runs_won(self) -> None:
        """record_run with won=True increments runs_won."""
        from src.data.save_manager import MetaProgress
        m = MetaProgress()
        m.record_run(won=True, fold_stability=80.0, nodes_reached=5)
        self.assertEqual(m.runs_won, 1)

    def test_record_loss_does_not_increment_runs_won(self) -> None:
        """record_run with won=False does not change runs_won."""
        from src.data.save_manager import MetaProgress
        m = MetaProgress(runs_won=2)
        m.record_run(won=False, fold_stability=20.0, nodes_reached=1)
        self.assertEqual(m.runs_won, 2)

    def test_best_stability_tracks_maximum(self) -> None:
        """best_stability is updated only when new value exceeds current best."""
        from src.data.save_manager import MetaProgress
        m = MetaProgress()
        m.record_run(won=False, fold_stability=60.0, nodes_reached=2)
        m.record_run(won=False, fold_stability=40.0, nodes_reached=2)
        self.assertAlmostEqual(m.best_stability, 60.0)

    def test_best_nodes_reached_tracks_maximum(self) -> None:
        """best_nodes_reached is updated only when new value exceeds current best."""
        from src.data.save_manager import MetaProgress
        m = MetaProgress()
        m.record_run(won=False, fold_stability=50.0, nodes_reached=3)
        m.record_run(won=False, fold_stability=50.0, nodes_reached=1)
        self.assertEqual(m.best_nodes_reached, 3)

    def test_multiple_saves_accumulate(self) -> None:
        """Saving twice with incremented data persists the latest version."""
        from src.data.save_manager import MetaProgress
        mgr = self._make_manager()
        m = MetaProgress()
        m.record_run(won=False, fold_stability=40.0, nodes_reached=2)
        mgr.save(m)
        m.record_run(won=True, fold_stability=90.0, nodes_reached=5)
        mgr.save(m)
        loaded = mgr.load()
        self.assertEqual(loaded.total_runs, 2)
        self.assertEqual(loaded.runs_won, 1)
        self.assertAlmostEqual(loaded.best_stability, 90.0)


if __name__ == "__main__":
    unittest.main()
