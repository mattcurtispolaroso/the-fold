"""The Fold — entry point and game loop orchestrator.

All physics logic lives in src/physics/. All level logic in src/levels/.
All rendering logic in src/rendering/. This file only orchestrates.
"""
import os
import pygame
import sys

from constants import (
    COYOTE_TIME,
    FPS,
    PLAYER_SIZE,
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
    clamp_terminal_velocity,
    gravity_is_vertical,
    resolve_collisions,
    rotate_gravity_ccw,
)
from src.rendering.camera import Camera

# Display
WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
BLUE = (50, 80, 180)
GREEN = (50, 220, 50)

# Level file path
LEVEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")
DEFAULT_LEVEL = os.path.join(LEVEL_DIR, "level_01.json")


def load_player_sprite():
    """Load player.png scaled to PLAYER_SIZE height. Returns None if not found."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "player.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    w, h = img.get_size()
    scale = PLAYER_SIZE / h
    return pygame.transform.smoothscale(img, (int(w * scale), PLAYER_SIZE))


def load_background():
    """Load background.png scaled to screen size. Returns None if not found."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "backgrounds", "background.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path).convert()
    return pygame.transform.smoothscale(img, (WIDTH, HEIGHT))


def main():
    """Main game loop — orchestrates physics, rendering, input."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)

    # Load level
    level = LevelRenderer()
    level.load(DEFAULT_LEVEL)

    # Camera
    camera = Camera(WIDTH, HEIGHT)
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn

    # Load assets
    background = load_background()
    sprite_right = load_player_sprite()
    sprite_left = pygame.transform.flip(sprite_right, True, False) if sprite_right else None
    if sprite_right:
        player_w, player_h = sprite_right.get_size()
    else:
        player_w, player_h = PLAYER_SIZE, PLAYER_SIZE
    facing_right = True

    # Player state
    px, py = level.spawn
    vx, vy = 0.0, 0.0
    gravity_dir = tuple(level.gravity_start)
    on_ground = False
    coyote_timer = 0.0
    jumping = False
    goal_reached = False

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
                if event.key == pygame.K_r:
                    gravity_dir = rotate_gravity_ccw(gravity_dir)
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

        # --- Physics ---
        grav_vert = gravity_is_vertical(gravity_dir)

        # Lateral movement from input
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
        vx, vy = apply_gravity(vx, vy, gravity_dir, on_ground)
        vx, vy = clamp_terminal_velocity(vx, vy, gravity_dir)

        # Level + collision
        level.update()
        all_platforms = level.all_platform_rects()
        px, py, vx, vy, on_ground = resolve_collisions(
            px, py, vx, vy, player_w, player_h, all_platforms, gravity_dir,
        )

        # Coyote time
        if on_ground:
            jumping = False
            coyote_timer = COYOTE_TIME
        else:
            coyote_timer = max(0.0, coyote_timer - dt)

        # Clamp player to level bounds
        px = max(player_w / 2, min(level.level_width - player_w / 2, px))
        py = max(player_h / 2, min(level.level_height - player_h / 2, py))

        # Camera
        camera.update(px, py, dt)

        # Goal check
        player_rect = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        if player_rect.colliderect(level.goal_rect):
            goal_reached = True

        # --- Draw ---
        if background:
            screen.blit(background, (0, 0))
        else:
            screen.fill(BLACK)

        cam_offset = camera.offset
        level.draw(screen, cam_offset)

        ox, oy = cam_offset
        pr_screen = pygame.Rect(
            px - player_w / 2 + ox, py - player_h / 2 + oy,
            player_w, player_h,
        )
        if sprite_right:
            sprite = sprite_right if facing_right else sprite_left
            screen.blit(sprite, pr_screen.topleft)
        else:
            pygame.draw.rect(screen, RED, pr_screen)
            cx, cy = pr_screen.center
            pygame.draw.circle(screen, WHITE, (
                int(cx - gravity_dir[0] * 12),
                int(cy - gravity_dir[1] * 12),
            ), 4)

        # HUD (screen space)
        label = font.render(
            f"Gravity: {GRAVITY_LABELS[gravity_dir]}  |  R to rotate  |  Arrow keys + Space",
            True, BLUE,
        )
        screen.blit(label, (10, 10))
        if goal_reached:
            goal_text = font.render("GOAL REACHED!", True, GREEN)
            screen.blit(goal_text, (WIDTH // 2 - goal_text.get_width() // 2, HEIGHT // 2))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
