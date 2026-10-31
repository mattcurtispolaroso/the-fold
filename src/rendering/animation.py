"""Sprite animation system for The Fold.

Loads player sprites from individual PNGs or horizontal sprite sheets,
handles walk/jump cycle animation, falls back to coloured rectangles
when sprites are missing. Rotates sprites to match gravity direction.
Includes helmet overlay system with independent state machine.
"""
from __future__ import annotations

import os
import logging
from enum import Enum, auto

import pygame

import constants as C
from src.rendering.sprite_sheet import load_sheet

logger = logging.getLogger(__name__)

# Fallback colors for states without sprites
FALLBACK_COLORS: dict[str, tuple[int, int, int]] = {
    "idle": (220, 50, 50),
    "walk": (220, 50, 50),
    "jump_rising": (220, 50, 50),
    "jump_falling": (255, 140, 0),
    "jump_peak": (200, 200, 50),
    "jump_anticipation": (180, 50, 50),
    "land": (220, 50, 50),
}

DEFAULT_FALLBACK: tuple[int, int, int] = (220, 50, 50)

# Helmet placeholder color
HELMET_PLACEHOLDER_COLOR: tuple[int, int, int] = (200, 150, 30)


class PlayerState(Enum):
    """Player animation states."""

    IDLE = auto()
    WALK = auto()
    JUMP_RISING = auto()
    JUMP_PEAK = auto()
    JUMP_FALLING = auto()
    JUMP_ANTICIPATION = auto()
    LAND = auto()


class HelmetState(Enum):
    """Helmet overlay animation states."""

    OFF = auto()
    ACTIVATING = auto()
    ON = auto()
    DEACTIVATING = auto()


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
            # Reverse direction mid-animation
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
            # Reverse direction mid-animation
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

        # ACTIVATING or DEACTIVATING — use activation sheet
        if self._activate_frames and 0 <= self._anim_frame < len(self._activate_frames):
            return self._activate_frames[self._anim_frame]

        return None

    @staticmethod
    def head_position(
        cx: float, cy: float,
        gravity_dir: tuple[int, int],
    ) -> tuple[float, float]:
        """Calculate the head position in screen coordinates.

        Head is always opposite to gravity direction, offset from
        the sprite centre by HELMET_HEAD_DISTANCE * sprite height.
        Fine-tuning offsets are applied after.
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

        # Debug: cyan dot at calculated head position
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
            # Placeholder: amber rectangle centred on head position
            head_h = C.PLAYER_SPRITE_HEIGHT // 4
            head_w = C.PLAYER_SPRITE_WIDTH // 2
            placeholder = pygame.Surface((head_w, head_h), pygame.SRCALPHA)
            placeholder.fill((*HELMET_PLACEHOLDER_COLOR, 160))
            rotated = _apply_gravity_rotation(placeholder, gravity_dir)
            rx = int(hx - rotated.get_width() / 2)
            ry = int(hy - rotated.get_height() / 2)
            surface.blit(rotated, (rx, ry))


class PlayerAnimator:
    """Manages player sprite loading, animation, and gravity rotation."""

    def __init__(self, sprite_dir: str = C.PLAYER_1_SPRITE_PATH) -> None:
        """Load all available sprites from the given directory."""
        self._base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__),
            ))),
            sprite_dir,
        )
        self._sprites: dict[PlayerState, list[pygame.Surface]] = {}
        self._walk_timer: float = 0.0
        self._walk_frame: int = 0
        self._lateral_speed: float = 0.0

        self.helmet = HelmetOverlay(self._base)

        self._load_individual_sprites()
        self._load_sheets()

    def _load_individual_sprites(self) -> None:
        """Load individual PNG sprites (existing approved assets)."""
        idle = _load_sprite(os.path.join(self._base, "player_1_idle.png"))
        if idle:
            self._sprites[PlayerState.IDLE] = [idle]

        walk1 = _load_sprite(os.path.join(self._base, "player_1_walk_1.png"))
        if walk1:
            walk2 = pygame.transform.flip(walk1, True, False)
            self._sprites[PlayerState.WALK] = [walk1, walk2]

        jump_r = _load_sprite(os.path.join(self._base, "player_1_jump_rising.png"))
        if jump_r:
            self._sprites[PlayerState.JUMP_RISING] = [jump_r]

    def _load_sheets(self) -> None:
        """Load sprite sheets, overriding individual sprites where applicable."""
        # Jump sheet — maps 8 frames to specific PlayerStates
        jump_path = os.path.join(self._base, C.SHEET_FILENAMES["jump"])
        jump_frames = load_sheet(
            jump_path,
            C.SHEET_FRAME_COUNTS["jump"],
            C.PLAYER_SPRITE_WIDTH,
            C.PLAYER_SPRITE_HEIGHT,
            C.SPRITE_SHEET_FRAME_WIDTH,
            C.SPRITE_SHEET_FRAME_HEIGHT,
        )
        if jump_frames:
            self._sprites[PlayerState.JUMP_ANTICIPATION] = [
                jump_frames[C.JUMP_SHEET_ANTICIPATION],
            ]
            # Rising: launch + rising_fast + rising_slow
            self._sprites[PlayerState.JUMP_RISING] = [
                jump_frames[C.JUMP_SHEET_LAUNCH],
                jump_frames[C.JUMP_SHEET_RISING_FAST],
                jump_frames[C.JUMP_SHEET_RISING_SLOW],
            ]
            self._sprites[PlayerState.JUMP_PEAK] = [
                jump_frames[C.JUMP_SHEET_PEAK],
            ]
            # Falling: falling_slow + falling_fast
            self._sprites[PlayerState.JUMP_FALLING] = [
                jump_frames[C.JUMP_SHEET_FALLING_SLOW],
                jump_frames[C.JUMP_SHEET_FALLING_FAST],
            ]
            self._sprites[PlayerState.LAND] = [
                jump_frames[C.JUMP_SHEET_LAND_IMPACT],
            ]

        # Walk sheet — replaces the 2-frame flip system with full cycle
        walk_path = os.path.join(self._base, C.SHEET_FILENAMES["walk"])
        walk_frames = load_sheet(
            walk_path,
            C.SHEET_FRAME_COUNTS["walk"],
            C.PLAYER_SPRITE_WIDTH,
            C.PLAYER_SPRITE_HEIGHT,
            C.SPRITE_SHEET_FRAME_WIDTH,
            C.SPRITE_SHEET_FRAME_HEIGHT,
        )
        if walk_frames:
            self._sprites[PlayerState.WALK] = walk_frames

        # Idle sheet — replaces single idle frame with breathing cycle
        idle_path = os.path.join(self._base, C.SHEET_FILENAMES["idle"])
        idle_frames = load_sheet(
            idle_path,
            C.SHEET_FRAME_COUNTS["idle"],
            C.PLAYER_SPRITE_WIDTH,
            C.PLAYER_SPRITE_HEIGHT,
            C.SPRITE_SHEET_FRAME_WIDTH,
            C.SPRITE_SHEET_FRAME_HEIGHT,
        )
        if idle_frames:
            self._sprites[PlayerState.IDLE] = idle_frames

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
        self.helmet.update(dt)

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
        debug: bool = False,
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

        # Draw helmet overlay on top
        self.helmet.draw(surface, cx, cy, facing_right, gravity_dir, debug)

    def has_sprite(self, state: PlayerState) -> bool:
        """Return True if a sprite is loaded for this state."""
        return state in self._sprites
