"""Full-screen menu/state screens: start, node map, reward, hole, death, win.

Split out of hud.py (which keeps the in-game HUD and overlays). Every function
is a pure draw: it reads state and renders, never mutates it. These run on the
software path; the GPU path uploads the same surface as a fullscreen quad.
"""
from __future__ import annotations

import pygame

import constants as C

_TITLE_COLOR = (200, 220, 255)
_STAT_COLOR = (160, 160, 180)
_BEST_COLOR = (70, 80, 100)           # all-time line on death / win screens
_START_BEST_COLOR = (50, 60, 80)      # all-time line on the start screen
_PROMPT_COLOR = (80, 100, 140)
_STAT_LINE_STEP = 40
_NODE_LINE_STEP = 46
_ITEMS_MAX_CHARS = 70
_NODE_LABELS = {"combat": "COMBAT", "hole": "ANOMALY", "singularity": "SINGULARITY"}


def _blit_centered(screen: pygame.Surface, surf: pygame.Surface, cx: int, y: int) -> None:
    """Blit `surf` horizontally centred on cx at height y."""
    screen.blit(surf, (cx - surf.get_width() // 2, y))


def _draw_text(screen: pygame.Surface, font: pygame.font.Font, text: str,
               color: tuple[int, int, int], cx: int, y: int) -> None:
    """Render one line of text centred on cx at height y."""
    _blit_centered(screen, font.render(text, True, color), cx, y)


def _draw_all_time_best(screen: pygame.Surface, font: pygame.font.Font, meta: object,
                        cx: int, y: int, color: tuple[int, int, int], prefix: str = "") -> None:
    """Meta stats line (runs / wins / best stability); hidden before the first run."""
    if meta is None or meta.total_runs <= 0:
        return
    _draw_text(screen, font,
               f"{prefix}Runs: {meta.total_runs}   Wins: {meta.runs_won}   "
               f"Best stability: {meta.best_stability:.0f}",
               color, cx, y)


def _draw_run_stats(screen: pygame.Surface, font: pygame.font.Font,
                    run_state: object, cx: int, y: int) -> None:
    """The three end-of-run stat lines (nodes, deaths, stability) from height y."""
    lines = [
        f"Nodes reached:   {run_state.current_node_idx} / {run_state.node_count}",
        f"Deaths:          {run_state.deaths}",
        f"Fold stability:  {run_state.fold_stability:.0f}",
    ]
    for j, line in enumerate(lines):
        _draw_text(screen, font, line, _STAT_COLOR, cx, y + j * _STAT_LINE_STEP)


def draw_start_screen(
    screen: pygame.Surface,
    font: pygame.font.Font,
    screen_width: int,
    screen_height: int,
    meta: object = None,
) -> None:
    """Draw the pre-run start screen with optional all-time meta stats."""
    screen.fill((0, 0, 0))
    cx = screen_width // 2
    cy = screen_height // 2
    _draw_text(screen, font, "THE FOLD", _TITLE_COLOR, cx, cy - 60)
    _draw_text(screen, font, "Press ENTER to begin", (120, 140, 180), cx, cy)
    _draw_text(screen, font,
               "Move: A/D   Jump: Space   Rotate gravity: R   Time Dilation: E",
               (60, 75, 95), cx, cy + 46)
    _draw_all_time_best(screen, font, meta, cx, cy + 80, _START_BEST_COLOR)


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
    _draw_text(screen, font, "NODE MAP", _TITLE_COLOR, cx, 80)
    y = _draw_node_list(screen, font, run_state, cx, 160)
    _draw_owned_items(screen, font, run_state, registry, cx, y + 20)
    _draw_text(screen, font, "Press ENTER to continue", _PROMPT_COLOR, cx, screen_height - 60)


def _draw_node_list(screen: pygame.Surface, font: pygame.font.Font,
                    run_state: object, cx: int, y: int) -> int:
    """One line per node: past greyed, current highlighted. Returns the next y."""
    for i, node_type in enumerate(C.NODE_SEQUENCE):
        if i < run_state.current_node_idx:
            color, marker = (60, 60, 60), "  "
        elif i == run_state.current_node_idx:
            color, marker = (200, 220, 255), "> "
        else:
            color, marker = (100, 100, 120), "  "
        label = _NODE_LABELS.get(node_type, node_type.upper())
        _draw_text(screen, font, f"{marker}NODE {i + 1} — {label}", color, cx, y)
        y += _NODE_LINE_STEP
    return y


def _draw_owned_items(screen: pygame.Surface, font: pygame.font.Font,
                      run_state: object, registry: object, cx: int, y: int) -> None:
    """ITEMS line listing owned items with ranks, truncated to fit."""
    owned = getattr(run_state, "owned_items", [])
    if not owned or registry is None:
        return
    parts = []
    for entry in owned:
        defn = registry.get_item(entry["id"])
        name = defn.name if defn else entry["id"]
        parts.append(f"{name} R{entry.get('rank', 1)}")
    items_text = "ITEMS: " + ", ".join(parts)
    if len(items_text) > _ITEMS_MAX_CHARS:
        items_text = items_text[:_ITEMS_MAX_CHARS - 1] + "…"
    _draw_text(screen, font, items_text, (100, 160, 100), cx, y)


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
    _draw_text(screen, font, "CHOOSE YOUR REWARD", _TITLE_COLOR, cx, 60)
    if at_modifier_cap:
        _draw_text(screen, font, "MODIFIER CAP REACHED — OLDEST WILL BE DROPPED",
                   (220, 160, 60), cx, 100)
    y = 155
    for i, offer in enumerate(offers):
        header, name_color, desc, desc_color = _offer_lines(offer, i + 1, fold_stability)
        _draw_text(screen, font, header, name_color, cx, y)
        y += 28
        _draw_text(screen, font, desc, desc_color, cx, y)
        y += 40
    _draw_text(screen, font, "  S. Skip — take nothing", (80, 100, 140), cx, y + 10)


def _offer_lines(offer: object, key: int, fold_stability: float) -> tuple[str, tuple, str, tuple]:
    """(header, header colour, description, description colour) for one offer."""
    defn = offer.item_def
    cost_str = ""
    if offer.is_paradox:
        takeable = offer.takeable(fold_stability)
        name_color = (200, 80, 80) if takeable else (80, 60, 60)
        cost_str = f"  [PARADOX: -{offer.paradox_cost:.0f} STABILITY]"
        if not takeable:
            cost_str += " INSUFFICIENT"
        rank_str = ""
    else:
        name_color = (180, 200, 255)
        if offer.is_rank_up:
            rank_str = f"  R{offer.current_rank} → R{offer.target_rank}"
        else:
            tier_label = "MOD" if defn.tier == "modifier" else "ART"
            rank_str = f"  [{tier_label}] {defn.domain.upper()}"
    desc_color = (140, 80, 80) if offer.is_paradox else (100, 120, 140)
    header = f"  {key}. {defn.name}{rank_str}"
    return header, name_color, f"     {defn.description}{cost_str}", desc_color


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
        _draw_text(screen, font, "ENTERING THE ANOMALY...", (120, 120, 140), cx, cy)
        return
    if is_white:
        color = (180, 220, 255)
        lines = ["WHITE HOLE",
                 f"ANCHOR RESTORED  +{C.WHITE_HOLE_STABILITY_RESTORE:.0f} STABILITY"]
    else:
        color = (220, 80, 80)
        lines = ["BLACK HOLE",
                 f"ANCHOR DESTABILISED  −{C.BLACK_HOLE_STABILITY_COST:.0f} STABILITY"]
    for j, text in enumerate(lines):
        _draw_text(screen, font, text, color, cx, cy - 20 + j * 50)


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
    _draw_text(screen, font, "RUN OVER", (220, 80, 80), cx, cy - 110)
    cause = getattr(run_state, "last_death_cause", "")
    if cause:
        _draw_text(screen, font, f"Cause: {cause}", (200, 100, 100), cx, cy - 60)
    _draw_run_stats(screen, font, run_state, cx, cy + 10)
    _draw_all_time_best(screen, font, meta, cx, cy + 140, _BEST_COLOR, prefix="All time — ")
    _draw_text(screen, font, "Press ENTER", _PROMPT_COLOR, cx, cy + 190)


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
    _draw_text(screen, font, "THE FOLD HOLDS", (200, 220, 100), cx, cy - 90)
    _draw_run_stats(screen, font, run_state, cx, cy - 20)
    _draw_all_time_best(screen, font, meta, cx, cy + 120, _BEST_COLOR, prefix="All time — ")
    _draw_text(screen, font, "Press ENTER", _PROMPT_COLOR, cx, cy + 170)
