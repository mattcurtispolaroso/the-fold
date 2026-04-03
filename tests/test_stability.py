"""Tests for stability infrastructure.

Covers logging, level fallback, watchdog constants, entity limits.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import tests.conftest  # noqa: F401

import constants as C
from src.systems.logging_manager import LoggingManager
from src.levels.level_data import LevelData, LevelLoadError


class TestLoggingManagerInit(unittest.TestCase):
    """LoggingManager creates log files and directory."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self.logger = LoggingManager(log_dir=self._tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_log_dir_created(self):
        self.assertTrue(os.path.isdir(self._tmpdir))

    def test_log_event_creates_file(self):
        self.logger.log_event("test event")
        self.assertTrue(os.path.isfile(os.path.join(self._tmpdir, "game_log.txt")))

    def test_log_performance_creates_file(self):
        self.logger.log_performance("slow", 20.0, 5)
        self.assertTrue(os.path.isfile(os.path.join(self._tmpdir, "performance_log.txt")))

    def test_log_crash_creates_file(self):
        self.logger.log_crash(RuntimeError("test"), {"px": 0}, [])
        self.assertTrue(os.path.isfile(os.path.join(self._tmpdir, "crash_log.txt")))

    def test_log_event_appends(self):
        self.logger.log_event("line1")
        self.logger.log_event("line2")
        path = os.path.join(self._tmpdir, "game_log.txt")
        with open(path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)


class TestLoggingManagerNeverCrashes(unittest.TestCase):
    """LoggingManager must never raise exceptions."""

    def test_bad_log_dir_does_not_crash(self):
        logger = LoggingManager(log_dir="/nonexistent/path/logs")
        logger.log_event("should not crash")

    def test_none_player_state_does_not_crash(self):
        tmpdir = tempfile.mkdtemp()
        try:
            logger = LoggingManager(log_dir=tmpdir)
            logger.log_crash(RuntimeError("x"), None, None)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestLoggingRotation(unittest.TestCase):
    """Log rotation triggers at correct file size."""

    def test_rotation_renames_large_file(self):
        tmpdir = tempfile.mkdtemp()
        try:
            logger = LoggingManager(log_dir=tmpdir)
            log_path = os.path.join(tmpdir, "game_log.txt")
            # Create a file just over the limit
            with open(log_path, "w") as f:
                f.write("x" * (10 * 1024 * 1024 + 1))
            logger.log_event("after rotation")
            # Original file should be small now (just the new entry)
            self.assertLess(os.path.getsize(log_path), 1000)
            # Archive should exist
            archives = [f for f in os.listdir(tmpdir) if "archive" in f]
            self.assertGreater(len(archives), 0)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestLevelFallback(unittest.TestCase):
    """Level loading falls back gracefully on bad data."""

    def test_fallback_on_missing_file(self):
        data = LevelData.load("/nonexistent/level.json")
        self.assertEqual(data.name, "Fallback Level")
        self.assertGreater(len(data.static_platforms), 0)

    def test_fallback_on_malformed_json(self):
        tmpdir = tempfile.mkdtemp()
        try:
            bad_path = os.path.join(tmpdir, "bad.json")
            with open(bad_path, "w") as f:
                f.write("{invalid json!!")
            data = LevelData.load(bad_path)
            self.assertEqual(data.name, "Fallback Level")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_fallback_has_spawn(self):
        data = LevelData.fallback()
        self.assertIsInstance(data.spawn, tuple)
        self.assertEqual(len(data.spawn), 2)

    def test_fallback_has_goal(self):
        data = LevelData.fallback()
        self.assertGreater(data.goal.w, 0)

    def test_level_load_error_is_exception(self):
        self.assertTrue(issubclass(LevelLoadError, Exception))


class TestWatchdogConstants(unittest.TestCase):
    """Physics watchdog constants exist and are correct types."""

    def test_threshold_is_float(self):
        self.assertIsInstance(C.PHYSICS_WATCHDOG_THRESHOLD_MS, float)

    def test_threshold_positive(self):
        self.assertGreater(C.PHYSICS_WATCHDOG_THRESHOLD_MS, 0)

    def test_enabled_is_bool(self):
        self.assertIsInstance(C.PHYSICS_WATCHDOG_ENABLED, bool)


class TestEntityCountLimits(unittest.TestCase):
    """Entity count limit constants exist and are positive integers."""

    def test_max_enemies(self):
        self.assertIsInstance(C.MAX_ENEMIES, int)
        self.assertGreater(C.MAX_ENEMIES, 0)

    def test_max_particles(self):
        self.assertIsInstance(C.MAX_PARTICLES, int)
        self.assertGreater(C.MAX_PARTICLES, 0)

    def test_max_projectiles(self):
        self.assertIsInstance(C.MAX_PROJECTILES, int)
        self.assertGreater(C.MAX_PROJECTILES, 0)

    def test_max_active_abilities(self):
        self.assertIsInstance(C.MAX_ACTIVE_ABILITIES, int)
        self.assertGreater(C.MAX_ACTIVE_ABILITIES, 0)


if __name__ == "__main__":
    unittest.main()
