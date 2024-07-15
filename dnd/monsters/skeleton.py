from dnd.battlemap import Entity
from dnd.statsblock import StatsBlock
from dnd.equipment import Armor, ArmorType, Weapon
from dnd.core import Ability, AbilityScores, AbilityScore, ModifiableValue, Dice, Speed, Skills, Sense, Sensory
from dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType, Size, MonsterType, Alignment, SensesType, Language
from dnd.actions import Damage, Range

def create_skeleton() -> Entity:
    skeleton_stats = StatsBlock(
        name="Skeleton",
        size=Size.MEDIUM,
        type=MonsterType.UNDEAD,
        alignment=Alignment.LAWFUL_EVIL,
        speed=Speed(walk=ModifiableValue(base_value=30)),
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=10)),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=14)),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=15)),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=6)),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=8)),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=5)),
        ),
        languages=[Language.COMMON],
        challenge=0.25,
        experience_points=50,
        hit_dice=Dice(dice_count=2, dice_value=8, modifier=0),
        sensory=Sensory(senses=[Sense(type=SensesType.DARKVISION, range=60)]),
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON]
    )

    

    armor_scraps = Armor(name="Armor Scraps", type=ArmorType.LIGHT, base_ac=13, dex_bonus=True)
    skeleton_stats.armor_class.equip_armor(armor_scraps, ability_scores=skeleton_stats.ability_scores)
    
    shortsword = Weapon(
        name="Shortsword",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5)
    )
    skeleton_stats.weapons.append(shortsword)
    
    shortbow = Weapon(
        name="Shortbow",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=Range(type=RangeType.RANGE, normal=80, long=320)
    )
    skeleton_stats.weapons.append(shortbow)
    skeleton = Entity(**skeleton_stats.model_dump())
    return skeleton