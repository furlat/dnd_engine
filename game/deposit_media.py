"""Observed material pieces and their witnessed discharge dates.

Existing native owners carry material geometry and membership. This module
retains only presentation dates; it never reconstructs a pool from live state.
"""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from dnd.types.material_deposits import MaterialDepositSource
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline
from game.environment_art import load_environment_art
from game.player_facts import ObjectDestroyedFact, PlayerLineage, PlayerState


@dataclass(frozen=True, slots=True)
class ObservedMaterialDeposit:
    source: MaterialDepositSource
    material_id: str
    positions: frozenset[tuple[int, int]]


def observed_deposits(state: PlayerState, data: AnimationData) -> tuple[ObservedMaterialDeposit, ...]:
    """Group only retained fragments; missing cells never enlarge coverage."""
    pieces: dict[tuple[MaterialDepositSource, str], set[tuple[int, int]]] = {}
    for position, tile in state.tiles.items():
        for residue in tile.residues:
            binding = data.deposit_media.get(residue.residue_id)
            if binding is None:
                continue
            for contribution in residue.contributions:
                source = contribution.deposit_source
                if source is not None and source.radius_cells == binding.radiusCells:
                    pieces.setdefault((source, residue.residue_id), set()).add(position)
    if state.senses is not None:
        for effect in state.senses.spatial_effects.values():
            binding = data.deposit_media.get(effect.content_ref.content_id)
            source = effect.deposit_source
            if binding is not None and source is not None and source.radius_cells == binding.radiusCells:
                pieces.setdefault((source, effect.content_ref.content_id), set()).update(effect.positions)
    return tuple(ObservedMaterialDeposit(source, material, frozenset(positions))
                 for (source, material), positions in pieces.items() if positions)


def register_deposit_starts(
    retained: Mapping[UUID, float], before: PlayerState, data: AnimationData, *,
    absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, float]:
    """Only a witnessed native break starts an intro; cold material sustains."""
    owners = {row.source.deposit_uuid for row in observed_deposits(before, data)}
    result = {identity: start for identity, start in retained.items() if identity in owners}
    witnessed = {node.fact.object_uuid: node.lineage_uuid
        for node in lineage.events if not node.canceled and isinstance(node.fact, ObjectDestroyedFact)
    } if lineage is not None else {}
    # Bound timelines already flatten nested reactions at their actual offsets.
    transitions = (motion.world_transitions if motion is not None else
                   choreography.world_transitions if choreography is not None else ())
    environment = load_environment_art()
    for transition in transitions:
        identity = witnessed.get(transition.identity)
        contact = transition.destruction
        if identity is None or contact is None or contact.bank_id is None:
            continue
        bank = environment.banks[contact.bank_id]
        if bank.release_frame is not None:
            result.setdefault(identity, absolute_start_ms + transition.start_ms + bank.frame_times_ms[bank.release_frame])
    return result
