"""Sprite sheet slicer for The Fold.

Loads horizontal-strip sprite sheets and slices them into
individual frames, scaling each to the target dimensions.
"""
from __future__ import annotations

import os
import logging

import pygame

logger = logging.getLogger(__name__)


def load_sheet(
    path: str,
    frame_count: int,
    target_width: int,
    target_height: int,
    source_frame_width: int = 0,
    source_frame_height: int = 0,
) -> list[pygame.Surface]:
    """Load a horizontal sprite sheet and return a list of scaled frames.

    Args:
        path: Absolute path to the sprite sheet PNG.
        frame_count: Number of frames in the strip.
        target_width: Width to scale each frame to.
        target_height: Height to scale each frame to.
        source_frame_width: Width of each frame on the sheet.
            If 0, calculated as sheet_width / frame_count.
        source_frame_height: Height of each frame on the sheet.
            If 0, uses the full sheet height.

    Returns:
        List of pygame.Surface, one per frame, scaled to target size.
        Returns empty list if the file is missing or loading fails.
    """
    if not os.path.isfile(path):
        logger.warning("Sprite sheet not found: %s", path)
        return []

    try:
        sheet = pygame.image.load(path).convert_alpha()
    except pygame.error as e:
        logger.warning("Failed to load sprite sheet %s: %s", path, e)
        return []

    sheet_w = sheet.get_width()
    sheet_h = sheet.get_height()

    fw = source_frame_width if source_frame_width > 0 else sheet_w // frame_count
    fh = source_frame_height if source_frame_height > 0 else sheet_h

    frames: list[pygame.Surface] = []
    for i in range(frame_count):
        x = i * fw
        if x + fw > sheet_w:
            logger.warning(
                "Frame %d exceeds sheet width in %s (x=%d, fw=%d, sheet_w=%d)",
                i, path, x, fw, sheet_w,
            )
            break
        frame_rect = pygame.Rect(x, 0, fw, fh)
        frame = sheet.subsurface(frame_rect).copy()
        scaled = pygame.transform.smoothscale(frame, (target_width, target_height))
        frames.append(scaled)

    if len(frames) != frame_count:
        logger.warning(
            "Expected %d frames from %s, got %d", frame_count, path, len(frames),
        )

    return frames
