"""Asset loading helpers — fonts and backgrounds.

Separated from main.py so the entry point stays thin.
"""
from __future__ import annotations

import os

import pygame

import constants as C


def load_font(base_dir: str) -> pygame.font.Font:
    """Load bundled font or fall back to system font."""
    font_path = os.path.join(base_dir, C.FONT_PATH)
    if os.path.isfile(font_path):
        return pygame.font.Font(font_path, C.FONT_SIZE)
    return pygame.font.SysFont(None, C.FONT_SIZE)


def load_background(base_dir: str, width: int, height: int) -> pygame.Surface | None:
    """Load background.png scaled to screen size. Returns None if not found."""
    path = os.path.join(base_dir, "assets", "backgrounds", "background.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, (width, height))
