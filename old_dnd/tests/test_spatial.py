import pytest
from old_dnd.spatial import RegistryHolder, BaseSpatial, FOV, DistanceMatrix, Path, Paths
from typing import Dict, Set, Tuple

# Mock BattleMap for testing
class MockBattleMap(RegistryHolder):
    def __init__(self, id: str, positions: Dict[Tuple[int, int], Set[str]]):
        self.id = id
        self.positions = positions
        self.register(self, id)

@pytest.fixture
def mock_battlemap():
    positions = {
        (0, 0): {"entity1"},
        (1, 1): {"entity2"},
        (2, 2): {"entity3"},
    }
    return MockBattleMap("test_battlemap", positions)

class TestRegistryHolder:
    def test_register_and_get_instance(self, mock_battlemap):
        assert RegistryHolder.get_instance("test_battlemap") == mock_battlemap

    def test_all_instances(self, mock_battlemap):
        instances = RegistryHolder.all_instances()
        assert mock_battlemap in instances

    def test_all_types(self, mock_battlemap):
        types = RegistryHolder.all_types()
        assert "MockBattleMap" in types

class TestFOV:
    @pytest.fixture
    def fov(self, mock_battlemap):
        return FOV(battlemap_id="test_battlemap", origin=(0, 0), visible_tiles={(0, 0), (1, 1), (2, 2)})

    def test_is_visible(self, fov):
        assert fov.is_visible((0, 0))  # Source position
        assert fov.is_visible((1, 1))
        assert fov.is_visible((2, 2))
        assert not fov.is_visible((3, 3))

    def test_get_visible_positions(self, fov):
        assert set(fov.get_visible_positions()) == {(0, 0), (1, 1), (2, 2)}

    def test_get_visible_entities(self, fov):
        assert set(fov.get_visible_entities()) == {"entity1", "entity2", "entity3"}

    def test_get_positions_in_range(self, fov):
        result = set(fov.get_positions_in_range(5))
        print(f"Visible tiles: {fov.visible_tiles}")
        print(f"Positions in range 5: {result}")
        assert result == {(0, 0), (1, 1), (2, 2)}

    def test_get_entities_in_range(self, fov):
        result = set(fov.get_entities_in_range(5))
        print(f"Entities in range 5: {result}")
        assert result == {"entity1", "entity2", "entity3"}

    def test_bresenham(self):
        ray = FOV.bresenham((0, 0), (2, 2))
        assert ray == [(0, 0), (1, 1), (2, 2)]

    def test_get_ray_to(self, fov):
        assert fov.get_ray_to((0, 0)) == [(0, 0)]
        assert fov.get_ray_to((2, 2)) == [(0, 0), (1, 1), (2, 2)]
        assert fov.get_ray_to((3, 3)) is None

    def test_get_all_rays(self, fov):
        all_rays = fov.get_all_rays()
        assert all_rays == {
            (0, 0): [(0, 0)],
            (1, 1): [(0, 0), (1, 1)],
            (2, 2): [(0, 0), (1, 1), (2, 2)]
        }

class TestDistanceMatrix:
    @pytest.fixture
    def distance_matrix(self, mock_battlemap):
        return DistanceMatrix(
            battlemap_id="test_battlemap",
            origin=(0, 0),
            distances={(0, 0): 0, (1, 1): 1, (2, 2): 2}
        )

    def test_get_distance(self, distance_matrix):
        assert distance_matrix.get_distance((1, 1)) == 1
        assert distance_matrix.get_distance((3, 3)) is None

    def test_get_positions_within_distance(self, distance_matrix):
        assert set(distance_matrix.get_positions_within_distance(1)) == {(0, 0), (1, 1)}

    def test_get_entities_within_distance(self, distance_matrix):
        assert set(distance_matrix.get_entities_within_distance(1)) == {"entity1", "entity2"}

class TestPath:
    @pytest.fixture
    def path(self, mock_battlemap):
        return Path(battlemap_id="test_battlemap", origin=(0, 0), path=[(0, 0), (1, 1), (2, 2)])

    def test_get_path_length(self, path):
        assert path.get_path_length() == 2

    def test_is_valid_movement(self, path):
        assert path.is_valid_movement(2)
        assert not path.is_valid_movement(1)

    def test_get_entities_on_path(self, path):
        assert set(path.get_entities_on_path()) == {"entity1", "entity2", "entity3"}

class TestPaths:
    @pytest.fixture
    def paths(self, mock_battlemap):
        return Paths(
            battlemap_id="test_battlemap",
            origin=(0, 0),
            paths={
                (1, 1): [(0, 0), (1, 1)],
                (2, 2): [(0, 0), (1, 1), (2, 2)]
            }
        )

    def test_get_path_to(self, paths):
        assert paths.get_path_to((1, 1)) == [(0, 0), (1, 1)]
        assert paths.get_path_to((3, 3)) is None

    def test_get_reachable_positions(self, paths):
        assert set(paths.get_reachable_positions(1)) == {(1, 1)}
        assert set(paths.get_reachable_positions(2)) == {(1, 1), (2, 2)}

    def test_get_reachable_entities(self, paths):
        assert set(paths.get_reachable_entities(1)) == {"entity2"}
        assert set(paths.get_reachable_entities(2)) == {"entity2", "entity3"}

if __name__ == "__main__":
    pytest.main([__file__])
