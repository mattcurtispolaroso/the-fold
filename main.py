import os
import pygame
import sys

from src.levels.level_renderer import LevelRenderer

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SIZE = 90

# Physics scale: 50 pixels = 1 meter
PPM = 50
EARTH_GRAVITY = 9.8                              # m/s²
GRAVITY_STRENGTH = EARTH_GRAVITY * PPM / FPS**2  # ~0.136 px/frame²
TERMINAL_VELOCITY = 53.0 * PPM / FPS             # ~44.2 px/frame (human free-fall ~53 m/s)

JUMP_SPEED = 8.0     # strong, intentional launch
MOVE_SPEED = 5

# Movement tuning
ACCEL = 1.5              # ground horizontal acceleration per frame
DECEL = 1.0              # ground horizontal deceleration per frame (smoother stops)
AIR_ACCEL = 0.4          # air horizontal acceleration (limited air control)
AIR_DECEL = 0.1          # air horizontal deceleration (preserve momentum in air)
MAX_MOVE_SPEED = 5       # max horizontal speed

# Jump tuning
COYOTE_TIME = 0.1    # seconds after leaving ground where jump is still allowed
JUMP_CUT_MULTIPLIER = 0.4  # multiply velocity by this when jump key released early
PEAK_GRAVITY_MULT = 2.5    # extra gravity when near the peak of a jump

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
BLUE = (50, 80, 180)
GREEN = (50, 220, 50)

# Gravity — single directional vector as unit (dx, dy).
GRAVITY_DOWN = (0, 1)
GRAVITY_LEFT = (-1, 0)
GRAVITY_UP = (0, -1)
GRAVITY_RIGHT = (1, 0)

GRAVITY_LABELS = {
    GRAVITY_DOWN: "Down",
    GRAVITY_LEFT: "Left",
    GRAVITY_UP: "Up",
    GRAVITY_RIGHT: "Right",
}

# Level file path
LEVEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "levels")
DEFAULT_LEVEL = os.path.join(LEVEL_DIR, "level_01.json")


def rotate_gravity_ccw(gravity_dir):
    """Rotate gravity 90 degrees counter-clockwise in screen coordinates."""
    dx, dy = gravity_dir
    return (dy, -dx)


def gravity_is_vertical(gravity_dir):
    """True if gravity pulls along the Y axis."""
    return gravity_dir[1] != 0


def gravity_speed(vx, vy, gravity_dir):
    """Return velocity component along the gravity axis (dot product with gravity_dir)."""
    return vx * gravity_dir[0] + vy * gravity_dir[1]


def resolve_collisions(px, py, vx, vy, player_w, player_h, platforms, gravity_dir):
    """Two-pass collision resolution: lateral axis first, gravity axis second.

    Returns (px, py, vx, vy, on_ground).
    """
    grav_vert = gravity_is_vertical(gravity_dir)
    on_ground = False

    if grav_vert:
        px += vx
        pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        for plat in platforms:
            if pr.colliderect(plat):
                if vx > 0:
                    px = plat.left - player_w / 2
                elif vx < 0:
                    px = plat.right + player_w / 2
                vx = 0
                pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        py += vy
        pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        for plat in platforms:
            if pr.colliderect(plat):
                if vy > 0 or (vy == 0 and gravity_dir[1] > 0):
                    py = plat.top - player_h / 2
                    if gravity_dir[1] > 0:
                        on_ground = True
                else:
                    py = plat.bottom + player_h / 2
                    if gravity_dir[1] < 0:
                        on_ground = True
                vy = 0
                pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
    else:
        py += vy
        pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        for plat in platforms:
            if pr.colliderect(plat):
                if vy > 0:
                    py = plat.top - player_h / 2
                elif vy < 0:
                    py = plat.bottom + player_h / 2
                vy = 0
                pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        px += vx
        pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        for plat in platforms:
            if pr.colliderect(plat):
                if vx > 0 or (vx == 0 and gravity_dir[0] > 0):
                    px = plat.left - player_w / 2
                    if gravity_dir[0] > 0:
                        on_ground = True
                else:
                    px = plat.right + player_w / 2
                    if gravity_dir[0] < 0:
                        on_ground = True
                vx = 0
                pr = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)

    return px, py, vx, vy, on_ground


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
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)

    # Load level
    level = LevelRenderer()
    level.load(DEFAULT_LEVEL)

    # Load background (falls back to solid black if missing)
    background = load_background()

    # Load sprite (falls back to rectangle if missing)
    sprite_right = load_player_sprite()
    sprite_left = pygame.transform.flip(sprite_right, True, False) if sprite_right else None
    if sprite_right:
        player_w, player_h = sprite_right.get_size()
    else:
        player_w, player_h = PLAYER_SIZE, PLAYER_SIZE
    facing_right = True

    # Player state — spawn from level data
    px, py = level.spawn
    vx, vy = 0.0, 0.0
    gravity_dir = tuple(level.gravity_start)
    on_ground = False
    coyote_timer = 0.0
    jumping = False
    goal_reached = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        grav_vert = gravity_is_vertical(gravity_dir)

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    gravity_dir = rotate_gravity_ccw(gravity_dir)
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and coyote_timer > 0:
                    vx -= gravity_dir[0] * JUMP_SPEED
                    vy -= gravity_dir[1] * JUMP_SPEED
                    coyote_timer = 0.0
                    jumping = True
            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and jumping:
                    going_up = gravity_speed(vx, vy, gravity_dir) < 0
                    if going_up:
                        if grav_vert:
                            vy *= JUMP_CUT_MULTIPLIER
                        else:
                            vx *= JUMP_CUT_MULTIPLIER
                    jumping = False

        # Movement input
        keys = pygame.key.get_pressed()
        accel = ACCEL if on_ground else AIR_ACCEL
        decel = DECEL if on_ground else AIR_DECEL
        if grav_vert:
            move_input = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                move_input = -1
                facing_right = False
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                move_input = 1
                facing_right = True
            if move_input != 0:
                vx += move_input * accel
                vx = max(-MAX_MOVE_SPEED, min(MAX_MOVE_SPEED, vx))
            else:
                if abs(vx) < decel:
                    vx = 0
                else:
                    vx -= decel if vx > 0 else -decel
        else:
            move_input = 0
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                move_input = -1
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                move_input = 1
            if move_input != 0:
                vy += move_input * accel
                vy = max(-MAX_MOVE_SPEED, min(MAX_MOVE_SPEED, vy))
            else:
                if abs(vy) < decel:
                    vy = 0
                else:
                    vy -= decel if vy > 0 else -decel

        # Apply gravity
        grav_vel = gravity_speed(vx, vy, gravity_dir)
        at_peak = not on_ground and abs(grav_vel) < 2.0
        mult = PEAK_GRAVITY_MULT if at_peak else 1.0
        vx += gravity_dir[0] * GRAVITY_STRENGTH * mult
        vy += gravity_dir[1] * GRAVITY_STRENGTH * mult

        # Clamp gravity-axis velocity to terminal velocity
        grav_component = gravity_speed(vx, vy, gravity_dir)
        if abs(grav_component) > TERMINAL_VELOCITY:
            clamped = max(-TERMINAL_VELOCITY, min(TERMINAL_VELOCITY, grav_component))
            diff = clamped - grav_component
            vx += diff * gravity_dir[0]
            vy += diff * gravity_dir[1]

        # Update level
        level.update()

        # Collision resolution
        all_platforms = level.all_platform_rects()
        px, py, vx, vy, on_ground = resolve_collisions(
            px, py, vx, vy, player_w, player_h, all_platforms, gravity_dir
        )

        if on_ground:
            jumping = False
            coyote_timer = COYOTE_TIME
        else:
            coyote_timer = max(0.0, coyote_timer - dt)

        # Keep player on screen
        px = max(player_w / 2, min(WIDTH - player_w / 2, px))
        py = max(player_h / 2, min(HEIGHT - player_h / 2, py))

        # Goal check
        player_rect = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        if player_rect.colliderect(level.goal_rect):
            goal_reached = True

        # Draw
        if background:
            screen.blit(background, (0, 0))
        else:
            screen.fill(BLACK)

        level.draw(screen)

        # Draw player
        player_rect = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        if sprite_right:
            sprite = sprite_right if facing_right else sprite_left
            screen.blit(sprite, player_rect.topleft)
        else:
            pygame.draw.rect(screen, RED, player_rect)
            cx, cy = player_rect.center
            pygame.draw.circle(screen, WHITE, (
                int(cx - gravity_dir[0] * 12),
                int(cy - gravity_dir[1] * 12),
            ), 4)

        # HUD
        label = font.render(
            f"Gravity: {GRAVITY_LABELS[gravity_dir]}  |  R to rotate  |  Arrow keys + Space",
            True, BLUE
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
