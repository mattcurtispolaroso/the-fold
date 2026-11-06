"""Shader compile watcher (TA-4) — recompiles every shader in shaders/ on change.

Usage:
    python tools/shader_watch.py          # watch, recompiling on every save
    python tools/shader_watch.py --once   # compile everything once; exit 1 on errors

Each .frag is linked against the vertex shader it runs with in the game, so
link errors (mismatched in/out names) are caught as well as syntax errors.
Uses a standalone GL context, so the game does not need to be running.
"""
from __future__ import annotations

import os
import sys
import time

import moderngl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHADER_DIR = os.path.join(ROOT, "shaders")
POLL_SECONDS: float = 0.5

# Which vertex shader each fragment shader is paired with at runtime
VERTEX_FOR: dict[str, str] = {
    "sprite.frag": "sprite.vert",
    "upscale.frag": "upscale.vert",
    "light.frag": "upscale.vert",
}
DEFAULT_VERTEX: str = "post.vert"


def _read(name: str) -> str:
    """Return the source of one shader file."""
    with open(os.path.join(SHADER_DIR, name)) as f:
        return f.read()


def compile_all(ctx: moderngl.Context) -> list[str]:
    """Compile and link every fragment shader; return one message per failure."""
    errors: list[str] = []
    for frag in sorted(f for f in os.listdir(SHADER_DIR) if f.endswith(".frag")):
        vert = VERTEX_FOR.get(frag, DEFAULT_VERTEX)
        try:
            ctx.program(vertex_shader=_read(vert), fragment_shader=_read(frag)).release()
        except Exception as e:  # moderngl raises a generic Error with the GL log
            errors.append(f"{frag} (+ {vert}):\n{e}")
    return errors


def _snapshot() -> dict[str, float]:
    """Return {filename: mtime} for every shader file."""
    return {f: os.path.getmtime(os.path.join(SHADER_DIR, f)) for f in os.listdir(SHADER_DIR)}


def _report(ctx: moderngl.Context) -> bool:
    """Compile everything, print the result, and return True when all shaders are OK."""
    errors = compile_all(ctx)
    stamp = time.strftime("%H:%M:%S")
    if errors:
        print(f"[{stamp}] {len(errors)} shader error(s):")
        for err in errors:
            print("  " + err.replace("\n", "\n  "))
    else:
        print(f"[{stamp}] all shaders compile")
    return not errors


def main() -> int:
    """Entry point: compile once, then poll for changes unless --once is given."""
    ctx = moderngl.create_standalone_context()
    ok = _report(ctx)
    if "--once" in sys.argv:
        return 0 if ok else 1
    print(f"Watching {SHADER_DIR} (Ctrl+C to stop)")
    seen = _snapshot()
    try:
        while True:
            time.sleep(POLL_SECONDS)
            now = _snapshot()
            if now != seen:
                seen = now
                _report(ctx)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
