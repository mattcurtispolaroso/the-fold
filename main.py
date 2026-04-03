"""The Fold — entry point and game loop orchestrator.

All physics logic lives in src/physics/. All level logic in src/levels/.
All rendering logic in src/rendering/. This file only orchestrates.
"""
from __future__ import annotations

import os
import sys
import time
from collections import deque

import pygame

from constants import (
    COYOTE_TIME,
    FONT_PATH,
    FONT_SIZE,
    FPS,
    JUMP_PEAK_THRESHOLD,
    JUMP_RISING_THRESHOLD,
    PHYSICS_WATCHDOG_ENABLED,
    PHYSICS_WATCHDOG_THRESHOLD_MS,
    ROTATE_SHAKE_DURATION,
    ROTATE_SHAKE_INTENSITY,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from src.levels.level_renderer import LevelRenderer
from src.physics import (
    GRAVITY_LABELS,
    apply_gravity,
    apply_jump_cut,
    apply_jump_impulse,
    apply_lateral_movement,
    check_ground_adjacent,
    clamp_terminal_velocity,
    get_player_physics_size,
    gravity_is_vertical,
    gravity_speed,
    resolve_collisions,
    rotate_gravity_ccw,
)
from src.rendering.animation import PlayerAnimator, PlayerState
from src.rendering.camera import Camera
from src.systems.logging_manager import LoggingManager

# Display
WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT

# Colors
BLACK = (0, 0, 0)
BLUE = (50, 80, 180)
GREEN = (50, 220, 50)

# Level file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEVEL_DIR = os.path.join(BASE_DIR, "levels")
DEFAULT_LEVEL = os.path.join(LEVEL_DIR, "level_01.json")


def _load_font() -> pygame.font.Font:
    """Load bundled font or fall back to system font."""
    font_path = os.path.join(BASE_DIR, FONT_PATH)
    if os.path.isfile(font_path):
        return pygame.font.Font(font_path, FONT_SIZE)
    return pygame.font.SysFont(None, FONT_SIZE)


def load_background() -> pygame.Surface | None:
    """Load background.png scaled to screen size. Returns None if not found."""
    path = os.path.join(BASE_DIR, "assets", "backgrounds", "background.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, (WIDTH, HEIGHT))


def _determine_player_state(
    on_ground: bool, vx: float, vy: float,
    gravity_dir: tuple[int, int], move_input: int,
) -> PlayerState:
    """Determine the current player animation state."""
    if on_ground:
        return PlayerState.WALK if move_input != 0 else PlayerState.IDLE
    gv = gravity_speed(vx, vy, gravity_dir)
    if gv < JUMP_RISING_THRESHOLD:
        return PlayerState.JUMP_RISING
    return PlayerState.JUMP_PEAK if abs(gv) <= JUMP_PEAK_THRESHOLD else PlayerState.JUMP_FALLING


def _player_snapshot(px: float, py: float, vx: float, vy: float,
                     gravity_dir: tuple[int, int], on_ground: bool) -> dict:
    """Snapshot player state for crash logging."""
    return {"px": px, "py": py, "vx": vx, "vy": vy,
            "gravity_dir": gravity_dir, "on_ground": on_ground}


def main() -> None:
    """Main game loop — orchestrates physics, rendering, input."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    logger = LoggingManager()
    logger.log_event("Game started")
    font = _load_font()

    # Load level
    level = LevelRenderer()
    level.load(DEFAULT_LEVEL)

    # Camera
    camera = Camera(WIDTH, HEIGHT)
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn

    # Load assets
    background = load_background()
    animator = PlayerAnimator()
    facing_right = True

    # Player state
    px, py = level.spawn
    vx, vy = 0.0, 0.0
    gravity_dir = tuple(level.gravity_start)
    player_w, player_h = get_player_physics_size(gravity_dir)
    on_ground = False
    coyote_timer = 0.0
    jumping = False
    goal_reached = False
    move_input = 0
    debug_draw = False

    # Physics frame history for crash reports
    physics_history: deque = deque(maxlen=50)
    watchdog_consecutive: int = 0

    try:
        running = True
        while running:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)

            # --- Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if event.key == pygame.K_BACKQUOTE:
                        debug_draw = not debug_draw
                    if event.key == pygame.K_r:
                        gravity_dir = rotate_gravity_ccw(gravity_dir)
                        player_w, player_h = get_player_physics_size(gravity_dir)
                        px = round(px)
                        py = round(py)
                        all_plats = level.all_platform_rects()
                        on_ground = check_ground_adjacent(
                            px, py, player_w, player_h, all_plats, gravity_dir,
                        )
                        if on_ground:
                            coyote_timer = COYOTE_TIME
                            jumping = False
                        camera.on_gravity_rotate()
                        camera.shake(ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION)
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and coyote_timer > 0:
                        vx, vy = apply_jump_impulse(vx, vy, gravity_dir)
                        coyote_timer = 0.0
                        jumping = True
                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and jumping:
                        vx, vy = apply_jump_cut(vx, vy, gravity_dir)
                        jumping = False

            # --- Physics (with watchdog) ---
            physics_start = time.perf_counter()

            grav_vert = gravity_is_vertical(gravity_dir)
            keys = pygame.key.get_pressed()
            if grav_vert:
                move_input = 0
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    move_input = -1
                    facing_right = False
                elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    move_input = 1
                    facing_right = True
            else:
                move_input = 0
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    move_input = -1
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    move_input = 1

            vx, vy = apply_lateral_movement(vx, vy, move_input, gravity_dir, on_ground)
            if not on_ground:
                vx, vy = apply_gravity(vx, vy, gravity_dir, on_ground)
                vx, vy = clamp_terminal_velocity(vx, vy, gravity_dir)

            level.update()
            all_platforms = level.all_platform_rects()
            px, py, vx, vy, on_ground = resolve_collisions(
                px, py, vx, vy, player_w, player_h, all_platforms, gravity_dir,
            )

            if on_ground:
                jumping = False
                coyote_timer = COYOTE_TIME
            else:
                coyote_timer = max(0.0, coyote_timer - dt)

            # Level bounds clamp
            px_c = round(max(player_w / 2, min(level.level_width - player_w / 2, px)))
            py_c = round(max(player_h / 2, min(level.level_height - player_h / 2, py)))
            if px_c != round(px):
                if (gravity_dir[0] < 0 and px_c > px) or (gravity_dir[0] > 0 and px_c < px):
                    on_ground, jumping, coyote_timer = True, False, COYOTE_TIME
                vx, px = 0.0, float(px_c)
            if py_c != round(py):
                if (gravity_dir[1] < 0 and py_c > py) or (gravity_dir[1] > 0 and py_c < py):
                    on_ground, jumping, coyote_timer = True, False, COYOTE_TIME
                vy, py = 0.0, float(py_c)

            # Physics watchdog
            physics_ms = (time.perf_counter() - physics_start) * 1000
            if PHYSICS_WATCHDOG_ENABLED and physics_ms > PHYSICS_WATCHDOG_THRESHOLD_MS:
                watchdog_consecutive += 1
                level_str = "CRITICAL" if watchdog_consecutive >= 3 else "WARNING"
                logger.log_performance(
                    f"{level_str}: Physics step slow",
                    physics_ms, len(all_platforms),
                )
            else:
                watchdog_consecutive = 0

            # Record physics frame
            physics_history.append(_player_snapshot(
                px, py, vx, vy, gravity_dir, on_ground,
            ))

            # Camera + animation
            camera.update(px, py, dt)
            player_state = _determine_player_state(on_ground, vx, vy, gravity_dir, move_input)
            lateral_speed = vx if grav_vert else vy
            animator.update(dt, player_state, lateral_speed)

            # Goal check
            pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
            if pr.colliderect(level.goal_rect):
                goal_reached = True

            # --- Draw ---
            screen.fill(BLACK)
            if background:
                screen.blit(background, (0, 0))

            cam_offset = camera.offset
            level.draw(screen, cam_offset)

            ox, oy = cam_offset
            sw, sh = animator.width, animator.height
            animator.draw(screen, px - sw / 2 + ox, py - sh / 2 + oy,
                          player_state, facing_right, gravity_dir)

            if debug_draw:
                dr = pygame.Rect(int(px - player_w / 2 + ox), int(py - player_h / 2 + oy),
                                 player_w, player_h)
                pygame.draw.rect(screen, (255, 0, 0), dr, 2)
                pygame.draw.circle(screen, (0, 255, 0), (int(px + ox), int(py + oy)), 4)

            label = font.render(
                f"Gravity: {GRAVITY_LABELS[gravity_dir]}  |  R rotate  |  Arrows+Space",
                True, BLUE)
            screen.blit(label, (10, 10))
            if goal_reached:
                gt = font.render("GOAL REACHED!", True, GREEN)
                screen.blit(gt, (WIDTH // 2 - gt.get_width() // 2, HEIGHT // 2))

            pygame.display.flip()

    except Exception as e:
        logger.log_crash(
            e,
            _player_snapshot(px, py, vx, vy, gravity_dir, on_ground),
            list(physics_history),
        )
        print(f"The Fold encountered an error. Crash log written to {logger.crash_log_path}")
        raise
    finally:
        logger.log_event("Game shutting down")
        pygame.quit()


if __name__ == "__main__":
    main()
