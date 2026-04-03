"""Sprite animation system for The Fold.

Loads player sprites by state, handles walk cycle animation,
falls back to coloured rectangles when sprites are missing.
Rotates sprites to match gravity direction.
"""
from __future__ import annotations

import os
import logging
from enum import Enum, auto

import pygame

import constants as C

logger = logging.getLogger(__name__)

# Fallback colors for states without sprites
FALLBACK_COLORS: dict[str, tuple[int, int, int]] = {
    "idle": (220, 50, 50),
    "walk": (220, 50, 50),
    "jump_rising": (220, 50, 50),
    "jump_falling": (255, 140, 0),
    "jump_peak": (200, 200, 50),
    "land": (220, 50, 50),
}

DEFAULT_FALLBACK: tuple[int, int, int] = (220, 50, 50)


class PlayerState(Enum):
    """Player animation states."""

    IDLE = auto()
    WALK = auto()
    JUMP_RISING = auto()
    JUMP_PEAK = auto()
    JUMP_FALLING = auto()
    LAND = auto()


def _load_sprite(path: str) -> pygame.Surface | None:
    """Load a single sprite, scale it, return None if not found."""
    if not os.path.isfile(path):
        logger.warning("Sprite not found: %s", path)
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.smoothscale(
        img, (C.PLAYER_SPRITE_WIDTH, C.PLAYER_SPRITE_HEIGHT),
    )


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation clamped to [a, b] range."""
    return a + (b - a) * max(0.0, min(1.0, t))


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


class PlayerAnimator:
    """Manages player sprite loading, animation, and gravity rotation."""

    def __init__(self, sprite_dir: str = C.PLAYER_1_SPRITE_PATH) -> None:
        """Load all available sprites from the given directory."""
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__),
            ))),
            sprite_dir,
        )
        self._sprites: dict[PlayerState, list[pygame.Surface]] = {}
        self._walk_timer: float = 0.0
        self._walk_frame: int = 0
        self._lateral_speed: float = 0.0

        self._load_sprites(base)

    def _load_sprites(self, base: str) -> None:
        """Load all sprite files from base directory."""
        idle = _load_sprite(os.path.join(base, "player_1_idle.png"))
        if idle:
            self._sprites[PlayerState.IDLE] = [idle]

        walk1 = _load_sprite(os.path.join(base, "player_1_walk_1.png"))
        if walk1:
            walk2 = pygame.transform.flip(walk1, True, False)
            self._sprites[PlayerState.WALK] = [walk1, walk2]

        jump_r = _load_sprite(os.path.join(base, "player_1_jump_rising.png"))
        if jump_r:
            self._sprites[PlayerState.JUMP_RISING] = [jump_r]

    @property
    def width(self) -> int:
        """Sprite width in pixels."""
        return C.PLAYER_SPRITE_WIDTH

    @property
    def height(self) -> int:
        """Sprite height in pixels."""
        return C.PLAYER_SPRITE_HEIGHT

    def update(
        self, dt: float, state: PlayerState, lateral_speed: float = 0.0,
    ) -> None:
        """Advance animation timers. lateral_speed drives walk cycle."""
        self._lateral_speed = abs(lateral_speed)

        if state != PlayerState.WALK or PlayerState.WALK not in self._sprites:
            self._walk_timer = 0.0
            self._walk_frame = 0
            return

        if self._lateral_speed < C.WALK_ANIM_MIN_SPEED:
            self._walk_timer = 0.0
            self._walk_frame = 0
            return

        speed_t = min(self._lateral_speed / C.MAX_MOVE_SPEED, 1.0)
        current_fps = _lerp(C.WALK_ANIM_MIN_FPS, C.WALK_ANIM_MAX_FPS, speed_t)
        frame_dur = 1.0 / current_fps

        self._walk_timer += dt
        if self._walk_timer >= frame_dur:
            self._walk_timer -= frame_dur
            frame_count = len(self._sprites[PlayerState.WALK])
            self._walk_frame = (self._walk_frame + 1) % frame_count

    def get_frame(self, state: PlayerState) -> pygame.Surface | None:
        """Return the current animation frame, or None for fallback."""
        frames = self._sprites.get(state)
        if not frames:
            return None
        if state == PlayerState.WALK:
            return frames[self._walk_frame % len(frames)]
        return frames[0]

    def draw(
        self,
        surface: pygame.Surface,
        x: float, y: float,
        state: PlayerState,
        facing_right: bool,
        gravity_dir: tuple[int, int] = (0, 1),
    ) -> None:
        """Draw the current frame with direction flip and gravity rotation."""
        # Physics rect centre in screen coordinates
        cx = x + C.PLAYER_SPRITE_WIDTH / 2
        cy = y + C.PLAYER_SPRITE_HEIGHT / 2 + C.SPRITE_PHYSICS_OFFSET_Y

        frame = self.get_frame(state)
        if frame:
            if not facing_right:
                frame = pygame.transform.flip(frame, True, False)
            frame = _apply_gravity_rotation(frame, gravity_dir)
            # Centre rotated surface on physics rect centre
            rx = int(cx - frame.get_width() / 2)
            ry = int(cy - frame.get_height() / 2)
            surface.blit(frame, (rx, ry))
        else:
            # Always draw fallback so player is visible
            state_name = state.name.lower()
            color = FALLBACK_COLORS.get(state_name, DEFAULT_FALLBACK)
            rect = pygame.Rect(
                int(cx - C.PLAYER_SPRITE_WIDTH / 2),
                int(cy - C.PLAYER_SPRITE_HEIGHT / 2),
                C.PLAYER_SPRITE_WIDTH,
                C.PLAYER_SPRITE_HEIGHT,
            )
            pygame.draw.rect(surface, color, rect)

    def has_sprite(self, state: PlayerState) -> bool:
        """Return True if a sprite is loaded for this state."""
        return state in self._sprites
