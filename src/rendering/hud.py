"""HUD and frame-drawing helpers.

Extracted from main.py to keep the entry point under 300 lines.
All functions are pure draw calls — they read state and render, never mutate it.
"""
from __future__ import annotations

import pygame

import constants as C
from src.entities.anchored import TheAnchored
from src.entities.fold_predator import FoldPredator
from src.entities.player import Player
from src.levels.level_renderer import LevelRenderer
from src.physics import GRAVITY_LABELS
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


def draw_start_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    screen_width: int,
    screen_height: int,
    meta: object = None,
) -> None:
    """Draw the pre-run start screen with optional all-time meta stats."""
    screen.fill((0, 0, 0))
    title = font.render("THE FOLD", True, (200, 220, 255))
    prompt = font.render("Press ENTER to begin", True, (120, 140, 180))
    cx = screen_width // 2
    cy = screen_height // 2
    screen.blit(title, (cx - title.get_width() // 2, cy - 60))
    screen.blit(prompt, (cx - prompt.get_width() // 2, cy))
    if meta is not None and meta.total_runs > 0:
        stats = font.render(
            f"Runs: {meta.total_runs}   Wins: {meta.runs_won}   "
            f"Best stability: {meta.best_stability:.0f}",
            True, (70, 80, 100),
        )
        screen.blit(stats, (cx - stats.get_width() // 2, cy + 50))


def draw_node_map(
    screen: pygame.Surface,
    font: pygame.font.Font,
    run_state: object,
    screen_width: int,
    screen_height: int,
    registry: object = None,
) -> None:
    """Draw the between-room node list showing run progress and owned items."""
    screen.fill((0, 0, 0))
    cx = screen_width // 2
    title = font.render("NODE MAP", True, (200, 220, 255))
    screen.blit(title, (cx - title.get_width() // 2, 80))

    node_labels = {"combat": "COMBAT", "hole": "ANOMALY", "singularity": "SINGULARITY"}
    y = 160
    for i, node_type in enumerate(C.NODE_SEQUENCE):
        if i < run_state.current_node_idx:
            color = (60, 60, 60)
            marker = "  "
        elif i == run_state.current_node_idx:
            color = (200, 220, 255)
            marker = "> "
        else:
            color = (100, 100, 120)
            marker = "  "
        label = node_labels.get(node_type, node_type.upper())
        surf = font.render(f"{marker}NODE {i + 1} — {label}", True, color)
        screen.blit(surf, (cx - surf.get_width() // 2, y))
        y += 46

    # Show owned items if any
    owned = getattr(run_state, "owned_items", [])
    if owned and registry is not None:
        parts = []
        for entry in owned:
            defn = registry.get_item(entry["id"])
            name = defn.name if defn else entry["id"]
            rank = entry.get("rank", 1)
            parts.append(f"{name} R{rank}")
        items_text = "ITEMS: " + ", ".join(parts)
        # Truncate if too wide
        max_chars = 70
        if len(items_text) > max_chars:
            items_text = items_text[:max_chars - 1] + "…"
        item_surf = font.render(items_text, True, (100, 160, 100))
        screen.blit(item_surf, (cx - item_surf.get_width() // 2, y + 20))

    prompt = font.render("Press ENTER to continue", True, (80, 100, 140))
    screen.blit(prompt, (cx - prompt.get_width() // 2, screen_height - 60))


def draw_reward_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    offers: list,
    fold_stability: float,
    screen_width: int,
    screen_height: int,
    at_modifier_cap: bool = False,
) -> None:
    """Draw the pick-1-of-N reward screen after a combat room or white hole."""
    screen.fill((0, 0, 0))
    cx = screen_width // 2

    title = font.render("CHOOSE YOUR REWARD", True, (200, 220, 255))
    screen.blit(title, (cx - title.get_width() // 2, 60))

    if at_modifier_cap:
        cap_warn = font.render("MODIFIER CAP REACHED — OLDEST WILL BE DROPPED", True, (220, 160, 60))
        screen.blit(cap_warn, (cx - cap_warn.get_width() // 2, 100))

    y = 155
    for i, offer in enumerate(offers):
        defn = offer.item_def
        key_label = str(i + 1)

        if offer.is_paradox:
            takeable = offer.takeable(fold_stability)
            name_color = (200, 80, 80) if takeable else (80, 60, 60)
            cost_str = f"  [PARADOX: -{offer.paradox_cost:.0f} STABILITY]"
            if not takeable:
                cost_str += " INSUFFICIENT"
            rank_str = ""
        else:
            name_color = (180, 200, 255)
            cost_str = ""
            if offer.is_rank_up:
                rank_str = f"  R{offer.current_rank} → R{offer.target_rank}"
            else:
                tier_label = "MOD" if defn.tier == "modifier" else "ART"
                rank_str = f"  [{tier_label}] {defn.domain.upper()}"

        header = font.render(f"  {key_label}. {defn.name}{rank_str}", True, name_color)
        screen.blit(header, (cx - header.get_width() // 2, y))
        y += 28

        desc_color = (100, 120, 140) if not offer.is_paradox else (140, 80, 80)
        desc_text = defn.description
        if cost_str:
            desc_text += cost_str
        desc = font.render(f"     {desc_text}", True, desc_color)
        screen.blit(desc, (cx - desc.get_width() // 2, y))
        y += 40

    skip_color = (80, 100, 140)
    skip = font.render("  S. Skip — take nothing", True, skip_color)
    screen.blit(skip, (cx - skip.get_width() // 2, y + 10))


def draw_hole_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    hole_timer: float,
    is_white: bool,
    screen_width: int,
    screen_height: int,
) -> None:
    """Draw the hole encounter reveal screen — phase 1 is neutral, phase 2 shows outcome."""
    screen.fill((0, 0, 0))
    cx, cy = screen_width // 2, screen_height // 2

    if hole_timer > C.HOLE_ENCOUNTER_PHASE2_DURATION:
        line = font.render("ENTERING THE ANOMALY...", True, (120, 120, 140))
        screen.blit(line, (cx - line.get_width() // 2, cy))
    else:
        if is_white:
            color = (180, 220, 255)
            lines = [
                "WHITE HOLE",
                f"ANCHOR RESTORED  +{C.WHITE_HOLE_STABILITY_RESTORE:.0f} STABILITY",
            ]
        else:
            color = (220, 80, 80)
            lines = [
                "BLACK HOLE",
                f"ANCHOR DESTABILISED  −{C.BLACK_HOLE_STABILITY_COST:.0f} STABILITY",
            ]
        for j, text in enumerate(lines):
            surf = font.render(text, True, color)
            screen.blit(surf, (cx - surf.get_width() // 2, cy - 20 + j * 50))


def draw_death_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    run_state: object,
    screen_width: int,
    screen_height: int,
    meta: object = None,
) -> None:
    """Draw the end-of-run death screen with stats and all-time bests."""
    screen.fill((0, 0, 0))
    cx, cy = screen_width // 2, screen_height // 2
    title = font.render("RUN OVER", True, (220, 80, 80))
    screen.blit(title, (cx - title.get_width() // 2, cy - 90))
    stats = [
        f"Nodes reached:   {run_state.current_node_idx} / {run_state.node_count}",
        f"Deaths:          {run_state.deaths}",
        f"Fold stability:  {run_state.fold_stability:.0f}",
    ]
    for j, line in enumerate(stats):
        surf = font.render(line, True, (160, 160, 180))
        screen.blit(surf, (cx - surf.get_width() // 2, cy - 20 + j * 40))
    if meta is not None and meta.total_runs > 0:
        best = font.render(
            f"All time — Runs: {meta.total_runs}   Wins: {meta.runs_won}   "
            f"Best stability: {meta.best_stability:.0f}",
            True, (70, 80, 100),
        )
        screen.blit(best, (cx - best.get_width() // 2, cy + 120))
    prompt = font.render("Press ENTER", True, (80, 100, 140))
    screen.blit(prompt, (cx - prompt.get_width() // 2, cy + 170))


def draw_win_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    run_state: object,
    screen_width: int,
    screen_height: int,
    meta: object = None,
) -> None:
    """Draw the win screen shown when the singularity node is reached."""
    screen.fill((0, 0, 0))
    cx, cy = screen_width // 2, screen_height // 2
    title = font.render("THE FOLD HOLDS", True, (200, 220, 100))
    screen.blit(title, (cx - title.get_width() // 2, cy - 90))
    stats = [
        f"Nodes reached:   {run_state.current_node_idx} / {run_state.node_count}",
        f"Deaths:          {run_state.deaths}",
        f"Fold stability:  {run_state.fold_stability:.0f}",
    ]
    for j, line in enumerate(stats):
        surf = font.render(line, True, (160, 160, 180))
        screen.blit(surf, (cx - surf.get_width() // 2, cy - 20 + j * 40))
    if meta is not None and meta.total_runs > 0:
        best = font.render(
            f"All time — Runs: {meta.total_runs}   Wins: {meta.runs_won}   "
            f"Best stability: {meta.best_stability:.0f}",
            True, (70, 80, 100),
        )
        screen.blit(best, (cx - best.get_width() // 2, cy + 120))
    prompt = font.render("Press ENTER", True, (80, 100, 140))
    screen.blit(prompt, (cx - prompt.get_width() // 2, cy + 170))
