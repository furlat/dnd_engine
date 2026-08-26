"""Engine semantic tests for object identity and registries."""

import pytest
from uuid import uuid4
from pydantic import ValidationError

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.positioning import PositionCommitError
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import Senses, capture_senses_snapshot
from dnd.core.base_tiles import Tile
from dnd.content.monsters.monster_builders import create_monster
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.game import Game
from dnd.core.values import (
    BaseValue,
    ContextualValue,
    ModifiableValue,
    StaticValue,
)
from dnd.entities.entity import Entity, EntityConfig
from dnd.types.materials import Material, TileSurface
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.types.world import LightLevel
from dnd.spatial.area_conditions import SpatialCondition
from tests.engine.support import create_test_entity, reset_combat_state


class RegistryProbe(BaseObject):
    """Small concrete object used to isolate BaseObject registry behavior."""


class OtherRegistryProbe(BaseObject):
    """Second concrete object used to verify typed registry lookup."""


def reset_identity_state() -> None:
    """Clear the global state touched by these registry examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()


def test_slice_6_1_position_owners_are_strict_and_base_blocks_are_neutral() -> None:
    """The objective-position cut leaves only explicit strict owners."""
    reset_identity_state()
    source_uuid = uuid4()
    surface = TileSurface(base_material=Material.STONE)
    condition_ref = ContentRef(
        pack_id="test.pack",
        definition_kind=ContentDefinitionKind.SPATIAL_EFFECT,
        content_id="spatial.position_probe",
        content_version=1,
        definition_contract_hash="0" * 64,
    )

    tile = Tile(
        source_entity_uuid=source_uuid,
        surface=surface,
        position=(1, 2),
    )
    entity = Entity(source_entity_uuid=source_uuid, position=(3, 4))
    senses = Senses(source_entity_uuid=source_uuid, position=(5, 6))
    condition = SpatialCondition(
        source_entity_uuid=source_uuid,
        content_ref=condition_ref,
        position=(7, 8),
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        use_register=False,
    )
    config = EntityConfig(position=(9, 10))

    assert tile.get_position() == (1, 2)
    assert entity.get_position() == (3, 4)
    assert senses.get_position() == (5, 6)
    assert condition.get_position() == (7, 8)
    assert config.position == (9, 10)

    for owner_factory in (
        lambda value: Tile(
            source_entity_uuid=source_uuid,
            surface=surface,
            position=value,
        ),
        lambda value: Entity(source_entity_uuid=source_uuid, position=value),
        lambda value: Senses(source_entity_uuid=source_uuid, position=value),
        lambda value: SpatialCondition(
            source_entity_uuid=source_uuid,
            content_ref=condition_ref,
            position=value,
            layer=SpatialEffectLayer.FIELD,
            occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
            use_register=False,
        ),
        lambda value: EntityConfig(position=value),
    ):
        for invalid_position in ((True, 2), (1.5, 2), ("1", 2)):
            with pytest.raises(ValidationError):
                owner_factory(invalid_position)

    base_block = BaseBlock(source_entity_uuid=source_uuid)
    floor_item = BaseItem(source_entity_uuid=source_uuid)
    contained_item = BaseItem(
        source_entity_uuid=source_uuid,
        owner_uuid=base_block.uuid,
    )
    assert base_block.get_position() is None
    assert floor_item.get_position() is None
    assert contained_item.get_position() is None
    assert "position" not in BaseItem.model_fields
    assert "position" not in floor_item.model_dump()
    with pytest.raises(ValidationError):
        BaseItem(source_entity_uuid=source_uuid, position=(1, 2))
    assert not hasattr(BaseBlock, "set_position")


@pytest.mark.parametrize("invalid_x, invalid_y", ((True, 2), (1.5, 2), ("1", 2)))
def test_set_tile_rejects_non_exact_coordinates_before_any_public_change(
    invalid_x: object,
    invalid_y: object,
) -> None:
    """Tile admission rejects coercible coordinates before the candidate moves."""
    reset_identity_state()
    grid = get_map()
    candidate = Tile.create(
        position=(1, 1),
        surface=TileSurface(base_material=Material.STONE),
    )
    before_tiles = grid.get_all_tiles()
    before_candidate = (
        candidate.uuid,
        candidate.get_position(),
        BaseBlock.get(candidate.uuid) is candidate,
        grid.get_tile_by_uuid(candidate.uuid),
    )
    before_revisions = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    before_cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="exact tuple"):
        grid.set_tile(
            invalid_x,
            invalid_y,
            tile=candidate,
        )

    assert grid.get_all_tiles() == before_tiles
    assert (
        candidate.uuid,
        candidate.get_position(),
        BaseBlock.get(candidate.uuid) is candidate,
        grid.get_tile_by_uuid(candidate.uuid),
    ) == before_candidate
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == before_revisions
    assert EventQueue.event_cursor() == before_cursor


def test_eb_01_001_base_object_registration_lifecycle() -> None:
    """EB-01-001: BaseObject registers by default and can opt out."""
    reset_identity_state()
    source_uuid = uuid4()

    registered = RegistryProbe(source_entity_uuid=source_uuid)
    assert RegistryProbe.get(registered.uuid) is registered
    assert registered.use_register is True

    transient = RegistryProbe(source_entity_uuid=source_uuid, use_register=False)
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False

    transient.add_to_register()
    assert RegistryProbe.get(transient.uuid) is transient
    assert transient.use_register is True

    transient.remove_from_register()
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False


def test_eb_01_002_base_object_lookup_is_typed() -> None:
    """EB-01-002: subclass lookup rejects another registered object type."""
    reset_identity_state()
    source_uuid = uuid4()

    other = OtherRegistryProbe(source_entity_uuid=source_uuid)

    try:
        RegistryProbe.get(other.uuid)
    except ValueError as error:
        assert "is not a RegistryProbe" in str(error)
    else:
        raise AssertionError("RegistryProbe.get() should reject OtherRegistryProbe")


def test_eb_01_003_value_and_block_registries_are_separate() -> None:
    """EB-01-003: values and blocks use registries separate from BaseObject."""
    reset_identity_state()
    source_uuid = uuid4()

    value = BaseValue(source_entity_uuid=source_uuid)
    block = BaseBlock(source_entity_uuid=source_uuid)

    assert BaseValue.get(value.uuid) is value
    assert BaseObject.get(value.uuid) is None

    assert BaseBlock.get(block.uuid) is block
    assert BaseValue.get(block.uuid) is None


def test_eb_01_004_entity_registers_as_block_and_entity() -> None:
    """EB-01-004: Entity creation populates block and entity registries."""
    reset_identity_state()
    get_map().create_rectangle(
        0,
        0,
        6,
        6,
        surface=TileSurface(base_material=Material.STONE),
    )
    entity_uuid = uuid4()
    config = EntityConfig(position=(2, 3))

    entity = create_test_entity(
        name="Registry Hero",
        config=config,
        entity_kind_id="test.registry_hero",
        source_id=entity_uuid,
    )

    assert Entity.get(entity_uuid) is entity
    assert BaseBlock.get(entity_uuid) is entity
    assert entity.uuid in get_map().get_entities_at((2, 3))

    Entity.update_entity_position(entity, (4, 5))

    assert entity.position == (4, 5)
    assert entity.senses.position == (4, 5)
    assert entity.uuid not in get_map().get_entities_at((2, 3))
    assert entity.uuid in get_map().get_entities_at((4, 5))


def test_entity_tile_membership_is_defensive_and_co_located_noop_is_quiet() -> None:
    """Tile membership admits co-location and exposes only defensive reads."""
    reset_identity_state()
    get_map().create_rectangle(
        0,
        0,
        6,
        6,
        surface=TileSurface(base_material=Material.STONE),
    )
    first = create_test_entity(
        name="First co-located",
        config=EntityConfig(position=(2, 3)),
        entity_kind_id="test.first_co_located",
    )
    second = create_test_entity(
        name="Second co-located",
        config=EntityConfig(position=(2, 3)),
        entity_kind_id="test.second_co_located",
    )
    grid = get_map()

    expected = {first.uuid, second.uuid}
    assert grid.get_entities_at((2, 3)) == expected
    assert grid.get_entity_position(first.uuid) == (2, 3)
    snapshot = grid.get_tile(2, 3).get_entity_uuids()
    snapshot.clear()
    assert grid.get_entities_at((2, 3)) == expected

    revision = grid.occupancy_revision
    cursor = EventQueue.event_cursor()
    Entity.update_entity_position(first, first.position)
    assert grid.occupancy_revision == revision
    assert EventQueue.event_cursor() == cursor
    assert grid.get_entities_at((2, 3)) == expected


def test_public_entity_lifecycle_revision_deltas_are_exact() -> None:
    """Real occupancy transitions bump once; no-op and rejected transitions do not."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        8,
        8,
        surface=TileSurface(base_material=Material.STONE),
    )
    game = Game()
    entity = create_monster("creature.commoner", uuid4(), faction="heroes")

    before_deploy = grid.occupancy_revision
    game.deploy_entity(entity, (1, 1))
    assert grid.occupancy_revision == before_deploy + 1

    before_noop = grid.occupancy_revision
    Entity.update_entity_position(entity, entity.position)
    assert grid.occupancy_revision == before_noop

    before_move = grid.occupancy_revision
    Entity.update_entity_position(entity, (2, 1))
    assert grid.occupancy_revision == before_move + 1

    grid.remove_tile(3, 1)
    before_rejected = grid.occupancy_revision
    with pytest.raises(PositionCommitError):
        Entity.update_entity_position(entity, (3, 1))
    assert grid.occupancy_revision == before_rejected
    assert entity.position == (2, 1)

    grid.set_tile(
        3,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    before_suspend = grid.occupancy_revision
    entity.suspend_spatial_presence()
    assert grid.occupancy_revision == before_suspend + 1

    before_restore = grid.occupancy_revision
    entity.restore_spatial_presence((3, 1))
    assert grid.occupancy_revision == before_restore + 1

    before_detach = grid.occupancy_revision
    assert game.remove_entity(entity.uuid) is entity
    assert grid.occupancy_revision == before_detach + 1


def test_entity_membership_has_no_block_route_and_rejects_live_tile_mutations() -> None:
    """Only Entity commands can create membership, and live support is protected."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        5,
        5,
        surface=TileSurface(base_material=Material.STONE),
    )
    entity = create_test_entity(
        name="Protected occupancy",
        config=EntityConfig(position=(2, 2)),
        entity_kind_id="test.protected_occupancy",
    )
    arbitrary_block = BaseBlock(source_entity_uuid=uuid4())

    assert arbitrary_block.uuid not in grid.get_entities_at((2, 2))
    assert not hasattr(grid, "register_entity")
    assert not hasattr(grid.get_tile(2, 2), "add_entity")

    replacement = TileSurface(base_material=Material.WATER)
    with pytest.raises(ValueError, match="entity occupancy"):
        grid.set_tile(2, 2, surface=replacement)
    with pytest.raises(ValueError, match="entities are deployed"):
        grid.clear()

    assert grid.get_entity_position(entity.uuid) == (2, 2)
    assert grid.get_entities_at((2, 2)) == {entity.uuid}


def test_missing_tile_move_is_publicly_atomic_for_occupancy_events_light_and_senses() -> None:
    """A rejected destination changes no objective, sensory, or light fact."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        5,
        5,
        surface=TileSurface(base_material=Material.STONE),
    )
    entity = create_test_entity(
        name="Missing destination",
        config=EntityConfig(position=(2, 2)),
        entity_kind_id="test.missing_destination",
    )
    grid.set_tile_base_light((2, 2), LightLevel.DARKNESS)
    before_senses = capture_senses_snapshot(entity.senses)
    before_position = entity.position
    before_membership = grid.get_entities_at(before_position)
    before_revision = grid.occupancy_revision
    before_cursor = EventQueue.event_cursor()
    before_light = grid.get_tile(*before_position).resolved_light_level
    grid.remove_tile(3, 2)
    before_senses = capture_senses_snapshot(entity.senses)
    before_cursor = EventQueue.event_cursor()

    with pytest.raises(PositionCommitError):
        Entity.update_entity_position(entity, (3, 2))

    assert entity.position == before_position
    assert grid.get_entity_position(entity.uuid) == before_position
    assert grid.get_entities_at(before_position) == before_membership
    assert grid.occupancy_revision == before_revision
    assert EventQueue.event_cursor() == before_cursor
    assert grid.get_tile(*before_position).resolved_light_level is before_light
    assert capture_senses_snapshot(entity.senses) == before_senses


def test_suspended_entity_keeps_game_identity_without_observer_or_second_left() -> None:
    """Suspension is world absence; suspended detach is a quiet ownership removal."""
    reset_identity_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        12,
        12,
        surface=TileSurface(base_material=Material.STONE),
    )
    game = Game()
    observer = create_monster("creature.commoner", uuid4(), faction="heroes")
    target = create_monster("creature.commoner", uuid4(), faction="monsters")
    game.deploy_entity(observer, (4, 4))
    game.deploy_entity(target, (5, 4))
    light_uuid = grid.add_light_source(
        target.position,
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=target.uuid,
    )
    retained_position = target.position
    revision_before = grid.occupancy_revision
    cursor_before = EventQueue.event_cursor()

    assert target.uuid in observer.senses.entities
    assert grid.get_entity_subscriptions(target.uuid)
    target.suspend_spatial_presence()

    left_events = [
        event
        for _, event in EventQueue.iter_events_since(cursor_before)
        if (
            event.event_type == EventType.SPATIAL_ENTITY_LEFT
            and event.phase.value == "completion"
        )
    ]
    assert len(left_events) == 1
    assert target.position == retained_position
    assert target.uuid not in grid.get_entities_at(retained_position)
    assert grid.get_entity_position(target.uuid) is None
    assert game.get_entity(target.uuid) is target
    assert target.uuid not in observer.senses.entities
    assert grid.get_entity_subscriptions(target.uuid) == set()
    assert target.get_attached_light_sources() == {light_uuid}
    assert grid.occupancy_revision == revision_before + 1

    cursor_after_suspend = EventQueue.event_cursor()
    assert game.remove_entity(target.uuid) is target
    assert game.get_entity(target.uuid) is None
    assert grid.get_entity_position(target.uuid) is None
    assert EventQueue.event_cursor() == cursor_after_suspend
    assert grid.occupancy_revision == revision_before + 1


def test_entity_membership_queries_are_map_size_invariant_at_public_boundary() -> None:
    """Small and large maps expose the same occupancy result and revision delta."""
    observations = []
    for size in (8, 40):
        reset_identity_state()
        grid = get_map()
        grid.create_rectangle(
            0,
            0,
            size,
            size,
            surface=TileSurface(base_material=Material.STONE),
        )
        entity = create_test_entity(
            name=f"Locality entity {size}",
            config=EntityConfig(position=(2, 2)),
            entity_kind_id=f"test.locality_{size}",
        )
        before_revision = grid.occupancy_revision
        observations.append(
            (
                grid.get_entities_at((2, 2)),
                grid.get_entities_at((size - 1, size - 1)),
                grid.get_entity_position(entity.uuid),
                grid.occupancy_revision - before_revision,
            )
        )

    assert len(observations[0][0]) == len(observations[1][0]) == 1
    assert observations[0][1] == observations[1][1] == set()
    assert observations[0][2:] == observations[1][2:] == ((2, 2), 0)


def test_eb_01_005_value_subclass_lookup_contracts() -> None:
    """EB-01-005: value subclasses share one registry but differ on misses."""
    reset_identity_state()
    source_uuid = uuid4()

    static_value = StaticValue(source_entity_uuid=source_uuid)
    contextual_value = ContextualValue(source_entity_uuid=source_uuid)
    modifiable_value = ModifiableValue.create(source_entity_uuid=source_uuid)

    assert BaseValue.get(static_value.uuid) is static_value
    assert BaseValue.get(contextual_value.uuid) is contextual_value
    assert BaseValue.get(modifiable_value.uuid) is modifiable_value

    assert StaticValue.get(static_value.uuid) is static_value
    assert ContextualValue.get(contextual_value.uuid) is contextual_value
    assert ModifiableValue.get(modifiable_value.uuid) is modifiable_value

    try:
        StaticValue.get(contextual_value.uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
    else:
        raise AssertionError("StaticValue.get() should reject ContextualValue")

    try:
        ContextualValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ContextualValue" in str(error)
    else:
        raise AssertionError("ContextualValue.get() should reject StaticValue")

    try:
        ModifiableValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ModifiableValue" in str(error)
    else:
        raise AssertionError("ModifiableValue.get() should reject StaticValue")

    missing_uuid = uuid4()
    assert BaseValue.get(missing_uuid) is None
    assert ContextualValue.get(missing_uuid) is None
    assert ModifiableValue.get(missing_uuid) is None

    try:
        StaticValue.get(missing_uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
        assert "NoneType" in str(error)
    else:
        raise AssertionError("StaticValue.get() should raise on missing UUID")


if __name__ == "__main__":
    test_eb_01_001_base_object_registration_lifecycle()
    test_eb_01_002_base_object_lookup_is_typed()
    test_eb_01_003_value_and_block_registries_are_separate()
    test_eb_01_004_entity_registers_as_block_and_entity()
    test_eb_01_005_value_subclass_lookup_contracts()
    print("PASS: engine book registry tests")
