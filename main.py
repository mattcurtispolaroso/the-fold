"""The Fold — entry point and game loop orchestrator.

The simulation lives in src/systems/world.py (World.step, fixed 60 Hz). This
file only orchestrates: it gathers input into an InputBuffer, steps the World,
reacts to the StepEvents it returns with presentation (camera, feel, particles,
animation), runs the screen flow (GameState), and renders.
"""
from __future__ import annotations

import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field

import pygame

from constants import (
    ANCHOR_INTEGRITY_MAX, BLACK_HOLE_STABILITY_COST, DEBUG_ITEMS, FOLD_STABILITY_MAX,
    FOLD_TINT_MAX_ALPHA, FOLD_TINT_THRESHOLD, HARD_LAND_FLASH_DURATION, HARD_LAND_HITSTOP,
    HARD_LAND_PUNCH_DURATION, HARD_LAND_PUNCH_MAGNITUDE, HARD_LAND_SQUASH, HIT_FLASH_COLOR,
    HIT_FLASH_DURATION, HIT_HITSTOP, HIT_SHAKE_DURATION, HIT_SHAKE_INTENSITY,
    HOLE_ENCOUNTER_PHASE1_DURATION, HOLE_ENCOUNTER_PHASE2_DURATION, JUMP_STRETCH, LAND_SQUASH,
    LUT_SIZE, MAX_RENDER_FPS, MODIFIER_CAP, PHYSICS_DT, PHYSICS_WATCHDOG_ENABLED,
    PHYSICS_WATCHDOG_THRESHOLD_MS, ROTATE_SHAKE_DURATION, ROTATE_SHAKE_INTENSITY,
    ROTATION_BLOCKED_SHAKE_DURATION, ROTATION_BLOCKED_SHAKE_INTENSITY, ROTATION_FLASH_DURATION,
    SCREEN_HEIGHT, SCREEN_WIDTH, VFX_POOL_SIZE, VSYNC_ENABLED, WHITE_HOLE_STABILITY_RESTORE,
)
from src.data.items import OwnedItem
from src.data.save_manager import SaveManager
from src.entities.player import Player
from src.physics import gravity_is_vertical
from src.rendering.animation import PlayerAnimator, determine_player_state
from src.rendering.camera import Camera
from src.rendering.gpu.atlas import RuntimeAtlas
from src.rendering.gpu.context import GPUContext, use_gpu_renderer
from src.rendering.gpu.debug_overlay import REDUCED_EFFECTS_KEY, draw_layer_timings, post_pass_for_key
from src.rendering.gpu.feel import Feel
from src.rendering.gpu.layer import LIGHT_TIMING_KEY, ParallaxStack
from src.rendering.gpu.layer_images import build_layer_images
from src.rendering.gpu.light_buffer import LightBuffer
from src.rendering.gpu.lut import load_lut
from src.rendering.gpu.particles import ParticleRenderer
from src.rendering.gpu.post_stack import PostStack
from src.rendering.gpu.sprite_batch import SpriteBatch
from src.rendering.gpu.world_draw import gpu_draw_world
from src.rendering.hud import (
    draw_debug_overlay, draw_flash_overlay, draw_fold_tint, draw_hud, draw_impact_flash, draw_world,
)
from src.rendering.interpolation import RenderInterpolator, step_alpha
from src.rendering.loader import load_background, load_font
from src.rendering.screens import (
    draw_death_screen, draw_hole_screen, draw_node_map, draw_reward_screen, draw_start_screen,
    draw_win_screen,
)
from src.rendering.vfx import ParticlePool
from src.systems.events import EventBus, GameEvent
from src.systems.game_state import GameState
from src.systems.input_frame import InputBuffer
from src.systems.items import load_item_registry
from src.systems.items.offers import generate_offers
from src.systems.level_generator import pick_anomaly_room
from src.systems.logging_manager import LoggingManager
from src.systems.world import StepEvents, World

WIDTH, HEIGHT = SCREEN_WIDTH, SCREEN_HEIGHT
JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
REWARD_KEYS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
REWARD_SKIP_KEYS = (pygame.K_s, pygame.K_0)
SOFTWARE_ZOOM_EPSILON = 0.005  # software path only scales the world surface beyond this zoom

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


@dataclass
class Flow:
    """Screen-flow and presentation timers (frame time; not simulation state)."""

    state: GameState = GameState.START
    debug_draw: bool = False
    accumulator: float = 0.0          # physics time owed (fixed-step accumulator)
    flash_timer: float = 0.0          # rotation flash overlay
    impact_flash_timer: float = 0.0   # hard-landing flash overlay
    hole_timer: float = 0.0
    hole_is_white: bool = False
    reward_offers: list = field(default_factory=list)
    pending_node_advance: bool = False
    current_level_idx: int = 0
    watchdog_strikes: int = 0
    render_alpha: float = 1.0
    draw_pos: tuple[float, float] = (0.0, 0.0)   # interpolated player centre
    player_state: object = None


@dataclass
class Presentation:
    """Everything that reacts to the simulation but never drives it."""

    camera: Camera
    feel: Feel
    particles: ParticlePool
    animator: PlayerAnimator
    interp: RenderInterpolator
    logger: LoggingManager


# --- Small helpers -------------------------------------------------------------

def _open_gl_window(width: int, height: int) -> pygame.Surface:
    """Open the OpenGL window, with vsync when enabled and supported (fallback: without)."""
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    if VSYNC_ENABLED:
        try:
            return pygame.display.set_mode((width, height), flags, vsync=1)
        except pygame.error as e:
            print(f"[Display] vsync unavailable ({e}); continuing without it")
    return pygame.display.set_mode((width, height), flags)


def _held_axes(keys: object) -> tuple[int, int]:
    """(move_x, move_y) from held keys: A/D or ←/→, and W/S or ↑/↓."""
    move_x = -1 if (keys[pygame.K_LEFT] or keys[pygame.K_a]) else (
        1 if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) else 0)
    move_y = -1 if (keys[pygame.K_UP] or keys[pygame.K_w]) else (
        1 if (keys[pygame.K_DOWN] or keys[pygame.K_s]) else 0)
    return move_x, move_y


def _physics_frame(player: Player) -> dict:
    """Lightweight per-step record for the crash log (no deep copy of the player)."""
    return {"px": player.px, "py": player.py, "vx": player.vx, "vy": player.vy,
            "on_ground": player.on_ground, "gravity_dir": player.gravity_dir}


def _owned_item_list(run_state: object) -> list:
    """Convert run_state.owned_items dicts to OwnedItem instances."""
    return [OwnedItem(id=e["id"], rank=e.get("rank", 1)) for e in run_state.owned_items]


def _apply_hole_consequences(run_state: object, player: object, is_white: bool) -> None:
    """Apply resource consequences when entering a hole encounter."""
    if is_white:
        player.anchor_integrity = ANCHOR_INTEGRITY_MAX
        run_state.fold_stability = min(
            FOLD_STABILITY_MAX, run_state.fold_stability + WHITE_HOLE_STABILITY_RESTORE)
    else:
        player.anchor_integrity = max(0, player.anchor_integrity - 1)
        run_state.fold_stability = max(0.0, run_state.fold_stability - BLACK_HOLE_STABILITY_COST)
        run_state.deaths += 1
        run_state.last_death_cause = "black hole"


def _apply_offer(offer: object, run_state: object, item_manager: object, item_registry: object) -> None:
    """Apply a picked offer to run_state and sync the item manager."""
    if offer.is_paradox:
        run_state.fold_stability -= offer.paradox_cost
        run_state.paradox_spent += offer.paradox_cost
        if run_state.fold_stability <= 0.0:
            run_state.last_death_cause = "paradox artifact"
    entry = {"id": offer.item_def.id, "rank": offer.target_rank}
    owned = list(run_state.owned_items)
    if offer.is_rank_up:
        owned = [entry if e["id"] == entry["id"] else e for e in owned]
    else:
        if offer.item_def.tier == "modifier":  # at the modifier cap, drop the oldest modifier
            mods = [i for i, e in enumerate(owned) if _is_modifier(item_registry, e["id"])]
            if len(mods) >= MODIFIER_CAP:
                owned.pop(mods[0])
        owned.append(entry)
    run_state.owned_items = owned
    item_manager.sync_owned(_owned_item_list(run_state))


def _is_modifier(item_registry: object, item_id: str) -> bool:
    """True if the item exists and is a modifier."""
    defn = item_registry.get_item(item_id)
    return defn is not None and defn.tier == "modifier"


def _grant_debug_items(run_state: object, item_manager: object, item_registry: object) -> None:
    """Grant one of each item at rank 1 for playtesting. Only active when DEBUG_ITEMS=True."""
    owned = [OwnedItem(id=defn.id, rank=1) for defn in item_registry.all_items()]
    run_state.owned_items = [{"id": o.id, "rank": o.rank} for o in owned]
    item_manager.sync_owned(owned)


# --- Presentation reacting to the simulation -----------------------------------

def _reset_presentation(world: World, pres: Presentation, flow: Flow) -> None:
    """After a level load or respawn: camera to spawn, no interpolation streak, effects cleared."""
    pres.interp.snap()
    pres.camera.set_bounds(world.level.level_width, world.level.level_height)
    pres.camera.x, pres.camera.y = world.level.spawn
    pres.feel.reset()
    _update_helmet(world, pres)
    flow.accumulator = flow.flash_timer = 0.0


def _update_helmet(world: World, pres: Presentation) -> None:
    """Helmet visor is up only in the default (down) gravity."""
    if world.player.gravity_dir == (0, 1):
        pres.animator.helmet.request_off()
    else:
        pres.animator.helmet.request_on()


def _present_step(ev: StepEvents, world: World, pres: Presentation, flow: Flow) -> None:
    """React to one simulation step: log violations, then camera / feel / particles."""
    p = world.player
    for issue in ev.violations:
        pres.logger.log_physics_violation("player", issue)
    if ev.gravity_clamped:
        pres.logger.log_physics_violation("gravity", f"combined multiplier clamped to {world.gravity_mult:.2f}")
    if ev.rotated is not None:
        pres.camera.on_gravity_rotate()
        pres.feel.rotation_cinematic()
        pres.feel.shake(ROTATE_SHAKE_INTENSITY, ROTATE_SHAKE_DURATION)
        pres.feel.gravity_bend(p.gravity_dir)
        pres.particles.emit_rotation_burst(p.px, p.py)
        _update_helmet(world, pres)
        flow.flash_timer = ROTATION_FLASH_DURATION
    if ev.rotation_blocked:
        pres.feel.shake(ROTATION_BLOCKED_SHAKE_INTENSITY, ROTATION_BLOCKED_SHAKE_DURATION)
    if ev.jumped:
        pres.feel.squash(JUMP_STRETCH)
    if ev.landed or ev.hard_landed:
        pres.animator.notify_landed()
        pres.particles.emit_landing_dust(p.px, p.py, p.player_w, p.player_h, p.gravity_dir)
    if ev.landed:
        pres.feel.squash(LAND_SQUASH)
    if ev.hard_landed:
        _present_hard_landing(world, pres, flow)
    if ev.hit:
        pres.feel.hitstop(HIT_HITSTOP)
        pres.feel.flash(HIT_FLASH_COLOR, HIT_FLASH_DURATION)
        pres.feel.shake(HIT_SHAKE_INTENSITY, HIT_SHAKE_DURATION)
        pres.particles.emit_hit_spark(p.px, p.py, p.gravity_dir)


def _present_hard_landing(world: World, pres: Presentation, flow: Flow) -> None:
    """Sparks, a punch along gravity, a strong squash, a short hitstop and a red flash."""
    p = world.player
    gx, gy = p.gravity_dir
    pres.particles.emit_hit_spark(p.px, p.py, p.gravity_dir)
    pres.feel.punch(gx * HARD_LAND_PUNCH_MAGNITUDE, gy * HARD_LAND_PUNCH_MAGNITUDE,
                    HARD_LAND_PUNCH_DURATION)
    pres.feel.squash(HARD_LAND_SQUASH)
    pres.feel.hitstop(HARD_LAND_HITSTOP)
    flow.impact_flash_timer = HARD_LAND_FLASH_DURATION


# --- Simulation driving (fixed step) -------------------------------------------

def _simulate(world: World, pres: Presentation, flow: Flow, inputs: InputBuffer,
              history: deque, registry: object) -> None:
    """Run every physics step owed this frame, presenting each; handle death and goal."""
    inputs.set_held(*_held_axes(pygame.key.get_pressed()))
    while flow.accumulator >= PHYSICS_DT:
        pres.interp.begin_step(world.player, world.active_enemies)
        started = time.perf_counter()
        ev = world.step(inputs.take())
        _watchdog(flow, pres.logger, (time.perf_counter() - started) * 1000, world)
        history.append(_physics_frame(world.player))
        flow.accumulator -= PHYSICS_DT
        _present_step(ev, world, pres, flow)
        if ev.died is not None:
            _on_death(ev, world, pres, flow)
            return
        if ev.goal:
            _on_goal(world, flow, registry)
            return


def _watchdog(flow: Flow, logger: LoggingManager, step_ms: float, world: World) -> None:
    """Log slow physics steps; CRITICAL after 3 in a row (CLAUDE.md physics watchdog)."""
    if PHYSICS_WATCHDOG_ENABLED and step_ms > PHYSICS_WATCHDOG_THRESHOLD_MS:
        flow.watchdog_strikes += 1
        level = "CRITICAL" if flow.watchdog_strikes >= 3 else "WARNING"
        logger.log_performance(f"{level}: Physics step slow", step_ms,
                               len(world.level.collision_rects()))
    else:
        flow.watchdog_strikes = 0


def _on_death(ev: StepEvents, world: World, pres: Presentation, flow: Flow) -> None:
    """The World already charged stability and respawned (or ended the run)."""
    if ev.run_over:
        flow.state = GameState.DEAD
    _reset_presentation(world, pres, flow)


def _on_goal(world: World, flow: Flow, registry: object) -> None:
    """Room cleared: resolve the hole (anomaly rooms) or offer rewards (combat rooms)."""
    rs = world.run_state
    world.bus.emit(GameEvent.ROOM_CLEARED)
    if world.anomaly_pending:
        flow.hole_is_white = rs.current_hole_is_white()
        _apply_hole_consequences(rs, world.player, flow.hole_is_white)
        world.bus.emit(GameEvent.HOLE_RESOLVED, is_white=flow.hole_is_white)
        flow.hole_timer = HOLE_ENCOUNTER_PHASE1_DURATION + HOLE_ENCOUNTER_PHASE2_DURATION
        world.anomaly_pending = False
        flow.state = GameState.HOLE_ENCOUNTER
    else:
        flow.reward_offers = generate_offers(
            registry, _owned_item_list(rs), rs.run_seed, rs.current_node_idx,
            getattr(rs, "extra_reward_options", 0))
        flow.pending_node_advance = True
        flow.state = GameState.REWARD
    flow.accumulator = flow.flash_timer = 0.0
    world.time_dilation.reset()


def _present_frame(world: World, pres: Presentation, flow: Flow, frame_dt: float) -> None:
    """Per-frame presentation after stepping: interpolation, camera, feel, animation, timers."""
    flow.flash_timer = max(0.0, flow.flash_timer - frame_dt)
    flow.impact_flash_timer = max(0.0, flow.impact_flash_timer - frame_dt)
    pres.particles.update(frame_dt)
    p = world.player
    flow.render_alpha = step_alpha(flow.accumulator, PHYSICS_DT)
    flow.draw_pos = pres.interp.player_pos(p, flow.render_alpha)
    pres.camera.update(*flow.draw_pos, frame_dt)
    pres.feel.track_dilation(world.time_dilation.is_active, p.px, p.py)
    pres.feel.update(frame_dt)
    flow.player_state = determine_player_state(
        p.on_ground, p.vx, p.vy, p.gravity_dir, p.move_input, pres.animator._land_timer)
    lateral_speed = p.vx if gravity_is_vertical(p.gravity_dir) else p.vy
    pres.animator.update(frame_dt, flow.player_state, lateral_speed)


# --- Screen flow (event-time UI, never simulation) ----------------------------

def _enter_level(world: World, pres: Presentation, flow: Flow, inputs: InputBuffer,
                 path: str, anomaly: bool = False) -> None:
    """Load a room and start playing it."""
    world.load_level(path, anomaly=anomaly)
    _reset_presentation(world, pres, flow)
    inputs.clear()
    flow.state = GameState.PLAYING


def _on_enter_key(world: World, pres: Presentation, flow: Flow, inputs: InputBuffer,
                  meta: object, save_manager: SaveManager) -> None:
    """ENTER advances the start / node map / end screens."""
    rs = world.run_state
    if flow.state is GameState.START:
        world.new_run()
        flow.state = GameState.NODE_MAP
        flow.accumulator = 0.0
    elif flow.state is GameState.NODE_MAP:
        node_type = rs.current_node_type
        if node_type == "combat":
            flow.current_level_idx = rs.combat_level_for_current_node()
            _enter_level(world, pres, flow, inputs, LEVELS[flow.current_level_idx])
        elif node_type == "hole":
            _enter_level(world, pres, flow, inputs,
                         pick_anomaly_room(rs.run_seed, rs.current_node_idx), anomaly=True)
        elif node_type == "singularity":
            flow.state = GameState.WIN
    elif flow.state in (GameState.DEAD, GameState.WIN):
        meta.record_run(won=flow.state is GameState.WIN, fold_stability=rs.fold_stability,
                        nodes_reached=rs.current_node_idx)
        save_manager.save(meta)
        flow.state = GameState.START
        rs.is_active = False
        flow.current_level_idx = 0
        world.load_level(LEVELS[0], announce=False)


def _on_reward_key(key: int, world: World, flow: Flow, registry: object) -> None:
    """1-4 pick an offer (if takeable), S/0 skip; either returns to the node map."""
    skip = key in REWARD_SKIP_KEYS
    picked = REWARD_KEYS.get(key)
    if not skip and (picked is None or picked >= len(flow.reward_offers)):
        return
    if not skip:
        offer = flow.reward_offers[picked]
        if offer.takeable(world.run_state.fold_stability):
            _apply_offer(offer, world.run_state, world.item_manager, registry)
    if flow.pending_node_advance:
        world.run_state.advance_node()
    flow.state = GameState.NODE_MAP
    flow.reward_offers = []
    flow.pending_node_advance = False


def _on_playing_key(key: int, world: World, pres: Presentation, flow: Flow,
                    inputs: InputBuffer, gpu_post: PostStack | None, registry: object) -> None:
    """Gameplay keys become InputBuffer presses; debug keys act immediately."""
    if key == pygame.K_TAB:
        flow.current_level_idx = (flow.current_level_idx + 1) % len(LEVELS)
        _enter_level(world, pres, flow, inputs, LEVELS[flow.current_level_idx])
    elif key == pygame.K_F3:
        flow.debug_draw = not flow.debug_draw
    elif flow.debug_draw and gpu_post is not None and post_pass_for_key(key):
        gpu_post.toggle(post_pass_for_key(key))
    elif flow.debug_draw and key == REDUCED_EFFECTS_KEY:
        pres.feel.toggle_reduced_effects()
    elif DEBUG_ITEMS and key == pygame.K_f:
        _grant_debug_items(world.run_state, world.item_manager, registry)
    if key == pygame.K_r:
        inputs.press_rotate()
    if key == pygame.K_e:
        inputs.press_dilate()
    if key in JUMP_KEYS:
        inputs.press_jump()


def _handle_events(world: World, pres: Presentation, flow: Flow, inputs: InputBuffer,
                   meta: object, save_manager: SaveManager, gpu_post: PostStack | None,
                   registry: object) -> bool:
    """Process this frame's events. Returns False when the game should quit."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYUP and event.key in JUMP_KEYS:
            inputs.release_jump()
        if event.type != pygame.KEYDOWN:
            continue
        if event.key == pygame.K_ESCAPE:
            return False
        if event.key == pygame.K_RETURN and flow.state is not GameState.PLAYING:
            _on_enter_key(world, pres, flow, inputs, meta, save_manager)
        elif flow.state is GameState.REWARD:
            _on_reward_key(event.key, world, flow, registry)
        elif flow.state is GameState.PLAYING:
            _on_playing_key(event.key, world, pres, flow, inputs, gpu_post, registry)
    return True


# --- Rendering -----------------------------------------------------------------

@dataclass
class Gfx:
    """Everything needed to draw a frame (both renderers)."""

    screen: pygame.Surface
    font: pygame.font.Font
    background: pygame.Surface | None
    surfaces: dict[str, pygame.Surface]
    gpu_ctx: GPUContext | None = None
    atlas: RuntimeAtlas | None = None
    batch: SpriteBatch | None = None
    parallax: ParallaxStack | None = None
    lights: LightBuffer | None = None
    post: PostStack | None = None
    particles: ParticleRenderer | None = None

    @property
    def gpu_ready(self) -> bool:
        """True when the full GPU pipeline is up."""
        return None not in (self.gpu_ctx, self.batch, self.parallax, self.lights, self.post,
                            self.particles)


def _draw_menu_screen(surf: pygame.Surface, gfx: Gfx, world: World, flow: Flow, meta: object,
                      registry: object, at_modifier_cap: bool) -> None:
    """Draw whichever non-playing screen is active onto `surf`."""
    rs, f = world.run_state, gfx.font
    if flow.state is GameState.START:
        draw_start_screen(surf, f, WIDTH, HEIGHT, meta)
    elif flow.state is GameState.NODE_MAP:
        draw_node_map(surf, f, rs, WIDTH, HEIGHT, registry=registry)
    elif flow.state is GameState.REWARD:
        draw_reward_screen(surf, f, flow.reward_offers, rs.fold_stability, WIDTH, HEIGHT,
                           at_modifier_cap=at_modifier_cap)
    elif flow.state is GameState.HOLE_ENCOUNTER:
        draw_hole_screen(surf, f, flow.hole_timer, flow.hole_is_white, WIDTH, HEIGHT)
    elif flow.state is GameState.DEAD:
        draw_death_screen(surf, f, rs, WIDTH, HEIGHT, meta)
    elif flow.state is GameState.WIN:
        draw_win_screen(surf, f, rs, WIDTH, HEIGHT, meta)


def _draw_overlays(surf: pygame.Surface, gfx: Gfx, world: World, pres: Presentation,
                   flow: Flow) -> None:
    """HUD, rotation/impact flashes and the debug overlay (both renderers)."""
    td, s = world.time_dilation, gfx.surfaces
    fx = pres.feel.screen_flash_scale()
    draw_flash_overlay(surf, s["flash"], flow.flash_timer * fx)
    draw_impact_flash(surf, s["impact"], flow.impact_flash_timer * fx)
    draw_hud(surf, gfx.font, world.player, td.active_timer, td.cooldown_timer, WIDTH, HEIGHT,
             in_anomaly=world.anomaly_pending)
    if flow.debug_draw:
        draw_debug_overlay(surf, gfx.font, world.player, pres.camera.offset, HEIGHT)


def _render_gpu_world(gfx: Gfx, world: World, pres: Presentation, flow: Flow) -> None:
    """Parallax layers → playfield + particles → lights → post stack → screen."""
    cam, lvl = pres.camera, world.level
    gfx.parallax.profiling = flow.debug_draw
    gfx.parallax.begin_frame()
    gfx.parallax.draw_image_layers(cam.offset, lvl.level_data.layer_scrolls)
    with gfx.parallax.target("play"):
        gpu_draw_world(gfx.batch, gfx.atlas, lvl, world.active_enemies, pres.animator,
                       world.player, flow.player_state, cam.offset, pres.feel,
                       pres.interp, flow.render_alpha)
        gfx.particles.draw(pres.particles, cam.offset)
    with gfx.parallax.timed(LIGHT_TIMING_KEY):
        light_tex = gfx.lights.render(lvl.level_data.lights, flow.draw_pos, cam.offset)
    gfx.parallax.composite(gfx.post.begin_scene(), light_tex, cam.zoom)
    gfx.post.set_distortion(pres.feel.distortion_params(cam.offset, (WIDTH, HEIGHT), cam.zoom))
    gfx.post.render(gfx.gpu_ctx.ctx.screen)
    stability = world.run_state.fold_stability
    if stability < FOLD_TINT_THRESHOLD:
        alpha = (1.0 - stability / FOLD_TINT_THRESHOLD) * FOLD_TINT_MAX_ALPHA / 255.0
        gfx.batch.begin()
        gfx.batch.draw_rect(0, 0, WIDTH, HEIGHT, (0.6, 0.0, 0.0, alpha))
        gfx.batch.flush()
    hud = gfx.surfaces["hud"]
    hud.fill((0, 0, 0, 0))
    _draw_overlays(hud, gfx, world, pres, flow)
    if flow.debug_draw:
        draw_layer_timings(hud, gfx.font, gfx.parallax.layer_ms, gfx.post.enabled,
                           pres.feel.reduced_effects)
    gfx.batch.draw_fullscreen_surface(hud)


def _render_software_world(gfx: Gfx, world: World, pres: Presentation, flow: Flow) -> None:
    """Software path: world (scaled during the rotation zoom), particles, tint, overlays."""
    cam, screen = pres.camera, gfx.screen
    args = (gfx.background, world.level, world.active_enemies, pres.animator, world.player,
            flow.player_state, cam.offset, flow.debug_draw, flow.draw_pos)
    if abs(cam.zoom - 1.0) > SOFTWARE_ZOOM_EPSILON:
        world_surf = gfx.surfaces["world"]
        draw_world(world_surf, *args)
        pres.particles.draw(world_surf, cam.offset)
        sw, sh = int(WIDTH * cam.zoom), int(HEIGHT * cam.zoom)
        screen.blit(pygame.transform.scale(world_surf, (sw, sh)), ((WIDTH - sw) // 2, (HEIGHT - sh) // 2))
    else:
        draw_world(screen, *args)
        pres.particles.draw(screen, cam.offset)
    draw_fold_tint(screen, gfx.surfaces["tint"], world.run_state.fold_stability)
    _draw_overlays(screen, gfx, world, pres, flow)


def _render(gfx: Gfx, world: World, pres: Presentation, flow: Flow, meta: object,
            registry: object) -> None:
    """Draw one frame with whichever renderer is active, then flip."""
    at_cap = sum(1 for o in world.run_state.owned_items
                 if _is_modifier(registry, o.get("id", ""))) >= MODIFIER_CAP
    playing = flow.state is GameState.PLAYING
    if gfx.gpu_ready:
        gfx.gpu_ctx.clear()
        if playing:
            _render_gpu_world(gfx, world, pres, flow)
        else:
            menu = gfx.surfaces["menu"]
            menu.fill((0, 0, 0))
            _draw_menu_screen(menu, gfx, world, flow, meta, registry, at_cap)
            gfx.batch.draw_fullscreen_surface(menu)
    elif playing:
        _render_software_world(gfx, world, pres, flow)
    else:
        _draw_menu_screen(gfx.screen, gfx, world, flow, meta, registry, at_cap)
    pygame.display.flip()


# --- Startup / shutdown ----------------------------------------------------------

def _open_display(use_gpu: bool) -> pygame.Surface:
    """Create the window: an OpenGL 3.3 core context for the GPU path, else software."""
    if not use_gpu:
        return pygame.display.set_mode((WIDTH, HEIGHT))
    # macOS requires an explicit Core Profile request before set_mode — without it
    # SDL2 returns a legacy 2.1 context and ModernGL refuses to initialise.
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, True)
    return _open_gl_window(WIDTH, HEIGHT)


def _build_gfx(screen: pygame.Surface, use_gpu: bool, animator: PlayerAnimator) -> Gfx:
    """Load fonts/art and build the GPU pipeline (when enabled)."""
    background = load_background(BASE_DIR, WIDTH, HEIGHT)
    surfaces = {name: pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                for name in ("flash", "impact", "tint", "hud")}
    surfaces["world"] = pygame.Surface((WIDTH, HEIGHT))
    surfaces["menu"] = pygame.Surface((WIDTH, HEIGHT))
    gfx = Gfx(screen=screen, font=load_font(BASE_DIR), background=background, surfaces=surfaces)
    if not use_gpu:
        return gfx
    gfx.gpu_ctx = GPUContext()
    ctx = gfx.gpu_ctx.ctx
    frames = {f"player_{st.name.lower()}_{i}": surf
              for st, frame_list in animator._sprites.items() for i, surf in enumerate(frame_list)}
    gfx.atlas = RuntimeAtlas(ctx, frames)
    gfx.batch = SpriteBatch(ctx, gfx.atlas, (WIDTH, HEIGHT))
    gfx.parallax = ParallaxStack(ctx, (WIDTH, HEIGHT), build_layer_images(BASE_DIR, background, (WIDTH, HEIGHT)))
    gfx.lights = LightBuffer(ctx, (WIDTH, HEIGHT))
    gfx.post = PostStack(ctx, (WIDTH, HEIGHT), load_lut(BASE_DIR, LUT_SIZE), timed=gfx.parallax.timed)
    gfx.particles = ParticleRenderer(ctx, (WIDTH, HEIGHT), VFX_POOL_SIZE)
    return gfx


def _release_gfx(gfx: Gfx) -> None:
    """Free GPU resources in reverse creation order."""
    for res in (gfx.particles, gfx.post, gfx.lights, gfx.parallax, gfx.batch, gfx.atlas, gfx.gpu_ctx):
        if res is not None:
            res.release()


def _init_services() -> tuple[LoggingManager, SaveManager, object, object]:
    """Logger, save manager + loaded meta progress, and the item registry."""
    logger = LoggingManager(log_dir=os.path.join(WRITABLE_DIR, "logs"))
    logger.log_event("Game started")
    save_manager = SaveManager(os.path.join(WRITABLE_DIR, "save.json"))
    return logger, save_manager, save_manager.load(), load_item_registry(BASE_DIR, logger)


def _tick_hole_encounter(world: World, flow: Flow, frame_dt: float) -> None:
    """Count down the hole reveal screen, then advance to the node map (or death)."""
    flow.hole_timer = max(0.0, flow.hole_timer - frame_dt)
    if flow.hole_timer <= 0:
        world.run_state.advance_node()
        flow.state = GameState.DEAD if world.run_state.fold_stability <= 0.0 else GameState.NODE_MAP


def main() -> None:
    """Start the game and run the loop: events → fixed-step simulation → present → render."""
    pygame.init()
    use_gpu = use_gpu_renderer()
    screen = _open_display(use_gpu)
    pygame.display.set_caption("The Fold")
    clock = pygame.time.Clock()
    logger, save_manager, meta, registry = _init_services()
    world = World(registry, EventBus())
    world.load_level(LEVELS[0], announce=False)
    animator = PlayerAnimator()
    gfx = _build_gfx(screen, use_gpu, animator)
    camera = Camera(WIDTH, HEIGHT)
    pres = Presentation(camera=camera, feel=Feel(camera), particles=ParticlePool(),
                        animator=animator, interp=RenderInterpolator(), logger=logger)
    flow, inputs = Flow(), InputBuffer()
    _reset_presentation(world, pres, flow)
    history: deque = deque(maxlen=50)
    try:
        running = True
        while running:
            frame_dt = min(clock.tick(MAX_RENDER_FPS) / 1000.0, 0.05)  # render rate; physics 60 Hz
            flow.accumulator += pres.feel.physics_time(frame_dt)        # 0 during hitstop
            running = _handle_events(world, pres, flow, inputs, meta, save_manager, gfx.post, registry)
            if flow.state is GameState.HOLE_ENCOUNTER:
                _tick_hole_encounter(world, flow, frame_dt)
            if flow.state is GameState.PLAYING:
                _simulate(world, pres, flow, inputs, history, registry)
                _present_frame(world, pres, flow, frame_dt)
            _render(gfx, world, pres, flow, meta, registry)
    except Exception as e:
        logger.log_crash(e, world.player.to_dict(), list(history))
        print(f"The Fold encountered an error. Crash log written to {logger.crash_log_path}")
        raise
    finally:
        logger.log_event("Game shutting down")
        _release_gfx(gfx)
        pygame.quit()


if __name__ == "__main__":
    main()
