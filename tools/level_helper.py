#!/usr/bin/env python3
"""ASCII art to level JSON converter for The Fold.

Usage:
    python tools/level_helper.py              # prints example level JSON
    python tools/level_helper.py -o out.json  # writes to file

Character map:
    #  = solid platform tile
    M  = moving platform origin (configure in moving_platforms dict)
    S  = spawn point
    X  = goal area
    .  = empty space

Tile size is configurable (default 40px). The grid is read top-to-bottom,
left-to-right. Adjacent '#' tiles on the same row are merged into single
platform rects for efficiency.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Append project root so we can import src.levels
sys.path.insert(0, str(__file__).rsplit("/tools", 1)[0])

from src.levels.level_data import (
    GoalDef,
    LevelData,
    MovingPlatformDef,
    PlatformDef,
)


def merge_row_tiles(
    row: str, row_idx: int, tile_size: int,
) -> list[PlatformDef]:
    """Merge adjacent '#' chars in a row into platform rects."""
    platforms: list[PlatformDef] = []
    run_start: int | None = None

    for col, ch in enumerate(row):
        if ch == "#":
            if run_start is None:
                run_start = col
        else:
            if run_start is not None:
                platforms.append(PlatformDef(
                    x=run_start * tile_size,
                    y=row_idx * tile_size,
                    w=(col - run_start) * tile_size,
                    h=tile_size,
                ))
                run_start = None

    # Close any open run at end of row
    if run_start is not None:
        platforms.append(PlatformDef(
            x=run_start * tile_size,
            y=row_idx * tile_size,
            w=(len(row) - run_start) * tile_size,
            h=tile_size,
        ))

    return platforms


def parse_ascii_level(
    grid: list[str],
    tile_size: int = 40,
    name: str = "Untitled",
    gravity_start: tuple[int, int] = (0, 1),
    moving_platform_defs: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> LevelData:
    """Convert an ASCII grid into a LevelData object.

    Args:
        grid: list of strings, one per row
        tile_size: pixel size of each tile
        name: level name
        gravity_start: initial gravity direction as unit vector
        moving_platform_defs: dict mapping (row, col) to moving platform
            properties: axis, min_val, max_val, speed
    """
    if moving_platform_defs is None:
        moving_platform_defs = {}

    static: list[PlatformDef] = []
    moving: list[MovingPlatformDef] = []
    spawn: tuple[float, float] = (0.0, 0.0)
    goal: GoalDef | None = None

    for row_idx, row in enumerate(grid):
        # Merge solid tiles
        static.extend(merge_row_tiles(row, row_idx, tile_size))

        # Scan for special characters
        for col_idx, ch in enumerate(row):
            px = col_idx * tile_size
            py = row_idx * tile_size

            if ch == "S":
                spawn = (px + tile_size / 2, py + tile_size / 2)

            elif ch == "X":
                goal = GoalDef(x=px, y=py, w=tile_size, h=tile_size)

            elif ch == "M":
                props = moving_platform_defs.get((row_idx, col_idx), {})
                moving.append(MovingPlatformDef(
                    x=px, y=py, w=tile_size * 2, h=tile_size // 2,
                    axis=props.get("axis", "x"),
                    min_val=props.get("min_val", px),
                    max_val=props.get("max_val", px + tile_size * 4),
                    speed=props.get("speed", 2),
                ))

    if goal is None:
        goal = GoalDef(x=0, y=0, w=tile_size, h=tile_size)

    return LevelData(
        name=name,
        gravity_start=gravity_start,
        spawn=spawn,
        goal=goal,
        static_platforms=static,
        moving_platforms=moving,
        tile_size=tile_size,
    )


def example_level() -> LevelData:
    """Return a small example level for demonstration."""
    grid = [
        "....................",
        "....................",
        "X.......####..####.",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        ".....M.............",
        "S...........####...",
        "######..........###",
    ]
    return parse_ascii_level(
        grid,
        tile_size=40,
        name="Example Level",
        moving_platform_defs={
            (12, 5): {"axis": "x", "min_val": 200, "max_val": 360, "speed": 2},
        },
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="ASCII to level JSON")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    args = parser.parse_args()

    level = example_level()
    json_str = level.to_json()

    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"Wrote {args.output}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
