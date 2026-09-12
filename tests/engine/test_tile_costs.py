"""Compact terrain costs retain the existing modifier and authoring contracts."""

from typing import Any
from uuid import UUID, uuid4

import pytest

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import Tile
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ContextualNumericalModifier, NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import MovementMode
from dnd.world_authoring import project_world_tile, set_world_tile


def test_ordinary_tile_queries_allocate_no_modifier_graphs() -> None:
    """Untouched terrain creates only its Tile identity, including after reads."""
    reset_engine_runtime()
    blocks = set(BaseBlock._registry)
    values = set(BaseValue._registry)
    objects = set(BaseObject._registry)

    tile = Tile.create((0, 0), walking_cost=2, flying_cost=3)

    assert tuple(tile.get_movement_cost(mode) for mode in MovementMode) == (2, 3, 0, 0)
    assert not tile.blocks_walking(mode=MovementMode.WALKING)
    assert tile.blocks_walking(mode=MovementMode.SWIMMING)
    assert set(BaseBlock._registry) == blocks | {tile.uuid}
    assert set(BaseValue._registry) == values
    assert set(BaseObject._registry) == objects


@pytest.mark.parametrize("mode", tuple(MovementMode))
@pytest.mark.parametrize("base", (0, 2))
def test_movement_edits_preserve_mode_caps_and_removable_identity(
    mode: MovementMode, base: int,
) -> None:
    """Each mode remains independent; blocked ground modes keep their zero cap."""
    reset_engine_runtime()
    tile = Tile.create(
        (0, 0), walking_cost=base, flying_cost=base,
        swimming_cost=base, burrowing_cost=base,
    )
    sibling = Tile.create((1, 0))
    sibling_costs = tuple(sibling.get_movement_cost(item) for item in MovementMode)
    value = tile.edit_movement_cost(mode)
    modifier_uuid = value.self_static.add_value_modifier(NumericalModifier.create(
        source_entity_uuid=tile.uuid, name="Terrain effect", value=3,
    ))

    expected = 0 if base == 0 and mode is not MovementMode.FLYING else base + 3
    assert tile.get_movement_cost(mode) == expected
    assert all(tile.get_movement_cost(other) == base for other in MovementMode if other is not mode)
    assert tuple(sibling.get_movement_cost(item) for item in MovementMode) == sibling_costs
    assert tile.edit_movement_cost(mode) is value
    assert value.source_entity_uuid == tile.uuid
    retained = ModifiableValue.get(value.uuid)
    assert retained is not None
    assert retained is value

    retained.remove_modifier(modifier_uuid)

    assert tile.get_movement_cost(mode) == base
    assert tile.edit_movement_cost(mode) is retained
    assert ModifiableValue.get(value.uuid) is retained


def test_movement_promotion_preserves_current_and_later_context_and_target() -> None:
    """A contextual modifier sees the same Tile metadata before and after promotion."""
    reset_engine_runtime()
    tile = Tile.create((0, 0))
    target = uuid4()
    tile.set_target_entity(target, "Walker")
    tile.set_context({"terrain_effect": True})
    value = tile.edit_movement_cost(MovementMode.WALKING)
    bonus = NumericalModifier.create(source_entity_uuid=tile.uuid, value=3)
    no_bonus = NumericalModifier.create(source_entity_uuid=tile.uuid, value=0)

    def terrain_effect(
        source_uuid: UUID, target_uuid: UUID | None, context: dict[str, Any] | None,
    ) -> NumericalModifier:
        applies = source_uuid == tile.uuid and target_uuid == target and context == {"terrain_effect": True}
        return bonus if applies else no_bonus

    value.self_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=tile.uuid, callable=terrain_effect,
    ))

    assert tile.get_movement_cost(MovementMode.WALKING) == 4
    tile.clear_target_entity()
    assert tile.get_movement_cost(MovementMode.WALKING) == 1
    tile.set_target_entity(target, "Walker")
    assert tile.get_movement_cost(MovementMode.WALKING) == 4
    tile.clear_context()
    assert tile.get_movement_cost(MovementMode.WALKING) == 1
    tile.set_context({"terrain_effect": True})
    assert tile.get_movement_cost(MovementMode.WALKING) == 4


def test_terrain_authoring_compares_base_while_world_projection_reports_effective_cost() -> None:
    """Reapplying authored terrain must preserve an active cost modifier and its owner."""
    reset_engine_runtime()
    tile = get_map().set_tile(0, 0, fire_event=False)
    value = tile.edit_movement_cost(MovementMode.WALKING)
    value.self_static.add_value_modifier(NumericalModifier.create(
        source_entity_uuid=tile.uuid, name="Difficult terrain", value=1,
    ))
    cursor = EventQueue.event_cursor()

    assert project_world_tile(tile).walking_cost == 2
    assert set_world_tile((0, 0), author_uuid=uuid4(), surface=tile.surface) is None
    assert EventQueue.event_cursor() == cursor
    assert get_map().get_tile(0, 0) is tile
    assert tile.get_movement_cost(MovementMode.WALKING) == 2
    assert ModifiableValue.get(value.uuid) is value
