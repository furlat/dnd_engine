"""Three ordinary authored devils; no summoning-specific creature factories."""

from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.creature_possessions import (
    CreaturePossessionDisposition, CreaturePossessionGrant, apply_creature_possessions,
)
from dnd.core.base_block import SenseMode, SensesType
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.entity import Entity
from dnd.monsters.multiattack_definitions import BODY_MULTIATTACK_CONFIGURATIONS_BY_ID, MultiattackConfigurationDefinition
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import InnateFlight, MagicResistance, MultiattackAction, register_multiattack


class FiendParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class FiendDefinition:
    key: str
    name: str
    source_id: str
    abilities: tuple[int, int, int, int, int, int]
    size: Size
    hit_points: int
    hit_die: HitDieValue
    hit_dice: int
    speed: int
    proficiency: int
    natural_armor: bool = False
    gore: bool = False
    flying_speed: int | None = None
    devils_sight: bool = False
    magic_resistance: bool = False


FIEND_DEFINITIONS = (
    FiendDefinition("claw_mote_devil", "Claw Mote Devil", "C27", (12,12,10,6,10,6),
        Size.SMALL, 7,6,2,25,2),
    FiendDefinition("huntsman_wing_devil", "Huntsman Wing Devil", "C05", (18,16,18,12,14,12),
        Size.MEDIUM, 93,8,11,30,2, natural_armor=True, flying_speed=40, devils_sight=True),
    FiendDefinition("fellwing_devil", "Fellwing Devil", "C04", (20,14,20,12,14,14),
        Size.LARGE, 136,10,13,30,3, natural_armor=True, gore=True, flying_speed=50, magic_resistance=True),
)


def _declare_fiend(definition: FiendDefinition) -> ContentDeclaration:
    multiattack = BODY_MULTIATTACK_CONFIGURATIONS_BY_ID.get(definition.key)
    grants = [CreaturePossessionGrant(item_id=f"weapon.creature.{definition.key}_claws",
        disposition=CreaturePossessionDisposition.INTRINSIC, equipment_slot=WeaponSlot.MELEE_MAIN)]
    if definition.gore:
        grants.append(CreaturePossessionGrant(item_id=f"weapon.creature.{definition.key}_gore",
            disposition=CreaturePossessionDisposition.INTRINSIC, equipment_slot=WeaponSlot.MELEE_OFF))
    if definition.natural_armor:
        grants.append(CreaturePossessionGrant(item_id=f"armor.creature.{definition.key}_natural",
            disposition=CreaturePossessionDisposition.INTRINSIC, equipment_slot=BodyPart.BODY))
    possessions = tuple(grants)

    def factory(raw_context: object, parameters: FiendParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        entity = create_creature_entity(context=context,
            description=f"{definition.name}; authored Devil {definition.source_id}.",
            abilities=definition.abilities, hit_die_value=definition.hit_die, hit_die_count=definition.hit_dice,
            hit_points=definition.hit_points, proficiency_bonus=definition.proficiency,
            creature_type=CreatureType.FIEND, size=definition.size, movement=definition.speed,
            immunities=(DamageType.FIRE, DamageType.POISON),
        )
        # Preserve original sprite proportions independently of rules-level Size.
        entity.appearance.visual_scale = 1.0
        install_body_response(entity, BLOOD_BODY_RESPONSE)
        entity.add_condition_immunity("Poisoned", immunity_name=definition.name)
        entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DARKVISION,
            range_feet=120 if definition.devils_sight else 60))
        if definition.devils_sight:
            entity.senses.sense_modes.append(SenseMode(sense_type=SensesType.DEVILS_SIGHT, range_feet=120))
        apply_creature_possessions(entity, possessions, possession_mode=context.possession_mode)
        if definition.flying_speed is not None:
            entity.add_condition(InnateFlight(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
                flying_speed=definition.flying_speed))
        if definition.magic_resistance:
            entity.add_condition(MagicResistance(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))
        if multiattack is not None:
            config = MultiattackConfigurationDefinition.model_validate(multiattack.definition_payload)
            register_multiattack(entity, multiattack.descriptor.display_name,
                tuple((step.weapon_slot, step.count) for step in config.steps), configured_action_ref=multiattack.ref)
        return entity

    factory.__name__ = f"build_{definition.key}"
    factory.__qualname__ = factory.__name__
    dependencies = tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
        for row in CORE_STANDARD_ACTION_DECLARATIONS)
    dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
        target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref)
        for enabled, feature in ((definition.flying_speed is not None, InnateFlight),
            (definition.magic_resistance, MagicResistance)) if enabled)
    if multiattack is not None:
        dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
            for row in (ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[MultiattackAction], multiattack))
    declared = creature_factory(pack_id="content.neurodragon", content_id=f"creature.{definition.key}", version=1,
        parameters=FiendParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description=f"Authored Devil {definition.source_id}; intrinsic attacks and explicit passive traits.",
            tags=("creature", "fiend", "devil"), visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(portrait_key=f"creature.{definition.key}", visual_variant_key=definition.key, ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor=f"Authored Devils study 2026-10-01, {definition.source_id}",
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT, fidelity=ContentFidelity.COMPLETE,
            review_status=ContentReviewStatus.REVIEWED,
            notes="Explicit authored stats; ground-to-ground flight, no hovering, holding, spells or Flyby."),
        dependencies=dependencies,
    )(factory)
    return get_content_declaration(declared)


FIEND_DECLARATIONS = tuple(_declare_fiend(row) for row in FIEND_DEFINITIONS)
FIEND_RECIPES_BY_ID = MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref, parameters={}) for row in FIEND_DECLARATIONS})
