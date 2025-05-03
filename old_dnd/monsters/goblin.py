from old_dnd.core import  Ability, AbilityScores,AbilityScore, Speed, Sensory,Armor, Shield, Weapon
from old_dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType, Size, MonsterType, Alignment, SensesType, Language, AttackHand,ArmorType
from old_dnd.contextual import ModifiableValue, BaseValue
from old_dnd.statsblock import StatsBlock

def create_goblin(name:str ='Goblin') -> StatsBlock:
    goblin = StatsBlock(
        meta=dict(
            name=name,
            size=Size.SMALL,
            type=MonsterType.HUMANOID,
            alignment=Alignment.NEUTRAL_EVIL,
            languages=[Language.COMMON, Language.GOBLIN],
            challenge=0.25,
            experience_points=50
        ),
        speed=Speed(
            description="The goblin can move 30 feet per turn.",
            walk=ModifiableValue(name="walk_speed", base_value=BaseValue(name="base_walk_speed", base_value=30))
        ),
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(name="strength", base_value=BaseValue(name="base_strength", base_value=8))),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(name="dexterity", base_value=BaseValue(name="base_dexterity", base_value=14))),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(name="constitution", base_value=BaseValue(name="base_constitution", base_value=10))),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(name="intelligence", base_value=BaseValue(name="base_intelligence", base_value=10))),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(name="wisdom", base_value=BaseValue(name="base_wisdom", base_value=8))),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(name="charisma", base_value=BaseValue(name="base_charisma", base_value=8)))
        ),
        health=dict(
            hit_dice_value=6,
            hit_dice_count=2
        ),
        sensory=Sensory(
            senses=[dict(type=SensesType.DARKVISION, range=60)]
        )
    )

    # Equip armor
    leather_armor = Armor(name="Leather Armor", type=ArmorType.LIGHT, base_ac=11, dex_bonus=True)
    goblin.armor_class.equip_armor(leather_armor)
    
    # Equip shield
    shield = Shield(name="Shield", ac_bonus=2)
    goblin.armor_class.equip_shield(shield)
    
    # Create and equip weapons
    scimitar = Weapon(
        name="Scimitar",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.SLASHING,
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE,WeaponProperty.LIGHT],
        range=dict(type=RangeType.REACH, normal=5)
    )
    goblin.attacks_manager.equip_right_hand_melee_weapon(scimitar)
    goblin.attacks_manager.equip_left_hand_melee_weapon(scimitar)
    
    shortbow = Weapon(
        name="Shortbow",
        damage_dice=6,
        dice_numbers=1,
        damage_type=DamageType.PIERCING,
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=dict(type=RangeType.RANGE, normal=80, long=320)
    )
    goblin.attacks_manager.equip_right_hand_ranged_weapon(shortbow)

    return goblin


if __name__ == "__main__":
    goblin = create_goblin()
    print(goblin.health.max_hit_points)
    print(goblin.health.current_hit_points)
    print(goblin.health.total_hit_points)