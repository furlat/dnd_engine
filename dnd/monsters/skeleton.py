from dnd.statsblock import StatsBlock
from dnd.equipment import Armor, ArmorType, Shield, Weapon, WeaponProperty, ArmorClass
from dnd.actions import Action, ActionCost, ActionType, Targeting, TargetType, AttackType, Attack
from dnd.core import Ability, AbilityScores, AbilityScore, ModifiableValue, Dice, \
 Damage, DamageType, Range, RangeType, Size, MonsterType, Alignment, Speed, Skills, Sense, SensesType, Language, ActionEconomy
from dnd.core import SkillSet, SavingThrow
from typing import List
import random

def create_skeleton() -> StatsBlock:
    skeleton = StatsBlock(
        name="Skeleton",
        size=Size.MEDIUM,
        type=MonsterType.UNDEAD,
        alignment=Alignment.LAWFUL_EVIL,
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=10)),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=14)),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=15)),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=6)),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=8)),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=5)),
            proficiency_bonus=ModifiableValue(base_value=2)
        ),
        speed=Speed(walk=ModifiableValue(base_value=30)),
        armor_class=ArmorClass(base_ac=ModifiableValue(base_value=13)),
        vulnerabilities=[DamageType.BLUDGEONING],
        immunities=[DamageType.POISON],
        senses=[Sense(type=SensesType.DARKVISION, range=60)],
        languages=[Language.COMMON],
        challenge=0.25,
        experience_points=50,
        skills=SkillSet(),
        saving_throws={ability: SavingThrow(ability=ability, proficient=False) for ability in Ability},
        special_traits=[
            "Undead Nature: The skeleton doesn't require air, food, drink, or sleep."
        ],
        hit_dice=Dice(dice_count=2, dice_value=8, modifier=0),
        action_economy=ActionEconomy(speed=30)
    )

    # Equip armor
    armor_scraps = Armor(name="Armor Scraps", type=ArmorType.LIGHT, base_ac=13, dex_bonus=True)
    skeleton.equip_armor(armor_scraps)

    # Add weapons
    shortsword = Weapon(
        name="Shortsword",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5)
    )
    skeleton.add_weapon(shortsword)

    shortbow = Weapon(
        name="Shortbow",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=Range(type=RangeType.RANGE, normal=80, long=320)
    )
    skeleton.add_weapon(shortbow)

    # Add Undead Fortitude trait
    skeleton.add_action(UndeadFortitude(stats_block=skeleton))

    return skeleton

class UndeadFortitude(Action):
    def __init__(self, stats_block: 'StatsBlock'):
        super().__init__(
            name="Undead Fortitude",
            description="If damage reduces the skeleton to 0 hit points, it must make a Constitution saving throw with a DC of 5 + the damage taken, unless the damage is radiant or from a critical hit. On a success, the skeleton drops to 1 hit point instead.",
            cost=[],  # This is a passive trait, so no action cost
            limited_usage=None,
            targeting=Targeting(type=TargetType.SELF),
            stats_block=stats_block
        )

    def execute(self, damage: int, damage_type: DamageType, is_critical: bool) -> bool:
        if self.stats_block.current_hit_points == 0 and damage_type != DamageType.RADIANT and not is_critical:
            dc = 5 + damage
            return self.stats_block.perform_saving_throw(Ability.CON, dc)
        return False

def print_skeleton_details(skeleton: StatsBlock):
    print("\nSkeleton Details:")
    print(f"Name: {skeleton.name}")
    print(f"Size: {skeleton.size.value}")
    print(f"Type: {skeleton.type.value}")
    print(f"Alignment: {skeleton.alignment.value}")
    print("Ability Scores:")
    for ability in Ability:
        score = getattr(skeleton.ability_scores, ability.value.lower())
        print(f"  {ability.value}: {score.score.get_value(skeleton)} (Modifier: {score.get_modifier(skeleton)})")
    print(f"Speed: Walk {skeleton.speed.walk.get_value(skeleton)} ft")
    print(f"Armor Class: {skeleton.armor_class.get_value(skeleton)}")
    print(f"Hit Points: {skeleton.current_hit_points}/{skeleton.max_hit_points}")
    print(f"Proficiency Bonus: +{skeleton.proficiency_bonus}")
    print("Damage Vulnerabilities: " + ", ".join([v.value for v in skeleton.vulnerabilities]))
    print("Damage Immunities: " + ", ".join([i.value for i in skeleton.immunities]))
    print("Senses:")
    for sense in skeleton.senses:
        print(f"  {sense.type.value}: {sense.range} ft")
    print(f"Languages: {', '.join([lang.value for lang in skeleton.languages])}")
    print(f"Challenge Rating: {skeleton.challenge} ({skeleton.experience_points} XP)")
    print("Special Traits:")
    for trait in skeleton.special_traits:
        print(f"  {trait}")
    print("Actions:")
    for action in skeleton.actions:
        if isinstance(action, Attack):
            print(f"  {action.action_docstring()}")
        else:
            print(f"  {action.name}: {action.description}")
    print(f"Equipment: {', '.join([weapon.name for weapon in skeleton.weapons])}, "
          f"{skeleton.armor_class.equipped_armor.name if skeleton.armor_class.equipped_armor else 'No Armor'}")

def main():
    skeleton = create_skeleton()
    print_skeleton_details(skeleton)

if __name__ == "__main__":
    main()