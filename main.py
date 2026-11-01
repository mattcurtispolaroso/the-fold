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
    ANCHOR_INTEGRITY_MAX,
    BLACK_HOLE_STABILITY_COST,
    COYOTE_TIME,
    DEBUG_ITEMS,
    FOLD_STABILITY_INTEGRITY_COST,
    FOLD_STABILITY_MAX,
    HOLE_ENCOUNTER_PHASE1_DURATION,
    HOLE_ENCOUNTER_PHASE2_DURATION,
    TEMPORAL_ECHO_SPEED,
    FPS,
    PHYSICS_DT,
    PHYSICS_WATCHDOG_ENABLED,
    PHYSICS_WATCHDOG_THRESHOLD_MS,
    ROTATE_SHAKE_DURATION,
    ROTATE_SHAKE_INTENSITY,
    ROTATION_FLASH_DURATION,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE_HOLE_STABILITY_RESTORE,
)
from src.data.run_state import RunState
from src.entities.enemy import TemporalEcho
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
    resolve_collisions,
    rotate_gravity_ccw,
)
from src.rendering.animation import PlayerAnimator, PlayerState, determine_player_state
from src.rendering.camera import Camera
from src.rendering.hud import (
    draw_debug_overlay, draw_death_screen, draw_flash_overlay, draw_fold_tint,
    draw_hole_screen, draw_hud_labels, draw_node_map, draw_start_screen,
    draw_win_screen, draw_world,
)
from src.rendering.loader import load_background, load_font
from src.systems.combat import check_hit, compute_knockback
from src.systems.events import EventBus, GameEvent
from src.systems.items import ItemManager, load_item_registry
from src.systems.items.effects import EffectContext
from src.data.items import OwnedItem
from src.systems.logging_manager import LoggingManager
from src.systems.spacetime import make_time_dilation

WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEVEL_DIR = os.path.join(BASE_DIR, "levels")
LEVELS = [os.path.join(LEVEL_DIR, f"level_0{i}.json") for i in range(1, 5)]


def _reset_level_state(
    level: object, player: object, camera: object, animator: object, enemy: object,
) -> None:
    """Reset camera, player, and enemy to the current level's spawn. Does not reload the level."""
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn
    player.reset(level.spawn, tuple(level.gravity_start))
    enemy.reset()
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


def _grant_debug_items(run_state: object, item_manager: object, item_registry: object) -> None:
    """Grant one of each item at rank 1 for playtesting. Only active when DEBUG_ITEMS=True."""
    from src.data.items import OwnedItem
    owned = [OwnedItem(id=defn.id, rank=1) for defn in item_registry.all_items()]
    run_state.owned_items = [{"id": o.id, "rank": o.rank} for o in owned]
    item_manager.sync_owned(owned)


def main() -> None:
    """Main game loop — orchestrates physics, rendering, input."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    logger = LoggingManager()
    logger.log_event("Game started")
    font = load_font(BASE_DIR)

    current_level_idx = 0
    level = LevelRenderer()
    level.load(LEVELS[current_level_idx])

    camera = Camera(WIDTH, HEIGHT)
    camera.set_bounds(level.level_width, level.level_height)
    camera.x, camera.y = level.spawn

    background = load_background(BASE_DIR, WIDTH, HEIGHT)
    animator = PlayerAnimator()
    flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    fold_tint_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    player = Player.from_spawn(level.spawn, tuple(level.gravity_start))
    enemy = TemporalEcho(px=130.0, py=790.0, min_x=30.0, max_x=230.0, speed=TEMPORAL_ECHO_SPEED)
    run_state = RunState(fold_stability=100.0, current_node_idx=0, run_seed=0, is_active=False)
    bus = EventBus()
    time_dilation = make_time_dilation()
    item_registry = load_item_registry(BASE_DIR, logger)
    item_manager = ItemManager(
        registry=item_registry, bus=bus, player=player, enemies=[enemy],
        run_state=run_state, ability_slot=time_dilation, rng_seed=0,
    )
    item_manager.sync_owned([])
    game_state = "start"
    debug_draw = False
    physics_accumulator: float = 0.0
    flash_timer: float = 0.0
    hole_timer: float = 0.0
    hole_is_white: bool = False

    physics_history: deque = deque(maxlen=50)
    watchdog_consecutive: int = 0

    try:
        running = True
        while running:
            frame_dt = min(clock.tick(FPS) / 1000.0, 0.05)
            physics_accumulator += frame_dt

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
                                _reset_level_state(level, player, camera, animator, enemy)
                                physics_accumulator = flash_timer = 0.0
                                time_dilation.reset()
                                game_state = "playing"
                                bus.emit(GameEvent.ROOM_ENTERED)
                            elif node_type == "hole":
                                hole_is_white = run_state.current_hole_is_white()
                                _apply_hole_consequences(run_state, player, hole_is_white)
                                bus.emit(GameEvent.HOLE_RESOLVED, is_white=hole_is_white)
                                hole_timer = HOLE_ENCOUNTER_PHASE1_DURATION + HOLE_ENCOUNTER_PHASE2_DURATION
                                game_state = "hole_encounter"
                            elif node_type == "singularity":
                                game_state = "win"
                        elif game_state in ("dead", "win"):
                            game_state = "start"
                            run_state.is_active = False
                            current_level_idx = 0
                            level.load(LEVELS[current_level_idx])
                    elif game_state == "playing":
                        if event.key == pygame.K_TAB:
                            current_level_idx = (current_level_idx + 1) % len(LEVELS)
                            level.load(LEVELS[current_level_idx])
                            _reset_level_state(level, player, camera, animator, enemy)
                            physics_accumulator = flash_timer = 0.0
                            time_dilation.reset()
                            bus.emit(GameEvent.ROOM_ENTERED)
                        if event.key == pygame.K_BACKQUOTE:
                            debug_draw = not debug_draw
                        if DEBUG_ITEMS and event.key == pygame.K_f:
                            _grant_debug_items(run_state, item_manager, item_registry)
                        if event.key == pygame.K_r:
                            bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=player.gravity_dir)
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
                        if event.key == pygame.K_e and time_dilation.is_ready and player.chrono_reserve >= time_dilation.cost:
                            player.chrono_reserve = time_dilation.activate(player.chrono_reserve)
                            bus.emit(GameEvent.ABILITY_USED, ability_name="time_dilation")
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

            if game_state == "hole_encounter":
                hole_timer = max(0.0, hole_timer - frame_dt)
                if hole_timer <= 0:
                    run_state.advance_node()
                    game_state = "dead" if run_state.fold_stability <= 0.0 else "node_map"

            if game_state == "playing":
                time_dilation.tick(frame_dt, bus)
                item_manager.tick(frame_dt)
                time_scale = time_dilation.time_scale()
                if flash_timer > 0:
                    flash_timer = max(0.0, flash_timer - frame_dt)

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

                    player.tick_chrono_regen(PHYSICS_DT, player.move_input != 0)
                    player.iframes_timer = max(0.0, player.iframes_timer - PHYSICS_DT)
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
                    enemy.update(time_scale, dt=PHYSICS_DT)
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

                    if player.on_ground:
                        player.jumping = False
                        player.coyote_timer = COYOTE_TIME
                        if player.py < level.level_height - player.player_h:
                            player.last_safe_px = player.px
                            player.last_safe_py = player.py
                    else:
                        player.coyote_timer = max(0.0, player.coyote_timer - PHYSICS_DT)

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

                level_reset = False
                if player.gravity_dir == (0, 1):
                    fall_threshold = level.level_height - player.player_h / 2 - 10.0
                    if player.py >= fall_threshold:
                        if player.take_fall_damage():
                            result = bus.emit(GameEvent.INTEGRITY_ZERO)
                            level_reset = not result.cancelled
                if not level_reset and check_hit(player, enemy):
                    hit_result = bus.emit(GameEvent.PLAYER_HIT)
                    if not hit_result.cancelled:
                        kx, ky = compute_knockback(
                            player.px, player.py, enemy.px, enemy.py, player.gravity_dir,
                        )
                        if player.take_hit(kx, ky):
                            result = bus.emit(GameEvent.INTEGRITY_ZERO)
                            level_reset = not result.cancelled
                if level_reset:
                    run_state.deaths += 1
                    run_state.fold_stability = max(
                        0.0, run_state.fold_stability - FOLD_STABILITY_INTEGRITY_COST,
                    )
                    if run_state.fold_stability <= 0.0:
                        game_state = "dead"
                        run_state.is_active = False
                    else:
                        _reset_level_state(level, player, camera, animator, enemy)
                    physics_accumulator = flash_timer = 0.0
                    time_dilation.reset()

                camera.update(player.px, player.py, frame_dt)
                player_state = determine_player_state(
                    player.on_ground, player.vx, player.vy, player.gravity_dir, player.move_input,
                )
                lateral_speed = player.vx if grav_vert else player.vy
                animator.update(frame_dt, player_state, lateral_speed)

                if level.goal_rect.collidepoint(player.px, player.py):
                    player.goal_reached = True

                if player.goal_reached:
                    bus.emit(GameEvent.ROOM_CLEARED)
                    run_state.advance_node()
                    game_state = "node_map"
                    physics_accumulator = flash_timer = 0.0
                    time_dilation.reset()

            if game_state == "start":
                draw_start_screen(screen, font, WIDTH, HEIGHT)
            elif game_state == "node_map":
                draw_node_map(screen, font, run_state, WIDTH, HEIGHT)
            elif game_state == "hole_encounter":
                draw_hole_screen(screen, font, hole_timer, hole_is_white, WIDTH, HEIGHT)
            elif game_state == "dead":
                draw_death_screen(screen, font, run_state, WIDTH, HEIGHT)
            elif game_state == "win":
                draw_win_screen(screen, font, run_state, WIDTH, HEIGHT)
            else:  # "playing"
                cam_offset = camera.offset
                draw_world(screen, background, level, enemy, animator, player,
                           player_state, cam_offset, debug_draw)
                if debug_draw:
                    draw_debug_overlay(screen, font, player, cam_offset, HEIGHT)
                draw_fold_tint(screen, fold_tint_surf, run_state.fold_stability)
                draw_flash_overlay(screen, flash_surf, flash_timer)
                draw_hud_labels(screen, font, player, time_dilation.active_timer, WIDTH, HEIGHT)
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
