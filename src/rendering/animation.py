"""Player animation system for The Fold.

Loads player sprites from individual PNGs or horizontal sprite sheets,
handles walk/jump cycle animation, and falls back to coloured rectangles
when sprites are missing. Rotates sprites to match gravity direction.
"""
from __future__ import annotations

import os
from enum import Enum, auto

import pygame

import constants as C
from constants import LAND_ANIM_DURATION
from src.physics import gravity_speed
from src.rendering.helmet import HelmetOverlay, _apply_gravity_rotation, _load_sprite
from src.rendering.sprite_sheet import load_sheet

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


class PlayerState(Enum):
    """Player animation states."""

    IDLE = auto()
    WALK = auto()
    JUMP_RISING = auto()
    JUMP_PEAK = auto()
    JUMP_FALLING = auto()
    JUMP_ANTICIPATION = auto()
    LAND = auto()


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation clamped to [a, b] range."""
    return a + (b - a) * max(0.0, min(1.0, t))


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
        self._air_timer: float = 0.0
        self._air_frame: int = 0
        self._land_timer: float = 0.0  # counts down after touching ground

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
            self._sprites[PlayerState.JUMP_RISING] = [
                jump_frames[C.JUMP_SHEET_LAUNCH],
                jump_frames[C.JUMP_SHEET_RISING_FAST],
                jump_frames[C.JUMP_SHEET_RISING_SLOW],
            ]
            self._sprites[PlayerState.JUMP_PEAK] = [jump_frames[C.JUMP_SHEET_PEAK]]
            self._sprites[PlayerState.JUMP_FALLING] = [
                jump_frames[C.JUMP_SHEET_FALLING_SLOW],
                jump_frames[C.JUMP_SHEET_FALLING_FAST],
            ]
            self._sprites[PlayerState.LAND] = [jump_frames[C.JUMP_SHEET_LAND_IMPACT]]

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

    def notify_landed(self) -> None:
        """Call when player transitions from air to ground to trigger LAND animation."""
        self._land_timer = LAND_ANIM_DURATION

    def update(
        self, dt: float, state: PlayerState, lateral_speed: float = 0.0,
    ) -> None:
        """Advance animation timers. lateral_speed drives walk cycle."""
        self._lateral_speed = abs(lateral_speed)
        self.helmet.update(dt)
        if self._land_timer > 0:
            self._land_timer = max(0.0, self._land_timer - dt)

        _AIR_STATES = (PlayerState.JUMP_RISING, PlayerState.JUMP_FALLING)
        _AIR_FPS = 10.0  # fixed playback rate for air frames

        if state in _AIR_STATES and state in self._sprites:
            self._walk_timer = 0.0
            self._walk_frame = 0
            self._air_timer += dt
            frame_dur = 1.0 / _AIR_FPS
            if self._air_timer >= frame_dur:
                self._air_timer -= frame_dur
                frame_count = len(self._sprites[state])
                self._air_frame = (self._air_frame + 1) % frame_count
            return

        if state != PlayerState.WALK or PlayerState.WALK not in self._sprites:
            self._walk_timer = 0.0
            self._walk_frame = 0
            self._air_timer = 0.0
            self._air_frame = 0
            return

        self._air_timer = 0.0
        self._air_frame = 0

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
        if state in (PlayerState.JUMP_RISING, PlayerState.JUMP_FALLING):
            return frames[self._air_frame % len(frames)]
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
        cx = x + C.PLAYER_SPRITE_WIDTH / 2
        cy = y + C.PLAYER_SPRITE_HEIGHT / 2 + C.SPRITE_PHYSICS_OFFSET_Y

        frame = self.get_frame(state)
        if frame:
            if not facing_right:
                frame = pygame.transform.flip(frame, True, False)
            frame = _apply_gravity_rotation(frame, gravity_dir)
            rx = int(cx - frame.get_width() / 2)
            ry = int(cy - frame.get_height() / 2)
            surface.blit(frame, (rx, ry))
        else:
            state_name = state.name.lower()
            color = FALLBACK_COLORS.get(state_name, DEFAULT_FALLBACK)
            # Swap sprite dimensions to match 90° rotation in horizontal gravity
            if gravity_dir[1] != 0:
                fw, fh = C.PLAYER_SPRITE_WIDTH, C.PLAYER_SPRITE_HEIGHT
            else:
                fw, fh = C.PLAYER_SPRITE_HEIGHT, C.PLAYER_SPRITE_WIDTH
            rect = pygame.Rect(int(cx - fw / 2), int(cy - fh / 2), fw, fh)
            pygame.draw.rect(surface, color, rect)

        self.helmet.draw(surface, cx, cy, facing_right, gravity_dir, debug)

    def has_sprite(self, state: PlayerState) -> bool:
        """Return True if a sprite is loaded for this state."""
        return state in self._sprites


def determine_player_state(
    on_ground: bool,
    vx: float,
    vy: float,
    gravity_dir: tuple[int, int],
    move_input: int,
    land_timer: float = 0.0,
) -> PlayerState:
    """Map current physics state to the correct animation state.

    land_timer: seconds remaining in the LAND animation (set by PlayerAnimator.notify_landed).
    """
    if not on_ground:
        gv = gravity_speed(vx, vy, gravity_dir)
        if gv < C.JUMP_RISING_THRESHOLD:
            return PlayerState.JUMP_RISING
        return PlayerState.JUMP_PEAK if abs(gv) <= C.JUMP_PEAK_THRESHOLD else PlayerState.JUMP_FALLING

    if land_timer > 0:
        return PlayerState.LAND

    # Use lateral speed, not just move_input, so the player shows WALK while
    # decelerating on a moving platform or after knockback.
    lat_speed = abs(vx) if gravity_dir[1] != 0 else abs(vy)
    return PlayerState.WALK if lat_speed > C.WALK_ANIM_MIN_SPEED or move_input != 0 else PlayerState.IDLE
