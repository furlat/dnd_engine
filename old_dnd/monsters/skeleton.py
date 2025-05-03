from old_dnd.core import Ability, AbilityScores, AbilityScore, Speed, Sensory, Armor, Weapon
from old_dnd.statsblock import StatsBlock
from old_dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType, Size, MonsterType, Alignment, SensesType, Language, AttackHand, ArmorType
from old_dnd.contextual import ModifiableValue, BaseValue

def create_skeleton(name: str = 'Skeleton') -> StatsBlock:
    skeleton = StatsBlock(
        meta=dict(
            name=name,
            size=Size.MEDIUM,
            type=MonsterType.UNDEAD,
            alignment=Alignment.LAWFUL_EVIL,
            challenge=0.25,
            experience_points=50
        ),
        speed=Speed(
            description="The skeleton can move 30 feet per turn.",
            walk=ModifiableValue(name="walk_speed", base_value=BaseValue(name="base_walk_speed", base_value=30))
        ),
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(name="strength", base_value=BaseValue(name="base_strength", base_value=10))),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(name="dexterity", base_value=BaseValue(name="base_dexterity", base_value=14))),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(name="constitution", base_value=BaseValue(name="base_constitution", base_value=15))),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(name="intelligence", base_value=BaseValue(name="base_intelligence", base_value=6))),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(name="wisdom", base_value=BaseValue(name="base_wisdom", base_value=8))),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(name="charisma", base_value=BaseValue(name="base_charisma", base_value=5)))
        ),
        health=dict(
            hit_dice_value=8,
            hit_dice_count=2
        ),
        sensory=Sensory(
            senses=[dict(type=SensesType.DARKVISION, range=60)]
        )
    )

    # Equip armor
    armor_scraps = Armor(name="Armor Scraps", type=ArmorType.LIGHT, base_ac=13, dex_bonus=True)
    skeleton.armor_class.equip_armor(armor_scraps)
    
    # Create and equip weapons
    shortsword = Weapon(
        name="Shortsword",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE],
        range=dict(type=RangeType.REACH, normal=5)
    )
    skeleton.attacks_manager.equip_right_hand_melee_weapon(shortsword)
    
    shortbow = Weapon(
        name="Shortbow",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=dict(type=RangeType.RANGE, normal=80, long=320)
    )
    skeleton.attacks_manager.equip_right_hand_ranged_weapon(shortbow)

    return skeleton