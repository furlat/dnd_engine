from dnd.statsblock import StatsBlock
from dnd.equipment import Armor, ArmorType, Shield, Weapon, WeaponProperty, ArmorClass
from dnd.actions import Action, ActionCost, ActionType, Targeting, TargetType, AttackType, Attack
from dnd.core import Ability, AbilityScores, AbilityScore, ModifiableValue, Dice, \
 Damage, DamageType, Range, RangeType, Size, MonsterType, Alignment, Speed, Skills, Sense, SensesType, Language, ActionEconomy
from dnd.contextual import ContextualEffects
from dnd.core import SkillSet, SavingThrow

class GoblinNimbleEscape(Action):
    def __init__(self, **data):
        super().__init__(
            name="Nimble Escape",
            description="The goblin can take the Disengage or Hide action as a bonus action on each of its turns.",
            cost=[ActionCost(type=ActionType.BONUS_ACTION, cost=1)],
            limited_usage=None,
            targeting=Targeting(type=TargetType.SELF),
            **data
        )

def create_goblin() -> StatsBlock:
    goblin = StatsBlock(
        name="Goblin",
        size=Size.SMALL,
        type=MonsterType.HUMANOID,
        alignment=Alignment.NEUTRAL_EVIL,
        ability_scores=AbilityScores(
            strength=AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=8)),
            dexterity=AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=14)),
            constitution=AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=10)),
            intelligence=AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=10)),
            wisdom=AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=8)),
            charisma=AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=8)),
            proficiency_bonus=ModifiableValue(base_value=2)
        ),
        speed=Speed(walk=ModifiableValue(base_value=30)),
        armor_class=ArmorClass(base_ac=ModifiableValue(base_value=15)),
        challenge=0.25,
        experience_points=50,
        skills=SkillSet(),
        saving_throws={ability: SavingThrow(ability=ability, proficient=False) for ability in Ability},
        senses=[Sense(type=SensesType.DARKVISION, range=60)],
        languages=[Language.COMMON, Language.GOBLIN],
        special_traits=["Nimble Escape: The goblin can take the Disengage or Hide action as a bonus action on each of its turns."],
        hit_dice=Dice(dice_count=2, dice_value=6, modifier=0),
        action_economy=ActionEconomy(speed=30)
    )

    # Set skill proficiency
    goblin.set_skill_proficiency(Skills.STEALTH)

    # Equip armor and shield
    leather_armor = Armor(name="Leather Armor", type=ArmorType.LIGHT, base_ac=11, dex_bonus=True)
    goblin.equip_armor(leather_armor)
    shield = Shield(name="Shield", ac_bonus=2)
    goblin.equip_shield(shield)

    # Add weapons
    scimitar = Weapon(
        name="Scimitar",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.SLASHING),
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.FINESSE],
        range=Range(type=RangeType.REACH, normal=5)
    )
    goblin.add_weapon(scimitar)

    shortbow = Weapon(
        name="Shortbow",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.RANGED_WEAPON,
        properties=[WeaponProperty.RANGED],
        range=Range(type=RangeType.RANGE, normal=80, long=320)
    )
    goblin.add_weapon(shortbow)

    # Add Nimble Escape action
    goblin.add_action(GoblinNimbleEscape(stats_block=goblin))

    return goblin

def print_goblin_details(goblin: StatsBlock):
    print("\nGoblin Details:")
    print(f"Name: {goblin.name}")
    print(f"Size: {goblin.size.value}")
    print(f"Type: {goblin.type.value}")
    print(f"Alignment: {goblin.alignment.value}")
    print("Ability Scores:")
    for ability in Ability:
        score = getattr(goblin.ability_scores, ability.value.lower())
        print(f"  {ability.value}: {score.score.get_value(goblin)} (Modifier: {score.get_modifier(goblin)})")
    print(f"Speed: Walk {goblin.speed.walk.get_value(goblin)} ft")
    print(f"Armor Class: {goblin.armor_class.get_value(goblin)}")
    print(f"Hit Points: {goblin.current_hit_points}/{goblin.max_hit_points}")
    print(f"Proficiency Bonus: +{goblin.proficiency_bonus}")
    print("Skills:")
    for skill in Skills:
        skill_obj = goblin.skills.get_skill(skill)
        if skill_obj.proficient:
            print(f"  {skill.value}: +{skill_obj.get_bonus(goblin)}")
    print("Senses:")
    for sense in goblin.senses:
        print(f"  {sense.type.value}: {sense.range} ft")
    print(f"Languages: {', '.join([lang.value for lang in goblin.languages])}")
    print(f"Challenge Rating: {goblin.challenge} ({goblin.experience_points} XP)")
    print("Special Traits:")
    for trait in goblin.special_traits:
        print(f"  {trait}")
    print("Actions:")
    for action in goblin.actions:
        if isinstance(action, Attack):
            print(f"  {action.action_docstring()}")
        else:
            print(f"  {action.name}: {action.description}")
    print(f"Equipment: {', '.join([weapon.name for weapon in goblin.weapons])}, "
          f"{goblin.armor_class.equipped_armor.name if goblin.armor_class.equipped_armor else 'No Armor'}, "
          f"{goblin.armor_class.equipped_shield.name if goblin.armor_class.equipped_shield else 'No Shield'}")

def main():
    goblin = create_goblin()
    print_goblin_details(goblin)

if __name__ == "__main__":
    main()