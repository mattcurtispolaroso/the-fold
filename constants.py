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

# --- Rotation Cinematic Zoom ---
ROTATION_ZOOM_PEAK: float = 1.08    # zoom factor at cinematic peak
ROTATION_ZOOM_IN_DUR: float = 0.07  # seconds to zoom in (ease-out)
ROTATION_ZOOM_HOLD_DUR: float = 0.03  # seconds held at peak
ROTATION_ZOOM_OUT_DUR: float = 0.08  # seconds to zoom out (ease-in)

# --- Physics Safety ---
EPSILON: float = 0.001  # floating-point zero threshold; use abs(v) < EPSILON instead of v == 0

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
AIR_DECEL: float = 0.25      # air lateral deceleration
MAX_MOVE_SPEED: float = 5.0  # max lateral speed

# --- Jump Tuning ---
COYOTE_TIME: float = 0.1             # seconds grace period after leaving ground
JUMP_CUT_MULTIPLIER: float = 0.4     # velocity multiplier on early jump release
JUMP_BUFFER_FRAMES: int = 10         # frames a buffered jump input stays alive
JUMP_BUFFER_TIME: float = JUMP_BUFFER_FRAMES / FPS  # ~0.167s at 60fps
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

# --- Renderer ---
USE_GPU_RENDERER: bool = True   # False or env FOLD_RENDERER=software → Pygame fallback

# --- Parallax Layers (TA-2, GPU path only) ---
# Back-to-front draw order. "play" holds geometry, enemies and the player and
# must always scroll at 1.0 so it stays locked to physics.
PARALLAX_LAYER_NAMES: tuple[str, ...] = ("sky", "far", "mid", "play", "fore")
PARALLAX_PLAY_LAYER: str = "play"
PARALLAX_IMAGE_LAYERS: tuple[str, ...] = ("sky", "far", "mid")  # drawn from background images
PARALLAX_SCROLL_FACTORS: dict[str, float] = {
    "sky": 0.05, "far": 0.20, "mid": 0.50, "play": 1.00, "fore": 1.30,
}
PARALLAX_SCROLL_MIN: float = 0.0   # level JSON overrides are clamped to this range
PARALLAX_SCROLL_MAX: float = 2.0
PARALLAX_LAYER_ART_DIR: str = "assets/backgrounds/layers"  # <name>.png overrides placeholder
# Procedural placeholder split of background.png (Q6) — RGB multipliers + alpha shaping
PARALLAX_SKY_TINT: tuple[float, float, float] = (0.45, 0.55, 0.85)   # dim, cool, opaque
PARALLAX_SKY_BLUR_DIVISOR: int = 8   # downscale factor for the sky haze blur (1 = sharp)
PARALLAX_FAR_TINT: tuple[float, float, float] = (1.25, 1.35, 1.40)   # bright features only
PARALLAX_FAR_LUMA_LOW: float = 0.10    # luminance at which far-layer alpha starts rising
PARALLAX_FAR_LUMA_HIGH: float = 0.35   # luminance at which far-layer alpha is full
PARALLAX_MID_TINT: tuple[float, float, float] = (0.35, 0.30, 0.30)   # dark silhouette band
PARALLAX_MID_BAND_START: float = 0.55  # fraction of height where mid-layer alpha starts
PARALLAX_MID_BAND_FULL: float = 0.75   # fraction of height where mid-layer alpha is full

# --- 2D Lighting (TA-3, GPU path only) ---
# Only levels with a "lights" key are lit; others render unlit (identity).
LIGHT_MAX_PER_LEVEL: int = 10           # point + spot lights; extras are dropped with a warning
LIGHT_SHADER_SLOTS: int = LIGHT_MAX_PER_LEVEL + 1   # + the player light
LIGHT_RADIUS_MIN: float = 1.0           # px; clamps level JSON values
LIGHT_RADIUS_MAX: float = 2000.0
LIGHT_INTENSITY_MAX: float = 4.0
LIGHT_SPREAD_MAX: float = 360.0         # spot cone full width, degrees
LIGHT_SPOT_INNER_FRAC: float = 0.7      # fraction of the cone at full strength (soft edge beyond)
LIGHT_BUFFER_MAX_BRIGHTNESS: float = 2.0  # per-channel cap on summed light (allows mild overbright)
LIGHT_DEFAULT_AMBIENT: tuple[float, float, float] = (0.35, 0.38, 0.45)  # lit level with no ambient entry
PARALLAX_LIT_LAYERS: tuple[str, ...] = ("mid", "play")  # multiplied by the light buffer
PLAYER_LIGHT_RADIUS: float = 220.0
PLAYER_LIGHT_COLOR: tuple[float, float, float] = (1.0, 0.72, 0.38)   # warm amber (exosuit glow)
PLAYER_LIGHT_INTENSITY: float = 0.85

# --- Post-Processing (TA-4, GPU path only; HUD and fold tint are drawn after, unaffected) ---
POST_PASS_ORDER: tuple[str, ...] = ("bloom", "distortion", "lut", "vignette", "grain", "crt")
POST_PASS_DEFAULTS: dict[str, bool] = {
    "bloom": True, "distortion": True, "lut": True, "vignette": True, "grain": True,
    "crt": False,   # TA Q5: toggle wired, shader is a pass-through stub
}
BLOOM_THRESHOLD: float = 0.55      # luminance where bloom starts (art is dark; goal/cyan ≈ 0.65)
BLOOM_KNEE: float = 0.15           # soft-knee width below/above the threshold
BLOOM_INTENSITY: float = 0.9       # strength of the blurred glow added back
BLOOM_DOWNSAMPLE: int = 2          # bloom buffers run at 1/N resolution
BLOOM_BLUR_PASSES: int = 2         # horizontal+vertical blur iterations
VIGNETTE_STRENGTH: float = 0.45    # 0 = none, 1 = corners fully black
VIGNETTE_INNER: float = 0.35       # normalised radius where darkening starts
VIGNETTE_OUTER: float = 0.95       # normalised radius where darkening is full
GRAIN_AMOUNT: float = 0.03         # ± noise amplitude in highlights (0-1 colour units)
GRAIN_SHADOW_SCALE: float = 0.25   # grain multiplier at black (keeps near-black art readable)
GRAIN_FULL_LUMA: float = 0.4       # luminance at which grain reaches full amplitude
LUT_SIZE: int = 16                 # 16×16×16 colour-grading cube
LUT_STRENGTH: float = 1.0          # 0 = ungraded, 1 = full grade
LUT_ART_PATH: str = "assets/luts/grade.png"   # 256×16 strip overrides the procedural grade
GRADE_CONTRAST: float = 1.05       # procedural grade: contrast around GRADE_CONTRAST_PIVOT
GRADE_CONTRAST_PIVOT: float = 0.18 # photographic mid-grey; a 0.5 pivot crushes this dark art
GRADE_SATURATION: float = 0.92     # procedural grade: 1 = unchanged
GRADE_SHADOW_TINT: tuple[float, float, float] = (0.0, 0.008, 0.02)     # teal lift (never subtracts)
GRADE_HIGHLIGHT_TINT: tuple[float, float, float] = (0.04, 0.02, -0.025)  # warm highlights

# --- Fold Distortion + Gravity Bend (TA-5; pixels are internal-resolution pixels) ---
DISTORTION_MAX_RIPPLES: int = 4        # concurrent ripples; the oldest is recycled
DISTORTION_STRENGTH_MAX: float = 3.0   # clamp on feel.distortion(strength=...)
DISTORTION_MAX_OFFSET_PX: float = 32.0 # hard cap on total per-pixel displacement
RIPPLE_DURATION: float = 0.6           # seconds for a ripple to expand and fade
RIPPLE_MAX_RADIUS_PX: float = 420.0    # ring radius at the end of the ripple
RIPPLE_WIDTH_PX: float = 40.0          # thickness of the ring (Gaussian width)
RIPPLE_AMPLITUDE_PX: float = 14.0      # peak ring displacement at strength 1.0
BEND_DURATION: float = 0.35            # seconds for the gravity-flip bend (out and back)
BEND_AMPLITUDE_PX: float = 18.0        # peak bow of the frame toward the new gravity
ABERRATION_MAX_PX: float = 4.0         # red/blue split at the screen corners at peak effect

# --- Feel framework (TA-6) ---
ACCESSIBILITY_REDUCED_EFFECTS: bool = False  # start in reduced-effects mode (F3 + 0 toggles)
FEEL_INTENSITY_DEFAULT: float = 1.0
FEEL_INTENSITY_REDUCED: float = 0.3    # multiplier on every feel effect in reduced mode
HITSTOP_MAX: float = 0.2               # clamp on any single hitstop (seconds)
HIT_HITSTOP: float = 0.06              # physics freeze when an enemy hits the player
HARD_LAND_HITSTOP: float = 0.04        # physics freeze on a damaging hard landing
HIT_SHAKE_INTENSITY: float = 4.0       # px; small kick when hit
HIT_SHAKE_DURATION: float = 0.12
SPRITE_FLASH_MAX: float = 0.85         # peak mix toward the flash colour (1 = solid silhouette)
HIT_FLASH_COLOR: tuple[float, float, float] = (1.0, 1.0, 1.0)      # white
HIT_FLASH_DURATION: float = 0.12
DILATION_FLASH_COLOR: tuple[float, float, float] = (1.0, 0.68, 0.28)  # exosuit amber
DILATION_FLASH_DURATION: float = 0.2
SQUASH_MAX: float = 0.4                # clamp on |squash amount|
SQUASH_DURATION: float = 0.15          # seconds to spring back to 1
LAND_SQUASH: float = 0.15              # positive = squash along gravity
HARD_LAND_SQUASH: float = 0.3
JUMP_STRETCH: float = -0.12            # negative = stretch along gravity

DEBUG_DRAW_RECTS: bool = False        # draw physics rects for debugging
SPRITE_PHYSICS_OFFSET_Y: int = 0      # vertical pixel offset to align sprite to physics rect

# --- Sprite Sheet Source Dimensions ---
SPRITE_SHEET_FRAME_WIDTH: int = 256   # source frame width on sheets
SPRITE_SHEET_FRAME_HEIGHT: int = 384  # source frame height on sheets

# Walk / Land animation tuning
WALK_ANIM_MIN_SPEED: float = 0.5     # lateral speed below which walk anim pauses
LAND_ANIM_DURATION: float = 0.1      # seconds to show LAND frame after touching ground
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
JUMP_SHEET_ANTICIPATION: int = 0  # frame exists in sheet; no in-game state maps to it
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

# --- Item System (M5a) ---
MODIFIER_CAP: int = 6
HAWKING_RADIUS: float = 200.0
PARADOX_OFFER_CHANCE: float = 0.15
DEBUG_ITEMS: bool = True
ARTIFACT_COST_PENROSE_DIAGRAM: float = 10.0
ARTIFACT_COST_KERR_RING: float = 20.0
ARTIFACT_COST_HAWKING_EMITTER: float = 25.0

# --- Fold Stability (run survival resource) ---
FOLD_STABILITY_MAX: float = 100.0
FOLD_STABILITY_INTEGRITY_COST: float = 15.0  # lost per integrity-0 death (~6-7 deaths end a run)
FOLD_TINT_THRESHOLD: float = 80.0            # stability below this → red tint starts
FOLD_TINT_MAX_ALPHA: int = 110               # tint alpha at stability = 0

# --- Combat (M3) ---
IFRAMES_DURATION: float = 0.8         # seconds invincible after taking a hit
KNOCKBACK_FORCE: float = 6.0          # px/frame lateral velocity impulse on hit
KNOCKBACK_VERTICAL_FORCE: float = 4.0  # px/frame upward (anti-gravity) impulse on hit

# --- Fold Predator (M5b enemy) ---
FOLD_PREDATOR_W: int = 40
FOLD_PREDATOR_H: int = 60
FOLD_PREDATOR_SPEED: float = 2.5
FOLD_PREDATOR_CHASE_RANGE: float = 350.0
FOLD_PREDATOR_STUN_DURATION: float = 2.0
FOLD_PREDATOR_PHASE_INTERVAL: float = 4.0
FOLD_PREDATOR_PHASE_DURATION: float = 0.5
FOLD_PREDATOR_PHASE_SPEED_MULT: float = 2.5
FOLD_PREDATOR_COLOR: tuple = (180, 60, 220)       # purple
FOLD_PREDATOR_STUN_COLOR: tuple = (220, 220, 255)  # pale blue-white
FOLD_PREDATOR_PHASE_COLOR: tuple = (230, 120, 255) # bright purple

# --- The Anchored (M5e enemy) ---
ANCHORED_W: int = 44
ANCHORED_H: int = 64
ANCHORED_SPEED: float = 1.2
ANCHORED_WANDER_CHANGE_INTERVAL: float = 2.0   # seconds between random direction changes
ANCHORED_STUTTER_INTERVAL: float = 5.0          # seconds between stutter bursts
ANCHORED_STUTTER_DURATION: float = 0.4          # seconds the burst lasts
ANCHORED_STUTTER_SPEED_MULT: float = 4.0        # speed multiplier during stutter
ANCHORED_COLOR: tuple = (140, 210, 60)           # sickly yellow-green
ANCHORED_STUTTER_COLOR: tuple = (255, 240, 100)  # bright yellow during stutter

# --- Temporal Echo (M3 enemy placeholder) ---
TEMPORAL_ECHO_W: int = 40
TEMPORAL_ECHO_H: int = 60
TEMPORAL_ECHO_SPEED: float = 2.0
TEMPORAL_ECHO_COLOR: tuple = (80, 220, 220)  # cyan

# --- Anchor Integrity (personal survival — 3-hit pool) ---
ANCHOR_INTEGRITY_MAX: int = 3

# --- Chrono Reserve (ability fuel resource) ---
CHRONO_RESERVE_MAX: float = 100.0
CHRONO_REGEN_MOVE: float = 15.0   # per second during active lateral movement
CHRONO_REGEN_IDLE: float = 0.0    # per second while idle (passive play earns nothing)

# --- Gravity Rotation ---
GRAVITY_ROTATION_COST: float = 10.0     # chrono spent per rotation; blocks rotation if insufficient
ROTATION_COOLDOWN: float = 0.4          # seconds before another rotation is allowed

# --- Gravity Off-Default Drain ---
# Chrono drains while in non-default gravity; when chrono hits 0, gravity snaps back.
# Net movement regen (15/s) exceeds drain early game (+5/s), but near singularity
# regen throttles to ~5/s so even moving can't offset the drain — gravity becomes
# unsustainable late game by design.
GRAVITY_OFFDEFAULT_DRAIN: float = 10.0  # chrono per second

# --- Fall / Impact Damage ---
HARD_LAND_VELOCITY: float = 13.0  # px/physics-frame — impact above this deals 1 integrity hit
HARD_LAND_PUNCH_MAGNITUDE: float = 14.0   # pixels of camera jolt in gravity direction
HARD_LAND_PUNCH_DURATION: float = 0.22    # seconds for jolt to decay to zero
HARD_LAND_FLASH_COLOR: tuple = (220, 60, 60)   # red-orange
HARD_LAND_FLASH_DURATION: float = 0.30          # seconds to fade out
HARD_LAND_FLASH_MAX_ALPHA: int = 80             # peak opacity (0-255)

# --- Singularity Pressure ---
SINGULARITY_CHRONO_REGEN_MIN_MULT: float = 0.33  # regen fraction at max pressure
SINGULARITY_ABILITY_COST_MAX_MULT: float = 2.0   # ability cost multiplier at max pressure
SINGULARITY_GRAVITY_MAX_MULT: float = 1.5        # gravity strength multiplier at max pressure

# --- Time Dilation (M2 ability, E key) ---
TIME_DILATION_COST: float = 25.0             # chrono_reserve spent on activation
TIME_DILATION_DURATION: float = 3.0          # seconds platforms are frozen
TIME_DILATION_POST_EFFECT_WAIT: float = 2.0  # seconds AFTER effect ends before reuse
                                              # total recharge = DURATION + POST_EFFECT_WAIT = 5.0s
TIME_DILATION_FACTOR: float = 0.0            # platform time scale while active (0 = frozen)

# --- Node Map (M4b) ---
NODE_SEQUENCE: tuple = (
    "combat", "hole", "combat", "hole",
    "combat", "hole", "combat", "hole",
    "singularity"
)

# --- Hole Encounter (M4b) ---
WHITE_HOLE_STABILITY_RESTORE: float = 15.0   # fold_stability restored on white hole
BLACK_HOLE_STABILITY_COST: float = 10.0      # fold_stability lost on black hole
HOLE_ENCOUNTER_PHASE1_DURATION: float = 1.5  # seconds showing "ENTERING THE ANOMALY..."
HOLE_ENCOUNTER_PHASE2_DURATION: float = 2.0  # seconds showing the outcome

# --- HUD Layout ---
HUD_PIP_SIZE: int = 16               # integrity pip square size (px)
HUD_PIP_GAP: int = 5                 # gap between pips
HUD_PIP_X: int = 14                  # pip row left edge
HUD_PIP_Y: int = 14                  # pip row top edge
HUD_CHRONO_SEG_W: int = 16           # chrono segment width
HUD_CHRONO_SEG_H: int = 8            # chrono segment height
HUD_CHRONO_SEG_GAP: int = 2          # gap between segments
HUD_CHRONO_SEG_COUNT: int = 10       # total segments
HUD_CHRONO_X: int = 14               # chrono bar left edge
HUD_CHRONO_BOTTOM_OFFSET: int = 36   # pixels from screen bottom
HUD_COLOR_PIP_FULL: tuple = (210, 160, 50)    # amber
HUD_COLOR_PIP_LOST: tuple = (45, 33, 14)      # dark amber
HUD_COLOR_PIP_ZERO: tuple = (140, 28, 28)     # danger red
HUD_COLOR_CHRONO_HI: tuple = (210, 160, 50)   # amber (>50%)
HUD_COLOR_CHRONO_LO: tuple = (120, 85, 20)    # dim orange (<50%)
HUD_COLOR_CHRONO_EMPTY: tuple = (30, 22, 8)   # near-black
HUD_COLOR_DILATION_ACTIVE: tuple = (80, 180, 255)    # cyan-blue
HUD_COLOR_DILATION_COOLDOWN: tuple = (35, 75, 115)   # dim cyan

# --- Particle VFX ---
VFX_POOL_SIZE: int = 200           # total pre-allocated particle slots
VFX_ROTATION_BURST_COUNT: int = 20  # particles per gravity rotation
VFX_HIT_SPARK_COUNT: int = 12       # particles per damage event
VFX_LANDING_DUST_COUNT: int = 8     # particles per landing

# --- Font ---
FONT_PATH: str = "assets/fonts/main_font.ttf"
FONT_SIZE: int = 28
