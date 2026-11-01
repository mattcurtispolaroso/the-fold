"""All tunable game constants in one place.

Import from here — never hardcode numeric values in logic files.
"""

# --- Display ---
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60
PHYSICS_DT: float = 1.0 / FPS  # fixed physics timestep (seconds per step)

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

# --- Rotation Flash Overlay ---
ROTATION_FLASH_COLOR: tuple = (200, 220, 255)  # pale blue-white
ROTATION_FLASH_DURATION: float = 0.35          # seconds to fade out
ROTATION_FLASH_MAX_ALPHA: int = 90             # peak opacity (0-255)

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

# --- Player Physics Rect ---
PLAYER_PHYSICS_WIDTH_NORMAL: int = 64    # width when gravity is DOWN or UP
PLAYER_PHYSICS_HEIGHT_NORMAL: int = 96   # height when gravity is DOWN or UP
PLAYER_PHYSICS_WIDTH_HORIZONTAL: int = 96  # width when gravity is LEFT or RIGHT
PLAYER_PHYSICS_HEIGHT_HORIZONTAL: int = 64  # height when gravity is LEFT or RIGHT

# --- Player Sprites ---
PLAYER_SPRITE_WIDTH: int = 60
PLAYER_SPRITE_HEIGHT: int = 90

DEBUG_DRAW_RECTS: bool = False        # draw physics rects for debugging
SPRITE_PHYSICS_OFFSET_Y: int = 0      # vertical pixel offset to align sprite to physics rect

# --- Sprite Sheet Source Dimensions ---
SPRITE_SHEET_FRAME_WIDTH: int = 256   # source frame width on sheets
SPRITE_SHEET_FRAME_HEIGHT: int = 384  # source frame height on sheets

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

# --- Jump Sheet Frame Mapping ---
# 8-frame jump sheet: anticipation, launch, rising_fast, rising_slow,
#                     peak, falling_slow, falling_fast, land_impact
JUMP_SHEET_FRAMES: int = 8
JUMP_SHEET_ANTICIPATION: int = 0
JUMP_SHEET_LAUNCH: int = 1
JUMP_SHEET_RISING_FAST: int = 2
JUMP_SHEET_RISING_SLOW: int = 3
JUMP_SHEET_PEAK: int = 4
JUMP_SHEET_FALLING_SLOW: int = 5
JUMP_SHEET_FALLING_FAST: int = 6
JUMP_SHEET_LAND_IMPACT: int = 7

# --- Helmet Overlay ---
HELMET_HEAD_DISTANCE: float = 0.35   # fraction of sprite height from centre to head
HELMET_HEAD_OFFSET_X: int = 0        # fine-tuning offset applied AFTER gravity calc
HELMET_HEAD_OFFSET_Y: int = 0        # fine-tuning offset applied AFTER gravity calc
HELMET_ACTIVATE_FRAMES: int = 5      # frames in activation sequence
HELMET_ANIM_FPS: int = 12            # playback speed for helmet animation

PLAYER_SPRITE_PATHS: dict = {
    "player_1": "assets/sprites/players/player_1/",
    "player_2": "assets/sprites/players/player_2/",
    "player_3": "assets/sprites/players/player_3/",
}
PLAYER_1_SPRITE_PATH: str = PLAYER_SPRITE_PATHS["player_1"]

# Sprite sheet filenames (placed inside each player's sprite directory)
SHEET_FILENAMES: dict = {
    "jump": "player_1_jump_sheet.png",
    "walk": "player_1_walk_sheet.png",
    "idle": "player_1_idle_sheet.png",
    "gravity_rotating": "player_1_gravity_rotating_sheet.png",
    "combat": "player_1_combat_sheet.png",
    "ability": "player_1_ability_sheet.png",
}
SHEET_FRAME_COUNTS: dict = {
    "jump": 8,
    "walk": 6,
    "idle": 4,
    "gravity_rotating": 5,
    "combat": 7,
    "ability": 6,
}

# Helmet overlay sheet filenames
HELMET_ACTIVATE_SHEET: str = "player_1_helmet_activate.png"
HELMET_ON_SPRITE: str = "player_1_helmet_on.png"

# --- Physics Watchdog ---
PHYSICS_WATCHDOG_THRESHOLD_MS: float = 16.0  # warn if physics step exceeds this
PHYSICS_WATCHDOG_ENABLED: bool = True

# --- Entity Count Limits (enforced by entity system in Module 5) ---
MAX_ENEMIES: int = 20
MAX_PARTICLES: int = 500
MAX_PROJECTILES: int = 50
MAX_ACTIVE_ABILITIES: int = 10

# --- Chrono Reserve (ability fuel resource) ---
CHRONO_RESERVE_MAX: float = 100.0
CHRONO_REGEN_MOVE: float = 15.0   # per second during active lateral movement
CHRONO_REGEN_IDLE: float = 0.0    # per second while idle (passive play earns nothing)
CHRONO_DRAIN_TEST: float = 30.0   # per second drain via Q key (placeholder until abilities land)

# --- Time Dilation (M2 ability, E key) ---
TIME_DILATION_COST: float = 25.0      # chrono_reserve spent on activation
TIME_DILATION_DURATION: float = 3.0   # seconds platforms are frozen
TIME_DILATION_COOLDOWN: float = 2.0   # seconds after duration before reuse
TIME_DILATION_FACTOR: float = 0.0     # platform time scale while active (0 = frozen)

# --- Font ---
FONT_PATH: str = "assets/fonts/main_font.ttf"
FONT_SIZE: int = 28
