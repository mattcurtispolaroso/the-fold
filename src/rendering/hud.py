"""In-game HUD and frame-drawing helpers (software path).

World draw, resource HUD, debug overlay, and the full-screen flash/tint
overlays. Menu/state screens (start, node map, reward, hole, death, win) live
in screens.py. All functions are pure draw calls — they read state and render,
never mutate it.
"""
from __future__ import annotations

import pygame

import constants as C
from src.entities.player import Player
from src.levels.level_renderer import LevelRenderer
from src.rendering.animation import PlayerAnimator, PlayerState

_BLACK = (0, 0, 0)
_BLUE = (50, 80, 180)
_GREEN = (50, 220, 50)


def draw_world(
    screen: pygame.Surface,
    background: pygame.Surface | None,
    level: LevelRenderer,
    enemies: list,
    animator: PlayerAnimator,
    player: Player,
    player_state: PlayerState,
    cam_offset: tuple[float, float],
    debug_draw: bool,
) -> None:
    """Draw background, level geometry, all enemies, and player sprite."""
    screen.fill(_BLACK)
    if background:
        screen.blit(background, (0, 0))
    level.draw(screen, cam_offset)
    for enemy in enemies:
        enemy.draw(screen, cam_offset)
    ox, oy = cam_offset
    sw, sh = animator.width, animator.height
    animator.draw(
        screen, player.px - sw / 2 + ox, player.py - sh / 2 + oy,
        player_state, player.facing_right, player.gravity_dir, debug_draw,
    )


def draw_debug_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    player: Player,
    cam_offset: tuple[float, float],
    screen_height: int,
) -> None:
    """Draw physics collision rect and resource bars (debug mode only)."""
    ox, oy = cam_offset
    dr = pygame.Rect(
        int(player.px - player.player_w / 2 + ox),
        int(player.py - player.player_h / 2 + oy),
        player.player_w, player.player_h,
    )
    pygame.draw.rect(screen, (255, 0, 0), dr, 2)
    pygame.draw.circle(screen, (0, 255, 0), (int(player.px + ox), int(player.py + oy)), 4)
    cr_pct = player.chrono_reserve / C.CHRONO_RESERVE_MAX
    pygame.draw.rect(screen, (40, 40, 60), (10, screen_height - 30, 200, 14))
    pygame.draw.rect(screen, (80, 180, 255), (10, screen_height - 30, int(200 * cr_pct), 14))
    cr_surf = font.render(
        f"CR {player.chrono_reserve:.0f}  [Q drain]", True, (160, 200, 255),
    )
    screen.blit(cr_surf, (220, screen_height - 40))
    ai_surf = font.render(
        f"AI {player.anchor_integrity}/{C.ANCHOR_INTEGRITY_MAX}", True, (255, 180, 80),
    )
    screen.blit(ai_surf, (10, screen_height - 60))


def draw_flash_overlay(
    screen: pygame.Surface,
    flash_surf: pygame.Surface,
    flash_timer: float,
) -> None:
    """Draw the rotation flash if the timer is still running."""
    if flash_timer <= 0:
        return
    alpha = int(C.ROTATION_FLASH_MAX_ALPHA * (flash_timer / C.ROTATION_FLASH_DURATION))
    flash_surf.fill((*C.ROTATION_FLASH_COLOR, alpha))
    screen.blit(flash_surf, (0, 0))


def draw_impact_flash(
    screen: pygame.Surface,
    flash_surf: pygame.Surface,
    flash_timer: float,
) -> None:
    """Draw the hard-landing impact flash if the timer is still running."""
    if flash_timer <= 0:
        return
    alpha = int(C.HARD_LAND_FLASH_MAX_ALPHA * (flash_timer / C.HARD_LAND_FLASH_DURATION))
    flash_surf.fill((*C.HARD_LAND_FLASH_COLOR, alpha))
    screen.blit(flash_surf, (0, 0))


def draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    player: Player,
    dilation_timer: float,
    dilation_cooldown_timer: float,
    screen_width: int,
    screen_height: int,
    in_anomaly: bool = False,
) -> None:
    """Draw always-visible resource HUD: integrity pips, chrono bar, dilation status."""
    _draw_integrity_pips(screen, player.anchor_integrity)
    _draw_chrono_bar(screen, font, player.chrono_reserve, screen_height)
    _draw_dilation_status(screen, font, dilation_timer, dilation_cooldown_timer,
                          screen_width, screen_height)
    if in_anomaly:
        _draw_anomaly_label(screen, font, screen_width)
    if player.goal_reached:
        gt = font.render("GOAL REACHED!", True, _GREEN)
        screen.blit(gt, (screen_width // 2 - gt.get_width() // 2, screen_height // 2))


def _draw_integrity_pips(screen: pygame.Surface, anchor_integrity: int) -> None:
    """Draw 3 integrity pips top-left. Amber = intact, dark = lost, red = all gone."""
    x = C.HUD_PIP_X
    for i in range(C.ANCHOR_INTEGRITY_MAX):
        if anchor_integrity <= 0:
            color = C.HUD_COLOR_PIP_ZERO
        elif i < anchor_integrity:
            color = C.HUD_COLOR_PIP_FULL
        else:
            color = C.HUD_COLOR_PIP_LOST
        pygame.draw.rect(screen, color, (x, C.HUD_PIP_Y, C.HUD_PIP_SIZE, C.HUD_PIP_SIZE))
        x += C.HUD_PIP_SIZE + C.HUD_PIP_GAP


def _draw_chrono_bar(
    screen: pygame.Surface, font: pygame.font.Font,
    chrono_reserve: float, screen_height: int,
) -> None:
    """Draw segmented chrono bar bottom-left."""
    ratio = max(0.0, min(1.0, chrono_reserve / C.CHRONO_RESERVE_MAX))
    filled = round(ratio * C.HUD_CHRONO_SEG_COUNT)
    y = screen_height - C.HUD_CHRONO_BOTTOM_OFFSET
    x = C.HUD_CHRONO_X
    for i in range(C.HUD_CHRONO_SEG_COUNT):
        if i < filled:
            color = C.HUD_COLOR_CHRONO_HI if ratio > 0.5 else C.HUD_COLOR_CHRONO_LO
        else:
            color = C.HUD_COLOR_CHRONO_EMPTY
        pygame.draw.rect(screen, color, (x, y, C.HUD_CHRONO_SEG_W, C.HUD_CHRONO_SEG_H))
        x += C.HUD_CHRONO_SEG_W + C.HUD_CHRONO_SEG_GAP
    label = font.render("CHRONO", True, (80, 60, 20))
    screen.blit(label, (x + 4, y - 2))


def _draw_dilation_status(
    screen: pygame.Surface, font: pygame.font.Font,
    active_timer: float, cooldown_timer: float,
    screen_width: int, screen_height: int,
) -> None:
    """Draw Time Dilation status centred at the bottom. Hidden when ready and idle."""
    if active_timer > 0:
        text = f"◄ TIME DILATION  {active_timer:.1f}s ►"
        color = C.HUD_COLOR_DILATION_ACTIVE
    elif cooldown_timer > 0:
        text = f"DILATION  {cooldown_timer:.1f}s"
        color = C.HUD_COLOR_DILATION_COOLDOWN
    else:
        return
    surf = font.render(text, True, color)
    screen.blit(surf, (screen_width // 2 - surf.get_width() // 2, screen_height - 52))


def _draw_anomaly_label(
    screen: pygame.Surface, font: pygame.font.Font, screen_width: int,
) -> None:
    """Show ANOMALY label at top-centre during hole encounter levels."""
    surf = font.render("ANOMALY", True, (120, 100, 160))
    screen.blit(surf, (screen_width // 2 - surf.get_width() // 2, C.HUD_PIP_Y))


def draw_fold_tint(
    screen: pygame.Surface,
    fold_tint_surf: pygame.Surface,
    fold_stability: float,
) -> None:
    """Draw a red environmental tint that deepens as fold_stability depletes."""
    if fold_stability >= C.FOLD_TINT_THRESHOLD:
        return
    t = 1.0 - (fold_stability / C.FOLD_TINT_THRESHOLD)
    alpha = int(C.FOLD_TINT_MAX_ALPHA * t)
    fold_tint_surf.fill((180, 0, 0, alpha))
    screen.blit(fold_tint_surf, (0, 0))

