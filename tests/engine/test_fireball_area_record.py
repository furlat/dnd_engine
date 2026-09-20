"""Native area execution owns both creature damage and inert Ashen tile state."""

from collections.abc import Iterator

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventQueue, EventType
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.residues import ASHEN_RESIDUE, BLOOD_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import Fireball
from dnd.types.world import CardinalDirection
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.fixture
def caster() -> Iterator[Entity]:
    reset_spell_regression_arena(13, 13)
    actor = create_spell_regression_actor("Caster", (0, 0), "heroes", spell_slots={3: 3})
    register_spell(actor, Fireball, caster_level=5)
    yield actor
    reset_engine_runtime()


def cast_fireball(caster: Entity, position: tuple[int, int]) -> tuple[SpellEvent, tuple[Event, ...]]:
    Entity.update_all_entities_senses()
    available = get_available_actions(caster)
    action = next(row for row in available.all_actions if row.behavior_id == "spell.fireball")
    target = next(row for row in action.valid_targets if row.position == position)
    cursor = EventQueue.event_cursor()
    # Every creature rolls a failed save followed by eight damage dice of one.
    with fixed_dice_faces(*([1] * 30)):
        result = execute_available_action(caster, action, target)
    assert isinstance(result, SpellEvent) and not result.canceled
    events = tuple(event for _, event in EventQueue.iter_events_since(cursor)
                   if event.phase is EventPhase.COMPLETION)
    return result, events


def ashen_tiles() -> dict[tuple[int, int], tuple]:
    return {position: tuple(row for row in tile.to_world_tile_state().residues
                            if row.residue_id == ASHEN_RESIDUE.residue_id)
            for position, tile in get_map().get_all_tiles().items()
            if "Ashen" in tile.active_conditions}


def test_empty_visible_area_records_footprint_and_causal_tile_conditions(caster: Entity) -> None:
    revision = get_map().movement_revision
    result, events = cast_fireball(caster, (6, 6))
    expected = {(x, y) for x in range(2, 11) for y in range(2, 11)
                if (x - 6) ** 2 + (y - 6) ** 2 <= 16}
    assert result.total_targets == 0
    assert result.total_damage == 0
    assert result.resolved_area_positions == tuple(sorted(expected))
    assert set(ashen_tiles()) == expected
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 2
    assert get_map().movement_revision == revision
    applied = [event for event in events if event.event_type is EventType.CONDITION_APPLICATION]
    assert len(applied) == len(expected)
    assert all(event.parent_event is not None for event in applied)
    for event in applied:
        parent = EventQueue.get_event_by_uuid(event.parent_event)
        assert parent is not None and parent.lineage_uuid == result.lineage_uuid
    assert not any(isinstance(event, DamageAppliedEvent) for event in events)


def test_repeat_hit_preserves_residue_identity_and_other_tile_conditions(caster: Entity) -> None:
    tile = get_map().get_tile(6, 6)
    assert tile is not None
    blood = deposit_residue(tile, BLOOD_RESIDUE)
    cast_fireball(caster, tile.position)
    before = ashen_tiles()
    caster.on_turn_start()
    _, events = cast_fireball(caster, tile.position)
    assert ashen_tiles() == before
    assert blood in tile.to_world_tile_state().residues
    assert not any(event.event_type is EventType.CONDITION_APPLICATION for event in events)
    assert caster.action_economy.spell_slot_3.normalized_score == 1


def test_native_area_results_keep_independent_creature_saves_and_damage(caster: Entity) -> None:
    first = create_spell_regression_actor("First", (6, 6), "enemies")
    second = create_spell_regression_actor("Second", (7, 6), "enemies")
    before = first.get_hp(), second.get_hp()
    result, events = cast_fireball(caster, (6, 6))
    assert (first.get_hp(), second.get_hp()) == (before[0] - 8, before[1] - 8)
    assert result.total_targets == 2 and result.total_damage == 16
    children = [event for event in events if isinstance(event, SpellEvent) and event.application_id is not None]
    assert {event.target_entity_uuid for event in children} == {first.uuid, second.uuid}
    assert [event.application_index for event in children] == [0, 1]
    assert all(event.resolved_area_positions is None for event in children)
    assert {event.save_success for event in children} == {False}
    assert result.resolved_area_positions is not None
    assert set(ashen_tiles()) == set(result.resolved_area_positions)


@pytest.mark.parametrize("direction", (CardinalDirection.EAST, CardinalDirection.NORTH))
@pytest.mark.parametrize("door_open", (None, False, True), ids=("wall", "closed-door", "open-door"))
def test_area_and_ashen_stop_at_physical_boundaries(
    caster: Entity, direction: CardinalDirection, door_open: bool | None,
) -> None:
    barriers = []
    for offset in range(13):
        position = (7, offset) if direction is CardinalDirection.EAST else (offset, 7)
        if door_open is None:
            barrier = DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.wall")
        else:
            barrier = DirectionalDoor(source_entity_uuid=caster.uuid, item_id="test.door", is_open=door_open)
        barrier.place_on_grid(position, boundary_direction=direction)
        barriers.append(barrier)
    behind = (8, 6) if direction is CardinalDirection.EAST else (6, 8)
    target = create_spell_regression_actor("Behind", behind, "enemies")
    hp = target.get_hp()
    result, events = cast_fireball(caster, (6, 6))
    assert result.resolved_area_positions is not None
    reaches = door_open is True
    assert (behind in result.resolved_area_positions) is reaches
    assert (behind in ashen_tiles()) is reaches
    assert target.get_hp() == hp - (8 if reaches else 0)
    assert set(ashen_tiles()) == set(result.resolved_area_positions)
    contact = barriers[6]
    residue = contact.to_item_presentation_state().surface_residues
    near_face = CardinalDirection.WEST if direction is CardinalDirection.EAST else CardinalDirection.SOUTH
    assert len(residue) == 1 and residue[0].residue_id == ASHEN_RESIDUE.residue_id
    assert set(residue[0].faces) == ({near_face, direction} if reaches else {near_face})
    recorded = [event.resulting_item for event in events
                if isinstance(event, ConditionApplicationEvent) and event.target_entity_uuid == contact.uuid]
    assert len(recorded) == 1 and recorded[0] == contact.to_item_presentation_state()


def test_off_map_footprint_does_not_create_floor(caster: Entity) -> None:
    before = set(get_map().get_all_tiles())
    result, _ = cast_fireball(caster, (1, 6))
    assert result.resolved_area_positions is not None
    assert set(get_map().get_all_tiles()) == before
    assert set(ashen_tiles()) == set(result.resolved_area_positions) & before


def test_boundary_condition_remembers_both_contacted_sides_and_records_removal(caster: Entity) -> None:
    walls = []
    for y in range(13):
        wall = DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.wall")
        wall.place_on_grid((7, y), boundary_direction=CardinalDirection.EAST)
        walls.append(wall)
    wall = walls[6]
    cast_fireball(caster, (6, 6))
    first = wall.to_item_presentation_state().surface_residues
    assert len(first) == 1 and first[0].faces == (CardinalDirection.WEST,)
    caster.on_turn_start()
    cast_fireball(caster, (6, 6))
    assert wall.to_item_presentation_state().surface_residues == first

    other = create_spell_regression_actor("Other Caster", (12, 0), "heroes", spell_slots={3: 1})
    register_spell(other, Fireball, caster_level=5)
    cast_fireball(other, (9, 6))
    union = wall.to_item_presentation_state().surface_residues
    assert len(union) == 1 and set(union[0].faces) == {CardinalDirection.EAST, CardinalDirection.WEST}
    assert len(wall.active_conditions) == 1
    cursor = EventQueue.event_cursor()
    assert wall.remove_condition_by_uuid(union[0].condition_uuid)
    removals = [event for _, event in EventQueue.iter_events_since(cursor)
                if isinstance(event, ConditionRemovalEvent) and event.phase is EventPhase.COMPLETION]
    assert len(removals) == 1
    assert removals[0].resulting_item == wall.to_item_presentation_state()
    assert removals[0].resulting_item is not None and removals[0].resulting_item.surface_residues == ()
