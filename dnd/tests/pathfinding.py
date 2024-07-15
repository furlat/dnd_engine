from dnd.battlemap import BattleMap

# Define the map as a string
map_str = '''
##################
#................#
#...###..........#
#...###....#.....#
#...###....#.....#
#..........#.....#
##################
'''[1:] # Use [1:] to remove the first newline

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

# Define start position
start_position = (1, 1)

# Visualize absolute distances
print("Absolute distances visualization:")
print(battle_map.visualize_absolute_distances(start_position))

# Define start and end positions
start_position = (1, 1)
end_position = (14, 5)

# Visualize Dijkstra distances
print("\nDijkstra distances visualization:")
print(battle_map.visualize_dijkstra_distances(start_position))

print("\n")

# Visualize Dijkstra path
print("Dijkstra path visualization:")
print(battle_map.visualize_dijkstra_path(start_position, end_position))
