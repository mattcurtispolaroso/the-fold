import pygame
import sys

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SIZE = 30
GRAVITY_STRENGTH = 0.5
MOVE_SPEED = 5
JUMP_SPEED = 10
FLOOR_THICKNESS = 20

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


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)

    # Player state
    px, py = WIDTH / 2.0, HEIGHT / 2.0
    vx, vy = 0.0, 0.0
    orientation = 0  # 0=down, 1=left, 2=up, 3=right
    on_ground = False

    running = True
    while running:
        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    orientation = (orientation + 1) % 4
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and on_ground:
                    # Jump opposite to gravity
                    gx, gy = GRAVITY_VECTORS[orientation]
                    vx -= gx * JUMP_SPEED / GRAVITY_STRENGTH
                    vy -= gy * JUMP_SPEED / GRAVITY_STRENGTH

        # Movement input (always relative to screen axes, perpendicular to gravity)
        keys = pygame.key.get_pressed()
        if orientation in (0, 2):  # gravity vertical -> move horizontally
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                vx = -MOVE_SPEED
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                vx = MOVE_SPEED
            else:
                vx *= 0.8  # friction
        else:  # gravity horizontal -> move vertically
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                vy = -MOVE_SPEED
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                vy = MOVE_SPEED
            else:
                vy *= 0.8

        # Apply gravity
        gx, gy = GRAVITY_VECTORS[orientation]
        vx += gx
        vy += gy

        # Move player
        px += vx
        py += vy

        # Collision with floor
        player_rect = pygame.Rect(px - PLAYER_SIZE / 2, py - PLAYER_SIZE / 2, PLAYER_SIZE, PLAYER_SIZE)
        floor_rect = FLOORS[orientation]
        on_ground = False

        if player_rect.colliderect(floor_rect):
            on_ground = True
            if orientation == 0:  # floor at bottom
                py = floor_rect.top - PLAYER_SIZE / 2
                vy = 0
            elif orientation == 1:  # floor at left
                px = floor_rect.right + PLAYER_SIZE / 2
                vx = 0
            elif orientation == 2:  # floor at top
                py = floor_rect.bottom + PLAYER_SIZE / 2
                vy = 0
            elif orientation == 3:  # floor at right
                px = floor_rect.left - PLAYER_SIZE / 2
                vx = 0

        # Keep player on screen
        px = max(PLAYER_SIZE / 2, min(WIDTH - PLAYER_SIZE / 2, px))
        py = max(PLAYER_SIZE / 2, min(HEIGHT - PLAYER_SIZE / 2, py))

        # Draw
        screen.fill(BLACK)

        # Draw floor
        pygame.draw.rect(screen, GRAY, floor_rect)

        # Draw player
        player_rect = pygame.Rect(px - PLAYER_SIZE / 2, py - PLAYER_SIZE / 2, PLAYER_SIZE, PLAYER_SIZE)
        pygame.draw.rect(screen, RED, player_rect)

        # Draw a small direction indicator on the player (shows which way is "up" for the player)
        cx, cy = player_rect.center
        gx, gy = GRAVITY_VECTORS[orientation]
        pygame.draw.circle(screen, WHITE, (int(cx - gx * 12 / GRAVITY_STRENGTH), int(cy - gy * 12 / GRAVITY_STRENGTH)), 4)

        # HUD
        label = font.render(f"Gravity: {ORIENTATION_LABELS[orientation]}  |  R to rotate  |  Arrow keys + Space", True, BLUE)
        screen.blit(label, (10, 10))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
