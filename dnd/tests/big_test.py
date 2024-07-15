from dnd.battlemap import BattleMap, Entity, MapDrawer
from dnd.statsblock import StatsBlock
from dnd.equipment import Weapon
from dnd.actions import Attack, MovementAction, Range, Damage
from dnd.dnd_enums import AttackType, WeaponProperty, DamageType, RangeType
from dnd.core import Dice

# Define the map as a string
map_str = '''
####################
#........#.........#
#...###..#....#....#
#...###..#....#....#
#...###..#....#....#
#........#....#....#
#........#....#....#
#........#....#....#
####################
'''[1:]  # Use [1:] to remove the first newline

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

# Create a MapDrawer instance
map_drawer = MapDrawer(battle_map)

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
    damage=Damage(dice=Dice(dice_count=1, dice_value=6, modifier=0),type=DamageType.PIERCING),
    attack_type=AttackType.RANGED_WEAPON,
    properties=[],
    range=Range(type=RangeType.REACH, normal=80, long=320)
)

# Define entities
warrior = Entity(id="warrior", name="Warrior", weapons=[sword])
archer = Entity(id="archer", name="Archer", weapons=[bow])

# Add entities to the battle map
battle_map.add_entity(warrior, (1, 1))
battle_map.add_entity(archer, (18, 7))

# Print the initial state of the battle map
print("Initial Battle Map:")
print(map_drawer.print_ascii_map())

# Move the warrior
warrior_path = battle_map.compute_dijkstra(warrior.get_position())[1][(8, 4)]
battle_map.move_entity(warrior, (8, 4))

print("\nAfter Warrior's Movement:")
print(map_drawer.print_ascii_map())

# Visualize the line of sight for the warrior
print("\nWarrior's Line of Sight:")
map_drawer.visualize_los(warrior)

# Visualize Dijkstra distances from the archer
print("\nDijkstra Distances from Archer:")
print(map_drawer.visualize_dijkstra_distances(archer.get_position()))

# Visualize Dijkstra path from archer to warrior
print("\nDijkstra Path from Archer to Warrior:")
print(map_drawer.visualize_dijkstra_path(archer.get_position(), warrior.get_position()))

# Print available actions for both entities
print("\nWarrior's Available Actions:")
warrior.update_available_actions()
for action in warrior.actions:
    if isinstance(action, Attack):
        print(f"- {action.action_docstring()}")
    elif isinstance(action, MovementAction):
        print(f"- {action.name}")

print("\nArcher's Available Actions:")
archer.update_available_actions()
for action in archer.actions:
    if isinstance(action, Attack):
        print(f"- {action.action_docstring()}")
    elif isinstance(action, MovementAction):
        print(f"- {action.name}")

# Simulate an attack
if any(isinstance(action, Attack) for action in archer.actions):
    attack_action = next(action for action in archer.actions if isinstance(action, Attack))
    result = attack_action.apply(warrior)
    print("\nArcher's Attack Result:")
    for success, message in result:
        print(message)

# Update entities' senses after the action
battle_map.update_entity_senses(warrior)
battle_map.update_entity_senses(archer)

print("\nFinal Battle Map State:")
print(map_drawer.print_ascii_map())