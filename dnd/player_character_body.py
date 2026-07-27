"""Class-neutral authored body used by schema-2 persistent characters."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.creature_proficiencies import CreatureProficienciesConfig
from dnd.blocks.health import HealthConfig
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    creature_factory,
    get_content_declaration,
)
from dnd.entity import Entity, EntityConfig


class PlayerCharacterBodyParameters(BaseModel):
    """The body owns no class, origin, ability, or possession selections."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_STANDARD_ACTION_DEPENDENCIES = tuple(
    ContentDependency(
        relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=declaration.ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        notes="Class-neutral player bodies own the standard action surface.",
    )
    for declaration in sorted(
        CORE_STANDARD_ACTION_DECLARATIONS,
        key=lambda row: row.ref.identity_key,
    )
)


@creature_factory(
    pack_id="content.neurodragon",
    content_id="creature.player.humanoid_body",
    version=1,
    parameters=PlayerCharacterBodyParameters,
    descriptor=ContentDescriptorSpec(
        display_name="Humanoid Player Body",
        description=(
            "Class-neutral persistent-character body. Species, background, "
            "abilities, class levels, features, and possessions are applied "
            "from authenticated character revisions."
        ),
        tags=("character_body", "creature", "humanoid", "player_capable"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            visual_variant_key="humanoid_player_body",
            ui_group="creatures.player_bodies",
        ),
        ordering=ContentOrdering(
            sort_group="creatures.player_bodies",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon persistent-character composition: class-neutral "
            "humanoid player body"
        ),
        relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
        adapted_from_source_id="wotc.srd_5_1_cc",
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "The body is deliberately rules-empty; authenticated species and "
            "progression definitions supply every structural grant."
        ),
    ),
    dependencies=_STANDARD_ACTION_DEPENDENCIES,
)
def _build_player_character_body(
    raw_context: object,
    parameters: PlayerCharacterBodyParameters,
) -> Entity:
    """Construct one reversible, class-neutral player entity."""
    _ = parameters
    context = CreatureBuildContext.model_validate(raw_context)
    zero = AbilityConfig(ability_score=0)
    entity = Entity.create(
        source_entity_uuid=context.runtime_entity_uuid,
        name=context.display_name,
        description="Class-neutral persistent player character",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=zero,
                dexterity=zero,
                constitution=zero,
                intelligence=zero,
                wisdom=zero,
                charisma=zero,
            ),
            health=HealthConfig(hit_dices=[]),
            creature_proficiencies=CreatureProficienciesConfig(
                base_simple_weapons=False,
                base_martial_weapons=False,
                base_weapon_refs=(),
                base_armor_types=(),
                base_shields=False,
            ),
            proficiency_bonus=0,
            position=context.position,
            faction=context.faction,
            uses_death_saves=False,
        ),
        content_ref=context.requested_ref,
    )
    setup_standard_actions(entity)
    return entity


PLAYER_CHARACTER_BODY_DECLARATION: ContentDeclaration = (
    get_content_declaration(_build_player_character_body)
)
PLAYER_CHARACTER_BODY_RECIPE = (
    ContentRecipe.create(
        ref=PLAYER_CHARACTER_BODY_DECLARATION.ref,
        parameters={},
    )
)


__all__ = [
    "PLAYER_CHARACTER_BODY_DECLARATION",
    "PLAYER_CHARACTER_BODY_RECIPE",
    "PlayerCharacterBodyParameters",
]
