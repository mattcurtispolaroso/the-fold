"""GPU playfield drawing — the GPU path's equivalent of hud.draw_world.

Submits level geometry, enemies and the player sprite to a SpriteBatch, in
that order, into whatever framebuffer is bound (normally the play layer).
The background is not drawn here: since TA-2 it lives in the sky/far/mid
parallax layers (src/rendering/gpu/layer.py).

Camera convention: cam_offset is ADDITIVE — screen_pos = world_pos + cam_offset.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import constants as C
from src.rendering.gpu.atlas import RuntimeAtlas
from src.rendering.gpu.sprite_batch import NO_FLASH, SpriteBatch

if TYPE_CHECKING:
    from src.rendering.gpu.feel import Feel
    from src.rendering.interpolation import RenderInterpolator

RGBA = tuple[float, float, float, float]

# Placeholder colours (match the software renderer's pygame colours / 255)
STATIC_PLATFORM_COLOR: RGBA = (0.392, 0.392, 0.392, 1.0)   # (100, 100, 100)
MOVING_PLATFORM_COLOR: RGBA = (0.196, 0.784, 0.784, 1.0)   # (50, 200, 200)
GOAL_COLOR: RGBA = (0.196, 0.863, 0.196, 1.0)              # (50, 220, 50)
PLAYER_FALLBACK_COLOR: RGBA = (0.863, 0.196, 0.196, 1.0)   # shown if a frame is missing
ZONE_DIRECTION_COLOR: RGBA = (0.863, 0.627, 0.196, 1.0)    # amber: snaps gravity direction
ZONE_WEAK_COLOR: RGBA = (0.314, 0.549, 0.863, 1.0)         # blue: weaker gravity
ZONE_STRONG_COLOR: RGBA = (0.863, 0.314, 0.196, 1.0)       # red-orange: stronger gravity
ENEMY_PREDATOR_COLOR: RGBA = (0.706, 0.235, 0.863, 1.0)    # purple
ENEMY_ANCHORED_COLOR: RGBA = (0.549, 0.824, 0.235, 1.0)    # yellow-green
ENEMY_DEFAULT_COLOR: RGBA = (0.314, 0.863, 0.863, 1.0)     # cyan (Temporal Echo)
ZONE_OUTLINE_PX: float = 2.0


def gpu_draw_world(
    batch: SpriteBatch,
    atlas: RuntimeAtlas,
    level: object,
    enemies: list,
    animator: object,
    player: object,
    player_state: object,
    cam_offset: tuple[float, float],
    feel: Feel | None = None,
    interp: RenderInterpolator | None = None,
    alpha: float = 1.0,
) -> None:
    """Draw the playfield in one batch: zones, platforms, goal, enemies, player.

    `feel` (TA-6) supplies the player's sprite flash and squash/stretch.
    `interp` + `alpha` (Engine Session 2) draw moving things between physics
    steps; without an interpolator everything draws at its current position.
    """
    batch.begin()
    _draw_gravity_zones(batch, level, cam_offset)
    _draw_platforms_and_goal(batch, level, cam_offset, interp, alpha)
    _draw_enemies(batch, enemies, cam_offset, interp, alpha)
    _draw_player(batch, atlas, animator, player, player_state, cam_offset, feel, interp, alpha)
    batch.flush()


def _draw_gravity_zones(batch: SpriteBatch, level: object, cam_offset: tuple[float, float]) -> None:
    """Outline each gravity zone with four thin rects."""
    ox, oy = cam_offset
    t = ZONE_OUTLINE_PX
    for zone in level.gravity_zones:
        col = _zone_color(zone)
        zx, zy, zw, zh = zone.x + ox, zone.y + oy, zone.w, zone.h
        batch.draw_rect(zx, zy, zw, t, col)
        batch.draw_rect(zx, zy + zh - t, zw, t, col)
        batch.draw_rect(zx, zy, t, zh, col)
        batch.draw_rect(zx + zw - t, zy, t, zh, col)


def _draw_platforms_and_goal(batch: SpriteBatch, level: object, cam_offset: tuple[float, float],
                             interp: RenderInterpolator | None, alpha: float) -> None:
    """Static platforms, then moving platforms (interpolated), then the goal rect."""
    ox, oy = cam_offset
    for plat in level.static_platforms:
        batch.draw_rect(plat.x + ox, plat.y + oy, plat.width, plat.height, STATIC_PLATFORM_COLOR)
    for mp in level.moving_platforms:
        r = mp.rect
        x, y = (r.x, r.y) if interp is None else interp.platform_pos(mp, alpha)
        batch.draw_rect(x + ox, y + oy, r.width, r.height, MOVING_PLATFORM_COLOR)
    gr = level.goal_rect
    batch.draw_rect(gr.x + ox, gr.y + oy, gr.width, gr.height, GOAL_COLOR)


def _draw_enemies(batch: SpriteBatch, enemies: list, cam_offset: tuple[float, float],
                  interp: RenderInterpolator | None, alpha: float) -> None:
    """Each enemy as a solid rect coloured by type (interpolated)."""
    ox, oy = cam_offset
    for enemy in enemies:
        r = enemy.rect
        dx, dy = (0.0, 0.0) if interp is None else interp.enemy_offset(enemy, alpha)
        batch.draw_rect(r.x + dx + ox, r.y + dy + oy, r.width, r.height, _enemy_color(enemy))


def _draw_player(
    batch: SpriteBatch, atlas: RuntimeAtlas, animator: object, player: object,
    player_state: object, cam_offset: tuple[float, float], feel: Feel | None,
    interp: RenderInterpolator | None, alpha: float,
) -> None:
    """The player sprite, rotated to gravity, with feel flash/squash applied (interpolated)."""
    ox, oy = cam_offset
    sw, sh = animator.width, animator.height
    x, y = (player.px, player.py) if interp is None else interp.player_pos(player, alpha)
    px_screen = x + ox
    py_screen = y + oy
    frame_name = _player_frame_name(animator, player_state)
    if not atlas.has_frame(frame_name):
        batch.draw_rect(px_screen - sw / 2, py_screen - sh / 2, sw, sh, PLAYER_FALLBACK_COLOR)
        return
    flash, (cx, cy, qw, qh) = _player_feel(feel, player, px_screen, py_screen, sw, sh)
    batch.draw_sprite(
        frame_name,
        cx, cy + C.SPRITE_PHYSICS_OFFSET_Y,
        qw, qh,
        gravity_dir=tuple(player.gravity_dir),
        flip_x=not player.facing_right,
        flash=flash,
    )


def _player_feel(
    feel: Feel | None, player: object,
    cx: float, cy: float, w: float, h: float,
) -> tuple[RGBA, tuple[float, float, float, float]]:
    """Apply squash/stretch (feet stay planted along gravity) and return the flash.

    Returns (flash, (centre_x, centre_y, quad_w, quad_h)). Quad h runs along
    gravity because draw_sprite rotates the quad to the gravity direction.
    """
    if feel is None:
        return NO_FLASH, (cx, cy, w, h)
    along, across = feel.sprite_scale()
    new_h = h * along
    gx, gy = player.gravity_dir
    shift = (h - new_h) / 2.0  # move the centre toward the feet so they don't lift
    return feel.sprite_flash(), (cx + gx * shift, cy + gy * shift, w * across, new_h)


def _player_frame_name(animator: object, player_state: object) -> str:
    """Map animator state + current walk frame to an atlas frame name."""
    state_name = player_state.name.lower()
    if state_name == "walk":
        frame_idx = getattr(animator, "_walk_frame", 0)
        name = f"player_walk_{frame_idx}"
        return name if animator._sprites.get(player_state) else "player_walk_0"
    return f"player_{state_name}_0"


def _zone_color(zone: object) -> RGBA:
    """Outline colour for a gravity zone: direction snap, weaker, or stronger."""
    if zone.gravity_dir is not None:
        return ZONE_DIRECTION_COLOR
    if getattr(zone, "strength_mult", None) is not None and zone.strength_mult < 1.0:
        return ZONE_WEAK_COLOR
    return ZONE_STRONG_COLOR


def _enemy_color(enemy: object) -> RGBA:
    """Placeholder colour by enemy class name."""
    cls = type(enemy).__name__
    if cls == "FoldPredator":
        return ENEMY_PREDATOR_COLOR
    if cls == "TheAnchored":
        return ENEMY_ANCHORED_COLOR
    return ENEMY_DEFAULT_COLOR
