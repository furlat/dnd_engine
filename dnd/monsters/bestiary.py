"""
Simple creature factories for combat examples.

This module provides factory functions to create basic D&D 5e creatures
for testing and demonstrating the combat system.
"""

from uuid import UUID, uuid4
from typing import Optional, Tuple

from dnd.entity import Entity, EntityConfig
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.equipment import (
    EquipmentConfig, BodyArmor,
)
from dnd.core.equipment_types import ArmorType, BodyPart, WeaponSlot
from dnd.blocks.skills import SkillSetConfig, SkillConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.core.modifiers import DamageType, CreatureType, Size
from dnd.core.progression import full_caster_spell_slots_for_level, proficiency_bonus_for_level
from dnd.core.values import ModifiableValue
from dnd.core.base_block import SenseMode, SensesType
from dnd.actions import Hide, Disengage

from dnd.items import (
    create_scimitar,
    create_shortsword,
    create_shortbow,
    create_dagger,
    create_longsword,
    create_leather_armor,
    create_wooden_shield,
    create_crown,
)

from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.spells.evocation import (
    FireBolt, Fireball, MagicMissile, BurningHands, LightningBolt, Shatter, Thunderwave
)
from dnd.actions_functional import register_spell
from dnd.spells.illusion import Invisibility, GreaterInvisibility
from dnd.spells.evocation import EldritchBlast
from dnd.items.test_items import (
    create_potion_of_greater_invisibility,
    create_potion_of_haste,
    create_acid_flask, create_scroll_of_invisibility,
)
from dnd.items.weapons import create_arcane_staff
from dnd.spells.abjuration import register_shield_reaction
from dnd.spells.necromancy import NecroticBless
from dnd.monsters.skeleton_abilities import MarkTargetAction

GOBLIN_NIMBLE_HIDE_ACTION = "Nimble Escape: Hide"
GOBLIN_NIMBLE_DISENGAGE_ACTION = "Nimble Escape: Disengage"

GOBLIN_APPEARANCE = AppearanceConfig(
    visual_scale=0.82,
    body_category="NakedBody",
    skin_tint=0x7A9A3A,
    head_category=None,
    hair_tint=0,
    has_beard=False,
    beard_tint=0,
)

SKELETON_APPEARANCE = AppearanceConfig(
    body_category="NakedBody2",
    skin_tint=0xFFFFFF,
    head_category=None,
    hair_tint=0,
    has_beard=False,
    beard_tint=0,
)

CASTER_APPEARANCE = AppearanceConfig(
    body_category="NakedBody",
    skin_tint=0xDDAA88,
    head_category="Head9",
    hair_tint=0x6C5231,
    has_beard=False,
    beard_tint=0,
)


def register_goblin_nimble_escape(entity: Entity) -> None:
    """Register goblin bonus-action Hide and Disengage templates.

    Args:
        entity: Goblin entity receiving the Nimble Escape actions.
    """
    entity.register_action(
        Hide(
            source_entity_uuid=entity.uuid,
            template=True,
            name=GOBLIN_NIMBLE_HIDE_ACTION,
            description="Take the Hide action as a bonus action.",
            alt_cost_type="bonus_actions",
        )
    )
    entity.register_action(
        Disengage(
            source_entity_uuid=entity.uuid,
            template=True,
            name=GOBLIN_NIMBLE_DISENGAGE_ACTION,
            description="Take the Disengage action as a bonus action.",
            alt_cost_type="bonus_actions",
        )
    )


def create_armor_scraps(source_id: UUID) -> BodyArmor:
    """Create skeleton armor scraps with AC 13.

    Args:
        source_id: Entity UUID used as the item source.

    Returns:
        Armor scraps body armor.
    """
    return BodyArmor(
        source_entity_uuid=source_id,
        name="Armor Scraps",
        description="Rusted pieces of armor barely held together on bone.",
        type=ArmorType.LIGHT,
        body_part=BodyPart.BODY,
        ac=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=13,
            value_name="Armor Class"
        ),
        max_dex_bonus=ModifiableValue.create(
            source_entity_uuid=source_id,
            base_value=0,
            value_name="Max Dex Bonus"
        )
    )


def create_goblin(
    source_id: Optional[UUID] = None,
    name: str = "Goblin",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 40
) -> Entity:
    """
    Creates a Goblin (CR 1/4).

    Stats:
    - STR 8 (-1), DEX 14 (+2), CON 10 (+0), INT 10 (+0), WIS 8 (-1), CHA 8 (-1)
    - HP: 7 (2d6)
    - AC: 15 (leather armor + shield)
    - Speed: 30ft
    - Weapon: Scimitar (1d6+2 slashing)
    - Proficient: Stealth (+6 with expertise-like bonus)
    - Proficiency bonus: +2

    Args:
        source_id: UUID for the entity (generated if not provided)
        name: Name for the goblin
        position: Starting grid position
        faction: Optional faction identifier

    Returns:
        Entity: A configured goblin entity
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=10),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=8)
    )

    skill_set_config = SkillSetConfig(
        stealth=SkillConfig(proficiency=True, expertise=True)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )]
    )

    equipment_config = EquipmentConfig()

    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        size=Size.SMALL,
        appearance=GOBLIN_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A small, green-skinned creature with pointed ears and sharp teeth.",
        config=entity_config
    )

    setup_standard_actions(entity)
    entity.senses.sense_modes.append(
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    )
    register_goblin_nimble_escape(entity)

    scimitar = create_scimitar(entity.uuid)
    shortbow = create_shortbow(entity.uuid)
    leather_armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shortbow, WeaponSlot.RANGED_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    return entity


def create_skeleton(
    source_id: Optional[UUID] = None,
    name: str = "Skeleton",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 120,
    darkvision: bool = True
) -> Entity:
    """Create a Skeleton (CR 1/4).

    Stats:
    - STR 10 (+0), DEX 14 (+2), CON 15 (+2), INT 6 (-2), WIS 8 (-1), CHA 5 (-3)
    - HP: 13 (2d8+4)
    - AC: 13 (armor scraps)
    - Speed: 30ft
    - Weapons: Shortsword (1d6+2 piercing), shortbow (1d6+2 piercing)
    - Vulnerabilities: Bludgeoning
    - Immunities: poison damage, Poisoned, Exhaustion
    - Senses: darkvision 60 ft. by default
    - Proficiency bonus: +2

    Args:
        source_id: UUID for the entity, generated when omitted.
        name: Name for the skeleton.
        position: Starting grid position.
        faction: Optional faction identifier.
        weight: Weight in pounds.
        darkvision: Whether to grant darkvision 60 ft.

    Returns:
        A configured skeleton entity.
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=10),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=15),
        intelligence=AbilityConfig(ability_score=6),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=5)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=8,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )],
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        creature_type=CreatureType.UNDEAD,
        appearance=SKELETON_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="An animated skeleton wielding a rusty shortsword.",
        config=entity_config
    )

    setup_standard_actions(entity)

    if darkvision:
        entity.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
        )

    shortsword = create_shortsword(entity.uuid)
    shortbow = create_shortbow(entity.uuid)
    armor_scraps = create_armor_scraps(entity.uuid)

    entity.add_condition_immunity("Poisoned", immunity_name="Skeleton")
    entity.add_condition_immunity("Exhaustion", immunity_name="Skeleton")
    entity.equipment.equip(armor_scraps)
    entity.equipment.equip(shortsword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shortbow, WeaponSlot.RANGED_MAIN)

    return entity


def create_goblin_archer(
    source_id: Optional[UUID] = None,
    name: str = "Goblin Archer",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 40
) -> Entity:
    """
    Creates a Goblin Archer (CR 1/4) - Dual Wielder variant.

    Stats:
    - STR 8 (-1), DEX 14 (+2), CON 10 (+0), INT 10 (+0), WIS 8 (-1), CHA 8 (-1)
    - HP: 7 (2d6)
    - AC: 13 (leather armor, no shield for dual wield)
    - Speed: 30ft
    - Melee Main: Scimitar (1d6+2 slashing, finesse, light)
    - Melee Off: Dagger (1d4 piercing, finesse, light) - NO ability modifier to damage
    - Ranged: Shortbow (1d6+2 piercing, range 80/320)
    - Proficient: Stealth (+6 with expertise-like bonus)
    - Proficiency bonus: +2

    Args:
        source_id: UUID for the entity (generated if not provided)
        name: Name for the goblin archer
        position: Starting grid position
        faction: Optional faction identifier

    Returns:
        Entity: A configured goblin archer entity
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=10),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=8)
    )

    skill_set_config = SkillSetConfig(
        stealth=SkillConfig(proficiency=True, expertise=True)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )]
    )

    equipment_config = EquipmentConfig()

    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        size=Size.SMALL,
        appearance=GOBLIN_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A small goblin wielding a shortbow, preferring to attack from range.",
        config=entity_config
    )

    setup_standard_actions(entity)

    shortbow = create_shortbow(entity.uuid)
    scimitar = create_scimitar(entity.uuid)
    dagger = create_dagger(entity.uuid)
    leather_armor = create_leather_armor(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(shortbow, WeaponSlot.RANGED_MAIN)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(dagger, WeaponSlot.MELEE_OFF)

    return entity


def create_caster(
    source_id: Optional[UUID] = None,
    name: str = "Caster",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    level: int = 5
) -> Entity:
    """
    Create a generic spellcaster with AoE spells (Fireball, Magic Missile, etc.).

    No class features — use sorcerer_factory.create_sorcerer() for a real Sorcerer.

    Full-caster progression with:
    - CHA 18 (primary casting stat)
    - DEX 14, CON 14 (survivability)
    - Proficiency, hit dice, and spell slots determined by ``level``
    - Spells: Fireball, Magic Missile, BurningHands, LightningBolt, Shatter, Thunderwave

    Args:
        source_id: UUID for the entity (generated if not provided)
        name: Name for the caster
        position: Starting grid position
        faction: Optional faction identifier
        level: Caster level (default 5)

    Returns:
        Entity: A configured spellcaster entity (no class features)
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=14),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=10),
        charisma=AbilityConfig(ability_score=18),
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=level,
            mode="maximums"
        )]
    )

    action_economy_config = ActionEconomyConfig(
        spell_slots=full_caster_spell_slots_for_level(level)
    )

    equipment_config = EquipmentConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
        proficiency_bonus=proficiency_bonus_for_level(level),
        position=position,
        faction=faction,
        appearance=CASTER_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A spellcaster with innate magical abilities.",
        config=entity_config
    )

    setup_standard_actions(entity)

    register_spell(entity, FireBolt, caster_level=level)
    register_spell(entity, MagicMissile, caster_level=level)
    register_spell(entity, Fireball, caster_level=level)
    register_spell(entity, BurningHands, caster_level=level)
    register_spell(entity, LightningBolt, caster_level=level)
    register_spell(entity, Shatter, caster_level=level)
    register_spell(entity, Thunderwave, caster_level=level)
    register_spell(entity, Invisibility, caster_level=level)
    register_spell(entity, GreaterInvisibility, caster_level=level)

    register_shield_reaction(entity)

    dagger = create_dagger(entity.uuid)
    entity.equipment.equip(dagger, WeaponSlot.MELEE_MAIN)

    potion = create_potion_of_greater_invisibility(entity.uuid)
    entity.loot_item(potion)

    haste_potion = create_potion_of_haste(entity.uuid)
    entity.loot_item(haste_potion)

    return entity


def create_skeleton_warrior(
    source_id: Optional[UUID] = None,
    name: str = "Skeleton Warrior",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 120,
    darkvision: bool = False
) -> Entity:
    """
    Creates a Skeleton Warrior — frontline tank with shield and acid flask.

    Stats:
    - STR 10 (+0), DEX 14 (+2), CON 15 (+2), INT 6 (-2), WIS 8 (-1), CHA 5 (-3)
    - HP: 24 (4d8+8)
    - AC: 15 (armor scraps 13 + shield +2)
    - Weapon: Longsword (1d8 slashing)
    - Shield: Wooden Shield (+2 AC)
    - Item: Acid Flask (throwable 2x2 AoE, 2d4 acid, DEX DC 11)
    - Vulnerabilities: Bludgeoning
    - Immunities: Poison
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=10),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=15),
        intelligence=AbilityConfig(ability_score=6),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=5)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=8,
            hit_dice_count=4,
            mode="average",
            ignore_first_level=False
        )],
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        creature_type=CreatureType.UNDEAD,
        appearance=SKELETON_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A heavily armored skeleton wielding a longsword and shield.",
        config=entity_config
    )

    setup_standard_actions(entity)

    if darkvision:
        entity.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
        )

    longsword = create_longsword(entity.uuid)
    shield = create_wooden_shield(entity.uuid)
    armor_scraps = create_armor_scraps(entity.uuid)

    entity.equipment.equip(armor_scraps)
    entity.equipment.equip(longsword, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    acid_flask = create_acid_flask(entity.uuid)
    entity.loot_item(acid_flask)

    return entity


def create_skeleton_archer(
    source_id: Optional[UUID] = None,
    name: str = "Skeleton Archer",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 120,
    darkvision: bool = False
) -> Entity:
    """
    Creates a Skeleton Archer — ranged DPS with Mark Target support.

    Stats:
    - STR 10 (+0), DEX 16 (+3), CON 15 (+2), INT 6 (-2), WIS 8 (-1), CHA 5 (-3)
    - HP: 20 (3d8+6)
    - AC: 13 (armor scraps, no shield)
    - Weapons: Shortbow (RANGED_MAIN), Dagger x2 (MELEE_MAIN + MELEE_OFF)
    - Special: Mark Target (bonus action, concentration, grants advantage to attackers)
    - Vulnerabilities: Bludgeoning
    - Immunities: Poison
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=10),
        dexterity=AbilityConfig(ability_score=16),
        constitution=AbilityConfig(ability_score=15),
        intelligence=AbilityConfig(ability_score=6),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=5)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=8,
            hit_dice_count=3,
            mode="average",
            ignore_first_level=False
        )],
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig()

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        creature_type=CreatureType.UNDEAD,
        appearance=SKELETON_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A skeleton archer that can mark targets for its allies.",
        config=entity_config
    )

    setup_standard_actions(entity)

    if darkvision:
        entity.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
        )

    shortbow = create_shortbow(entity.uuid)
    dagger1 = create_dagger(entity.uuid)
    dagger2 = create_dagger(entity.uuid)
    armor_scraps = create_armor_scraps(entity.uuid)

    entity.equipment.equip(armor_scraps)
    entity.equipment.equip(shortbow, WeaponSlot.RANGED_MAIN)
    entity.equipment.equip(dagger1, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(dagger2, WeaponSlot.MELEE_OFF)

    mark_action = MarkTargetAction(
        source_entity_uuid=entity.uuid,
        template=True
    )
    entity.register_action(mark_action)

    return entity


def create_skeleton_warlock(
    source_id: Optional[UUID] = None,
    name: str = "Skeleton Warlock",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 120,
    darkvision: bool = False
) -> Entity:
    """
    Creates a Skeleton Warlock — glass cannon caster with Eldritch Blast.

    Stats:
    - STR 10 (+0), DEX 14 (+2), CON 15 (+2), INT 6 (-2), WIS 8 (-1), CHA 14 (+2)
    - HP: 13 (2d8+4)
    - AC: 13 (armor scraps)
    - Weapon: Arcane Staff (1d6 bludgeoning, +1 spell attack)
    - Spells: Eldritch Blast (cantrip), Burning Hands (L1), Thunderwave (L1)
    - Spell Slots: 2x Level 1
    - Item: Scroll of Invisibility
    - Spellcasting ability: Charisma
    - Vulnerabilities: Bludgeoning
    - Immunities: Poison
    """
    if source_id is None:
        source_id = uuid4()

    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=10),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=15),
        intelligence=AbilityConfig(ability_score=6),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=14)
    )

    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=8,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )],
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON]
    )

    equipment_config = EquipmentConfig()
    action_economy_config = ActionEconomyConfig(
        spell_slots={1: 2, 2: 1}
    )

    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        creature_type=CreatureType.UNDEAD,
        appearance=SKELETON_APPEARANCE
    )

    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A skeleton crackling with dark arcane energy.",
        config=entity_config
    )

    setup_standard_actions(entity)

    if darkvision:
        entity.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
        )

    staff = create_arcane_staff(entity.uuid)
    armor_scraps = create_armor_scraps(entity.uuid)
    crown = create_crown(entity.uuid)

    entity.equipment.equip(armor_scraps)
    entity.equipment.equip(crown)
    entity.equipment.equip(staff, WeaponSlot.MELEE_MAIN)

    register_spell(entity, EldritchBlast, caster_level=1)
    register_spell(entity, BurningHands, caster_level=1)
    register_spell(entity, Thunderwave, caster_level=1)
    register_spell(entity, NecroticBless, caster_level=1)

    register_shield_reaction(entity)

    scroll = create_scroll_of_invisibility(entity.uuid)
    entity.loot_item(scroll)

    return entity

if __name__ == "__main__":

    goblin = create_goblin(name="Test Goblin", position=(0, 0))
    skeleton = create_skeleton(name="Test Skeleton", position=(1, 0))

    print(f"Created {goblin.name}:")
    print(f"  HP: {goblin.get_hp()}")
    print(f"  AC: {goblin.ac_bonus().normalized_score}")
    print(f"  Position: {goblin.position}")

    print(f"\nCreated {skeleton.name}:")
    print(f"  HP: {skeleton.get_hp()}")
    print(f"  AC: {skeleton.ac_bonus().normalized_score}")
    print(f"  Position: {skeleton.position}")
