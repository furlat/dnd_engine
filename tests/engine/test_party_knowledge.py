"""Hidden traps and hazards are known by the party that finds them: noticed, searched for, or seen firing."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_use_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door, build_secret_door
from dnd.content.items.world_prop_builders import build_searchable_prop
from dnd.content.items.trap_hardware_builders import materialize_trap_hardware
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import wall_factory
from dnd.core.concealment_types import ConcealedAspect, concealment
from dnd.core.condition_types import ConditionCategory, HazardFilter
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SensoryUpdateEvent, SpatialEffectChangeEvent
from dnd.core.gridmap import get_map
from dnd.core.view import cell_visible
from dnd.entity import Entity
from dnd.items.concealment import install_concealment
from dnd.items.locks import build_thieves_tools, install_lock
from dnd.spatial.environmental_conditions import SpikeTrap, materialize_spike_trap_condition
from dnd.spatial.mechanisms import AreaGeometry, materialize_finite_trap
from dnd.spatial.triggers import materialize_pressure_plate, materialize_tripwire
from dnd.spells.transmutation import SpikeGrowth
from dnd.types.controls import ActivationLink
from dnd.types.world import CardinalDirection
from dnd.types.traps import TrapState
from tests.engine.test_senses_light_stealth import PerceptionModifierCondition
from tests.engine.test_triskelion_hazards_and_traps import act, arena, creature, row, walk
from tests.manual.spell_regression_support import create_spell_regression_actor

__all__ = ["arena"]


def check(hidden, cell: tuple[int, int], *, knowing: tuple[Entity, ...] = (), unaware: tuple[Entity, ...] = (),
          hazard: bool = True) -> None:
    """Who has the hidden thing on its map and, for a hazard, routes around its cell; and who neither."""
    grid = get_map()
    for entity in knowing:
        assert hidden.uuid in entity.senses.spatial_effects, entity.name
        assert not hazard or grid.is_position_hazardous_for(*cell, entity.uuid), entity.name
    for entity in unaware:
        assert hidden.uuid not in entity.senses.spatial_effects, entity.name
        assert not grid.is_position_hazardous_for(*cell, entity.uuid), entity.name


def wall(x: int) -> None:
    for y in range(8):
        get_map().set_tile(x, y, tile=wall_factory((x, y)))


def cause() -> Event:
    event = EventQueue.publish_declaration(Event(name="Test cause", source_entity_uuid=uuid4(),
                                                 event_type=EventType.BASE_ACTION, use_register=False))
    for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
        event = event.phase_to(phase)
    return event


def test_passive_perception_meeting_the_dc_notices_a_hidden_trap(arena):
    watcher = creature("Watcher", (2, 2))
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=watcher.get_passive_perception())
    check(trap, (4, 2), knowing=(watcher,))


def test_a_noticed_plate_stays_known_after_perception_drops(arena):
    watcher = creature("Watcher", (2, 2), wisdom=20)  # passive Perception 15
    mechanism = materialize_finite_trap((6, 6), geometry=AreaGeometry(), stealth_dc=30)
    plate = materialize_pressure_plate({(4, 2)}, ActivationLink(target_condition_uuid=mechanism.uuid), stealth_dc=14)
    check(plate, (4, 2), knowing=(watcher,), hazard=False)
    watcher.add_condition(PerceptionModifierCondition(source_entity_uuid=watcher.uuid,
                                                      target_entity_uuid=watcher.uuid, modifier_amount=-10))
    watcher.update_entity_senses()
    assert watcher.get_passive_perception() < 14
    check(plate, (4, 2), knowing=(watcher,), hazard=False)


def test_a_trap_no_one_in_the_party_has_seen_is_not_avoided(arena):
    wall(6)
    sharp = creature("Sharp", (2, 2), wisdom=20)
    trap = materialize_spike_trap_condition({(9, 2)}, stealth_dc=11)  # behind the wall
    sharp.update_entity_senses()
    check(trap, (9, 2), unaware=(sharp,))


def test_a_trap_one_member_notices_is_known_to_the_whole_party_and_no_one_else(arena):
    wall(8)
    sharp = creature("Sharp", (2, 2), wisdom=20)
    dull = creature("Dull", (2, 4), wisdom=8)
    behind = creature("Behind", (12, 3), wisdom=8)  # beyond the wall, out of this settlement
    goblin = creature("Goblin", (2, 6), wisdom=8, faction="goblins")
    trap = materialize_spike_trap_condition({(4, 3)}, stealth_dc=13)
    check(trap, (4, 3), knowing=(sharp, dull), unaware=(goblin,))  # one settlement: the party in view
    assert get_map().is_position_hazardous_for(4, 3, behind.uuid)  # its routes know it at once
    Entity.update_entity_position(behind, (5, 5), parent_event=cause().uuid)
    behind.update_entity_senses()
    check(trap, (4, 3), knowing=(behind,))  # and it draws it once it sees the cells


def test_a_search_teaches_the_searchers_party_and_tells_others_nothing(arena):
    searcher = creature("Searcher", (2, 2), wisdom=8)
    ally = creature("Ally", (2, 6), wisdom=8)
    goblin = creature("Goblin", (2, 4), wisdom=8, faction="goblins")
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=13)
    cursor = EventQueue.event_cursor()
    act(searcher, "Search", faces=(16,))
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert {event.observer_uuid for event in events if isinstance(event, SensoryUpdateEvent)} == {searcher.uuid}
    assert not any(isinstance(event, SpatialEffectChangeEvent) for event in events)
    ally.update_entity_senses()
    goblin.update_entity_senses()
    check(trap, (4, 2), knowing=(searcher, ally), unaware=(goblin,))


def test_a_failed_search_binds_only_the_searcher(arena):
    searcher = creature("Searcher", (2, 2), wisdom=8)
    partner = creature("Partner", (2, 4), wisdom=8)
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=13)
    act(searcher, "Search", faces=(5,))
    act(searcher, "Search", faces=(20,))  # one try per hidden thing
    check(trap, (4, 2), unaware=(searcher, partner))
    act(partner, "Search", faces=(16,))
    searcher.update_entity_senses()
    check(trap, (4, 2), knowing=(searcher, partner))


def test_raised_spikes_are_seen_by_anyone_and_hide_again_once_retracted(arena):
    wall(8)
    watcher = creature("Watcher", (2, 2), wisdom=8)
    goblin = creature("Goblin", (12, 2), wisdom=8, faction="goblins")
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=30)
    check(trap, (4, 2), unaware=(watcher,))
    assert isinstance(trap, SpikeTrap) and trap.set_trap_state(TrapState.ACTIVATED, parent_event=cause())
    check(trap, (4, 2), knowing=(watcher,))
    assert trap.set_trap_state(TrapState.READY, parent_event=cause())
    Entity.update_entity_position(goblin, (4, 4), parent_event=cause().uuid)
    goblin.update_entity_senses()
    watcher.update_entity_senses()
    check(trap, (4, 2), knowing=(watcher,), unaware=(goblin,))


def test_a_plate_and_the_trap_it_fires_give_themselves_away_to_the_watchers(arena):
    wall(8)
    watcher = creature("Watcher", (2, 2), wisdom=8)
    goblin = creature("Goblin", (12, 2), wisdom=8, faction="goblins")
    mechanism = materialize_finite_trap((6, 6), geometry=AreaGeometry(), stealth_dc=30)  # re-arms at once
    plate = materialize_pressure_plate({(4, 2)}, ActivationLink(target_condition_uuid=mechanism.uuid), stealth_dc=30)
    victim = creature("Victim", (3, 2), wisdom=8)
    check(plate, (4, 2), unaware=(watcher,))
    walk(victim, (4, 2), faces=(10,) * 8)
    assert mechanism.trap_state is TrapState.READY
    watcher.update_entity_senses()
    goblin.update_entity_senses()
    check(plate, (4, 2), knowing=(watcher,), unaware=(goblin,), hazard=False)
    assert mechanism.uuid in watcher.senses.spatial_effects and mechanism.uuid not in goblin.senses.spatial_effects


def test_crossing_a_tripwire_gives_it_away_to_the_watchers(arena):
    wall(8)
    watcher = creature("Watcher", (2, 2), wisdom=8)
    goblin = creature("Goblin", (12, 2), wisdom=8, faction="goblins")
    mechanism = materialize_finite_trap((6, 6), geometry=AreaGeometry(), stealth_dc=30)
    wire = materialize_tripwire((4, 3), (5, 3), ActivationLink(target_condition_uuid=mechanism.uuid), stealth_dc=30)
    victim = creature("Victim", (4, 3), wisdom=8)
    assert wire.uuid not in watcher.senses.spatial_effects
    walk(victim, (5, 3), faces=(10,) * 8)
    watcher.update_entity_senses()
    goblin.update_entity_senses()
    assert wire.uuid in watcher.senses.spatial_effects and wire.uuid not in goblin.senses.spatial_effects


def test_a_creature_without_a_faction_knows_only_what_it_noticed(arena):
    sharp = create_spell_regression_actor("Sharp", (2, 2), None, wisdom=20)  # type: ignore[arg-type]
    loner = create_spell_regression_actor("Loner", (2, 4), None, wisdom=8)  # type: ignore[arg-type]
    Entity.update_all_entities_senses()
    trap = materialize_spike_trap_condition({(4, 3)}, stealth_dc=13)
    check(trap, (4, 3), knowing=(sharp,), unaware=(loner,))


def test_a_notice_rides_on_the_one_sensory_event_of_its_cause(arena):
    sharp = creature("Sharp", (2, 2), wisdom=20)
    cursor = EventQueue.event_cursor()
    trap = materialize_spike_trap_condition({(4, 2)}, stealth_dc=13)
    updates = [event for _, event in EventQueue.iter_events_since(cursor)
               if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == sharp.uuid]
    assert [update.concealed_noticed for update in updates] == [frozenset({trap.uuid})]


def test_hidden_trap_hardware_shows_only_for_the_party_that_knows_its_mechanism(arena):
    sharp = creature("Sharp", (2, 2), wisdom=20)
    dull = creature("Dull", (2, 4), wisdom=8)
    goblin = creature("Goblin", (2, 6), wisdom=8, faction="goblins")
    hardware, _ = materialize_trap_hardware((4, 4), stealth_dc=13)
    for entity in (sharp, dull, goblin):
        entity.update_entity_senses()
    assert hardware.uuid in sharp.senses.objects and hardware.uuid in dull.senses.objects
    assert hardware.uuid not in goblin.senses.objects


def test_a_search_finds_a_hidden_hazard_held_by_a_tile(arena):
    searcher = creature("Searcher", (2, 2), wisdom=8)
    tile = get_map().get_tile(3, 2)
    assert tile is not None
    tile.add_condition(BaseCondition(name="Loose flagstone", source_entity_uuid=uuid4(), target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION, hazard_filter=HazardFilter.ALL, concealment=concealment(13)))
    searcher.update_entity_senses()
    assert not get_map().is_position_hazardous_for(3, 2, searcher.uuid)
    act(searcher, "Search", faces=(16,))
    assert get_map().is_position_hazardous_for(3, 2, searcher.uuid)


def test_spike_growth_is_known_to_its_casters_party_from_the_start(arena):
    caster = create_spell_regression_actor("Caster", (1, 1), "heroes", spell_slots={2: 1})
    ally = creature("Ally", (1, 3), wisdom=8)
    stranger = creature("Stranger", (1, 5), wisdom=8, faction="wanderers")
    Entity.update_all_entities_senses()
    with fixed_dice_faces(*([10] * 20)):
        result = SpikeGrowth(source_entity_uuid=caster.uuid, end_position=(10, 4), cast_at_level=2).apply()
    assert result is not None and not result.canceled
    assert get_map().is_position_hazardous_for(10, 4, ally.uuid)
    assert not get_map().is_position_hazardous_for(10, 4, stranger.uuid)


def hidden_key(cell: tuple[int, int], dc: int = 13):
    key = build_authored_item("tool.key", uuid4())
    install_concealment(key, ConcealedAspect.PRESENCE, dc)
    key.place_on_grid(cell)
    return key


def test_hidden_loot_is_unseen_until_noticed_and_then_seen_by_the_whole_party(arena):
    dull = creature("Dull", (2, 4), wisdom=8)
    goblin = creature("Goblin", (2, 6), wisdom=8, faction="goblins")
    key = hidden_key((4, 4))
    for entity in (dull, goblin):
        entity.update_entity_senses()
    assert key.uuid not in dull.senses.objects and key.uuid not in goblin.senses.objects
    sharp = creature("Sharp", (2, 2), wisdom=20)  # passive Perception 15 meets DC 13
    for entity in (dull, goblin):
        entity.update_entity_senses()
    assert key.uuid in sharp.senses.objects and key.uuid in dull.senses.objects
    assert key.uuid not in goblin.senses.objects


def test_hidden_loot_once_taken_is_seen_by_everyone_where_it_is_dropped(arena):
    sharp = creature("Sharp", (2, 2), wisdom=20)
    goblin = creature("Goblin", (2, 6), wisdom=8, faction="goblins")
    key = hidden_key((3, 2))
    sharp.update_entity_senses()
    act(sharp, "Pick Up", target=key)
    assert sharp.drop_item(key.uuid, (3, 2)) is not None
    goblin.update_entity_senses()
    assert key.uuid in goblin.senses.objects


def test_a_search_finds_hidden_loot(arena):
    searcher = creature("Searcher", (2, 2), wisdom=8)
    key = hidden_key((3, 2))
    searcher.update_entity_senses()
    assert key.uuid not in searcher.senses.objects
    act(searcher, "Search", faces=(16,))
    assert key.uuid in searcher.senses.objects


def test_a_camouflaged_door_offers_nothing_until_found_and_still_blocks_sight_and_passage(arena):
    door = build_secret_door(dc=15)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    hero = creature("Hero", (3, 2), wisdom=8)
    goblin = creature("Goblin", (4, 2), wisdom=8, faction="goblins")
    for entity in (hero, goblin):
        assert door.uuid in entity.senses.objects and row(entity, "Open Door") is None  # seen, as its wall
    assert not cell_visible(hero.senses.cells, (5, 2)) and not get_map().can_transition((3, 2), (4, 2))
    act(hero, "Search", faces=(16,))  # 16 - 1 meets DC 15
    assert row(hero, "Open Door") is not None and row(goblin, "Open Door") is None
    Entity.update_entity_position(goblin, (6, 2), parent_event=cause().uuid)  # clear of the door's swing
    act(hero, "Open Door")
    goblin.update_entity_senses()
    assert not door.hides_actions_from(goblin.faction, goblin.uuid)  # an open door is plain to see, and known


def test_a_camouflaged_door_is_noticed_from_either_side(arena):
    door = build_secret_door(dc=12)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    far = creature("Far", (4, 2), wisdom=20)  # passive Perception 15, on the far side of its own cell
    assert row(far, "Open Door") is not None


def test_hidden_actions_leave_a_locked_door_visible_but_offer_nothing_until_found(arena):
    door = build_authored_door("environment.door.secret_stone")
    install_concealment(door, ConcealedAspect.ACTIONS, 15)
    install_lock(door)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    rogue = creature("Rogue", (3, 2), wisdom=8, dexterity=16)
    assert rogue.loot_item(build_thieves_tools(rogue.uuid))
    rogue.update_entity_senses()
    assert door.uuid in rogue.senses.objects
    assert row(rogue, "Pick Lock") is None and row(rogue, "Unlock") is None
    act(rogue, "Search", faces=(16,))
    assert row(rogue, "Pick Lock") is not None


def test_an_unfound_secret_door_cannot_be_used_by_name(arena):
    door = build_secret_door(dc=15)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    hero = creature("Hero", (3, 2), wisdom=8)
    with pytest.raises(ValueError, match="not found"):
        execute_use_action(hero, door.uuid, "Open Door")
    assert not door.is_open


def test_an_object_can_hide_itself_and_its_contents_at_once(arena):
    dull = creature("Dull", (2, 4), wisdom=8)
    desk = build_searchable_prop("environment.furniture.writing_desk", dc=5)
    install_concealment(desk, ConcealedAspect.PRESENCE, 13)
    desk.place_on_grid((3, 2))
    assert desk.chest_inventory.add_item(build_authored_item("tool.key", desk.uuid))
    dull.update_entity_senses()
    assert desk.uuid not in dull.senses.objects
    sharp = creature("Sharp", (2, 2), wisdom=20)  # passive Perception 15 notices the desk, not what it hides
    act(sharp, "Open Chest")
    assert row(sharp, "Loot All") is None


def test_passive_perception_never_finds_hidden_contents(arena):
    sharp = creature("Sharp", (2, 2), wisdom=20)
    desk = build_searchable_prop("environment.furniture.writing_desk", dc=5)
    desk.place_on_grid((3, 2))
    assert desk.chest_inventory.add_item(build_authored_item("tool.key", desk.uuid))
    sharp.update_entity_senses()
    act(sharp, "Open Chest")
    assert row(sharp, "Loot All") is None  # passive Perception 15 against DC 5: only Search Inside finds them
