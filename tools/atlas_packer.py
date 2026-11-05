"""Offline atlas packer — build-time tool for shipping atlas PNGs.

Packs a directory of sprite PNGs into a 2048×2048 texture atlas and writes:
  - <out_dir>/atlas.png
  - <out_dir>/atlas_manifest.json

Usage:
    python tools/atlas_packer.py <sprite_dir> <out_dir>

The runtime uses RuntimeAtlas (src/rendering/gpu/atlas.py) for startup packing.
This offline tool is for shipping builds where startup packing time is a concern.
"""
from __future__ import annotations

import json
import os
import sys

import pygame

ATLAS_SIZE = 2048
_PADDING = 1


def pack(sprite_dir: str, out_dir: str) -> None:
    """Pack all PNGs in sprite_dir into an atlas and write to out_dir."""
    pygame.init()

    pngs = sorted(
        f for f in os.listdir(sprite_dir) if f.lower().endswith(".png")
    )
    if not pngs:
        print(f"No PNGs found in {sprite_dir}")
        return

    frames: list[tuple[str, pygame.Surface]] = []
    for fname in pngs:
        surf = pygame.image.load(os.path.join(sprite_dir, fname)).convert_alpha()
        name = os.path.splitext(fname)[0]
        frames.append((name, surf))

    atlas_surf = pygame.Surface((ATLAS_SIZE, ATLAS_SIZE), pygame.SRCALPHA)
    atlas_surf.fill((0, 0, 0, 0))

    manifest: dict[str, dict] = {}
    sorted_frames = sorted(frames, key=lambda kv: kv[1].get_height(), reverse=True)

    cx, cy, row_h = _PADDING, _PADDING, 0
    for name, surf in sorted_frames:
        fw, fh = surf.get_size()
        if cx + fw + _PADDING > ATLAS_SIZE:
            cx = _PADDING
            cy += row_h + _PADDING
            row_h = 0
        if cy + fh + _PADDING > ATLAS_SIZE:
            print(f"Warning: '{name}' doesn't fit in {ATLAS_SIZE}px atlas, skipped")
            continue
        atlas_surf.blit(surf, (cx, cy))
        manifest[name] = {"x": cx, "y": cy, "w": fw, "h": fh}
        row_h = max(row_h, fh)
        cx += fw + _PADDING

    os.makedirs(out_dir, exist_ok=True)
    atlas_path = os.path.join(out_dir, "atlas.png")
    manifest_path = os.path.join(out_dir, "atlas_manifest.json")

    pygame.image.save(atlas_surf, atlas_path)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Packed {len(manifest)} frames → {atlas_path}")
    print(f"Manifest → {manifest_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    pack(sys.argv[1], sys.argv[2])
