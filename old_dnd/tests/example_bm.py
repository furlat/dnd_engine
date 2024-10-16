from old_dnd.monsters.goblin import create_goblin
from old_dnd.monsters.skeleton import create_skeleton
from old_dnd.battlemap import BattleMap, Entity
from old_dnd.statsblock import StatsBlock
from old_dnd.equipment import Weapon
from old_dnd.actions import Attack, MovementAction, Range, Damage
from old_dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType
from old_dnd.core import Dice

def create_battlemap_with_entities():
    # Define the map as a string
    map_str = '''
####################
#........#.........#
#...###..#....#....#
#...###..#....#....#
#...###..#....#....#
#........#....#....#
#.............#....#
#........#....#....#
####################
    '''.strip()  # Use strip() to remove the first and last newlines

    width = 20
    height = 9

    # Create a BattleMap instance
    battle_map = BattleMap(width=width, height=height)

    # Populate the map with tiles
    map_list = list(map_str.splitlines())
    for y, row in enumerate(map_list):
        for x, char in enumerate(row):
            if char == '#':
                battle_map.set_tile(x, y, "WALL")
            elif char == '.':
                battle_map.set_tile(x, y, "FLOOR")



    # Create entities
    goblin = create_goblin()
    skeleton = create_skeleton()

    # Define weapons
    sword = Weapon(
        name="Longsword",
        damage=Damage(dice=Dice(dice_count=1, dice_value=8, modifier=0), type=DamageType.SLASHING),
        attack_type=AttackType.MELEE_WEAPON,
        properties=[WeaponProperty.VERSATILE],
        range=Range(type=RangeType.REACH, normal=5)
    )

    bow = Weapon(
        name="Shortbow",
        damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0), type=DamageType.PIERCING),
        attack_type=AttackType.RANGED_WEAPON,
        properties=[],
        range=Range(type=RangeType.REACH, normal=80, long=320)
    )

    # Add entities to the battle map
    battle_map.add_entity(goblin, (18, 6))
    battle_map.add_entity(skeleton, (18, 7))

    return battle_map, goblin, skeleton
bm, goblin, skeleton = create_battlemap_with_entities()
