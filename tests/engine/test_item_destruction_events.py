"""Physical breakage owns geometry and cleanup through one native lineage."""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.blocks.inventory import Inventory
from dnd.content.items.environment_item_builders import build_authored_door, build_oil_barrel
from dnd.core.base_block import BaseBlock
from dnd.core.creature_types import DamageType
from dnd.core.events import (
    EventPhase, EventQueue, ItemDestructionEvent, SpatialChangeEvent,
    SpatialChangeType, SpatialEffectChangeEvent, TakeDamageEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.residues import ASHEN_RESIDUE, ObjectResidueCondition
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection


@pytest.fixture
def world():
    reset_engine_runtime(grid_size=(5, 5))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def completed_since(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if event.phase is EventPhase.COMPLETION]


def test_destruction_is_the_causal_owner_of_physical_change_and_keeps_surface_state(world):
    door = build_authored_door("environment.door.desert_c7", hit_points=4)
    original = door.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    ash = ObjectResidueCondition(source_entity_uuid=door.uuid, target_entity_uuid=door.uuid,
        name="Ashen", description="Scorched wood", profile=ASHEN_RESIDUE,
        faces=(CardinalDirection.WEST,))
    assert door.add_condition(ash) is not None
    before = door.to_item_presentation_state()
    cursor = EventQueue.event_cursor()
    assert door.receive_damage(4, DamageType.BLUDGEONING, door.uuid) == 4
    completed = completed_since(cursor)
    destruction, = [event for event in completed if isinstance(event, ItemDestructionEvent)]
    damage, = [event for event in completed if isinstance(event, TakeDamageEvent)]
    geometry, = [event for event in completed if isinstance(event, SpatialChangeEvent)
                  and event.object_uuid == door.uuid]
    assert destruction.parent_lineage == damage.lineage_uuid
    assert geometry.parent_lineage == destruction.lineage_uuid
    assert geometry.change_type is SpatialChangeType.OBJECT_CHANGED
    assert destruction.previous_state.integrity is ItemIntegrity.INTACT
    assert destruction.previous_placement == original
    assert destruction.resulting_state.integrity is ItemIntegrity.DESTROYED
    assert destruction.resulting_state.item_uuid == door.uuid
    assert destruction.resulting_state.item_id == before.item_id
    assert destruction.resulting_state.surface_residues == before.surface_residues
    assert geometry.object_state.integrity is ItemIntegrity.DESTROYED
    assert geometry.object_boundary_structure.blocked_channels == ()
    assert get_map().can_transition((2, 2), (3, 2))
    assert BaseBlock.get(door.uuid) is door
    versions = [event.phase for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ItemDestructionEvent)]
    assert versions == [EventPhase.DECLARATION, EventPhase.EXECUTION,
                        EventPhase.EFFECT, EventPhase.COMPLETION]
    count = len(completed)
    assert door.receive_damage(4, DamageType.FIRE, door.uuid) == 0
    door.destroy()
    assert len(completed_since(cursor)) == count
    door.retire()
    assert BaseBlock.get(door.uuid) is None
    assert get_map().get_object_placement(door.uuid) is None


@pytest.mark.parametrize("damage_type", (DamageType.BLUDGEONING, DamageType.FIRE))
def test_barrel_spill_and_ignition_remain_descendants_of_destruction(world, damage_type):
    barrel = build_oil_barrel(uuid4())
    barrel.place_on_grid((2, 2))
    cursor = EventQueue.event_cursor()
    barrel.receive_damage(12, damage_type, barrel.uuid)
    events = completed_since(cursor)
    destruction, = [event for event in events if isinstance(event, ItemDestructionEvent)]
    assert destruction.damage_types == (damage_type,)
    assert destruction.resulting_state.integrity is ItemIntegrity.DESTROYED
    by_lineage = {event.lineage_uuid: event for event in events}
    consequences = [event for event in events if isinstance(event, SpatialEffectChangeEvent)]
    assert consequences
    for consequence in consequences:
        ancestor = consequence.parent_lineage
        while ancestor != destruction.lineage_uuid and ancestor in by_lineage:
            ancestor = by_lineage[ancestor].parent_lineage
        assert ancestor == destruction.lineage_uuid
    conditions = get_map().get_spatial_conditions()
    # Ignition transforms the spilled material through the existing spatial
    # interaction, so the burning result is Fire Surface rather than two areas.
    expected_material = "Fire Surface" if damage_type is DamageType.FIRE else "Oil Surface"
    assert {condition.name for condition in conditions} == {expected_material}


def test_persistent_carried_prop_keeps_its_container_while_terminal_disposal_has_no_break(world):
    # No equip/durability expansion: this explicitly authored breakable prop is
    # stored using the same public inventory contract as any other item.
    owner = uuid4()
    inventory = Inventory(source_entity_uuid=owner)
    prop = BaseItem(source_entity_uuid=owner, item_id="test.breakable_cup", name="Cup",
        is_targetable=True, health=BaseItem.create_item_health(owner, 2),
        destruction_profile=ItemDestructionProfile(name="Broken Cup", is_pickable=True))
    assert inventory.add_item(prop)
    prop.owner_uuid = owner
    prop.stored_in_uuid = inventory.uuid
    prop.receive_damage(2, DamageType.BLUDGEONING, owner)
    assert inventory.items[prop.uuid] is prop and prop.stored_in_uuid == inventory.uuid
    assert prop.integrity is ItemIntegrity.DESTROYED
    cursor = EventQueue.event_cursor()
    prop.retire()
    assert prop.uuid not in inventory.items and BaseBlock.get(prop.uuid) is None
    assert not any(isinstance(event, ItemDestructionEvent) for event in completed_since(cursor))


def test_initial_wreck_starts_inert_without_replaying_destruction(world):
    cursor = EventQueue.event_cursor()
    # The ordinary door composes its default Health and aftermath itself.
    door = DirectionalDoor(source_entity_uuid=uuid4(), item_id="environment.directional_door",
                           name="Door", integrity=ItemIntegrity.DESTROYED)
    door.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    state = door.to_item_presentation_state()
    assert state.name == "Broken Door"
    assert state.integrity is ItemIntegrity.DESTROYED
    assert state.current_hit_points == door.get_hp() == 0
    assert not state.is_targetable and not state.is_usable and not door.is_breakable()
    assert door.get_use_actions(uuid4()) == []
    assert get_map().can_transition((2, 2), (3, 2))
    assert not any(isinstance(event, ItemDestructionEvent) for event in completed_since(cursor))


def test_direct_destruction_resolves_durability_without_inventing_damage(world):
    door = build_authored_door("environment.door.desert_c7", hit_points=4)
    door.place_on_grid((2, 2), boundary_direction=CardinalDirection.EAST)
    cursor = EventQueue.event_cursor()
    door.destroy()
    events = completed_since(cursor)
    destruction, = [event for event in events if isinstance(event, ItemDestructionEvent)]
    assert destruction.previous_state.current_hit_points == 4
    assert destruction.resulting_state.current_hit_points == door.get_hp() == 0
    assert not any(isinstance(event, TakeDamageEvent) for event in events)
