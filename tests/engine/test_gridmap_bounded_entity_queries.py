"""GridMap box and radius reads return exactly the deployed entities a world filter would.

Boundary: public GridMap reads over committed Tile membership.
Inputs: creatures in every life state around spatial chunk borders, then moved across one.
Output: the same ordered uuids as a brute-force filter of the registry by deployment,
inclusive bounds or range admission's distance, ordered by (position, str(uuid)).
"""

from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import SPATIAL_CHUNK_SIZE, get_map
from dnd.core.creature_types import DamageType
from dnd.core.life_types import LifeState, RemainsDisposition
from dnd.entity import Entity
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena

BORDER = SPATIAL_CHUNK_SIZE
BOUNDS = (
    (BORDER - 2, BORDER - 2, BORDER + 1, BORDER + 1),
    (BORDER, 0, BORDER, 3 * BORDER - 1),
    (0, 0, 3 * BORDER - 1, 3 * BORDER - 1),
    (-4, -4, 2, 2),
    (2 * BORDER - 1, BORDER - 1, 2 * BORDER, BORDER),
    (5, 5, 4, 4),
)
RADII = (
    ((BORDER, BORDER), 30),
    ((BORDER - 1, BORDER - 1), 5),
    ((BORDER - 1, BORDER - 1), 7),
    ((2 * BORDER - 1, BORDER), 60),
    ((0, 0), 300),
    ((BORDER + 1, BORDER), 0),
)


def check() -> None:
    grid = get_map()
    members = sorted((entity for entity in Entity.get_all_entities() if entity.is_deployed),
                     key=lambda entity: (entity.position, str(entity.uuid)))
    for min_x, min_y, max_x, max_y in BOUNDS:
        expected = tuple(entity.uuid for entity in members
                         if min_x <= entity.position[0] <= max_x and min_y <= entity.position[1] <= max_y)
        assert grid.get_entities_in_bounds((min_x, min_y, max_x, max_y)) == expected, (min_x, min_y, max_x, max_y)
    for center, radius_feet in RADII:
        expected = tuple(entity.uuid for entity in members
                         if grid_distance_feet(center, entity.position) <= radius_feet)
        assert grid.get_entities_within(center, radius_feet) == expected, (center, radius_feet)


def test_box_and_radius_reads_equal_a_brute_force_filter_across_chunks_and_life_states() -> None:
    reset_spell_regression_arena(3 * BORDER, 3 * BORDER)
    positions = [(BORDER - 1, BORDER - 1), (BORDER, BORDER - 1), (BORDER - 1, BORDER), (BORDER, BORDER),
                 (BORDER + 1, BORDER), (2 * BORDER - 1, BORDER), (2 * BORDER, BORDER), (0, 0), (1, 1),
                 (3 * BORDER - 1, 3 * BORDER - 1), (BORDER, 2 * BORDER + 3)]
    actors = [create_spell_regression_actor(f"Creature {index}", position, "heroes" if index % 2 else "monsters")
              for index, position in enumerate(positions)]
    dying, dead, disintegrated, suspended = actors[1], actors[3], actors[5], actors[6]
    dying.uses_death_saves = True
    dying.receive_damage(dying.get_hp(), DamageType.FORCE, actors[0].uuid)
    dead.receive_damage(1000, DamageType.FORCE, actors[0].uuid)
    disintegrated.receive_damage(1000, DamageType.FORCE, actors[0].uuid,
                                 zero_hp_disposition=RemainsDisposition.DISINTEGRATED)
    suspended.suspend_spatial_presence()
    assert dying.health.life_state is LifeState.DYING and dead.health.life_state is LifeState.DEAD
    assert dead.is_deployed and not suspended.is_deployed
    check()
    Entity.update_entity_position(actors[4], (BORDER + 2, BORDER - 1))
    Entity.update_entity_position(actors[0], (BORDER, BORDER + 1))
    check()
