"""The simulation: everything that must advance deterministically on the fixed step.

World owns all gameplay state — player, level, enemies, run state, Time
Dilation, items, cooldowns, gravity zones — and advances it only through
step(input), one fixed PHYSICS_DT at a time. The same InputFrame sequence from
the same snapshot always produces the same state, regardless of frame rate.

Presentation (camera, feel, particles, animation, rendering) never runs here;
step() returns StepEvents describing what happened so main.py can react.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from constants import (
    COYOTE_TIME, FOLD_STABILITY_INTEGRITY_COST, ROTATION_SAFE_SEARCH_PX, TEMPORAL_ECHO_SPEED,
    VALIDATION_EJECT_SEARCH_PX,
)
from src.data.run_state import RunState
from src.entities.anchored import TheAnchored
from src.entities.enemy import TemporalEcho
from src.entities.fold_predator import FoldPredator
from src.entities.player import Player
from src.levels.level_renderer import LevelRenderer
from src.physics import GravityDir, find_safe_position, try_rotate
from src.systems import world_phases as phases
from src.systems.events import EventBus, GameEvent
from src.systems.input_frame import InputFrame
from src.systems.items import ItemManager
from src.systems.spacetime import make_time_dilation
from src.systems.world_snapshot import WorldSnapshot, capture, restore

logger = logging.getLogger(__name__)


@dataclass
class StepEvents:
    """What happened during one World.step — for presentation and flow to react to."""

    rotated: GravityDir | None = None     # new gravity direction, if any rotation happened
    rotation_blocked: bool = False        # rotate pressed but no room (no cost charged)
    jumped: bool = False
    landed: bool = False
    hard_landed: bool = False
    hit: bool = False                     # an enemy hit landed (not cancelled by an item)
    died: str | None = None               # cause, when integrity reached zero this step
    run_over: bool = False                # the death emptied fold stability
    goal: bool = False
    gravity_clamped: bool = False         # combined gravity multiplier became clamped this step
    violations: list[str] = field(default_factory=list)


class World:
    """Owns and steps all simulation state (see module docstring)."""

    def __init__(self, registry: object, bus: EventBus, rng_seed: int = 0) -> None:
        """Create an empty world; call load_level() before stepping."""
        self.bus = bus
        self.level = LevelRenderer()
        self.player = Player.from_spawn((0.0, 0.0))
        self.enemies: list = []
        self.run_state = RunState(fold_stability=100.0, current_node_idx=0, run_seed=0,
                                  is_active=False)
        self.time_dilation = make_time_dilation()
        self.item_manager = ItemManager(
            registry=registry, bus=bus, player=self.player, enemies=self.enemies,
            run_state=self.run_state, ability_slot=self.time_dilation, rng_seed=rng_seed,
        )
        self.item_manager.sync_owned([])
        self.anomaly_pending = False
        self.rotation_cooldown = 0.0
        self.active_zones: set[int] = set()
        self.gravity_clamped = False
        self.gravity_mult = 1.0
        self.time_scale = 1.0
        self.gravity_expired = False
        self.steps = 0

    # --- Level and run lifecycle ---

    def load_level(self, path: str, anomaly: bool = False, announce: bool = True) -> None:
        """Load a level and put the player, enemies and timers at a fresh start."""
        self.level.load(path)
        self.anomaly_pending = anomaly
        self.respawn()
        if announce:
            self.bus.emit(GameEvent.ROOM_ENTERED)

    def respawn(self) -> None:
        """Player and enemies back to the level's spawn; per-room timers cleared.

        The spawn point is nudged to the nearest valid spot, so a level whose
        spawn overlaps geometry (levels 05-08 sit 18px inside the floor) never
        puts the player inside a solid, not even for one step.
        """
        p = self.player
        p.reset(self.level.spawn, tuple(self.level.gravity_start))
        spot = find_safe_position(p.px, p.py, p.player_w, p.player_h,
                                  self.level.collision_rects(), VALIDATION_EJECT_SEARCH_PX)
        if spot is not None:
            p.px, p.py = spot
            p.last_safe_px, p.last_safe_py = spot
        self.enemies.clear()  # in place: ItemManager holds this list
        self.enemies.extend(spawn_enemies(self.level))
        self.time_dilation.reset()
        self.rotation_cooldown = 0.0
        self.active_zones = set()
        self.gravity_expired = False

    def new_run(self, seed: int | None = None) -> None:
        """Start a fresh run. RunState is updated IN PLACE so item effects keep a live reference."""
        self.run_state.__dict__.update(RunState.new_run(seed).__dict__)
        self.item_manager.reset()
        self.item_manager.sync_owned([])

    @property
    def active_enemies(self) -> list:
        """Enemies that act this room (none during an anomaly room)."""
        return [] if self.anomaly_pending else self.enemies

    # --- Stepping ---

    def step(self, inp: InputFrame) -> StepEvents:
        """Advance the simulation by exactly one fixed physics step."""
        ev = StepEvents()
        phases.tick_timers(self)
        phases.update_zones(self, ev)
        phases.apply_input(self, inp, ev)
        phases.integrate(self, ev)
        phases.snap_back(self, ev)
        phases.hazards(self, ev)
        if ev.died is not None:
            self._on_death(ev)
        elif self.level.goal_rect.collidepoint(self.player.px, self.player.py):
            self.player.goal_reached = True
            ev.goal = True
        self.steps += 1
        return ev

    def rotate(self, new_dir: GravityDir) -> bool:
        """Rotate gravity if the rotated hitbox fits nearby; False (no change) if refused."""
        p = self.player
        result = try_rotate(p.px, p.py, p.vx, p.vy, new_dir,
                            self.level.collision_rects(), ROTATION_SAFE_SEARCH_PX)
        if result is None:
            return False
        self.bus.emit(GameEvent.GRAVITY_ROTATED, gravity_dir=p.gravity_dir)
        p.set_gravity(new_dir)
        p.px, p.py, p.vx, p.vy, p.on_ground = result.px, result.py, result.vx, result.vy, result.on_ground
        if p.on_ground:
            p.coyote_timer = COYOTE_TIME
            p.jumping = False
        for e in self.enemies:
            e.on_gravity_rotate()
        return True

    def _on_death(self, ev: StepEvents) -> None:
        """Integrity hit zero: charge fold stability, then respawn or end the run."""
        rs = self.run_state
        rs.last_death_cause = ev.died
        rs.deaths += 1
        rs.fold_stability = max(0.0, rs.fold_stability - FOLD_STABILITY_INTEGRITY_COST)
        if rs.fold_stability <= 0.0:
            ev.run_over = True
            rs.is_active = False
            self.time_dilation.reset()
            self.rotation_cooldown = 0.0
        else:
            self.respawn()

    # --- Snapshots (Closed Loop rewind, replays, tests) ---

    def snapshot(self) -> WorldSnapshot:
        """Capture all simulation state (valid until the next load_level)."""
        return capture(self)

    def restore(self, snap: WorldSnapshot) -> None:
        """Return to a snapshot taken in this same level load."""
        restore(self, snap)


def spawn_enemies(level: LevelRenderer) -> list:
    """Build enemy objects from the loaded level's EnemyDef list."""
    spawned = []
    for e in (level.level_data.enemies if level.level_data else []):
        spd = e.speed if e.speed > 0.0 else None
        kw = {"speed": spd} if spd is not None else {}
        if e.type == "temporal_echo":
            spawned.append(TemporalEcho(px=e.x, py=e.y, min_x=e.min_x, max_x=e.max_x,
                                        speed=spd if spd is not None else TEMPORAL_ECHO_SPEED))
        elif e.type == "fold_predator":
            spawned.append(FoldPredator(px=e.x, py=e.y, level_min=e.min_x, level_max=e.max_x, **kw))
        elif e.type == "anchored":
            spawned.append(TheAnchored(px=e.x, py=e.y, level_min=e.min_x, level_max=e.max_x, **kw))
        else:
            logger.warning("Unknown enemy type in level JSON: %r", e.type)
    return spawned
