"""Ordinary art-led beasts: canonical content, independent of summoning."""

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
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import (
    ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.creature_types import CreatureType, Size
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.entity import Entity
from dnd.monsters.multiattack_definitions import (
    BODY_MULTIATTACK_CONFIGURATIONS_BY_ID, MultiattackConfigurationDefinition,
)
from dnd.monsters.srd_roster import HitDieValue, create_creature_entity
from dnd.monsters.traits import (
    HitSaveRiderFeature, KeenPerceptionFeature, MultiattackAction, PackTacticsFeature,
    register_multiattack, register_pack_tactics,
)


class BeastParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class BeastDefinition:
    """Cold ordinary stats and explicit parameters of existing native traits."""

    key: str
    name: str
    source: str
    abilities: tuple[int, int, int, int, int, int]
    size: Size
    hit_points: int
    hit_die: HitDieValue
    hit_dice: int
    speed: int
    primary: str
    secondary: str | None = None
    natural_armor: bool = False
    proficiency: int = 2
    perception: bool = False
    perception_expertise: bool = False
    stealth_expertise: bool = False
    keen_modes: tuple[str, ...] = ()
    knockdown_dc: int | None = None
    pack_tactics: bool = False
    darkvision: bool = False
    visual_scale: float | None = None
    source_id: str = "wotc.srd_5_1_cc"
    adaptation: str = "Ordinary listed attack only; no charge dice, movement tracker or bonus follow-up."


BEAST_DEFINITIONS = (
    BeastDefinition("hound", "Hound", "SRD 5.1 p.384 Mastiff", (13,14,12,3,12,7), Size.MEDIUM, 5,8,1,40,
        "hound_bite", perception=True, keen_modes=("hearing","smell"), knockdown_dc=11,
        adaptation="Shepherd Dog artwork over Mastiff's supported combat rules."),
    BeastDefinition("boar", "Boar", "SRD 5.1 pp.368–369 Boar", (13,11,12,2,9,5), Size.MEDIUM, 11,8,2,40,
        "boar_tusk", natural_armor=True, knockdown_dc=11,
        adaptation="Tusk hit DC11 Prone replaces Charge; no Relentless."),
    BeastDefinition("stag", "Stag", "SRD 5.1 p.372 Elk", (16,10,12,2,10,6), Size.LARGE, 13,10,2,50,
        "stag_ram", knockdown_dc=13, visual_scale=1.5),
    BeastDefinition("jaguar", "Jaguar", "SRD 5.1 p.385 Panther", (14,15,10,3,14,7), Size.MEDIUM, 13,8,3,50,
        "jaguar_claws", "jaguar_bite", perception=True, stealth_expertise=True,
        keen_modes=("smell",), knockdown_dc=12),
    BeastDefinition("bison", "Bison", "SRD 5.1 p.376 Giant Goat", (17,11,12,3,12,6), Size.LARGE, 19,10,3,40,
        "bison_ram", natural_armor=True, knockdown_dc=13,
        adaptation="Ram hit DC13 Prone replaces Charge; no Sure-Footed extension in this bounded batch.", visual_scale=1.65),
    BeastDefinition("ostrich", "Ostrich", "SRD 5.1 pp.366–367 Axe Beak", (14,12,12,2,10,5), Size.LARGE, 19,10,3,50,
        "ostrich_beak", adaptation="Ostrich artwork over Axe Beak's ground movement and Beak.", visual_scale=1.5),
    BeastDefinition("brown_bear", "Brown Bear", "SRD 5.1 p.369 Brown Bear", (19,10,16,2,13,7), Size.LARGE, 34,10,4,40,
        "brown_bear_claws", "brown_bear_bite", natural_armor=True, perception=True, keen_modes=("smell",),
        adaptation="Bite then Claws Multiattack; printed +5 attack retained with explicit -1 item accuracy; climbing deferred.", visual_scale=1.7),
    BeastDefinition("lion", "Lion", "SRD 5.1 p.383 Lion", (17,15,13,3,12,8), Size.LARGE, 26,10,4,50,
        "lion_claws", "lion_bite", perception=True, stealth_expertise=True, keen_modes=("smell",),
        knockdown_dc=13, pack_tactics=True,
        adaptation="Claw hit DC13 Prone replaces Pounce; no bonus Bite or Running Leap extension.", visual_scale=1.5),
    BeastDefinition("tiger", "Tiger", "SRD 5.1 pp.391–392 Tiger", (17,15,14,3,12,8), Size.LARGE, 37,10,5,40,
        "tiger_claws", "tiger_bite", perception=True, stealth_expertise=True,
        keen_modes=("smell",), knockdown_dc=13, darkvision=True, visual_scale=1.55),
    BeastDefinition("polar_bear", "Polar Bear", "SRD 5.1 p.386 Polar Bear", (20,10,16,2,13,7), Size.LARGE, 42,10,5,40,
        "polar_bear_claws", "polar_bear_bite", natural_armor=True, perception=True, keen_modes=("smell",),
        adaptation="Bite then Claws Multiattack; swimming deferred, no invented cold resistance.", visual_scale=1.8),
    BeastDefinition("rhinoceros", "Rhinoceros", "SRD 5.1 p.388 Rhinoceros", (21,8,15,2,12,6), Size.LARGE, 45,10,6,40,
        "rhinoceros_gore", natural_armor=True, knockdown_dc=15, visual_scale=1.85),
    BeastDefinition("blue_raptor", "Blue Raptor", "SRD 5.2 p.341 Allosaurus", (19,13,17,2,12,5), Size.LARGE, 51,10,6,60,
        "blue_raptor_claws", "blue_raptor_bite", natural_armor=True, perception=True, perception_expertise=True,
        knockdown_dc=14, source_id="wotc.srd_5_2_cc",
        adaptation="5.2 numerical baseline; ordinary Claw hit DC14 STR Prone under 5.1 semantics, no run-up or bonus Bite.", visual_scale=1.8),
    BeastDefinition("stegosaurus", "Stegosaurus", "SRD 5.2 p.341 Ankylosaurus", (19,11,15,2,12,5), Size.HUGE, 68,12,8,30,
        "stegosaurus_tail", natural_armor=True, source_id="wotc.srd_5_2_cc",
        adaptation="Two reach10 1d10+4 piercing Tail attacks; no automatic 5.2 prone rider.", visual_scale=2.35),
    BeastDefinition("elephant", "Elephant", "SRD 5.1 pp.371–372 Elephant", (22,9,17,3,11,6), Size.HUGE, 76,12,8,40,
        "elephant_trunk", natural_armor=True, proficiency=2, knockdown_dc=12,
        adaptation="Gore's 3d8+6 becomes depicted bludgeoning Trunk Sweep with DC12 Prone; no Stomp/Charge chain.", visual_scale=2.4),
    BeastDefinition("triceratops", "Triceratops", "SRD 5.1 p.279 Triceratops", (22,9,17,2,11,5), Size.HUGE, 95,12,10,50,
        "triceratops_gore", natural_armor=True, proficiency=3, knockdown_dc=13, visual_scale=2.4),
    BeastDefinition("mammoth", "Mammoth", "SRD 5.1 p.384 Mammoth", (24,9,21,3,11,6), Size.HUGE, 126,12,11,40,
        "mammoth_gore", natural_armor=True, proficiency=3, knockdown_dc=18, visual_scale=2.6),
    BeastDefinition("raptor", "Raptor", "SRD 5.2 p.341 Allosaurus", (19,13,17,2,12,5), Size.LARGE, 51,10,6,60,
        "raptor_bite", "raptor_tail", natural_armor=True, perception=True, perception_expertise=True,
        source_id="wotc.srd_5_2_cc", visual_scale=1.55,
        adaptation="Human-selected raptor artwork assignment; Allosaurus numerical baseline, Bite OR depicted 1d8 bludgeoning Tail at reach5; no grapple or bonus follow-up."),
)


def _declare_beast(definition: BeastDefinition) -> ContentDeclaration:
    multiattack = BODY_MULTIATTACK_CONFIGURATIONS_BY_ID.get(definition.key)
    grants = tuple(CreaturePossessionGrant(
        item_id=f"weapon.creature.{key}", disposition=CreaturePossessionDisposition.INTRINSIC,
        equipment_slot=slot,
    ) for key, slot in ((definition.primary, WeaponSlot.MELEE_MAIN),
        (definition.secondary, WeaponSlot.MELEE_OFF)) if key is not None)
    if definition.natural_armor:
        grants = (*grants, CreaturePossessionGrant(
            item_id=f"armor.creature.{definition.key}_natural",
            disposition=CreaturePossessionDisposition.INTRINSIC, equipment_slot=BodyPart.BODY,
        ))

    def factory(raw_context: object, parameters: BeastParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        entity = create_creature_entity(
            context=context, description=f"{definition.name}. {definition.adaptation}",
            abilities=definition.abilities, hit_die_value=definition.hit_die, hit_die_count=definition.hit_dice,
            hit_points=definition.hit_points, proficiency_bonus=definition.proficiency,
            creature_type=CreatureType.BEAST, size=definition.size, movement=definition.speed,
            darkvision=definition.darkvision, skills={"perception": definition.perception},
        )
        install_body_response(entity, BLOOD_BODY_RESPONSE)
        if definition.visual_scale is not None:
            entity.appearance.visual_scale = definition.visual_scale
        if definition.perception_expertise:
            entity.skill_set.perception.set_expertise(True)
        if definition.stealth_expertise:
            entity.skill_set.stealth.set_expertise(True)
        apply_creature_possessions(entity, grants, possession_mode=context.possession_mode)
        if definition.keen_modes:
            entity.add_condition(KeenPerceptionFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
                modes=definition.keen_modes))
        if definition.pack_tactics:
            register_pack_tactics(entity)
        if definition.knockdown_dc is not None:
            entity.add_condition(HitSaveRiderFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid,
                weapon_item_ids=(f"weapon.creature.{definition.primary}",),
                save_dc=definition.knockdown_dc, condition_name="Prone"))
        if multiattack is not None:
            config = MultiattackConfigurationDefinition.model_validate(multiattack.definition_payload)
            register_multiattack(entity, multiattack.descriptor.display_name,
                tuple((step.weapon_slot, step.count) for step in config.steps), configured_action_ref=multiattack.ref)
        return entity

    factory.__name__ = f"build_{definition.key}"
    factory.__qualname__ = factory.__name__
    dependencies = tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
        for row in CORE_STANDARD_ACTION_DECLARATIONS)
    feature_types = tuple(feature for enabled, feature in (
        (bool(definition.keen_modes), KeenPerceptionFeature),
        (definition.pack_tactics, PackTacticsFeature),
        (definition.knockdown_dc is not None, HitSaveRiderFeature),
    ) if enabled)
    dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
        target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[feature].ref) for feature in feature_types)
    if multiattack is not None:
        dependencies += tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
            for row in (ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[MultiattackAction], multiattack))
    declared = creature_factory(
        pack_id="content.neurodragon", content_id=f"creature.{definition.key}", version=1,
        parameters=BeastParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description=definition.adaptation, tags=("creature", "beast", "adapted"),
            visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(visual_variant_key=definition.key, ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor=definition.source, relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,
            adapted_from_source_id=definition.source_id, fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED, notes=definition.adaptation),
        dependencies=dependencies,
    )(factory)
    return get_content_declaration(declared)


BEAST_DECLARATIONS = tuple(_declare_beast(row) for row in BEAST_DEFINITIONS)
BEAST_RECIPES_BY_ID = MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref, parameters={}) for row in BEAST_DECLARATIONS})
