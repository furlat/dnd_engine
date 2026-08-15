"""SRD 5.1 Halfling origin runtime mechanics."""

from __future__ import annotations

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
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events.resolution_events import (
    D20RollResultEvent,
)
from dnd.core.events.events_registry import (
    Event,
)
from dnd.types.rolls import AdvantageStatus


def _selected_natural_d20(roll: DiceRoll) -> int:
    results = roll.results if isinstance(roll.results, list) else [roll.results]
    if roll.advantage_status is AdvantageStatus.ADVANTAGE:
        return max(results)
    if roll.advantage_status is AdvantageStatus.DISADVANTAGE:
        return min(results)
    return results[0]


@behavior_identity(
    definition_kind=ContentDefinitionKind.TRAIT,
    runtime_behavior_kind=RuntimeBehaviorKind.TRAIT,
    pack_id="content.srd_5_1_cc",
    content_id="trait.origin.halfling.lucky",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Lucky",
        description=(
            "When you roll a 1 on an attack roll, ability check, or saving "
            "throw, reroll the die and use the new roll."
        ),
        tags=(
            "character_creation",
            "origin_feature",
            "srd_5_1",
            "trait",
        ),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="trait.halfling-lucky",
            visual_variant_key="halfling_lucky",
            ui_group="origin_features.active",
        ),
        ordering=ContentOrdering(
            sort_group="origin_features.active",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor="SRD 5.1 Races: Halfling Traits — Lucky",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "The automatic processor triggers only on the selected natural "
            "d20 result and must use its replacement, including another 1."
        ),
    ),
)
def halfling_lucky_processor(
    event: Event,
    source_entity_uuid: UUID,
) -> Optional[Event]:
    """Reroll one selected natural d20 result of 1 and use the replacement."""
    if (
        not isinstance(event, D20RollResultEvent)
        or event.source_entity_uuid != source_entity_uuid
        or _selected_natural_d20(event.get_effective_roll()) != 1
    ):
        return None
    if event.bonus is None:
        raise RuntimeError("Halfling Lucky requires the exact d20 bonus")
    replacement = Dice(
        count=1,
        value=20,
        bonus=event.bonus,
        roll_type=event.roll_type,
    ).roll
    return event.replace_roll(
        replacement,
        "Halfling Lucky",
        "Rerolled a natural 1 and used the replacement",
    )


HALFLING_LUCKY_DECLARATION = get_content_declaration(
    halfling_lucky_processor,
)
HALFLING_LUCKY_REF = HALFLING_LUCKY_DECLARATION.ref


__all__ = [
    "HALFLING_LUCKY_DECLARATION",
    "HALFLING_LUCKY_REF",
    "halfling_lucky_processor",
]
