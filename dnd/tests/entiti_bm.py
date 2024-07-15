from dnd.battlemap import BattleMap, Entity
from dnd.statsblock import StatsBlock

# Define the map as a string
map_str = '''
##################
#................#
#...###..........#
#...###....#.....#
#...###....#.....#
#..........#.....#
##################
'''[1:]  # Use [1:] to remove the first newline

width = 18
height = 7

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

# Define entities
entity1 = Entity(id="entity1")
entity2 = Entity(id="entity2")

# Add entities to the battle map
battle_map.add_entity(entity1, (1, 1))
battle_map.add_entity(entity2, (12, 5))

# Move entity1
battle_map.move_entity(entity1, (3, 3))

# Print the current state of the battle map
print(battle_map)

# Visualize the line of sight for entity1
print("Line of sight for entity1:")
battle_map.visualize_los(entity1.get_position())

# Visualize absolute distances from entity1
print("Absolute distances from entity1:")
print(battle_map.visualize_absolute_distances(entity1.get_position()))

# Visualize Dijkstra distances from entity1
print("Dijkstra distances from entity1:")
print(battle_map.visualize_dijkstra_distances(entity1.get_position()))

# Visualize Dijkstra path from entity1 to entity2
print("Dijkstra path from entity1 to entity2:")
print(battle_map.visualize_dijkstra_path(entity1.get_position(), entity2.get_position()))
