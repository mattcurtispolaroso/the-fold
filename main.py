import os
import pygame
import sys

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SIZE = 90
FLOOR_THICKNESS = 20

# Physics scale: 50 pixels = 1 meter
PPM = 50
EARTH_GRAVITY = 9.8                              # m/s²
GRAVITY_STRENGTH = EARTH_GRAVITY * PPM / FPS**2  # ~0.136 px/frame²
TERMINAL_VELOCITY = 53.0 * PPM / FPS             # ~44.2 px/frame (human free-fall ~53 m/s)

JUMP_SPEED = 4.0     # tuned for new gravity — ~0.5s to peak, ~2x player height
MOVE_SPEED = 5

# Movement tuning
ACCEL = 1.5          # horizontal acceleration per frame
DECEL = 2.0          # horizontal deceleration per frame (when no input)
MAX_MOVE_SPEED = 5   # max horizontal speed

# Jump tuning
COYOTE_TIME = 0.1    # seconds after leaving ground where jump is still allowed
JUMP_CUT_MULTIPLIER = 0.4  # multiply velocity by this when jump key released early
PEAK_GRAVITY_MULT = 2.5    # extra gravity when near the peak of a jump

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 50, 50)
GRAY = (100, 100, 100)
BLUE = (50, 80, 180)

# Gravity directions: 0=down, 1=left, 2=up, 3=right
GRAVITY_VECTORS = [
    (0, GRAVITY_STRENGTH),   # down
    (-GRAVITY_STRENGTH, 0),  # left
    (0, -GRAVITY_STRENGTH),  # up
    (GRAVITY_STRENGTH, 0),   # right
]

# Floor rects for each orientation (the surface you stand on)
FLOORS = [
    pygame.Rect(0, HEIGHT - FLOOR_THICKNESS, WIDTH, FLOOR_THICKNESS),          # bottom
    pygame.Rect(0, 0, FLOOR_THICKNESS, HEIGHT),                                 # left wall
    pygame.Rect(0, 0, WIDTH, FLOOR_THICKNESS),                                  # top
    pygame.Rect(WIDTH - FLOOR_THICKNESS, 0, FLOOR_THICKNESS, HEIGHT),           # right wall
]

ORIENTATION_LABELS = ["Down", "Left", "Up", "Right"]


def gravity_speed(vx, vy, orientation):
    """Return the velocity component along the gravity axis."""
    if orientation in (0, 2):
        return vy
    return vx


def load_player_sprite():
    """Load player.png from assets/, scaled to PLAYER_SIZE height preserving aspect ratio. Returns None if not found."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "player.png")
    if not os.path.isfile(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    # Scale to PLAYER_SIZE height, preserve aspect ratio
    w, h = img.get_size()
    scale = PLAYER_SIZE / h
    return pygame.transform.smoothscale(img, (int(w * scale), PLAYER_SIZE))


def load_background():
    """Load background.png from assets/backgrounds/, scaled to screen size. Returns None if not found."""
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

    # Player state
    px, py = WIDTH / 2.0, HEIGHT / 2.0
    vx, vy = 0.0, 0.0
    orientation = 0  # 0=down, 1=left, 2=up, 3=right
    on_ground = False
    coyote_timer = 0.0
    jumping = False  # True while player is holding jump after launching

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    orientation = (orientation - 1) % 4
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and coyote_timer > 0:
                    # Jump opposite to gravity
                    gx, gy = GRAVITY_VECTORS[orientation]
                    vx -= gx * JUMP_SPEED / GRAVITY_STRENGTH
                    vy -= gy * JUMP_SPEED / GRAVITY_STRENGTH
                    coyote_timer = 0.0
                    jumping = True
            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and jumping:
                    # Variable jump height: cut velocity short on early release
                    gx, gy = GRAVITY_VECTORS[orientation]
                    # Only cut if still moving upward (against gravity)
                    grav_vel = gravity_speed(vx, vy, orientation)
                    going_up = (orientation == 0 and vy < 0) or \
                               (orientation == 1 and vx > 0) or \
                               (orientation == 2 and vy > 0) or \
                               (orientation == 3 and vx < 0)
                    if going_up:
                        if orientation in (0, 2):
                            vy *= JUMP_CUT_MULTIPLIER
                        else:
                            vx *= JUMP_CUT_MULTIPLIER
                    jumping = False

        # Movement input (always relative to screen axes, perpendicular to gravity)
        keys = pygame.key.get_pressed()
        if orientation in (0, 2):  # gravity vertical -> move horizontally
            move_input = 0
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                move_input = -1
                facing_right = False
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                move_input = 1
                facing_right = True

            if move_input != 0:
                vx += move_input * ACCEL
                vx = max(-MAX_MOVE_SPEED, min(MAX_MOVE_SPEED, vx))
            else:
                # Decelerate
                if abs(vx) < DECEL:
                    vx = 0
                else:
                    vx -= DECEL if vx > 0 else -DECEL
        else:  # gravity horizontal -> move vertically
            move_input = 0
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                move_input = -1
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                move_input = 1

            if move_input != 0:
                vy += move_input * ACCEL
                vy = max(-MAX_MOVE_SPEED, min(MAX_MOVE_SPEED, vy))
            else:
                if abs(vy) < DECEL:
                    vy = 0
                else:
                    vy -= DECEL if vy > 0 else -DECEL

        # Apply gravity (with peak gravity multiplier for weighty feel)
        gx, gy = GRAVITY_VECTORS[orientation]
        grav_vel = gravity_speed(vx, vy, orientation)
        # Near peak of jump: low velocity against gravity direction
        at_peak = not on_ground and abs(grav_vel) < 2.0
        mult = PEAK_GRAVITY_MULT if at_peak else 1.0
        vx += gx * mult
        vy += gy * mult

        # Clamp fall speed to terminal velocity
        if orientation in (0, 2):
            vy = max(-TERMINAL_VELOCITY, min(TERMINAL_VELOCITY, vy))
        else:
            vx = max(-TERMINAL_VELOCITY, min(TERMINAL_VELOCITY, vx))

        # Move player
        px += vx
        py += vy

        # Collision with floor
        player_rect = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        floor_rect = FLOORS[orientation]
        on_ground = False

        if player_rect.colliderect(floor_rect):
            on_ground = True
            jumping = False
            if orientation == 0:  # floor at bottom
                py = floor_rect.top - player_h / 2
                vy = 0
            elif orientation == 1:  # floor at left
                px = floor_rect.right + player_w / 2
                vx = 0
            elif orientation == 2:  # floor at top
                py = floor_rect.bottom + player_h / 2
                vy = 0
            elif orientation == 3:  # floor at right
                px = floor_rect.left - player_w / 2
                vx = 0

        # Coyote time
        if on_ground:
            coyote_timer = COYOTE_TIME
        else:
            coyote_timer = max(0.0, coyote_timer - dt)

        # Keep player on screen
        px = max(player_w / 2, min(WIDTH - player_w / 2, px))
        py = max(player_h / 2, min(HEIGHT - player_h / 2, py))

        # Draw
        if background:
            screen.blit(background, (0, 0))
        else:
            screen.fill(BLACK)

        # Draw floor
        pygame.draw.rect(screen, GRAY, floor_rect)

        # Draw player
        player_rect = pygame.Rect(px - player_w / 2, py - player_h / 2, player_w, player_h)
        if sprite_right:
            sprite = sprite_right if facing_right else sprite_left
            screen.blit(sprite, player_rect.topleft)
        else:
            pygame.draw.rect(screen, RED, player_rect)
            # Direction indicator fallback (shows which way is "up" for the player)
            cx, cy = player_rect.center
            gx, gy = GRAVITY_VECTORS[orientation]
            pygame.draw.circle(screen, WHITE, (int(cx - gx * 12 / GRAVITY_STRENGTH), int(cy - gy * 12 / GRAVITY_STRENGTH)), 4)

        # HUD
        label = font.render(f"Gravity: {ORIENTATION_LABELS[orientation]}  |  R to rotate  |  Arrow keys + Space", True, BLUE)
        screen.blit(label, (10, 10))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
