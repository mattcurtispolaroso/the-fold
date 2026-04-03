"""All tunable game constants in one place.

Import from here — never hardcode numeric values in logic files.
"""

# --- Display ---
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60

# --- Camera ---
CAMERA_FOLLOW_SPEED: float = 5.0      # lerp speed (higher = snappier)
CAMERA_DEAD_ZONE_X: float = 30.0      # pixels — no follow within this range
CAMERA_DEAD_ZONE_Y: float = 20.0      # pixels — no follow within this range
CAMERA_RECENTRE_DURATION: float = 0.3  # seconds to re-centre after gravity rotation
CAMERA_RECENTRE_SPEED: float = 15.0    # boosted lerp speed during re-centre
CAMERA_ZOOM_SPEED: float = 3.0        # zoom lerp speed

# --- Screen Shake ---
SCREEN_SHAKE_ENABLED: bool = True
ROTATE_SHAKE_INTENSITY: float = 15.0   # pixels — dramatic world-shifting event
ROTATE_SHAKE_DURATION: float = 0.4     # seconds

# --- Physics Scale ---
PPM: int = 50                                             # pixels per meter
EARTH_GRAVITY: float = 9.8                                # m/s²
GRAVITY_STRENGTH: float = EARTH_GRAVITY * PPM / FPS**2    # ~0.136 px/frame²
TERMINAL_VELOCITY: float = 53.0 * PPM / FPS               # ~44.2 px/frame

# --- Player Movement ---
JUMP_SPEED: float = 8.0
ACCEL: float = 1.5           # ground lateral acceleration per frame
DECEL: float = 1.0           # ground lateral deceleration per frame
AIR_ACCEL: float = 0.4       # air lateral acceleration
AIR_DECEL: float = 0.1       # air lateral deceleration
MAX_MOVE_SPEED: float = 5.0  # max lateral speed

# --- Jump Tuning ---
COYOTE_TIME: float = 0.1             # seconds grace period after leaving ground
JUMP_CUT_MULTIPLIER: float = 0.4     # velocity multiplier on early jump release
PEAK_GRAVITY_MULT: float = 2.5       # gravity multiplier near jump peak
PEAK_SPEED_THRESHOLD: float = 2.0    # speed below which peak gravity kicks in

# --- Player Sprites ---
PLAYER_SPRITE_WIDTH: int = 60
PLAYER_SPRITE_HEIGHT: int = 90

DEBUG_DRAW_RECTS: bool = False        # draw physics rects for debugging
SPRITE_PHYSICS_OFFSET_Y: int = 0      # vertical pixel offset to align sprite to physics rect

# Walk animation tuning
WALK_ANIM_MIN_SPEED: float = 0.5     # lateral speed below which walk anim pauses
WALK_ANIM_MIN_FPS: int = 6           # slowest walk cycle rate
WALK_ANIM_MAX_FPS: int = 12          # fastest walk cycle rate

# Sprite rotation per gravity direction (degrees for pygame.transform.rotate)
# pygame.transform.rotate: positive = counter-clockwise
SPRITE_ROTATION: dict = {
    (0, 1): 0,      # DOWN — normal upright
    (0, -1): 180,   # UP — handled via flip(True, True) not rotate
    (-1, 0): -90,   # LEFT — rotate CW 90, feet point left
    (1, 0): 90,     # RIGHT — rotate CCW 90, feet point right
}
# --- Animation State Thresholds ---
JUMP_RISING_THRESHOLD: float = -1.0   # gravity_speed below this = rising
JUMP_PEAK_THRESHOLD: float = 1.0      # abs(gravity_speed) below this = peak

PLAYER_SPRITE_PATHS: dict = {
    "player_1": "assets/sprites/players/player_1/",
    "player_2": "assets/sprites/players/player_2/",
    "player_3": "assets/sprites/players/player_3/",
}
PLAYER_1_SPRITE_PATH: str = PLAYER_SPRITE_PATHS["player_1"]
