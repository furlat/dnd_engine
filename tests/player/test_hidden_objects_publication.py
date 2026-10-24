"""What a seat is shown of an object: its look as it changes, and hidden things only once its party has found them."""

from uuid import uuid4

import pytest

from dnd.actions_functional import execute_available_action, execute_use_action, setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_secret_door
from dnd.content.items.world_prop_builders import build_display_prop
from dnd.core.base_block import BaseBlock
from dnd.core.concealment_types import ConcealedAspect
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.concealment import install_concealment
from dnd.items.environment_interactables import StorageChest
from dnd.player.capture import capture_interval, capture_lineages
from dnd.player.audience import PlayerAudience
from dnd.spells.evocation import Fireball
from tests.manual.spell_regression_support import create_spell_regression_actor
from dnd.player.facts import ObjectDamageFact
from dnd.player.projection import SessionProjection, begin_projection, begin_projections, project_lineage
from dnd.player.reduction import reduce_initialization, reduce_lineage
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.world import CardinalDirection
from tests.engine.test_senses_light_stealth import PerceptionModifierCondition
from tests.player.test_object_look_static import armed_actor, attack


@pytest.fixture
def cache_world():
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    game = Game()
    actor = Entity.create(uuid4(), "Collector", config=EntityConfig(position=(4, 7)))
    actor.compose_entity()
    setup_standard_actions(actor)
    game.deploy_entity(actor, (4, 7))
    actor.update_entity_senses(max_distance=12)
    chest = BaseBlock.get(built.object_uuids["field_cache"])
    assert isinstance(chest, StorageChest)
    try:
        yield built, actor, chest
    finally:
        game.close()
        reset_engine_runtime()


def seat(built, actor, audience=None):
    session = SessionProjection()
    projection, public = begin_projection(session, capture_interval(name="hidden objects", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=actor.uuid, battlefield_id=built.definition.battlefield_id,
        audience=audience))
    return session, projection, reduce_initialization(public)


def observe(session, projection, state, observer, run, audience=None):
    """Run what happens, then the seat of `observer` folds it: its client state and the packets it was sent."""
    start = EventQueue.event_cursor()
    run()
    roots = tuple(event for _, event in EventQueue.iter_events_since(start)
                  if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    packets = []
    for native in capture_lineages(roots, observer_uuid=observer.uuid, audience=audience):
        packet = project_lineage(session, projection, native)
        if packet is not None:
            packets.append(packet)
            state = reduce_lineage(state, packet)
    return state, packets


def act(session, projection, state, actor, name, target=None, faces=(20,), observer=None):
    actor.action_economy.reset_all_costs()
    rows = [row for row in actor.get_available_actions().all_actions if row.template_name.split("__")[0] == name]
    info, choice = next((row, option) for row in rows for option in row.valid_targets
                        if target is None or target.uuid in (option.target_uuid, row.source_item_uuid))

    def run():
        with fixed_dice_faces(*faces):
            root = execute_available_action(actor, info, choice)
        assert root is not None and not root.canceled, root
    return observe(session, projection, state, observer or actor, run)[0]


def test_hidden_contents_are_never_sent_before_a_search_finds_them(cache_world):
    built, actor, chest = cache_world
    install_concealment(chest, ConcealedAspect.CONTENTS, 13)
    assert execute_use_action(actor, chest.uuid, "Open Chest") is not None
    session, projection, state = seat(built, actor)
    assert state.objects[chest.uuid].contained_items is None  # open, in sight, and still nothing to see
    state = act(session, projection, state, actor, "Search Inside", chest)
    contents = state.objects[chest.uuid].contained_items
    assert contents is not None and {row.item_uuid for row in contents} == set(chest.chest_inventory.items)



def test_a_rack_emptying_reaches_the_seat(cache_world):
    built, actor, _ = cache_world
    rack = build_display_prop("environment.furniture.wall_rack", look="swords", capacity=2)
    for _ in range(2):
        assert rack.chest_inventory.add_item(build_authored_item("weapon.longsword", rack.uuid))
    rack.place_on_grid((5, 7))  # filled before placing, as authored content is
    actor.update_entity_senses(max_distance=12)
    session, projection, state = seat(built, actor)
    assert state.objects[rack.uuid].item.visual_variant_id == "swords_full"
    state = act(session, projection, state, actor, "Loot All", rack)
    assert state.objects[rack.uuid].item.visual_variant_id == "swords_empty"


def shown(state, door):
    item = state.objects[door.uuid].item
    return item.item_id, item.name, item.map_char, item.door_mechanism, item.maximum_hit_points, item.is_open


WALL = ("environment.wall.fantasy_a1", "Fantasy A1 Wall", "W", None, None, None)


@pytest.fixture
def party_world():
    """A secret door on (4, 7)'s east side, a hero beside it, a partner of its party and a goblin who see it."""
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    game = Game()
    finder, partner = armed_actor(game, (4, 7)), armed_actor(game, (4, 8))
    goblin = Entity.create(uuid4(), "Goblin", config=EntityConfig(position=(4, 6), faction="goblins"))
    goblin.compose_entity()
    game.deploy_entity(goblin, (4, 6))
    door = build_secret_door(dc=15)
    door.place_on_grid((4, 7), boundary_direction=CardinalDirection.EAST)
    for entity in (finder, partner, goblin):
        entity.update_entity_senses(max_distance=12)
    try:
        yield built, finder, partner, goblin, door
    finally:
        game.close()
        reset_engine_runtime()


def test_a_camouflaged_door_is_its_wall_to_a_seat_until_its_party_finds_it(party_world):
    built, finder, _, _, door = party_world
    session, projection, state = seat(built, finder)
    assert shown(state, door) == WALL  # its look, name and glyph, and nothing of a door
    state = act(session, projection, state, finder, "Search")
    assert shown(state, door)[:2] == ("environment.door.secret_stone", "Secret stone door")
    assert state.objects[door.uuid].item.door_mechanism is not None


@pytest.mark.parametrize(("member", "expected"), (("partner", "environment.door.secret_stone"),
                                                  ("goblin", "environment.wall.fantasy_a1")))
def test_what_a_party_finds_reaches_its_members_seats_and_no_other(party_world, member, expected):
    built, finder, partner, goblin, door = party_world
    observer = partner if member == "partner" else goblin
    session, projection, state = seat(built, observer)
    state = act(session, projection, state, finder, "Search", observer=observer)
    assert state.objects[door.uuid].item.item_id == expected


def test_a_hit_reveals_a_camouflaged_door_to_every_seat_with_the_damage_it_took(party_world):
    built, finder, _, goblin, door = party_world
    session, projection, state = seat(built, goblin)
    state, packets = observe(session, projection, state, goblin, lambda: attack(finder, door, 3))  # nobody searched
    assert shown(state, door)[:2] == ("environment.door.secret_stone", "Secret stone door")
    assert [node.fact.resulting_hp for packet in packets for node in packet.events
            if isinstance(node.fact, ObjectDamageFact)] == [door.get_hp()]


def test_an_opened_camouflaged_door_is_a_door_for_everyone(party_world):
    built, finder, _, goblin, door = party_world
    session, projection, state = seat(built, goblin)
    state = act(session, projection, state, finder, "Search", observer=goblin)
    state = act(session, projection, state, finder, "Open Door", observer=goblin)
    assert shown(state, door)[0] == "environment.door.secret_stone" and shown(state, door)[5] is True


def test_an_attackers_row_names_an_unfound_camouflaged_door_as_its_wall(party_world):
    _, finder, _, _, door = party_world
    finder.action_economy.reset_all_costs()
    assert {target.target_name for row in finder.get_available_actions().all_actions for target in row.valid_targets
            if target.target_uuid == door.uuid} == {"Fantasy A1 Wall"}


@pytest.mark.parametrize("noticer_first", (True, False))
def test_a_members_passive_notice_reaches_a_seat_of_two_whichever_member_settles_first(party_world, noticer_first):
    built, finder, partner, _, door = party_world
    members = (partner.uuid, finder.uuid) if noticer_first else (finder.uuid, partner.uuid)
    audience = PlayerAudience(controlled=(), observers=members)
    session, projection, state = seat(built, finder, audience)
    assert shown(state, door) == WALL

    def sharpen():  # passive Perception 20 meets DC 15
        partner.add_condition(PerceptionModifierCondition(source_entity_uuid=partner.uuid,
                                                          target_entity_uuid=partner.uuid, modifier_amount=10))
        partner.update_entity_senses(max_distance=12)
    state, _ = observe(session, projection, state, finder, sharpen, audience)
    assert shown(state, door)[0] == "environment.door.secret_stone"


def test_a_camouflaged_door_placed_in_view_is_noticed_at_once(party_world):
    built, finder, *_ = party_world
    session, projection, state = seat(built, finder)
    door = build_secret_door(dc=5)  # passive Perception 10 meets it as it appears
    state, _ = observe(session, projection, state, finder,
                       lambda: door.place_on_grid((4, 7), boundary_direction=CardinalDirection.WEST))
    assert shown(state, door)[0] == "environment.door.secret_stone"



def test_what_a_party_member_noticed_before_the_seats_started_reaches_its_partners_seat(party_world):
    built, finder, partner, _, door = party_world  # DC 15: neither notices it at passive Perception 10
    partner.add_condition(PerceptionModifierCondition(source_entity_uuid=partner.uuid,
                                                      target_entity_uuid=partner.uuid, modifier_amount=10))
    partner.update_entity_senses(max_distance=12)
    cursor = EventQueue.event_cursor()
    started = begin_projections(SessionProjection(), tuple(capture_interval(name="hidden objects", start_cursor=0,
        end_cursor=cursor, observer_uuid=member.uuid, battlefield_id=built.definition.battlefield_id,
        audience=PlayerAudience(controlled=(member.uuid,), observers=(member.uuid,))) for member in (finder, partner)))
    for _, public in started:
        assert shown(reduce_initialization(public), door)[0] == "environment.door.secret_stone"



def test_a_fireball_that_reaches_a_camouflaged_door_reveals_it(party_world):
    built, _, _, goblin, door = party_world
    caster = create_spell_regression_actor("Caster", (1, 7), "heroes", spell_slots={3: 1})
    caster.update_entity_senses(max_distance=12)
    session, projection, state = seat(built, goblin)

    def blast():
        with fixed_dice_faces(*([1] * 40)):  # 8 damage: the door stands
            result = Fireball(source_entity_uuid=caster.uuid, end_position=(3, 8), cast_at_level=3).apply()
        assert result is not None and not result.canceled, result
    state, _ = observe(session, projection, state, goblin, blast)
    assert shown(state, door)[:2] == ("environment.door.secret_stone", "Secret stone door")
