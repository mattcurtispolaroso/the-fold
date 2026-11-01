"""The Fold — entry point and game loop orchestrator.

All physics logic lives in src/physics/. All level logic in src/levels/.
All rendering logic in src/rendering/. This file only orchestrates.
"""
from __future__ import annotations

import os
import time
from collections import deque

import pygame

from constants import (
    CHRONO_DRAIN_TEST,
    CHRONO_RESERVE_MAX,
    COYOTE_TIME,
    TIME_DILATION_COOLDOWN,
    TIME_DILATION_COST,
    TIME_DILATION_DURATION,
    TIME_DILATION_FACTOR,
    FONT_PATH,
    FONT_SIZE,
    FPS,
    PHYSICS_DT,
    JUMP_PEAK_THRESHOLD,
    JUMP_RISING_THRESHOLD,
    PHYSICS_WATCHDOG_ENABLED,
    PHYSICS_WATCHDOG_THRESHOLD_MS,
    ROTATE_SHAKE_DURATION,
    ROTATE_SHAKE_INTENSITY,
    ROTATION_FLASH_COLOR,
    ROTATION_FLASH_DURATION,
    ROTATION_FLASH_MAX_ALPHA,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from src.entities.player import Player
from src.levels.level_renderer import LevelRenderer
from src.physics import (
    GRAVITY_LABELS,
    apply_gravity,
    apply_jump_cut,
    apply_jump_impulse,
    apply_lateral_movement,
    check_ground_adjacent,
    clamp_terminal_velocity,
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
LEVELS = [os.path.join(LEVEL_DIR, f"level_0{i}.json") for i in range(1, 4)]


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
    current_level_idx = 0
    level = LevelRenderer()
    level.load(LEVELS[current_level_idx])

    # Camera
    camera = Camera(WIDTH, HEIGHT)
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn

    # Load assets
    background = load_background()
    animator = PlayerAnimator()
    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Player and non-player loop state
    player = Player.from_spawn(level.spawn, tuple(level.gravity_start))
    debug_draw = False
    physics_accumulator: float = 0.0
    flash_timer: float = 0.0
    dilation_timer: float = 0.0
    dilation_cooldown: float = 0.0

    # Physics frame history for crash reports
    physics_history: deque = deque(maxlen=50)
    watchdog_consecutive: int = 0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(FPS) / 1000.0, 0.05)
            physics_accumulator += frame_dt

            # --- Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if event.key == pygame.K_TAB:
                        current_level_idx = (current_level_idx + 1) % len(LEVELS)
                        level.load(LEVELS[current_level_idx])
                        camera.set_bounds(level.level_width, level.level_height)
                        camera.x, camera.y = level.spawn
                        player.reset(level.spawn, tuple(level.gravity_start))
                        physics_accumulator = 0.0
                        flash_timer = 0.0
                        dilation_timer = 0.0
                        dilation_cooldown = 0.0
                        if player.gravity_dir == (0, 1):
                            animator.helmet.request_off()
                        else:
                            animator.helmet.request_on()
                    if event.key == pygame.K_BACKQUOTE:
                        debug_draw = not debug_draw
                    if event.key == pygame.K_r:
                        player.set_gravity(rotate_gravity_ccw(player.gravity_dir))
                        player.px = round(player.px)
                        player.py = round(player.py)
                        all_plats = level.all_platform_rects()
                        player.on_ground = check_ground_adjacent(
                            player.px, player.py, player.player_w, player.player_h,
                            all_plats, player.gravity_dir,
                        )
                        if player.on_ground:
                            player.coyote_timer = COYOTE_TIME
                            player.jumping = False
                        camera.on_gravity_rotate()
                        camera.shake(ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION)
                        flash_timer = ROTATION_FLASH_DURATION
                        if player.gravity_dir == (0, 1):
                            animator.helmet.request_off()
                        else:
                            animator.helmet.request_on()
                    if event.key == pygame.K_e and dilation_cooldown <= 0 and player.chrono_reserve >= TIME_DILATION_COST:
                        player.chrono_reserve -= TIME_DILATION_COST
                        dilation_timer = TIME_DILATION_DURATION
                        dilation_cooldown = TIME_DILATION_DURATION + TIME_DILATION_COOLDOWN
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and player.coyote_timer > 0:
                        player.vx, player.vy = apply_jump_impulse(
                            player.vx, player.vy, player.gravity_dir,
                        )
                        player.coyote_timer = 0.0
                        player.jumping = True
                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and player.jumping:
                        player.vx, player.vy = apply_jump_cut(
                            player.vx, player.vy, player.gravity_dir,
                        )
                        player.jumping = False

            # Time dilation: compute scale first, then tick timers
            time_scale = TIME_DILATION_FACTOR if dilation_timer > 0 else 1.0
            dilation_timer = max(0.0, dilation_timer - frame_dt)
            dilation_cooldown = max(0.0, dilation_cooldown - frame_dt)

            # --- Physics (fixed 60hz steps) ---
            grav_vert = gravity_is_vertical(player.gravity_dir)
            while physics_accumulator >= PHYSICS_DT:
                physics_start = time.perf_counter()

                keys = pygame.key.get_pressed()
                if grav_vert:
                    player.move_input = 0
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        player.move_input = -1
                        player.facing_right = False
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        player.move_input = 1
                        player.facing_right = True
                else:
                    player.move_input = 0
                    if keys[pygame.K_UP] or keys[pygame.K_w]:
                        player.move_input = -1
                    elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                        player.move_input = 1

                if keys[pygame.K_q]:
                    player.chrono_reserve = max(
                        0.0, player.chrono_reserve - CHRONO_DRAIN_TEST * PHYSICS_DT,
                    )

                player.tick_chrono_regen(PHYSICS_DT, player.move_input != 0)
                player.vx, player.vy = apply_lateral_movement(
                    player.vx, player.vy, player.move_input, player.gravity_dir, player.on_ground,
                )
                if not player.on_ground:
                    player.vx, player.vy = apply_gravity(
                        player.vx, player.vy, player.gravity_dir, player.on_ground,
                    )
                    player.vx, player.vy = clamp_terminal_velocity(
                        player.vx, player.vy, player.gravity_dir,
                    )

                level.update(time_scale)
                all_platforms = level.all_platform_rects() + level.boundary_rects()
                player.px, player.py, player.vx, player.vy, player.on_ground = resolve_collisions(
                    player.px, player.py, player.vx, player.vy,
                    player.player_w, player.player_h, all_platforms, player.gravity_dir,
                )

                if player.on_ground:
                    player.jumping = False
                    player.coyote_timer = COYOTE_TIME
                else:
                    player.coyote_timer = max(0.0, player.coyote_timer - PHYSICS_DT)

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

                physics_history.append(player.to_dict())
                physics_accumulator -= PHYSICS_DT

            # Camera + animation (once per render frame)
            camera.update(player.px, player.py, frame_dt)
            player_state = _determine_player_state(
                player.on_ground, player.vx, player.vy, player.gravity_dir, player.move_input,
            )
            lateral_speed = player.vx if grav_vert else player.vy
            animator.update(frame_dt, player_state, lateral_speed)

            # Goal check
            pr = pygame.Rect(
                player.px - player.player_w / 2, player.py - player.player_h / 2,
                player.player_w, player.player_h,
            )
            if pr.colliderect(level.goal_rect):
                player.goal_reached = True

            # --- Draw ---
            screen.fill(BLACK)
            if background:
                screen.blit(background, (0, 0))

            cam_offset = camera.offset
            level.draw(screen, cam_offset)

            ox, oy = cam_offset
            sw, sh = animator.width, animator.height
            animator.draw(
                screen, player.px - sw / 2 + ox, player.py - sh / 2 + oy,
                player_state, player.facing_right, player.gravity_dir, debug_draw,
            )

            if debug_draw:
                dr = pygame.Rect(
                    int(player.px - player.player_w / 2 + ox),
                    int(player.py - player.player_h / 2 + oy),
                    player.player_w, player.player_h,
                )
                pygame.draw.rect(screen, (255, 0, 0), dr, 2)
                pygame.draw.circle(screen, (0, 255, 0), (int(player.px + ox), int(player.py + oy)), 4)
                cr_pct = player.chrono_reserve / CHRONO_RESERVE_MAX
                pygame.draw.rect(screen, (40, 40, 60), (10, HEIGHT - 30, 200, 14))
                pygame.draw.rect(screen, (80, 180, 255), (10, HEIGHT - 30, int(200 * cr_pct), 14))
                cr_surf = font.render(
                    f"CR {player.chrono_reserve:.0f}  [Q drain]", True, (160, 200, 255),
                )
                screen.blit(cr_surf, (220, HEIGHT - 40))

            if flash_timer > 0:
                flash_timer = max(0.0, flash_timer - frame_dt)
                alpha = int(ROTATION_FLASH_MAX_ALPHA * (flash_timer / ROTATION_FLASH_DURATION))
                flash_surf.fill((*ROTATION_FLASH_COLOR, alpha))
                screen.blit(flash_surf, (0, 0))

            label = font.render(
                f"Gravity: {GRAVITY_LABELS[player.gravity_dir]}  |  R rotate  |  TAB next level",
                True, BLUE,
            )
            screen.blit(label, (10, 10))
            if player.goal_reached:
                gt = font.render("GOAL REACHED!", True, GREEN)
                screen.blit(gt, (WIDTH // 2 - gt.get_width() // 2, HEIGHT // 2))
            if dilation_timer > 0:
                dil_surf = font.render(f"TIME DILATION  {dilation_timer:.1f}s", True, (80, 180, 255))
                screen.blit(dil_surf, (WIDTH // 2 - dil_surf.get_width() // 2, HEIGHT - 50))

            pygame.display.flip()

    except Exception as e:
        logger.log_crash(e, player.to_dict(), list(physics_history))
        print(f"The Fold encountered an error. Crash log written to {logger.crash_log_path}")
        raise
    finally:
        logger.log_event("Game shutting down")
        pygame.quit()


if __name__ == "__main__":
    main()
