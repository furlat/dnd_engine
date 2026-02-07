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
    WeaponSlot, ArmorType
)
from dnd.core.events import BodyPart
from dnd.blocks.skills import SkillSetConfig, SkillConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.modifiers import DamageType, CreatureType
from dnd.core.values import ModifiableValue

# Import weapons and armor from items module
from dnd.items import (
    create_scimitar,
    create_shortsword,
    create_shortbow,
    create_dagger,
    create_leather_armor,
    create_wooden_shield,
)

# Import spellcasting and spells for sorcerer
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.spells.evocation import (
    Fireball, MagicMissile, BurningHands, LightningBolt, Shatter, Thunderwave
)
from dnd.actions_functional import register_spell


def create_armor_scraps(source_id: UUID) -> BodyArmor:
    """Creates armor scraps - AC 13 (like skeleton's natural armor)"""
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
            base_value=0,  # No dex bonus for this armor type
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

    # Ability scores
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=10),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=8)
    )

    # Skills - Stealth proficiency
    skill_set_config = SkillSetConfig(
        stealth=SkillConfig(proficiency=True, expertise=True)  # +6 total
    )

    # Health: 2d6 = 7 average HP
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )]
    )

    # Equipment config (base values)
    equipment_config = EquipmentConfig()

    # Action economy (standard)
    action_economy_config = ActionEconomyConfig()

    # Entity config
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight
    )

    # Create entity
    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A small, green-skinned creature with pointed ears and sharp teeth.",
        config=entity_config
    )

    # Set up action templates (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # Equip weapons and armor (this triggers event handlers to register attack templates)
    scimitar = create_scimitar(entity.uuid)
    leather_armor = create_leather_armor(entity.uuid)
    shield = create_wooden_shield(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)
    entity.equipment.equip(shield, WeaponSlot.MELEE_OFF)

    return entity


def create_skeleton(
    source_id: Optional[UUID] = None,
    name: str = "Skeleton",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    weight: int = 120
) -> Entity:
    """
    Creates a Skeleton (CR 1/4).

    Stats:
    - STR 10 (+0), DEX 14 (+2), CON 15 (+2), INT 6 (-2), WIS 8 (-1), CHA 5 (-3)
    - HP: 13 (2d8+4)
    - AC: 13 (armor scraps)
    - Speed: 30ft
    - Weapon: Shortsword (1d6+2 piercing)
    - Vulnerabilities: Bludgeoning
    - Immunities: Poison
    - Proficiency bonus: +2

    Args:
        source_id: UUID for the entity (generated if not provided)
        name: Name for the skeleton
        position: Starting grid position
        faction: Optional faction identifier

    Returns:
        Entity: A configured skeleton entity
    """
    if source_id is None:
        source_id = uuid4()

    # Ability scores
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=10),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=15),
        intelligence=AbilityConfig(ability_score=6),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=5)
    )

    # Health: 2d8+4 = 13 average HP
    # CON modifier (+2) * 2 hit dice = +4
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

    # Equipment config (base values)
    equipment_config = EquipmentConfig()

    # Action economy (standard)
    action_economy_config = ActionEconomyConfig()

    # Entity config
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight,
        creature_type=CreatureType.UNDEAD
    )

    # Create entity
    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="An animated skeleton wielding a rusty shortsword.",
        config=entity_config
    )

    # Set up action templates (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # Equip weapons and armor (this triggers event handlers to register attack templates)
    shortsword = create_shortsword(entity.uuid)
    armor_scraps = create_armor_scraps(entity.uuid)

    entity.equipment.equip(armor_scraps)
    entity.equipment.equip(shortsword, WeaponSlot.MELEE_MAIN)

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

    # Ability scores
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=10),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=8),
        charisma=AbilityConfig(ability_score=8)
    )

    # Skills - Stealth proficiency
    skill_set_config = SkillSetConfig(
        stealth=SkillConfig(proficiency=True, expertise=True)  # +6 total
    )

    # Health: 2d6 = 7 average HP
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=2,
            mode="average",
            ignore_first_level=False
        )]
    )

    # Equipment config (base values)
    equipment_config = EquipmentConfig()

    # Action economy (standard)
    action_economy_config = ActionEconomyConfig()

    # Entity config
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        skill_set=skill_set_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        proficiency_bonus=2,
        position=position,
        faction=faction,
        weight=weight
    )

    # Create entity
    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A small goblin wielding a shortbow, preferring to attack from range.",
        config=entity_config
    )

    # Set up action templates (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # Equip weapons and armor - dual wield melee + ranged backup
    shortbow = create_shortbow(entity.uuid)
    scimitar = create_scimitar(entity.uuid)
    dagger = create_dagger(entity.uuid)
    leather_armor = create_leather_armor(entity.uuid)

    entity.equipment.equip(leather_armor)
    entity.equipment.equip(shortbow, WeaponSlot.RANGED_MAIN)  # Ranged weapon
    entity.equipment.equip(scimitar, WeaponSlot.MELEE_MAIN)   # Main melee weapon
    entity.equipment.equip(dagger, WeaponSlot.MELEE_OFF)      # Off-hand (two-weapon fighting)

    return entity


def create_sorcerer(
    source_id: Optional[UUID] = None,
    name: str = "Sorcerer",
    position: Tuple[int, int] = (0, 0),
    faction: Optional[str] = None,
    level: int = 5
) -> Entity:
    """
    Create a Sorcerer with AoE spells (Fireball, Magic Missile, etc.).

    Level 5 Sorcerer with:
    - CHA 18 (primary casting stat)
    - DEX 14, CON 14 (survivability)
    - Spell slots: 4/3/2 for levels 1/2/3
    - Spells: Fireball, Magic Missile, BurningHands, LightningBolt, Shatter, Thunderwave

    Args:
        source_id: UUID for the entity (generated if not provided)
        name: Name for the sorcerer
        position: Starting grid position
        faction: Optional faction identifier
        level: Sorcerer level (default 5)

    Returns:
        Entity: A configured sorcerer entity
    """
    if source_id is None:
        source_id = uuid4()

    # Ability scores - CHA primary
    ability_scores_config = AbilityScoresConfig(
        strength=AbilityConfig(ability_score=8),
        dexterity=AbilityConfig(ability_score=14),
        constitution=AbilityConfig(ability_score=14),
        intelligence=AbilityConfig(ability_score=10),
        wisdom=AbilityConfig(ability_score=10),
        charisma=AbilityConfig(ability_score=18),  # Sorcerer casting stat
    )

    # Health: level d6 hit dice
    health_config = HealthConfig(
        hit_dices=[HitDiceConfig(
            hit_dice_value=6,
            hit_dice_count=level,
            mode="maximums"  # Better HP for testing
        )]
    )

    # Action economy with spell slots for level 5
    action_economy_config = ActionEconomyConfig(
        spell_slots={1: 4, 2: 3, 3: 2}  # Level 5 sorcerer spell slots
    )

    # Equipment config (base values)
    equipment_config = EquipmentConfig()

    # Entity config
    entity_config = EntityConfig(
        ability_scores=ability_scores_config,
        health=health_config,
        equipment=equipment_config,
        action_economy=action_economy_config,
        spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
        proficiency_bonus=3,  # Level 5+
        position=position,
        faction=faction
    )

    # Create entity
    entity = Entity.create(
        name=name,
        source_entity_uuid=source_id,
        description="A spellcaster with innate magical abilities.",
        config=entity_config
    )

    # Set up action templates (Move, Dash, Dodge, etc.)
    setup_standard_actions(entity)

    # Register spells - both multi-entity and AoE
    register_spell(entity, MagicMissile, caster_level=level)  # Multi-entity
    register_spell(entity, Fireball, caster_level=level)      # AoE sphere
    register_spell(entity, BurningHands, caster_level=level)  # AoE cone
    register_spell(entity, LightningBolt, caster_level=level) # AoE line
    register_spell(entity, Shatter, caster_level=level)       # AoE sphere
    register_spell(entity, Thunderwave, caster_level=level)   # AoE cube + push

    return entity


if __name__ == "__main__":
    # Quick test of creature creation
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
