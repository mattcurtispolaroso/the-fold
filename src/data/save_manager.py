"""Save and meta-progression system — Module 16.

Persists run stats across sessions. Atomic write (temp → rename) prevents
corruption on crash mid-save. Corrupt files are backed up, never deleted.

Save file location: <game_dir>/save.json
Corruption backup:  <game_dir>/save_corrupted_<timestamp>.json
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass


SAVE_VERSION: int = 1


@dataclass
class MetaProgress:
    """Persistent stats that survive across all runs."""

    total_runs: int = 0
    runs_won: int = 0
    best_stability: float = 0.0
    best_nodes_reached: int = 0

    def record_run(self, *, won: bool, fold_stability: float, nodes_reached: int) -> None:
        """Update meta stats at the end of a run."""
        self.total_runs += 1
        if won:
            self.runs_won += 1
        if fold_stability > self.best_stability:
            self.best_stability = fold_stability
        if nodes_reached > self.best_nodes_reached:
            self.best_nodes_reached = nodes_reached

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON output."""
        return {"version": SAVE_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, d: dict) -> MetaProgress:
        """Deserialise from a loaded JSON dict, ignoring unknown keys."""
        return cls(
            total_runs=int(d.get("total_runs", 0)),
            runs_won=int(d.get("runs_won", 0)),
            best_stability=float(d.get("best_stability", 0.0)),
            best_nodes_reached=int(d.get("best_nodes_reached", 0)),
        )


class SaveManager:
    """Loads and saves MetaProgress atomically with corruption recovery."""

    def __init__(self, save_path: str) -> None:
        """Initialise with an absolute path to the save file."""
        self._path = save_path

    # --- Public API ---

    def load(self) -> MetaProgress:
        """Load MetaProgress from disk; returns empty progress if missing or corrupt."""
        if not os.path.exists(self._path):
            return MetaProgress()
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._validate(raw)
            return MetaProgress.from_dict(raw)
        except Exception:
            self._backup_corrupt()
            return MetaProgress()

    def save(self, meta: MetaProgress) -> None:
        """Write MetaProgress atomically — write temp file then rename."""
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(meta.to_dict(), f, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            # Never crash the game on a failed save — just log and continue
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # --- Internal ---

    def _validate(self, d: object) -> None:
        """Raise ValueError if d is not a recognisable save dict."""
        if not isinstance(d, dict):
            raise ValueError("save file root is not a dict")
        version = d.get("version")
        if version is None or int(version) > SAVE_VERSION:
            raise ValueError(f"unknown save version: {version}")

    def _backup_corrupt(self) -> None:
        """Rename the corrupt save file to a timestamped backup."""
        ts = int(time.time())
        backup = os.path.join(
            os.path.dirname(self._path),
            f"save_corrupted_{ts}.json",
        )
        try:
            os.rename(self._path, backup)
        except OSError:
            pass
