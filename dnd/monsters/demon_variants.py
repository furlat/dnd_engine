"""Explicit demonic-blood variants composed over the existing Dretch body."""

from pydantic import BaseModel, ConfigDict

from dnd.body_responses import (
    CORROSIVE_BODY_RESPONSE, DREAD_BODY_RESPONSE, BodyResponseProfile, install_body_response,
)
from dnd.core.content.dependencies import ContentDependency, ContentDependencyPhase, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.entity import Entity
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS_BY_ID, construct_srd_creature


class DemonVariantParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _declare_variant(
    variant: str, name: str, description: str, profile: BodyResponseProfile,
) -> ContentDeclaration:
    def factory(raw_context: object, parameters: DemonVariantParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        entity = construct_srd_creature(context, "dretch")
        entity.description = description
        install_body_response(entity, profile)
        return entity

    factory.__name__ = f"build_{variant}"
    factory.__qualname__ = factory.__name__
    declared = creature_factory(
        pack_id="content.neurodragon", content_id=f"creature.{variant}", version=1,
        parameters=DemonVariantParameters,
        descriptor=ContentDescriptorSpec(
            display_name=name, description=description,
            tags=("creature", "demon", "fiend", "small", "body_material"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(visual_variant_key=variant, ui_group="creatures.neurodragon"),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor=f"Authored demonic residue variant: {name}",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
            adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Adds authored demonic blood to the existing Dretch mechanical composition.",
        ),
        dependencies=(ContentDependency(
            relation=ContentDependencyRelation.CONFIGURES_CREATURE,
            target_ref=SRD_CREATURE_DECLARATIONS_BY_ID["dretch"].ref,
            phase=ContentDependencyPhase.CONSTRUCTION,
        ),),
    )(factory)
    return get_content_declaration(declared)


CORROSIVE_DEMON_DECLARATION = _declare_variant(
    "corrosive_demon", "Corrosive Demon",
    "An authored small demon with Dretch defenses and attacks whose physical wounds leave corrosive blood. "
    "Its blood deals 1d4 acid damage when a creature enters the stained ground.",
    CORROSIVE_BODY_RESPONSE,
)
DREAD_DEMON_DECLARATION = _declare_variant(
    "dread_demon", "Dread Demon",
    "An authored small demon with Dretch defenses and attacks whose physical wounds leave dread blood. "
    "Entering its stain requires a Wisdom DC 10 save or a frightened retreat toward the previous cell.",
    DREAD_BODY_RESPONSE,
)
DEMON_VARIANT_DECLARATIONS = (CORROSIVE_DEMON_DECLARATION, DREAD_DEMON_DECLARATION)
CORROSIVE_DEMON_RECIPE = ContentRecipe.create(ref=CORROSIVE_DEMON_DECLARATION.ref, parameters={})
DREAD_DEMON_RECIPE = ContentRecipe.create(ref=DREAD_DEMON_DECLARATION.ref, parameters={})
