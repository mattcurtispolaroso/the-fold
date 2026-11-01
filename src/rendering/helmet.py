"""Helmet overlay system for The Fold.

Manages the gravity-activated helmet: sprite loading, state machine
(OFF -> ACTIVATING -> ON -> DEACTIVATING -> OFF), head-position
calculation, and drawing. Depends only on Pygame and constants.
"""
from __future__ import annotations

import os
import logging
from enum import Enum, auto

import pygame

import constants as C
from src.rendering.sprite_sheet import load_sheet

logger = logging.getLogger(__name__)

HELMET_PLACEHOLDER_COLOR: tuple[int, int, int] = (200, 150, 30)


def _load_sprite(path: str) -> pygame.Surface | None:
    """Load a single sprite, scale it, return None if not found."""
    if not os.path.isfile(path):
        logger.warning("Sprite not found: %s", path)
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(
        img, (C.PLAYER_SPRITE_WIDTH, C.PLAYER_SPRITE_HEIGHT),
    )


def _apply_gravity_rotation(
    frame: pygame.Surface,
    gravity_dir: tuple[int, int],
) -> pygame.Surface:
    """Rotate sprite to match gravity. Uses flip for 180 to preserve size."""
    angle = C.SPRITE_ROTATION.get(gravity_dir, 0)
    if angle == 0:
        return frame
    if angle == 180:
        return pygame.transform.flip(frame, True, True)
    return pygame.transform.rotate(frame, angle)


class HelmetState(Enum):
    """Helmet overlay animation states."""

    OFF = auto()
    ACTIVATING = auto()
    ON = auto()
    DEACTIVATING = auto()


class HelmetOverlay:
    """Manages helmet overlay animation independent of body animation.

    State machine: OFF -> ACTIVATING -> ON -> DEACTIVATING -> OFF
    Triggered by gravity direction changes and ability use.
    """

    def __init__(self, sprite_dir: str) -> None:
        """Load helmet sprites from the given directory."""
        self._state: HelmetState = HelmetState.OFF
        self._anim_timer: float = 0.0
        self._anim_frame: int = 0
        self._frame_duration: float = 1.0 / C.HELMET_ANIM_FPS

        self._activate_frames: list[pygame.Surface] = []
        self._on_frame: pygame.Surface | None = None

        self._load_sprites(sprite_dir)

    def _load_sprites(self, sprite_dir: str) -> None:
        """Load helmet sheet and on-state sprite."""
        activate_path = os.path.join(sprite_dir, C.HELMET_ACTIVATE_SHEET)
        self._activate_frames = load_sheet(
            activate_path,
            C.HELMET_ACTIVATE_FRAMES,
            C.PLAYER_SPRITE_WIDTH,
            C.PLAYER_SPRITE_HEIGHT,
            C.SPRITE_SHEET_FRAME_WIDTH,
            C.SPRITE_SHEET_FRAME_HEIGHT,
        )

        on_path = os.path.join(sprite_dir, C.HELMET_ON_SPRITE)
        self._on_frame = _load_sprite(on_path)

    @property
    def state(self) -> HelmetState:
        """Current helmet state."""
        return self._state

    def request_on(self) -> None:
        """Request helmet activation (gravity rotated away from DOWN)."""
        if self._state == HelmetState.OFF:
            self._state = HelmetState.ACTIVATING
            self._anim_frame = 0
            self._anim_timer = 0.0
        elif self._state == HelmetState.DEACTIVATING:
            self._state = HelmetState.ACTIVATING
            reverse_frame = (C.HELMET_ACTIVATE_FRAMES - 1) - self._anim_frame
            self._anim_frame = max(0, reverse_frame)
            self._anim_timer = 0.0

    def request_off(self) -> None:
        """Request helmet deactivation (gravity returned to DOWN)."""
        if self._state == HelmetState.ON:
            self._state = HelmetState.DEACTIVATING
            self._anim_frame = C.HELMET_ACTIVATE_FRAMES - 1
            self._anim_timer = 0.0
        elif self._state == HelmetState.ACTIVATING:
            self._state = HelmetState.DEACTIVATING
            reverse_frame = (C.HELMET_ACTIVATE_FRAMES - 1) - self._anim_frame
            self._anim_frame = min(C.HELMET_ACTIVATE_FRAMES - 1, reverse_frame)
            self._anim_timer = 0.0

    def update(self, dt: float) -> None:
        """Advance helmet animation timers."""
        if self._state == HelmetState.OFF or self._state == HelmetState.ON:
            return

        self._anim_timer += dt
        if self._anim_timer < self._frame_duration:
            return
        self._anim_timer -= self._frame_duration

        if self._state == HelmetState.ACTIVATING:
            self._anim_frame += 1
            if self._anim_frame >= C.HELMET_ACTIVATE_FRAMES:
                self._state = HelmetState.ON
                self._anim_frame = 0
        elif self._state == HelmetState.DEACTIVATING:
            self._anim_frame -= 1
            if self._anim_frame < 0:
                self._state = HelmetState.OFF
                self._anim_frame = 0

    def get_frame(self) -> pygame.Surface | None:
        """Return current helmet frame, or None if OFF."""
        if self._state == HelmetState.OFF:
            return None

        if self._state == HelmetState.ON:
            return self._on_frame

        if self._activate_frames and 0 <= self._anim_frame < len(self._activate_frames):
            return self._activate_frames[self._anim_frame]

        return None

    @staticmethod
    def head_position(
        cx: float, cy: float,
        gravity_dir: tuple[int, int],
    ) -> tuple[float, float]:
        """Calculate head position in screen coordinates.

        Head is always opposite to gravity direction, offset from
        the sprite centre by HELMET_HEAD_DISTANCE * sprite height.
        """
        dist = C.HELMET_HEAD_DISTANCE * C.PLAYER_SPRITE_HEIGHT
        hx = cx + (-gravity_dir[0] * dist) + C.HELMET_HEAD_OFFSET_X
        hy = cy + (-gravity_dir[1] * dist) + C.HELMET_HEAD_OFFSET_Y
        return hx, hy

    def draw(
        self,
        surface: pygame.Surface,
        cx: float, cy: float,
        facing_right: bool,
        gravity_dir: tuple[int, int],
        debug: bool = False,
    ) -> None:
        """Draw helmet overlay at the player's head position."""
        hx, hy = self.head_position(cx, cy, gravity_dir)

        if debug:
            pygame.draw.circle(surface, (0, 255, 255), (int(hx), int(hy)), 4)

        if self._state == HelmetState.OFF:
            return

        frame = self.get_frame()
        if frame:
            if not facing_right:
                frame = pygame.transform.flip(frame, True, False)
            frame = _apply_gravity_rotation(frame, gravity_dir)
            rx = int(hx - frame.get_width() / 2)
            ry = int(hy - frame.get_height() / 2)
            surface.blit(frame, (rx, ry))
        else:
            head_h = C.PLAYER_SPRITE_HEIGHT // 4
            head_w = C.PLAYER_SPRITE_WIDTH // 2
            placeholder = pygame.Surface((head_w, head_h), pygame.SRCALPHA)
            placeholder.fill((*HELMET_PLACEHOLDER_COLOR, 160))
            rotated = _apply_gravity_rotation(placeholder, gravity_dir)
            rx = int(hx - rotated.get_width() / 2)
            ry = int(hy - rotated.get_height() / 2)
            surface.blit(rotated, (rx, ry))
