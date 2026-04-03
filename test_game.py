"""Test runner for The Fold — discovers and runs all tests in tests/ directory.

Usage: python test_game.py
"""
import os
import sys
import unittest

# Headless Pygame setup before any test imports
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
