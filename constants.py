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
PLAYER_SIZE: int = 90
JUMP_SPEED: float = 8.0
MOVE_SPEED: float = 5.0
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
