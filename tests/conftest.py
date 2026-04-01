"""Shared test setup — headless Pygame initialisation.

Imported by test modules before any Pygame usage.
"""
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()
