"""Reward offer generation — Module 5a Session 3.

generate_offers() produces a deterministic list of Offer objects for
a given run + node, suitable for display on the reward screen.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from constants import (
    ARTIFACT_COST_HAWKING_EMITTER,
    ARTIFACT_COST_KERR_RING,
    ARTIFACT_COST_PENROSE_DIAGRAM,
    MODIFIER_CAP,
    PARADOX_OFFER_CHANCE,
)
from src.data.items import ItemDef, OwnedItem
from src.systems.items.registry import ItemRegistry

_ARTIFACT_COSTS: dict[str, float] = {
    "kerr_ring": ARTIFACT_COST_KERR_RING,
    "hawking_emitter": ARTIFACT_COST_HAWKING_EMITTER,
    "penrose_diagram": ARTIFACT_COST_PENROSE_DIAGRAM,
}
_DOMAIN_WEIGHT_BOOST: int = 3  # weight multiplier for domains the player already owns
_BASE_OFFER_COUNT: int = 3


@dataclass
class Offer:
    """One option on the reward screen."""

    item_def: ItemDef
    is_rank_up: bool        # True when player already owns this modifier at a lower rank
    current_rank: int       # rank the player owns (0 if not owned), target rank = current + 1
    is_paradox: bool        # True when this is a fold_stability-cost artifact offer
    paradox_cost: float     # fold_stability cost; 0 if not a paradox offer

    @property
    def target_rank(self) -> int:
        """Rank this offer would bring the item to."""
        return self.current_rank + 1 if self.is_rank_up else 1

    def takeable(self, fold_stability: float) -> bool:
        """Return True if the player can take this offer."""
        if self.is_paradox:
            return fold_stability - self.paradox_cost > 0
        return True


def generate_offers(
    registry: ItemRegistry,
    owned_items: list[OwnedItem],
    run_seed: int,
    node_idx: int,
    extra_options: int = 0,
) -> list[Offer]:
    """Return a deterministic list of offers for this run + node.

    Seeded from run_seed XOR node_idx so the same run always produces
    the same offers at the same node.
    """
    seed = (run_seed ^ (node_idx * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)

    base_count = _BASE_OFFER_COUNT + extra_options
    owned_map: dict[str, OwnedItem] = {o.id: o for o in owned_items}
    owned_domains: set[str] = {
        registry.get_item(o.id).domain
        for o in owned_items
        if registry.get_item(o.id) is not None and registry.get_item(o.id).domain != "none"
    }

    # Build weighted candidate pool (modifiers only; artifacts go via paradox)
    candidates: list[tuple[int, ItemDef, bool, int]] = []  # (weight, defn, is_rank_up, cur_rank)
    for defn in registry.modifiers():
        cur_rank = owned_map[defn.id].rank if defn.id in owned_map else 0
        max_rank = len(defn.params_by_rank)
        if cur_rank >= max_rank:
            continue  # already maxed
        is_rank_up = defn.id in owned_map
        weight = 1
        if defn.domain in owned_domains:
            weight *= _DOMAIN_WEIGHT_BOOST
        if is_rank_up:
            weight *= 2  # rank-ups slightly preferred over new items
        candidates.append((weight, defn, is_rank_up, cur_rank))

    offers: list[Offer] = []
    used_ids: set[str] = set()

    # Fill base_count slots from weighted pool
    total_slots = min(base_count, len(candidates))
    for _ in range(total_slots):
        remaining = [(w, d, r, c) for w, d, r, c in candidates if d.id not in used_ids]
        if not remaining:
            break
        weights = [w for w, _, _, _ in remaining]
        chosen = rng.choices(remaining, weights=weights, k=1)[0]
        _, defn, is_rank_up, cur_rank = chosen
        offers.append(Offer(
            item_def=defn,
            is_rank_up=is_rank_up,
            current_rank=cur_rank,
            is_paradox=False,
            paradox_cost=0.0,
        ))
        used_ids.add(defn.id)

    # Paradox offer: one artifact, fold_stability cost, appears at configured probability
    if rng.random() < PARADOX_OFFER_CHANCE:
        artifact_candidates = [
            d for d in registry.artifacts() if d.id not in owned_map
        ]
        if artifact_candidates:
            chosen_artifact = rng.choice(artifact_candidates)
            cost = _ARTIFACT_COSTS.get(chosen_artifact.id, 20.0)
            offers.append(Offer(
                item_def=chosen_artifact,
                is_rank_up=False,
                current_rank=0,
                is_paradox=True,
                paradox_cost=cost,
            ))

    return offers
