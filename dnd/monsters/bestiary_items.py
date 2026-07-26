"""Canonical creature-owned possessions used by the active bestiary."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dnd.blocks.equipment import BodyArmor
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    get_content_declaration,
)
from dnd.core.equipment_types import ArmorType, BodyPart
from dnd.core.values import ModifiableValue
from dnd.items.authored_presentations import (
    authored_item_factory as item_factory,
)


class ArmorScrapsParameters(BaseModel):
    """Armor scraps have one exact authored construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


@item_factory(
    pack_id="content.neurodragon",
    content_id="armor.armor_scraps",
    version=1,
    parameters=ArmorScrapsParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Armor Scraps",
        description="Rusted pieces of armor barely held together on bone.",
        tags=("armor", "bestiary", "creature_possession", "neurodragon"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="armor.armor_scraps",
            visual_variant_key="armor_scraps",
            ui_group="armor.creature_possessions",
        ),
        ordering=ContentOrdering(
            sort_group="armor.creature_possessions",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: bestiary Armor Scraps"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Exact existing AC 13, zero-Dex-bonus skeleton equipment.",
    ),
    item_definition=ItemDefinition(
        persistence_policy=ItemPersistencePolicy.POSSESSION,
    ),
)
def _build_armor_scraps(
    raw_context: object,
    parameters: ArmorScrapsParameters,
) -> BodyArmor:
    """Construct the exact legacy skeleton armor possession."""
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return BodyArmor(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        name="Armor Scraps",
        description="Rusted pieces of armor barely held together on bone.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=13,
            value_name="Armor Class",
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=context.source_entity_uuid,
            base_value=0,
            value_name="Max Dex Bonus",
        ),
    )


ARMOR_SCRAPS_DECLARATION = get_content_declaration(_build_armor_scraps)
ARMOR_SCRAPS_RECIPE = ContentRecipe.create(
    ref=ARMOR_SCRAPS_DECLARATION.ref,
    parameters={},
)
NEURODRAGON_BESTIARY_ITEM_DECLARATIONS = (ARMOR_SCRAPS_DECLARATION,)
