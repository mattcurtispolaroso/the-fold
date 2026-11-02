"""Anomaly room picker — returns a seeded level path for hole encounters."""
from __future__ import annotations

import os
import random

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LEVEL_DIR = os.path.join(_BASE, "levels")

ANOMALY_LEVELS: list[str] = [
    os.path.join(_LEVEL_DIR, "anomaly_01.json"),
    os.path.join(_LEVEL_DIR, "anomaly_02.json"),
    os.path.join(_LEVEL_DIR, "anomaly_03.json"),
]


def pick_anomaly_room(run_seed: int, node_idx: int) -> str:
    """Return a path to an anomaly room JSON, seeded by run and node position."""
    rng = random.Random(run_seed ^ (node_idx * 31337))
    return rng.choice(ANOMALY_LEVELS)
