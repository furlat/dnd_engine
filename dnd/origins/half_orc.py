"""SRD 5.1 Half-Orc active origin mechanics."""

from typing import Optional
from uuid import UUID

from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.events import Event, TakeDamageEvent
from dnd.core.life_types import LifeState
from dnd.entity import Entity


HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE = (
    "half_orc_relentless_endurance"
)


@behavior_identity(
    definition_kind=ContentDefinitionKind.TRAIT,
    runtime_behavior_kind=RuntimeBehaviorKind.TRAIT,
    pack_id="content.srd_5_1_cc",
    content_id="trait.origin.half_orc.relentless_endurance",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Relentless Endurance",
        description=(
            "Once per long rest, drop to 1 hit point instead of 0 unless "
            "the damage would kill you outright."
        ),
        tags=(
            "character_creation",
            "origin_feature",
            "srd_5_1",
            "trait",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="trait.half-orc-relentless-endurance",
            visual_variant_key="half_orc_relentless_endurance",
            ui_group="origin_features.active",
        ),
        ordering=ContentOrdering(
            sort_group="origin_features.active",
            sort_order=20,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 Races: Half-Orc Traits — Relentless Endurance"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "The handler caps one qualifying damage packet at 1 normal hit "
            "point and consumes a source-owned long-rest resource."
        ),
    ),
)
def half_orc_relentless_endurance_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Cap one qualifying lethal damage packet at 1 normal hit point."""
    if (
        not isinstance(event, TakeDamageEvent)
        or event.target_entity_uuid != source_entity_uuid
    ):
        return None
    entity = Entity.get(source_entity_uuid)
    if (
        not isinstance(entity, Entity)
        or entity.health.life_state is LifeState.DEAD
        or entity.get_normal_hp() <= 0
    ):
        return None
    preview = entity.preview_take_damage(event)
    current_hp = entity.get_normal_hp()
    if current_hp - preview.normal_hit_point_damage > 0:
        return None
    if preview.overkill_damage >= entity.get_max_hp():
        return None
    if entity.action_economy.get_resource_current(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
    ) <= 0:
        return None
    if not entity.action_economy.consume_resource(
        HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE,
        1,
    ):
        return None
    damage_cap = max(0, current_hp - 1)
    if event.normal_hit_point_damage_cap is not None:
        damage_cap = min(
            damage_cap,
            event.normal_hit_point_damage_cap,
        )
    return event.with_updates(
        normal_hit_point_damage_cap=damage_cap,
        status_message=(
            "Relentless Endurance keeps the target at 1 hit point"
        ),
    )


HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION = get_content_declaration(
    half_orc_relentless_endurance_processor,
)
HALF_ORC_RELENTLESS_ENDURANCE_REF = (
    HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION.ref
)


__all__ = [
    "HALF_ORC_RELENTLESS_ENDURANCE_DECLARATION",
    "HALF_ORC_RELENTLESS_ENDURANCE_REF",
    "HALF_ORC_RELENTLESS_ENDURANCE_RESOURCE",
    "half_orc_relentless_endurance_processor",
]
