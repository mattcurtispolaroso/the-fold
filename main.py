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
    ANCHOR_INTEGRITY_MAX,
    BLACK_HOLE_STABILITY_COST,
    COYOTE_TIME,
    JUMP_BUFFER_TIME,
    DEBUG_ITEMS,
    FOLD_STABILITY_INTEGRITY_COST,
    FOLD_STABILITY_MAX,
    FOLD_TINT_THRESHOLD,
    FOLD_TINT_MAX_ALPHA,
    GRAVITY_OFFDEFAULT_DRAIN,
    GRAVITY_ROTATION_COST,
    HARD_LAND_VELOCITY,
    HOLE_ENCOUNTER_PHASE1_DURATION,
    HOLE_ENCOUNTER_PHASE2_DURATION,
    FPS,
    MODIFIER_CAP,
    PHYSICS_DT,
    PHYSICS_WATCHDOG_ENABLED,
    PHYSICS_WATCHDOG_THRESHOLD_MS,
    ROTATE_SHAKE_DURATION,
    ROTATE_SHAKE_INTENSITY,
    HARD_LAND_FLASH_DURATION,
    HARD_LAND_PUNCH_DURATION,
    HARD_LAND_PUNCH_MAGNITUDE,
    ROTATION_COOLDOWN,
    ROTATION_FLASH_DURATION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SINGULARITY_ABILITY_COST_MAX_MULT,
    SINGULARITY_CHRONO_REGEN_MIN_MULT,
    SINGULARITY_GRAVITY_MAX_MULT,
    TIME_DILATION_COST,
    WHITE_HOLE_STABILITY_RESTORE,
    LUT_SIZE,
    HARD_LAND_HITSTOP,
    HARD_LAND_SQUASH,
    HIT_FLASH_COLOR,
    HIT_FLASH_DURATION,
    HIT_HITSTOP,
    HIT_SHAKE_DURATION,
    HIT_SHAKE_INTENSITY,
    JUMP_STRETCH,
    LAND_SQUASH,
    VFX_POOL_SIZE,
)
from src.data.run_state import RunState
from src.entities.anchored import TheAnchored
from src.entities.enemy import TemporalEcho
from src.entities.fold_predator import FoldPredator
from src.entities.player import Player
from src.levels.level_renderer import LevelRenderer
from src.physics import (
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
from src.rendering.animation import PlayerAnimator, PlayerState, determine_player_state
from src.rendering.camera import Camera
from src.rendering.hud import (
    draw_debug_overlay, draw_death_screen, draw_flash_overlay, draw_fold_tint,
    draw_hole_screen, draw_hud, draw_impact_flash, draw_node_map, draw_reward_screen,
    draw_start_screen, draw_win_screen, draw_world,
)
from src.rendering.loader import load_background, load_font
from src.rendering.vfx import ParticlePool
from src.systems.combat import check_hit, compute_knockback
from src.systems.events import EventBus, GameEvent
from src.systems.items import ItemManager, load_item_registry
from src.systems.items.effects import EffectContext
from src.systems.items.offers import generate_offers
from src.data.items import OwnedItem
from src.data.save_manager import SaveManager, MetaProgress
from src.systems.logging_manager import LoggingManager
from src.systems.spacetime import make_time_dilation
from src.systems.level_generator import pick_anomaly_room
from src.rendering.gpu.context import GPUContext, use_gpu_renderer
from src.rendering.gpu.atlas import RuntimeAtlas
from src.rendering.gpu.sprite_batch import SpriteBatch, gpu_draw_world
from src.rendering.gpu.layer import LIGHT_TIMING_KEY, ParallaxStack
from src.rendering.gpu.light_buffer import LightBuffer
from src.rendering.gpu.layer_images import build_layer_images
from src.rendering.gpu.debug_overlay import (
    REDUCED_EFFECTS_KEY, draw_layer_timings, post_pass_for_key,
)
from src.rendering.gpu.lut import load_lut
from src.rendering.gpu.post_stack import PostStack
from src.rendering.gpu.feel import Feel
from src.rendering.gpu.particles import ParticleRenderer

WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT

# When frozen by PyInstaller, _MEIPASS holds bundled read-only data (assets,
# levels, item JSONs). Writable files (save, logs) go next to the executable
# so they persist across relaunches and aren't lost when the temp dir clears.
if getattr(sys, "frozen", False):
    BASE_DIR: str = sys._MEIPASS                          # type: ignore[attr-defined]
    WRITABLE_DIR: str = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    WRITABLE_DIR = BASE_DIR

LEVEL_DIR = os.path.join(BASE_DIR, "levels")
LEVELS = [os.path.join(LEVEL_DIR, f"level_{i:02d}.json") for i in range(1, 9)]


def _spawn_enemies_from_level(level: object) -> list:
    """Build enemy objects from the loaded level's EnemyDef list."""
    from constants import TEMPORAL_ECHO_SPEED
    spawned = []
    defs = level.level_data.enemies if level.level_data else []
    for e in defs:
        spd = e.speed if e.speed > 0.0 else None
        if e.type == "temporal_echo":
            spawned.append(TemporalEcho(
                px=e.x, py=e.y, min_x=e.min_x, max_x=e.max_x,
                speed=spd if spd is not None else TEMPORAL_ECHO_SPEED,
            ))
        elif e.type == "fold_predator":
            kw = {"speed": spd} if spd is not None else {}
            spawned.append(FoldPredator(px=e.x, py=e.y, level_min=e.min_x, level_max=e.max_x, **kw))
        elif e.type == "anchored":
            kw = {"speed": spd} if spd is not None else {}
            spawned.append(TheAnchored(px=e.x, py=e.y, level_min=e.min_x, level_max=e.max_x, **kw))
        else:
            import logging
            logging.getLogger(__name__).warning("Unknown enemy type in level JSON: %r", e.type)
    return spawned


def _reset_level_state(
    level: object, player: object, camera: object, animator: object, enemies: list,
) -> None:
    """Reset camera, player, and enemies (respawned from level data) to the current level's spawn."""
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn
    player.reset(level.spawn, tuple(level.gravity_start))
    enemies.clear()
    enemies.extend(_spawn_enemies_from_level(level))
    if player.gravity_dir == (0, 1):
        animator.helmet.request_off()
    else:
        animator.helmet.request_on()


def _apply_hole_consequences(
    run_state: object, player: object, is_white: bool,
) -> None:
    """Apply resource consequences when entering a hole encounter."""
    if is_white:
        player.anchor_integrity = ANCHOR_INTEGRITY_MAX
        run_state.fold_stability = min(
            FOLD_STABILITY_MAX, run_state.fold_stability + WHITE_HOLE_STABILITY_RESTORE,
        )
    else:
        player.anchor_integrity = max(0, player.anchor_integrity - 1)
        run_state.fold_stability = max(
            0.0, run_state.fold_stability - BLACK_HOLE_STABILITY_COST,
        )
        run_state.deaths += 1
        run_state.last_death_cause = "black hole"


def _owned_item_list(run_state: object) -> list:
    """Convert run_state.owned_items dicts to OwnedItem instances."""
    return [OwnedItem(id=e["id"], rank=e.get("rank", 1)) for e in run_state.owned_items]


def _apply_offer(offer: object, run_state: object, item_manager: object, item_registry: object) -> None:
    """Apply a picked offer to run_state and sync the item manager."""
    from constants import MODIFIER_CAP

    if offer.is_paradox:
        run_state.fold_stability -= offer.paradox_cost
        run_state.paradox_spent += offer.paradox_cost
        if run_state.fold_stability <= 0.0:
            run_state.last_death_cause = "paradox artifact"

    entry = {"id": offer.item_def.id, "rank": offer.target_rank}
    owned = list(run_state.owned_items)

    if offer.is_rank_up:
        for i, e in enumerate(owned):
            if e["id"] == entry["id"]:
                owned[i] = entry
                break
    else:
        # At modifier cap: drop the oldest modifier
        if offer.item_def.tier == "modifier":
            modifier_indices = [
                i for i, e in enumerate(owned)
                if item_registry.get_item(e["id"]) is not None
                and item_registry.get_item(e["id"]).tier == "modifier"
            ]
            if len(modifier_indices) >= MODIFIER_CAP:
                owned.pop(modifier_indices[0])
        owned.append(entry)

    run_state.owned_items = owned
    item_manager.sync_owned(_owned_item_list(run_state))


def _do_gravity_rotation(
    new_dir: tuple,
    player: object,
    level: object,
    camera: object,
    animator: object,
    enemies: list,
    particles: object,
    bus: object,
    feel: Feel,
) -> float:
    """Apply a gravity rotation: update player direction, resolve collisions, fire camera/VFX.

    Returns the new flash_timer value (ROTATION_FLASH_DURATION).
    """
    from constants import COYOTE_TIME, ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION, ROTATION_FLASH_DURATION
    bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=player.gravity_dir)
    player.set_gravity(new_dir)
    player.px, player.py = round(player.px), round(player.py)
    all_plats = level.all_platform_rects() + level.boundary_rects()
    player.px, player.py, player.vx, player.vy, player.on_ground = resolve_collisions(
        player.px, player.py, player.vx, player.vy,
        player.player_w, player.player_h, all_plats, player.gravity_dir,
    )
    player.on_ground = check_ground_adjacent(
        player.px, player.py, player.player_w, player.player_h,
        all_plats, player.gravity_dir,
    )
    if player.on_ground:
        player.coyote_timer = COYOTE_TIME
        player.jumping = False
    camera.on_gravity_rotate()
    feel.rotation_cinematic()
    feel.shake(ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION)
    feel.gravity_bend(player.gravity_dir)
    particles.emit_rotation_burst(player.px, player.py)
    for e in enemies:
        e.on_gravity_rotate()
    if player.gravity_dir == (0, 1):
        animator.helmet.request_off()
    else:
        animator.helmet.request_on()
    return ROTATION_FLASH_DURATION


def _grant_debug_items(run_state: object, item_manager: object, item_registry: object) -> None:
    """Grant one of each item at rank 1 for playtesting. Only active when DEBUG_ITEMS=True."""
    from src.data.items import OwnedItem
    owned = [OwnedItem(id=defn.id, rank=1) for defn in item_registry.all_items()]
    run_state.owned_items = [{"id": o.id, "rank": o.rank} for o in owned]
    item_manager.sync_owned(owned)


def main() -> None:
    """Main game loop — orchestrates physics, rendering, input."""
    pygame.init()
    _use_gpu = use_gpu_renderer()
    if _use_gpu:
        # macOS requires explicit Core Profile request before set_mode — without it
        # SDL2 returns a legacy 2.1 context and ModernGL refuses to initialise.
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(
            pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE,
        )
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, True)
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    else:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    gpu_ctx: GPUContext | None = None
    if _use_gpu:
        gpu_ctx = GPUContext()
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    logger = LoggingManager(log_dir=os.path.join(WRITABLE_DIR, "logs"))
    logger.log_event("Game started")
    font = load_font(BASE_DIR)

    save_manager = SaveManager(os.path.join(WRITABLE_DIR, "save.json"))
    meta = save_manager.load()

    current_level_idx = 0
    level = LevelRenderer()
    level.load(LEVELS[current_level_idx])

    camera = Camera(WIDTH, HEIGHT)
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn

    background = load_background(BASE_DIR, WIDTH, HEIGHT)
    animator = PlayerAnimator()

    # Build GPU atlas and sprite batch after sprites are loaded
    gpu_atlas: RuntimeAtlas | None = None
    gpu_batch: SpriteBatch | None = None
    gpu_parallax: ParallaxStack | None = None
    gpu_lights: LightBuffer | None = None
    gpu_post: PostStack | None = None
    gpu_particles: ParticleRenderer | None = None
    if gpu_ctx is not None:
        _atlas_frames: dict[str, pygame.Surface] = {}
        for state, frame_list in animator._sprites.items():
            for idx, surf in enumerate(frame_list):
                _atlas_frames[f"player_{state.name.lower()}_{idx}"] = surf
        gpu_atlas = RuntimeAtlas(gpu_ctx.ctx, _atlas_frames)
        gpu_batch = SpriteBatch(gpu_ctx.ctx, gpu_atlas, (WIDTH, HEIGHT))
        gpu_parallax = ParallaxStack(
            gpu_ctx.ctx, (WIDTH, HEIGHT),
            build_layer_images(BASE_DIR, background, (WIDTH, HEIGHT)),
        )
        gpu_lights = LightBuffer(gpu_ctx.ctx, (WIDTH, HEIGHT))
        gpu_post = PostStack(gpu_ctx.ctx, (WIDTH, HEIGHT), load_lut(BASE_DIR, LUT_SIZE),
                             timed=gpu_parallax.timed)
        gpu_particles = ParticleRenderer(gpu_ctx.ctx, (WIDTH, HEIGHT), VFX_POOL_SIZE)

    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    impact_flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    fold_tint_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    world_surf = pygame.Surface((WIDTH, HEIGHT))
    # Software-rendered frame for GPU overlay (non-playing states)
    gpu_sw_surf = pygame.Surface((WIDTH, HEIGHT))
    # Transparent overlay for HUD compositing over GPU world render
    gpu_hud_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    particles = ParticlePool()
    feel = Feel(camera)  # all game-feel effects: shake, hitstop, flash, squash, distortion

    player = Player.from_spawn(level.spawn, tuple(level.gravity_start))
    enemies = _spawn_enemies_from_level(level)
    run_state = RunState(fold_stability=100.0, current_node_idx=0, run_seed=0, is_active=False)
    bus = EventBus()
    time_dilation = make_time_dilation()
    item_registry = load_item_registry(BASE_DIR, logger)
    item_manager = ItemManager(
        registry=item_registry, bus=bus, player=player, enemies=enemies,
        run_state=run_state, ability_slot=time_dilation, rng_seed=0,
    )
    item_manager.sync_owned([])
    game_state = "start"
    debug_draw = False
    physics_accumulator: float = 0.0
    flash_timer: float = 0.0
    impact_flash_timer: float = 0.0
    rotation_cooldown_timer: float = 0.0
    hole_timer: float = 0.0
    hole_is_white: bool = False
    reward_offers: list = []
    pending_node_advance: bool = False
    anomaly_pending: bool = False

    active_zone_indices: set[int] = set()
    physics_history: deque = deque(maxlen=50)
    watchdog_consecutive: int = 0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(FPS) / 1000.0, 0.05)
            physics_accumulator += feel.physics_time(frame_dt)  # 0 during hitstop

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_RETURN:
                        if game_state == "start":
                            run_state = RunState.new_run()
                            item_manager.reset()
                            item_manager.sync_owned([])
                            game_state = "node_map"
                            physics_accumulator = 0.0
                        elif game_state == "node_map":
                            node_type = run_state.current_node_type
                            if node_type == "combat":
                                current_level_idx = run_state.combat_level_for_current_node()
                                level.load(LEVELS[current_level_idx])
                                _reset_level_state(level, player, camera, animator, enemies)
                                physics_accumulator = flash_timer = 0.0
                                active_zone_indices = set()
                                time_dilation.reset()
                                game_state = "playing"
                                bus.emit(GameEvent.ROOM_ENTERED)
                            elif node_type == "hole":
                                anomaly_path = pick_anomaly_room(
                                    run_state.run_seed, run_state.current_node_idx,
                                )
                                level.load(anomaly_path)
                                _reset_level_state(level, player, camera, animator, enemies)
                                physics_accumulator = flash_timer = 0.0
                                active_zone_indices = set()
                                time_dilation.reset()
                                anomaly_pending = True
                                game_state = "playing"
                                bus.emit(GameEvent.ROOM_ENTERED)
                            elif node_type == "singularity":
                                game_state = "win"
                        elif game_state in ("dead", "win"):
                            meta.record_run(
                                won=(game_state == "win"),
                                fold_stability=run_state.fold_stability,
                                nodes_reached=run_state.current_node_idx,
                            )
                            save_manager.save(meta)
                            game_state = "start"
                            run_state.is_active = False
                            current_level_idx = 0
                            level.load(LEVELS[current_level_idx])
                    elif game_state == "reward":
                        picked_idx = None
                        if event.key == pygame.K_1:
                            picked_idx = 0
                        elif event.key == pygame.K_2:
                            picked_idx = 1
                        elif event.key == pygame.K_3:
                            picked_idx = 2
                        elif event.key == pygame.K_4:
                            picked_idx = 3
                        skip = event.key in (pygame.K_s, pygame.K_0)
                        if skip or (picked_idx is not None and picked_idx < len(reward_offers)):
                            if not skip:
                                offer = reward_offers[picked_idx]
                                if offer.takeable(run_state.fold_stability):
                                    _apply_offer(offer, run_state, item_manager, item_registry)
                            if pending_node_advance:
                                run_state.advance_node()
                            game_state = "node_map"
                            reward_offers = []
                            pending_node_advance = False
                    elif game_state == "playing":
                        if event.key == pygame.K_TAB:
                            current_level_idx = (current_level_idx + 1) % len(LEVELS)
                            level.load(LEVELS[current_level_idx])
                            _reset_level_state(level, player, camera, animator, enemies)
                            physics_accumulator = flash_timer = 0.0
                            active_zone_indices = set()
                            time_dilation.reset()
                            bus.emit(GameEvent.ROOM_ENTERED)
                        if event.key == pygame.K_F3:
                            debug_draw = not debug_draw
                        if debug_draw and gpu_post is not None and post_pass_for_key(event.key):
                            gpu_post.toggle(post_pass_for_key(event.key))
                        if debug_draw and event.key == REDUCED_EFFECTS_KEY:
                            feel.toggle_reduced_effects()
                        if DEBUG_ITEMS and event.key == pygame.K_f:
                            _grant_debug_items(run_state, item_manager, item_registry)
                        if event.key == pygame.K_r and player.chrono_reserve >= GRAVITY_ROTATION_COST and rotation_cooldown_timer <= 0:
                            player.chrono_reserve -= GRAVITY_ROTATION_COST
                            rotation_cooldown_timer = ROTATION_COOLDOWN
                            flash_timer = _do_gravity_rotation(
                                rotate_gravity_ccw(player.gravity_dir),
                                player, level, camera, animator, enemies, particles, bus, feel,
                            )
                        if event.key == pygame.K_e and time_dilation.is_ready and player.chrono_reserve >= time_dilation.cost:
                            player.chrono_reserve = time_dilation.activate(player.chrono_reserve)
                            bus.emit(GameEvent.ABILITY_USED, ability_name="time_dilation")
                        if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                            if player.coyote_timer > 0:
                                player.vx, player.vy = apply_jump_impulse(
                                    player.vx, player.vy, player.gravity_dir,
                                )
                                feel.squash(JUMP_STRETCH)
                                player.coyote_timer = 0.0
                                player.jump_buffer_timer = 0.0
                                player.jumping = True
                            else:
                                player.jump_buffer_timer = JUMP_BUFFER_TIME
                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w) and player.jumping:
                        player.vx, player.vy = apply_jump_cut(
                            player.vx, player.vy, player.gravity_dir,
                        )
                        player.jumping = False

            if game_state == "hole_encounter":
                hole_timer = max(0.0, hole_timer - frame_dt)
                if hole_timer <= 0:
                    run_state.advance_node()
                    game_state = "dead" if run_state.fold_stability <= 0.0 else "node_map"

            if game_state == "playing":
                time_dilation.tick(frame_dt, bus)
                item_manager.tick(frame_dt)
                particles.update(frame_dt)
                time_scale = time_dilation.time_scale()
                pressure = run_state.singularity_pressure
                regen_mult = 1.0 - pressure * (1.0 - SINGULARITY_CHRONO_REGEN_MIN_MULT)

                # Gravity zone detection — strength accumulation and direction snaps
                player_rect = pygame.Rect(
                    int(player.px - player.player_w / 2),
                    int(player.py - player.player_h / 2),
                    player.player_w, player.player_h,
                )
                new_zone_indices: set[int] = set()
                zone_strength_mult = 1.0
                for _zi, _zone in enumerate(level.gravity_zones):
                    if pygame.Rect(_zone.x, _zone.y, _zone.w, _zone.h).colliderect(player_rect):
                        new_zone_indices.add(_zi)
                        if _zone.strength_mult is not None:
                            zone_strength_mult *= _zone.strength_mult
                for _zi in new_zone_indices - active_zone_indices:
                    _zone = level.gravity_zones[_zi]
                    if _zone.gravity_dir is not None and tuple(_zone.gravity_dir) != player.gravity_dir:
                        flash_timer = _do_gravity_rotation(
                            tuple(_zone.gravity_dir),
                            player, level, camera, animator, enemies, particles, bus, feel,
                        )
                active_zone_indices = new_zone_indices

                gravity_mult = level.gravity_multiplier * zone_strength_mult * (
                    1.0 + pressure * (SINGULARITY_GRAVITY_MAX_MULT - 1.0)
                )
                time_dilation.cost = TIME_DILATION_COST * (
                    1.0 + pressure * (SINGULARITY_ABILITY_COST_MAX_MULT - 1.0)
                )
                if flash_timer > 0:
                    flash_timer = max(0.0, flash_timer - frame_dt)
                if impact_flash_timer > 0:
                    impact_flash_timer = max(0.0, impact_flash_timer - frame_dt)
                if rotation_cooldown_timer > 0:
                    rotation_cooldown_timer = max(0.0, rotation_cooldown_timer - frame_dt)

                grav_vert = gravity_is_vertical(player.gravity_dir)
                _gravity_expired = False
                _hard_landing_occurred = False
                _landing_occurred = False
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

                    player.tick_chrono_regen(PHYSICS_DT, player.move_input != 0, regen_mult)
                    if player.gravity_dir != level.gravity_start:
                        player.chrono_reserve = max(
                            0.0, player.chrono_reserve - GRAVITY_OFFDEFAULT_DRAIN * PHYSICS_DT,
                        )
                        if player.chrono_reserve <= 0.0:
                            _gravity_expired = True
                    player.iframes_timer = max(0.0, player.iframes_timer - PHYSICS_DT)
                    player.vx, player.vy = apply_lateral_movement(
                        player.vx, player.vy, player.move_input, player.gravity_dir, player.on_ground,
                    )
                    if not player.on_ground:
                        player.vx, player.vy = apply_gravity(
                            player.vx, player.vy, player.gravity_dir,
                            player.on_ground, gravity_mult,
                        )
                        player.vx, player.vy = clamp_terminal_velocity(
                            player.vx, player.vy, player.gravity_dir, gravity_mult,
                        )

                    level.update(time_scale)
                    if not anomaly_pending:
                        for e in enemies:
                            e.update(
                                time_scale, dt=PHYSICS_DT,
                                player_px=player.px, player_py=player.py,
                                gravity_dir=player.gravity_dir,
                            )
                    _pre_land_grav_vel = gravity_speed(player.vx, player.vy, player.gravity_dir)
                    _was_grounded = player.on_ground
                    if player.on_ground:
                        pvx, pvy = level.riding_velocity(
                            player.px, player.py, player.player_w, player.player_h,
                            player.gravity_dir, time_scale,
                        )
                        player.px += pvx
                        player.py += pvy
                    all_platforms = level.all_platform_rects() + level.boundary_rects()
                    player.px, player.py, player.vx, player.vy, player.on_ground = resolve_collisions(
                        player.px, player.py, player.vx, player.vy,
                        player.player_w, player.player_h, all_platforms, player.gravity_dir,
                    )
                    if not _was_grounded and player.on_ground:
                        if _pre_land_grav_vel >= HARD_LAND_VELOCITY:
                            _hard_landing_occurred = True
                        else:
                            _landing_occurred = True

                    if player.on_ground:
                        player.jumping = False
                        player.coyote_timer = COYOTE_TIME
                        if not _was_grounded and player.jump_buffer_timer > 0:
                            player.vx, player.vy = apply_jump_impulse(
                                player.vx, player.vy, player.gravity_dir,
                            )
                            feel.squash(JUMP_STRETCH)
                            player.jumping = True
                            player.jump_buffer_timer = 0.0
                            player.coyote_timer = 0.0
                        if player.py < level.level_height - player.player_h:
                            player.last_safe_px = player.px
                            player.last_safe_py = player.py
                    else:
                        player.coyote_timer = max(0.0, player.coyote_timer - PHYSICS_DT)
                        player.jump_buffer_timer = max(0.0, player.jump_buffer_timer - PHYSICS_DT)

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

                # Landing VFX and animation (emitted once per frame, not per physics tick)
                if _landing_occurred or _hard_landing_occurred:
                    animator.notify_landed()
                if _landing_occurred:
                    particles.emit_landing_dust(
                        player.px, player.py, player.player_w, player.player_h, player.gravity_dir,
                    )
                    feel.squash(LAND_SQUASH)
                if _hard_landing_occurred:
                    particles.emit_landing_dust(
                        player.px, player.py, player.player_w, player.player_h, player.gravity_dir,
                    )
                    particles.emit_hit_spark(player.px, player.py, player.gravity_dir)
                    _gdir = player.gravity_dir
                    feel.punch(
                        _gdir[0] * HARD_LAND_PUNCH_MAGNITUDE,
                        _gdir[1] * HARD_LAND_PUNCH_MAGNITUDE,
                        HARD_LAND_PUNCH_DURATION,
                    )
                    feel.squash(HARD_LAND_SQUASH)
                    feel.hitstop(HARD_LAND_HITSTOP)
                    impact_flash_timer = HARD_LAND_FLASH_DURATION

                # Gravity snap-back when chrono exhausted while off default orientation
                if _gravity_expired and player.gravity_dir != level.gravity_start:
                    flash_timer = _do_gravity_rotation(
                        level.gravity_start,
                        player, level, camera, animator, enemies, particles, bus, feel,
                    )
                    grav_vert = gravity_is_vertical(player.gravity_dir)

                level_reset = False
                _death_cause = ""
                if _hard_landing_occurred:
                    if player.take_hit(0.0, 0.0):
                        result = bus.emit(GameEvent.INTEGRITY_ZERO)
                        level_reset = not result.cancelled
                        _death_cause = "hard landing"
                if not level_reset:
                    _gx, _gy = player.gravity_dir
                    _fell = False
                    if _gy == 1:    # DOWN — fell past bottom
                        _fell = player.py >= level.level_height - player.player_h / 2 - 10.0
                    elif _gy == -1:  # UP — fell past top
                        _fell = player.py <= player.player_h / 2 + 10.0
                    elif _gx == 1:  # RIGHT — fell past right edge
                        _fell = player.px >= level.level_width - player.player_w / 2 - 10.0
                    elif _gx == -1:  # LEFT — fell past left edge
                        _fell = player.px <= player.player_w / 2 + 10.0
                    if _fell:
                        if player.take_fall_damage():
                            result = bus.emit(GameEvent.INTEGRITY_ZERO)
                            level_reset = not result.cancelled
                            _death_cause = "fell into the void"
                if not level_reset and not anomaly_pending:
                    for e in enemies:
                        if check_hit(player, e):
                            hit_result = bus.emit(GameEvent.PLAYER_HIT)
                            if not hit_result.cancelled:
                                kx, ky = compute_knockback(
                                    player.px, player.py, e.px, e.py, player.gravity_dir,
                                )
                                feel.hitstop(HIT_HITSTOP)
                                feel.flash(HIT_FLASH_COLOR, HIT_FLASH_DURATION)
                                feel.shake(HIT_SHAKE_INTENSITY, HIT_SHAKE_DURATION)
                                particles.emit_hit_spark(player.px, player.py, player.gravity_dir)
                                if player.take_hit(kx, ky):
                                    result = bus.emit(GameEvent.INTEGRITY_ZERO)
                                    level_reset = not result.cancelled
                                    _death_cause = "enemy"
                            break
                if level_reset:
                    if _death_cause:
                        run_state.last_death_cause = _death_cause
                    run_state.deaths += 1
                    run_state.fold_stability = max(
                        0.0, run_state.fold_stability - FOLD_STABILITY_INTEGRITY_COST,
                    )
                    if run_state.fold_stability <= 0.0:
                        game_state = "dead"
                        run_state.is_active = False
                    else:
                        _reset_level_state(level, player, camera, animator, enemies)
                    physics_accumulator = flash_timer = rotation_cooldown_timer = 0.0
                    active_zone_indices = set()
                    time_dilation.reset()
                    feel.reset()

                camera.update(player.px, player.py, frame_dt)
                feel.track_dilation(time_dilation.is_active, player.px, player.py)
                feel.update(frame_dt)
                player_state = determine_player_state(
                    player.on_ground, player.vx, player.vy, player.gravity_dir, player.move_input,
                    animator._land_timer,
                )
                lateral_speed = player.vx if grav_vert else player.vy
                animator.update(frame_dt, player_state, lateral_speed)

                if level.goal_rect.collidepoint(player.px, player.py):
                    player.goal_reached = True

                if player.goal_reached:
                    bus.emit(GameEvent.ROOM_CLEARED)
                    if anomaly_pending:
                        hole_is_white = run_state.current_hole_is_white()
                        _apply_hole_consequences(run_state, player, hole_is_white)
                        bus.emit(GameEvent.HOLE_RESOLVED, is_white=hole_is_white)
                        hole_timer = (
                            HOLE_ENCOUNTER_PHASE1_DURATION + HOLE_ENCOUNTER_PHASE2_DURATION
                        )
                        anomaly_pending = False
                        game_state = "hole_encounter"
                    else:
                        reward_offers = generate_offers(
                            item_registry, _owned_item_list(run_state),
                            run_state.run_seed, run_state.current_node_idx,
                            getattr(run_state, "extra_reward_options", 0),
                        )
                        pending_node_advance = True
                        game_state = "reward"
                    physics_accumulator = flash_timer = 0.0
                    active_zone_indices = set()
                    time_dilation.reset()

            # Compute once — used in both render paths
            at_modifier_cap = sum(
                1 for o in run_state.owned_items
                if item_registry.get_item(o.get("id", "")) is not None
                and item_registry.get_item(o["id"]).tier == "modifier"
            ) >= MODIFIER_CAP

            if (gpu_ctx is not None and gpu_batch is not None and gpu_parallax is not None
                    and gpu_lights is not None and gpu_post is not None
                    and gpu_particles is not None):
                gpu_ctx.clear()
                if game_state == "playing":
                    _draw_enemies = [] if anomaly_pending else enemies
                    gpu_parallax.profiling = debug_draw
                    gpu_parallax.begin_frame()
                    gpu_parallax.draw_image_layers(
                        camera.offset, level.level_data.layer_scrolls,
                    )
                    with gpu_parallax.target("play"):
                        gpu_draw_world(
                            gpu_batch, gpu_atlas, level, _draw_enemies,
                            animator, player, player_state, camera.offset, feel,
                        )
                        gpu_particles.draw(particles, camera.offset)
                    with gpu_parallax.timed(LIGHT_TIMING_KEY):
                        light_tex = gpu_lights.render(
                            level.level_data.lights, (player.px, player.py), camera.offset,
                        )
                    gpu_parallax.composite(gpu_post.begin_scene(), light_tex, camera.zoom)
                    gpu_post.set_distortion(
                        feel.distortion_params(camera.offset, (WIDTH, HEIGHT), camera.zoom),
                    )
                    gpu_post.render(gpu_ctx.ctx.screen)
                    # Fold tint overlay
                    if run_state.fold_stability < FOLD_TINT_THRESHOLD:
                        t = 1.0 - run_state.fold_stability / FOLD_TINT_THRESHOLD
                        alpha = t * FOLD_TINT_MAX_ALPHA / 255.0
                        gpu_batch.begin()
                        gpu_batch.draw_rect(0, 0, WIDTH, HEIGHT, (0.6, 0.0, 0.0, alpha))
                        gpu_batch.flush()
                    # HUD + flash overlays — composite over game world
                    gpu_hud_surf.fill((0, 0, 0, 0))
                    draw_hud(gpu_hud_surf, font, player, time_dilation.active_timer,
                             time_dilation.cooldown_timer, WIDTH, HEIGHT,
                             in_anomaly=anomaly_pending)
                    _fx = feel.screen_flash_scale()
                    draw_flash_overlay(gpu_hud_surf, flash_surf, flash_timer * _fx)
                    draw_impact_flash(gpu_hud_surf, impact_flash_surf, impact_flash_timer * _fx)
                    if debug_draw:
                        draw_debug_overlay(gpu_hud_surf, font, player, camera.offset, HEIGHT)
                        draw_layer_timings(gpu_hud_surf, font, gpu_parallax.layer_ms,
                                           gpu_post.enabled, feel.reduced_effects)
                    gpu_batch.draw_fullscreen_surface(gpu_hud_surf)
                else:
                    # Non-playing states: render via existing software functions
                    gpu_sw_surf.fill((0, 0, 0))
                    if game_state == "start":
                        draw_start_screen(gpu_sw_surf, font, WIDTH, HEIGHT, meta)
                    elif game_state == "node_map":
                        draw_node_map(gpu_sw_surf, font, run_state, WIDTH, HEIGHT,
                                      registry=item_registry)
                    elif game_state == "reward":
                        draw_reward_screen(gpu_sw_surf, font, reward_offers,
                                           run_state.fold_stability, WIDTH, HEIGHT,
                                           at_modifier_cap=at_modifier_cap)
                    elif game_state == "hole_encounter":
                        draw_hole_screen(gpu_sw_surf, font, hole_timer, hole_is_white,
                                         WIDTH, HEIGHT)
                    elif game_state == "dead":
                        draw_death_screen(gpu_sw_surf, font, run_state, WIDTH, HEIGHT, meta)
                    elif game_state == "win":
                        draw_win_screen(gpu_sw_surf, font, run_state, WIDTH, HEIGHT, meta)
                    gpu_batch.draw_fullscreen_surface(gpu_sw_surf)
                pygame.display.flip()
                continue

            if game_state == "start":
                draw_start_screen(screen, font, WIDTH, HEIGHT, meta)
            elif game_state == "node_map":
                draw_node_map(screen, font, run_state, WIDTH, HEIGHT, registry=item_registry)
            elif game_state == "reward":
                draw_reward_screen(screen, font, reward_offers, run_state.fold_stability,
                                   WIDTH, HEIGHT, at_modifier_cap=at_modifier_cap)
            elif game_state == "hole_encounter":
                draw_hole_screen(screen, font, hole_timer, hole_is_white, WIDTH, HEIGHT)
            elif game_state == "dead":
                draw_death_screen(screen, font, run_state, WIDTH, HEIGHT, meta)
            elif game_state == "win":
                draw_win_screen(screen, font, run_state, WIDTH, HEIGHT, meta)
            else:  # "playing"
                cam_offset = camera.offset
                _draw_enemies = [] if anomaly_pending else enemies
                if abs(camera.zoom - 1.0) > 0.005:
                    draw_world(world_surf, background, level, _draw_enemies,
                               animator, player, player_state, cam_offset, debug_draw)
                    particles.draw(world_surf, cam_offset)
                    _sw = int(WIDTH * camera.zoom)
                    _sh = int(HEIGHT * camera.zoom)
                    _scaled = pygame.transform.scale(world_surf, (_sw, _sh))
                    screen.blit(_scaled, ((WIDTH - _sw) // 2, (HEIGHT - _sh) // 2))
                else:
                    draw_world(screen, background, level, _draw_enemies,
                               animator, player, player_state, cam_offset, debug_draw)
                    particles.draw(screen, cam_offset)
                if debug_draw:
                    draw_debug_overlay(screen, font, player, cam_offset, HEIGHT)
                draw_fold_tint(screen, fold_tint_surf, run_state.fold_stability)
                _fx = feel.screen_flash_scale()
                draw_flash_overlay(screen, flash_surf, flash_timer * _fx)
                draw_impact_flash(screen, impact_flash_surf, impact_flash_timer * _fx)
                draw_hud(screen, font, player, time_dilation.active_timer,
                         time_dilation.cooldown_timer, WIDTH, HEIGHT,
                         in_anomaly=anomaly_pending)
            pygame.display.flip()

    except Exception as e:
        logger.log_crash(e, player.to_dict(), list(physics_history))
        print(f"The Fold encountered an error. Crash log written to {logger.crash_log_path}")
        raise
    finally:
        logger.log_event("Game shutting down")
        if gpu_particles is not None:
            gpu_particles.release()
        if gpu_post is not None:
            gpu_post.release()
        if gpu_lights is not None:
            gpu_lights.release()
        if gpu_parallax is not None:
            gpu_parallax.release()
        if gpu_batch is not None:
            gpu_batch.release()
        if gpu_atlas is not None:
            gpu_atlas.release()
        if gpu_ctx is not None:
            gpu_ctx.release()
        pygame.quit()


if __name__ == "__main__":
    main()
