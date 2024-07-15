from dnd.battlemap import BattleMap
from dnd.shadowcast import compute_fov

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

# Define positions to test FOV
test_positions = [(9, 3), (1, 1), (5, 5)]

# Function to determine if a tile is blocking
def is_blocking(x, y):
    return battle_map.is_blocking(x, y)

# Function to visualize the FOV from a given position
def visualize_fov(position):
    is_visible = set()
    def reveal(x, y):
        is_visible.add((x, y))

    compute_fov(position, is_blocking, reveal)

    print(f"Map with line of sight from {position}:")
    print(battle_map.print_ascii_map(highlight_los=is_visible))

# Visualize FOV from each test position
for pos in test_positions:
    visualize_fov(pos)
    print("\n")