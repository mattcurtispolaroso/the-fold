"""RunState — serialisable container for all per-run state.

Holds fold_stability, node progress, and the run seed. Distinct from Player
(which holds per-character state). fold_stability belongs here because it
depletes permanently across rooms — it is a run stat, not a character stat.
"""
from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass, field

from constants import FOLD_STABILITY_MAX, NODE_SEQUENCE


@dataclass
class RunState:
    """All mutable state that persists across rooms within a single run."""

    fold_stability: float
    current_node_idx: int
    run_seed: int
    is_active: bool
    combat_levels: list = field(default_factory=list)   # level indices for combat nodes
    hole_outcomes: list = field(default_factory=list)   # True = white hole, per hole node
    deaths: int = 0
    last_death_cause: str = ""                          # human-readable cause of the final death
    owned_items: list = field(default_factory=list)     # list of {id, rank} dicts
    paradox_spent: float = 0.0                          # fold_stability spent on paradox artifacts
    extra_reward_options: int = 0                       # extra options from Penrose Diagram etc.

    @classmethod
    def new_run(cls, seed: int | None = None) -> RunState:
        """Create a fresh run — generates level assignments and hole outcomes from seed.

        Pass `seed` for a reproducible run (tests, replays); omit for a random one.
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)
        rng = random.Random(seed)
        combat_levels = [
            rng.randint(0, 1),   # node 0: levels 0-1 (easier)
            rng.randint(2, 3),   # node 2: levels 2-3 (adds Predator or Anchored)
            rng.randint(4, 5),   # node 4: levels 4-5 (gravity zone challenge)
            rng.randint(6, 7),   # node 6: levels 6-7 (all 3 enemy types, hardest)
        ]
        hole_outcomes = [rng.random() < 0.5 for _ in range(4)]
        return cls(
            fold_stability=FOLD_STABILITY_MAX,
            current_node_idx=0,
            run_seed=seed,
            is_active=True,
            combat_levels=combat_levels,
            hole_outcomes=hole_outcomes,
            deaths=0,
        )

    @property
    def current_node_type(self) -> str:
        """Return the type of the current node ('combat', 'hole', 'singularity')."""
        return NODE_SEQUENCE[self.current_node_idx]

    @property
    def node_count(self) -> int:
        """Total number of nodes in the run."""
        return len(NODE_SEQUENCE)

    def advance_node(self) -> None:
        """Move to the next node after completing the current one."""
        self.current_node_idx += 1

    @property
    def singularity_pressure(self) -> float:
        """0.0 at run start, 1.0 at the last playable node before singularity."""
        last_playable = self.node_count - 2
        if last_playable <= 0:
            return 0.0
        return min(1.0, self.current_node_idx / last_playable)

    def current_hole_is_white(self) -> bool:
        """Return True if the current hole node is a white hole."""
        hole_idx = sum(
            1 for i in range(self.current_node_idx) if NODE_SEQUENCE[i] == "hole"
        )
        return bool(self.hole_outcomes[hole_idx])

    def combat_level_for_current_node(self) -> int:
        """Return the level file index for the current combat node."""
        combat_idx = sum(
            1 for i in range(self.current_node_idx) if NODE_SEQUENCE[i] == "combat"
        )
        return int(self.combat_levels[combat_idx])

    def to_dict(self) -> dict:
        """Serialise for crash logging and save files."""
        return dataclasses.asdict(self)
