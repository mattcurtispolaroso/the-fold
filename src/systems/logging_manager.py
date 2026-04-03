"""Persistent logging for The Fold.

Manages three log files: game events, performance warnings, crash reports.
Log rotation at 10MB. Never crashes — all file ops wrapped in try/except.
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime
from pathlib import Path

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__),
))), "logs")

MAX_LOG_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB


def _timestamp() -> str:
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _archive_timestamp() -> str:
    """Return timestamp for archive filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class LoggingManager:
    """Manages game_log.txt, performance_log.txt, and crash_log.txt."""

    def __init__(self, log_dir: str = LOG_DIR) -> None:
        """Create log directory and files if they do not exist."""
        self._log_dir = log_dir
        self._game_log = os.path.join(log_dir, "game_log.txt")
        self._perf_log = os.path.join(log_dir, "performance_log.txt")
        self._crash_log = os.path.join(log_dir, "crash_log.txt")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            pass

    def _rotate_if_needed(self, path: str) -> None:
        """Rename log to archive if it exceeds MAX_LOG_SIZE_BYTES."""
        try:
            if os.path.isfile(path) and os.path.getsize(path) > MAX_LOG_SIZE_BYTES:
                archive = path.replace(".txt", f"_archive_{_archive_timestamp()}.txt")
                os.rename(path, archive)
        except OSError:
            pass

    def _append(self, path: str, line: str) -> None:
        """Append a timestamped line to a log file. Never raises."""
        self._rotate_if_needed(path)
        try:
            with open(path, "a") as f:
                f.write(f"[{_timestamp()}] {line}\n")
        except OSError:
            pass

    def log_event(self, message: str) -> None:
        """Log a general game event."""
        self._append(self._game_log, message)

    def log_performance(
        self, message: str, frame_time: float, entity_count: int,
    ) -> None:
        """Log a performance warning with frame time and entity count."""
        line = f"{message} | frame_time={frame_time:.3f}ms entities={entity_count}"
        self._append(self._perf_log, line)

    def log_crash(
        self,
        exception: Exception,
        player_state: dict | None = None,
        last_physics_frames: list | None = None,
    ) -> None:
        """Log an unhandled exception with full context."""
        lines = [
            f"CRASH: {type(exception).__name__}: {exception}",
            f"Traceback:\n{traceback.format_exc()}",
        ]
        if player_state:
            lines.append(f"Player state: {player_state}")
        if last_physics_frames:
            lines.append(f"Last {len(last_physics_frames)} physics frames:")
            for i, frame in enumerate(last_physics_frames[-10:]):
                lines.append(f"  [{i}] {frame}")
        self._append(self._crash_log, "\n".join(lines))

    @property
    def crash_log_path(self) -> str:
        """Return path to crash log file."""
        return self._crash_log
