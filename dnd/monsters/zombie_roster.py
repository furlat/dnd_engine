"""Fantasy zombie source variants composed as ordinary Zombie/Ogre Zombie kits."""

from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict

from dnd.actions import CORE_STANDARD_ACTION_DECLARATIONS
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content_system.action_definitions import ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.condition_definitions import CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS
from dnd.content_system.creature_possessions import CreaturePossessionDisposition, CreaturePossessionGrant, apply_creature_possessions
from dnd.core.content.dependencies import ContentDependency, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration, creature_factory, get_content_declaration
from dnd.core.creature_types import CreatureType, DamageType, Size
from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity
from dnd.monsters.srd_roster import create_creature_entity
from dnd.monsters.traits import NaturalAttack, UndeadFortitudeFeature, register_undead_fortitude


class ZombieRosterParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class ZombieDefinition:
    key: str
    name: str
    pack: str
    source_variant: str
    heavy: bool = False
    speed: int = 20
    athletics: bool = False
    weapons: tuple[tuple[str, WeaponSlot], ...] = ()


ZOMBIE_DEFINITIONS = (
    ZombieDefinition('zombie_hd_female_1', 'Marigold', 'hdz', 'ZombieFemale1'),
    ZombieDefinition('zombie_hd_female_2', 'Ash-Blue June', 'hdz', 'ZombieFemale2'),
    ZombieDefinition('zombie_hd_female_3', 'Copper Jane', 'hdz', 'ZombieFemale3'),
    ZombieDefinition('zombie_hd_female_4', 'Fen Green', 'hdz', 'ZombieFemale4'),
    ZombieDefinition('zombie_hd_female_5', 'Roseglass', 'hdz', 'ZombieFemale5' , athletics=True),
    ZombieDefinition('zombie_hd_female_6', 'Night Shift', 'hdz', 'ZombieFemale6'),
    ZombieDefinition('zombie_hd_female_7', 'Deep Teal', 'hdz', 'ZombieFemale7'),
    ZombieDefinition('zombie_hd_hulk_1', 'Greenbulge', 'hdz', 'ZombieHulk1' , heavy=True),
    ZombieDefinition('zombie_hd_hulk_2', 'White Knuckle', 'hdz', 'ZombieHulk2' , heavy=True),
    ZombieDefinition('zombie_hd_male_1', 'Olive Trousers', 'hdz', 'ZombieMale1'),
    ZombieDefinition('zombie_hd_male_2', 'The White Shirt', 'hdz', 'ZombieMale2'),
    ZombieDefinition('zombie_hd_male_3', 'Blue Sleeve', 'hdz', 'ZombieMale3'),
    ZombieDefinition('zombie_hd_male_6', 'Nightcoat', 'hdz', 'ZombieMale6'),
    ZombieDefinition('zombie_hd_male_7', 'Green Vest', 'hdz', 'ZombieMale7'),
    ZombieDefinition('zombie_hd_male_8', 'Red Thread', 'hdz', 'ZombieMale8'),
    ZombieDefinition('zombie_hd_male_9', 'Rust Collar', 'hdz', 'ZombieMale9' , athletics=True),
    ZombieDefinition('zombie_hd_monster_1', 'The Narrow One', 'hdz', 'ZombieMonster1'),
    ZombieDefinition('zombie_hd_monster_2', 'Red Suture', 'hdz', 'ZombieMonster2'),
    ZombieDefinition('zombie_hd_monster_3', 'Heavy Pale', 'hdz', 'ZombieMonster3' , heavy=True),
    ZombieDefinition('zombie_hd_radioactive_1', 'Fallow One', 'hdz', 'ZombieRadioactive1'),
    ZombieDefinition('zombie_hd_radioactive_2', 'Fallow Two', 'hdz', 'ZombieRadioactive2'),
    ZombieDefinition('zombie_hd_radioactive_3', 'Fallow Three', 'hdz', 'ZombieRadioactive3'),
    ZombieDefinition('zombie_top_01', 'Corner Walker', 'top', 'Zombie 01'),
    ZombieDefinition('zombie_top_02', 'Viridian Scour', 'top', 'Zombie 02'),
    ZombieDefinition('zombie_top_03', 'White Collar', 'top', 'Zombie 03'),
    ZombieDefinition('zombie_top_04', 'Barefoot Red', 'top', 'Zombie 04'),
    ZombieDefinition('zombie_top_06', 'Gold Fringe', 'top', 'Zombie 06'),
    ZombieDefinition('zombie_top_08', 'Acid Bloom', 'top', 'Zombie 08'),
    ZombieDefinition('zombie_top_09', 'Violet Stitch', 'top', 'Zombie 09' , athletics=True),
    ZombieDefinition('zombie_top_10', 'The Iron Stranger', 'top', 'Zombie 10'),
    ZombieDefinition('zombie_top_decay_01', 'Undercrypt One', 'top', 'Zombie Decay 01' , speed=15),
    ZombieDefinition('zombie_top_decay_02', 'Funeral Suit', 'top', 'Zombie Decay 02'),
    ZombieDefinition('zombie_top_decay_03', 'Wine-Stain Walker', 'top', 'Zombie Decay 03'),
    ZombieDefinition('zombie_top_decay_04', 'Undercrypt Four', 'top', 'Zombie Decay 04' , speed=15),
    ZombieDefinition('zombie_top_decay_05', 'The Mossed Coat', 'top', 'Zombie Decay 05' , athletics=True),
    ZombieDefinition('zombie_top_radioactive_01', 'Marshglass One', 'top', 'Zombie Radioactive 01'),
    ZombieDefinition('zombie_top_radioactive_02', 'Marshglass Two', 'top', 'Zombie Radioactive 02'),
    ZombieDefinition('zombie_top_radioactive_03', 'Marshglass Three', 'top', 'Zombie Radioactive 03'),
    ZombieDefinition('zombie_top_radioactive_04', 'Marshglass Four', 'top', 'Zombie Radioactive 04'),
    ZombieDefinition('zombie_top_swamp_01', 'Reed Stalker', 'top', 'Zombie Swamp 01' , weapons=(("weapon.longsword", WeaponSlot.MELEE_MAIN),)),
    ZombieDefinition('zombie_top_swamp_02', 'Fen Wader', 'top', 'Zombie Swamp 02'),
    ZombieDefinition('zombie_top_swamp_04', 'Mudroot', 'top', 'Zombie Swamp 04'),
    ZombieDefinition('zombie_top_swamp_05', 'The Mirelight', 'top', 'Zombie Swamp 05' , athletics=True),
    ZombieDefinition('zombie_top_swamp_07', 'Black Reed', 'top', 'Zombie Swamp 07'),
    ZombieDefinition('zombie_top_swamp_08', 'Pale Moss', 'top', 'Zombie Swamp 08'),
    ZombieDefinition('zombie_top_swamp_09', 'Siltstep', 'top', 'Zombie Swamp 09' , weapons=(("weapon.shortsword", WeaponSlot.MELEE_MAIN), ("weapon.dagger", WeaponSlot.MELEE_OFF))),
)


def _declare_zombie(definition: ZombieDefinition) -> ContentDeclaration:
    possessions = tuple(CreaturePossessionGrant(item_id=item_id,
        disposition=CreaturePossessionDisposition.EQUIPPED, equipment_slot=slot)
        for item_id, slot in definition.weapons)

    def factory(raw_context: object, parameters: ZombieRosterParameters) -> Entity:
        context = CreatureBuildContext.model_validate(raw_context)
        heavy = definition.heavy
        entity = create_creature_entity(context=context,
            description=f"{definition.name}; {definition.pack}/{definition.source_variant}, ordinary undead adaptation.",
            abilities=(19, 6, 18, 3, 6, 5) if heavy else (13, 6, 16, 3, 6, 5),
            hit_die_value=10 if heavy else 8, hit_die_count=9 if heavy else 3,
            hit_points=85 if heavy else 22, proficiency_bonus=2,
            creature_type=CreatureType.UNDEAD, size=Size.LARGE if heavy else Size.MEDIUM,
            weight=650 if heavy else 150, movement=30 if heavy else definition.speed,
            darkvision=True, immunities=(DamageType.POISON,), save_proficiencies=("wisdom",),
            skills={"athletics": True} if definition.athletics else {})
        entity.appearance.visual_scale = 1.0
        install_body_response(entity, BLOOD_BODY_RESPONSE)
        entity.add_condition_immunity("Poisoned", immunity_name="Zombie")
        apply_creature_possessions(entity, possessions, possession_mode=context.possession_mode)
        register_undead_fortitude(entity)
        entity.register_action(NaturalAttack(name="Slam", source_entity_uuid=entity.uuid, template=True,
            natural_damage_dice=8 if heavy else 6, natural_dice_numbers=2 if heavy else 1,
            natural_damage_type=DamageType.BLUDGEONING,
            fixed_attack_bonus=6 if heavy else 3, fixed_damage_bonus=4 if heavy else 1))
        return entity

    factory.__name__ = f"build_{definition.key}"
    factory.__qualname__ = factory.__name__
    dependencies = tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION, target_ref=row.ref)
                         for row in CORE_STANDARD_ACTION_DECLARATIONS)
    dependencies += (ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=ACTION_BEHAVIOR_DECLARATIONS_BY_CLASS[NaturalAttack].ref),
        ContentDependency(relation=ContentDependencyRelation.GRANTS_FEATURE,
        target_ref=CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[UndeadFortitudeFeature].ref))
    declared = creature_factory(pack_id="content.neurodragon", content_id=f"creature.{definition.key}",
        version=1, parameters=ZombieRosterParameters,
        descriptor=ContentDescriptorSpec(display_name=definition.name,
            description=f"{definition.pack}/{definition.source_variant}; {'Ogre Zombie' if definition.heavy else 'Zombie'} adaptation. Threat uncalibrated.",
            tags=("creature", "undead", "zombie", "roster", "uncalibrated"), visibility=ContentVisibility.PUBLIC,
            presentation=ContentPresentation(portrait_key=f"creature.{definition.key}",
                visual_variant_key=definition.key, ui_group="creatures.neurodragon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",
            source_anchor=f"Nonanimal roster2026-10-18: {definition.pack}/{definition.source_variant}",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION, adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL, review_status=ContentReviewStatus.REVIEWED,
            notes="Explicit undead size/HP/attack and possessions; source palette grants no powers. Grapple, drag, brace and lurch omitted; crawler uses speed15 without new aperture rules. Source clothing is presentation; no hidden armor."),
        dependencies=dependencies)(factory)
    return get_content_declaration(declared)


ZOMBIE_ROSTER_DECLARATIONS = tuple(_declare_zombie(row) for row in ZOMBIE_DEFINITIONS)
ZOMBIE_ROSTER_RECIPES_BY_ID = MappingProxyType({row.ref.content_id.removeprefix("creature."):
    ContentRecipe.create(ref=row.ref, parameters={}) for row in ZOMBIE_ROSTER_DECLARATIONS})
