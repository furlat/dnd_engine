from dnd.battlemap import Entity
from dnd.statsblock import StatsBlock
from dnd.equipment import Armor, ArmorType, Shield, Weapon
from dnd.core import Ability, AbilityScores, AbilityScore, ModifiableValue, Dice, Speed, Skills, Sense, Sensory
from dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType, Size, MonsterType, Alignment, SensesType, Language
from dnd.actions import Damage, Range

def create_goblin() -> Entity:
    goblin_stats = StatsBlock(
        name="Goblin",
        size=Size.SMALL,
        type=MonsterType.HUMANOID,
        alignment=Alignment.NEUTRAL_EVIL,
        speed=Speed(walk=ModifiableValue(base_value=30)),
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=8)),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=14)),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=10)),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=10)),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=8)),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=8)),
        ),
        languages=[Language.COMMON, Language.GOBLIN],
        challenge=0.25,
        experience_points=50,
        hit_dice=Dice(dice_count=2, dice_value=6, modifier=0),
        sensory=Sensory(senses=[Sense(type=SensesType.DARKVISION, range=60)])
    )

    

    leather_armor = Armor(name="Leather Armor", type=ArmorType.LIGHT, base_ac=11, dex_bonus=True)
    goblin_stats.armor_class.equip_armor(leather_armor, ability_scores=goblin_stats.ability_scores)
    
    shield = Shield(name="Shield", ac_bonus=2)
    goblin_stats.armor_class.equip_shield(shield, ability_scores=goblin_stats.ability_scores)
    
    scimitar = Weapon(
        name="Scimitar",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.SLASHING),
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5)
    )
    goblin_stats.weapons.append(scimitar)
    
    shortbow = Weapon(
        name="Shortbow",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=Range(type=RangeType.RANGE, normal=80, long=320)
    )
    goblin_stats.weapons.append(shortbow)
    goblin = Entity(**goblin_stats.model_dump())
    return goblin