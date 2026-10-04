"""Creation cues require a witnessed construction owner, not mere acquisition."""

from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.core.events import SpatialChangeType
from game.animation_types import AnimationData
from game.construction_media import construction_duration, construction_media_limitation
from game.player_facts import PlayerLineage, PlayerState, SpatialEffectStateFact, SpatialFact
from game.world_animation import WorldTransition


def construction_creation_transitions(before: PlayerState, states: list[tuple[float, PlayerState]],
        lineage: PlayerLineage, data: AnimationData) -> tuple[WorldTransition, ...]:
    created = {node.fact.spatial_effect_uuid for node in lineage.events if not node.canceled
        and isinstance(node.fact, SpatialEffectStateFact)
        and node.fact.operation is SpatialEffectChangeOperation.CREATED}
    sections = {node.fact.object_uuid for node in lineage.events if not node.canceled
        and isinstance(node.fact, SpatialFact) and node.fact.object_uuid is not None
        and node.fact.change_type is SpatialChangeType.OBJECT_PLACED}
    known = set(before.objects)
    result = []
    for at, state in states:
        owners = created & state.senses.spatial_effects.keys() if state.senses is not None else set()
        for identity, obj in state.objects.items():
            binding = data.construction_media.get(obj.item.item_id)
            if (identity in known or binding is None or construction_media_limitation(obj, binding) is not None
                    or identity not in sections and obj.item.construction_owner_uuid not in owners):
                continue
            result.append(WorldTransition(identity, 'creation', None, None, at,
                duration_ms=construction_duration(data, binding, 'application')))
            known.add(identity)
    return tuple(result)
