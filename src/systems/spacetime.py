"""Spacetime ability system — Module 4 foundation.

AbilitySlot is the unit of an active ability. It owns the timers that
were previously loose floats in main.py (dilation_timer, dilation_cooldown)
and exposes a clean interface so item modifiers can adjust duration/cost
without touching the game loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from constants import TIME_DILATION_COOLDOWN, TIME_DILATION_COST, TIME_DILATION_DURATION, TIME_DILATION_FACTOR
from src.systems.events import EventBus, EventResult, GameEvent


@dataclass
class AbilitySlot:
    """One active ability with its timers and parameters."""

    name: str
    duration: float
    cost: float
    cooldown: float
    active_timer: float = field(default=0.0)
    cooldown_timer: float = field(default=0.0)

    @property
    def is_active(self) -> bool:
        """True while the ability effect is running."""
        return self.active_timer > 0.0

    @property
    def is_ready(self) -> bool:
        """True when the ability can be activated again."""
        return self.cooldown_timer <= 0.0

    def activate(self, chrono_reserve: float) -> float:
        """Start the ability, deduct cost, return updated chrono_reserve."""
        chrono_reserve -= self.cost
        self.active_timer = self.duration
        self.cooldown_timer = self.duration + self.cooldown
        return chrono_reserve

    def tick(self, dt: float, bus: EventBus) -> None:
        """Advance timers by dt. Emits ABILITY_ENDED when effect expires."""
        was_active = self.is_active
        self.active_timer = max(0.0, self.active_timer - dt)
        self.cooldown_timer = max(0.0, self.cooldown_timer - dt)
        if was_active and not self.is_active:
            bus.emit(GameEvent.ABILITY_ENDED, ability_name=self.name)

    def reset(self) -> None:
        """Clear both timers — used when resetting the level or run."""
        self.active_timer = 0.0
        self.cooldown_timer = 0.0

    def time_scale(self) -> float:
        """Return physics time scale: dilated when active, normal otherwise."""
        return TIME_DILATION_FACTOR if self.is_active else 1.0


def make_time_dilation() -> AbilitySlot:
    """Create the Time Dilation ability slot from constants."""
    return AbilitySlot(
        name="time_dilation",
        duration=TIME_DILATION_DURATION,
        cost=TIME_DILATION_COST,
        cooldown=TIME_DILATION_COOLDOWN,
    )
