"""Player input sampled for the fixed physics step (Engine Session 3).

Before this, key events changed the simulation the moment they arrived (jump,
rotate, dilate), outside any physics step, so results depended on frame
timing. Now:

- Held keys (movement) are sampled once per frame.
- Edge presses (jump, jump release, rotate, dilate) accumulate in an
  InputBuffer until a physics step consumes them, so a press is never lost on
  frames with no step (hitstop, high refresh rates) and is never applied twice.

World.step() only ever sees an InputFrame — a plain value, easy to record and
replay.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class InputFrame:
    """Everything the simulation needs from the player for one physics step."""

    move_x: int = 0            # -1 left, 0, +1 right (held)
    move_y: int = 0            # -1 up, 0, +1 down (held)
    jump_pressed: bool = False
    jump_released: bool = False
    rotate_pressed: bool = False
    dilate_pressed: bool = False


class InputBuffer:
    """Collects a frame's input and hands it to physics steps without loss or repeats."""

    def __init__(self) -> None:
        """Start with nothing held or pending."""
        self._held = InputFrame()
        self._jump = self._release = self._rotate = self._dilate = False

    def press_jump(self) -> None:
        """Jump key went down."""
        self._jump = True

    def release_jump(self) -> None:
        """Jump key came up."""
        self._release = True

    def press_rotate(self) -> None:
        """Gravity-rotate key went down."""
        self._rotate = True

    def press_dilate(self) -> None:
        """Time Dilation key went down."""
        self._dilate = True

    def set_held(self, move_x: int, move_y: int) -> None:
        """Record which movement directions are held this frame."""
        self._held = InputFrame(move_x=move_x, move_y=move_y)

    def take(self) -> InputFrame:
        """Input for the next physics step; pending presses are consumed (cleared)."""
        frame = replace(self._held, jump_pressed=self._jump, jump_released=self._release,
                        rotate_pressed=self._rotate, dilate_pressed=self._dilate)
        self._jump = self._release = self._rotate = self._dilate = False
        return frame

    def clear(self) -> None:
        """Drop everything (entering gameplay: menu key presses must not leak in)."""
        self.__init__()
