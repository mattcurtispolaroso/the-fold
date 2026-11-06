"""The phases of one World.step, in order (Engine Session 3).

Each phase is a small function over the World, so the step reads top to
bottom like the old main.py loop it replaces — but everything here advances by
exactly PHYSICS_DT, never by frame time:

  tick_timers → update_zones → apply_input → integrate → snap_back → hazards
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from constants import (
    COYOTE_TIME, GRAVITY_OFFDEFAULT_DRAIN, GRAVITY_ROTATION_COST, HARD_LAND_VELOCITY,
    JUMP_BUFFER_TIME, PHYSICS_DT, ROTATION_COOLDOWN, SINGULARITY_ABILITY_COST_MAX_MULT,
    SINGULARITY_CHRONO_REGEN_MIN_MULT, SINGULARITY_GRAVITY_MAX_MULT, TIME_DILATION_COST,
    VALIDATION_EJECT_SEARCH_PX,
)
from src.physics import (
    apply_gravity, apply_jump_cut, apply_jump_impulse, apply_lateral_movement,
    clamp_terminal_velocity, combined_gravity_mult, gravity_is_vertical, gravity_speed,
    push_out_of_movers, resolve_collisions, rotate_gravity_ccw, validate_player,
)
from src.systems.combat import check_hit, compute_knockback
from src.systems.events import GameEvent
from src.systems.input_frame import InputFrame

if TYPE_CHECKING:
    from src.systems.world import StepEvents, World

FALL_MARGIN_PX: float = 10.0  # how close to the level edge (along gravity) counts as falling out


def tick_timers(world: World) -> None:
    """Ability, item and rotation cooldowns advance on the fixed step (hitstop freezes them)."""
    world.time_dilation.tick(PHYSICS_DT, world.bus)
    world.item_manager.tick(PHYSICS_DT)
    world.rotation_cooldown = max(0.0, world.rotation_cooldown - PHYSICS_DT)
    world.time_scale = world.time_dilation.time_scale()


def update_zones(world: World, ev: StepEvents) -> None:
    """Gravity zones: direction snaps on entry, strength multipliers; then the gravity cap."""
    p, zones = world.player, world.level.gravity_zones
    pr = pygame.Rect(int(p.px - p.player_w / 2), int(p.py - p.player_h / 2), p.player_w, p.player_h)
    inside, strength = set(), 1.0
    for i, z in enumerate(zones):
        if pygame.Rect(z.x, z.y, z.w, z.h).colliderect(pr):
            inside.add(i)
            if z.strength_mult is not None:
                strength *= z.strength_mult
    for i in inside - world.active_zones:
        z = zones[i]
        if z.gravity_dir is not None and tuple(z.gravity_dir) != p.gravity_dir:
            if world.rotate(tuple(z.gravity_dir)):
                ev.rotated = p.gravity_dir
    world.active_zones = inside
    pressure = world.run_state.singularity_pressure
    world.gravity_mult, clamped = combined_gravity_mult(
        world.level.gravity_multiplier, strength,
        1.0 + pressure * (SINGULARITY_GRAVITY_MAX_MULT - 1.0))
    ev.gravity_clamped = clamped and not world.gravity_clamped
    world.gravity_clamped = clamped
    world.time_dilation.cost = TIME_DILATION_COST * (
        1.0 + pressure * (SINGULARITY_ABILITY_COST_MAX_MULT - 1.0))


def apply_input(world: World, inp: InputFrame, ev: StepEvents) -> None:
    """Edge presses (rotate, dilate, jump, jump cut), then held movement."""
    p = world.player
    if inp.rotate_pressed and p.chrono_reserve >= GRAVITY_ROTATION_COST and world.rotation_cooldown <= 0:
        if world.rotate(rotate_gravity_ccw(p.gravity_dir)):
            p.chrono_reserve -= GRAVITY_ROTATION_COST
            world.rotation_cooldown = ROTATION_COOLDOWN
            ev.rotated = p.gravity_dir
        else:
            ev.rotation_blocked = True
    td = world.time_dilation
    if inp.dilate_pressed and td.is_ready and p.chrono_reserve >= td.cost:
        p.chrono_reserve = td.activate(p.chrono_reserve)
        world.bus.emit(GameEvent.ABILITY_USED, ability_name="time_dilation")
    if inp.jump_pressed:
        if p.coyote_timer > 0:
            p.vx, p.vy = apply_jump_impulse(p.vx, p.vy, p.gravity_dir)
            p.coyote_timer = p.jump_buffer_timer = 0.0
            p.jumping = ev.jumped = True
        else:
            p.jump_buffer_timer = JUMP_BUFFER_TIME
    if inp.jump_released and p.jumping:
        p.vx, p.vy = apply_jump_cut(p.vx, p.vy, p.gravity_dir)
        p.jumping = False
    _apply_held_movement(p, inp)


def _apply_held_movement(p: object, inp: InputFrame) -> None:
    """Map held keys onto the lateral axis for the current gravity."""
    if gravity_is_vertical(p.gravity_dir):
        p.move_input = inp.move_x
        if inp.move_x:
            p.facing_right = inp.move_x > 0
    else:
        p.move_input = inp.move_y


def integrate(world: World, ev: StepEvents) -> None:
    """One physics step for the player and the level."""
    _accelerate(world)
    _move_and_collide(world, ev)
    _ground_bookkeeping(world, ev)


def _accelerate(world: World) -> None:
    """Chrono regen/drain, i-frames, lateral input and gravity."""
    p = world.player
    pressure = world.run_state.singularity_pressure
    regen_mult = 1.0 - pressure * (1.0 - SINGULARITY_CHRONO_REGEN_MIN_MULT)
    p.tick_chrono_regen(PHYSICS_DT, p.move_input != 0, regen_mult)
    world.gravity_expired = False
    if p.gravity_dir != world.level.gravity_start:
        p.chrono_reserve = max(0.0, p.chrono_reserve - GRAVITY_OFFDEFAULT_DRAIN * PHYSICS_DT)
        world.gravity_expired = p.chrono_reserve <= 0.0  # re-evaluated every step (not sticky)
    p.iframes_timer = max(0.0, p.iframes_timer - PHYSICS_DT)
    p.vx, p.vy = apply_lateral_movement(p.vx, p.vy, p.move_input, p.gravity_dir, p.on_ground)
    if not p.on_ground:
        p.vx, p.vy = apply_gravity(p.vx, p.vy, p.gravity_dir, p.on_ground, world.gravity_mult)
        p.vx, p.vy = clamp_terminal_velocity(p.vx, p.vy, p.gravity_dir, world.gravity_mult)


def _move_and_collide(world: World, ev: StepEvents) -> None:
    """Move level and enemies, carry/push the player, collide, validate, classify landings."""
    p, level = world.player, world.level
    level.update(world.time_scale)
    for e in world.active_enemies:
        e.update(world.time_scale, dt=PHYSICS_DT, player_px=p.px, player_py=p.py,
                 gravity_dir=p.gravity_dir)
    fall_speed = gravity_speed(p.vx, p.vy, p.gravity_dir)
    was_grounded = p.on_ground
    if p.on_ground:
        dx, dy = level.riding_velocity(p.px, p.py, p.player_w, p.player_h, p.gravity_dir,
                                       world.time_scale)
        p.px, p.py = p.px + dx, p.py + dy
    p.px, p.py = push_out_of_movers(p.px, p.py, p.player_w, p.player_h, level.movers())
    rects = level.collision_rects()
    p.px, p.py, p.vx, p.vy, p.on_ground = resolve_collisions(
        p.px, p.py, p.vx, p.vy, p.player_w, p.player_h, rects, p.gravity_dir)
    state = validate_player(p.px, p.py, p.vx, p.vy, p.player_w, p.player_h, rects,
                            (p.last_safe_px, p.last_safe_py), VALIDATION_EJECT_SEARCH_PX)
    p.px, p.py, p.vx, p.vy = state.px, state.py, state.vx, state.vy
    ev.violations.extend(state.issues)
    if not was_grounded and p.on_ground:
        if fall_speed >= HARD_LAND_VELOCITY:
            ev.hard_landed = True
        else:
            ev.landed = True


def _ground_bookkeeping(world: World, ev: StepEvents) -> None:
    """Coyote time, buffered jumps and the last safe position."""
    p = world.player
    if not p.on_ground:
        p.coyote_timer = max(0.0, p.coyote_timer - PHYSICS_DT)
        p.jump_buffer_timer = max(0.0, p.jump_buffer_timer - PHYSICS_DT)
        return
    p.jumping = False
    p.coyote_timer = COYOTE_TIME
    if (ev.landed or ev.hard_landed) and p.jump_buffer_timer > 0:
        p.vx, p.vy = apply_jump_impulse(p.vx, p.vy, p.gravity_dir)
        p.jumping = ev.jumped = True
        p.jump_buffer_timer = p.coyote_timer = 0.0
    if p.py < world.level.level_height - p.player_h:
        p.last_safe_px, p.last_safe_py = p.px, p.py


def snap_back(world: World, ev: StepEvents) -> None:
    """Chrono ran out while off the default gravity: rotate back (no cost).

    If there's no room, nothing happens; it's retried on later steps while chrono stays empty.
    """
    if world.gravity_expired and world.rotate(world.level.gravity_start):
        ev.rotated = world.player.gravity_dir


def hazards(world: World, ev: StepEvents) -> None:
    """Hard-landing damage, falling out of the level, enemy contact. Sets ev.died."""
    p, bus = world.player, world.bus
    if ev.hard_landed and p.take_hit(0.0, 0.0) and not bus.emit(GameEvent.INTEGRITY_ZERO).cancelled:
        ev.died = "hard landing"
        return
    if _fell_out(world) and p.take_fall_damage() and not bus.emit(GameEvent.INTEGRITY_ZERO).cancelled:
        ev.died = "fell into the void"
        return
    for e in world.active_enemies:
        if not check_hit(p, e):
            continue
        if not bus.emit(GameEvent.PLAYER_HIT).cancelled:
            ev.hit = True
            kx, ky = compute_knockback(p.px, p.py, e.px, e.py, p.gravity_dir)
            if p.take_hit(kx, ky) and not bus.emit(GameEvent.INTEGRITY_ZERO).cancelled:
                ev.died = "enemy"
        return


def _fell_out(world: World) -> bool:
    """True when the player has reached the level edge in the gravity direction."""
    p, level = world.player, world.level
    gx, gy = p.gravity_dir
    if gy == 1:
        return p.py >= level.level_height - p.player_h / 2 - FALL_MARGIN_PX
    if gy == -1:
        return p.py <= p.player_h / 2 + FALL_MARGIN_PX
    if gx == 1:
        return p.px >= level.level_width - p.player_w / 2 - FALL_MARGIN_PX
    return p.px <= p.player_w / 2 + FALL_MARGIN_PX
