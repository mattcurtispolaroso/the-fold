"""Event bus for The Fold.

Simple synchronous pub/sub. Systems emit named events; item effects
and other systems subscribe to them. Cancellable events return an
EventResult that a listener can mark cancelled to suppress the default
consequence (e.g. Closed Timelike Curve cancels INTEGRITY_ZERO).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


class GameEvent(Enum):
    """All game events that can be emitted on the bus."""

    GRAVITY_ROTATED = auto()
    ABILITY_USED = auto()
    ABILITY_ENDED = auto()
    PLAYER_HIT = auto()       # cancellable
    INTEGRITY_ZERO = auto()   # cancellable
    ROOM_ENTERED = auto()
    ROOM_CLEARED = auto()
    HOLE_RESOLVED = auto()


@dataclass
class EventResult:
    """Returned by EventBus.emit. Listeners set cancelled=True to suppress the default action."""

    cancelled: bool = False


class EventBus:
    """Synchronous pub/sub bus. All handlers run in subscription order."""

    def __init__(self) -> None:
        """Initialise with no listeners."""
        self._listeners: dict[GameEvent, list[Callable[..., None]]] = {}

    def subscribe(self, event: GameEvent, handler: Callable[..., None]) -> None:
        """Register handler to be called when event is emitted."""
        self._listeners.setdefault(event, []).append(handler)

    def unsubscribe(self, event: GameEvent, handler: Callable[..., None]) -> None:
        """Remove a previously registered handler. No-op if not found."""
        listeners = self._listeners.get(event, [])
        if handler in listeners:
            listeners.remove(handler)

    def emit(self, event: GameEvent, **kwargs: object) -> EventResult:
        """Emit event, calling all registered handlers with kwargs.

        Returns an EventResult. Handlers may set result.cancelled = True
        to signal that the default consequence should be suppressed.
        """
        result = EventResult()
        for handler in list(self._listeners.get(event, [])):
            handler(result, **kwargs)
        return result

    def clear(self) -> None:
        """Remove all listeners. Used on run reset."""
        self._listeners.clear()
