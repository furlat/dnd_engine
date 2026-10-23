"""R65's haunting fungus and R63's shoved furniture, through turns, saves and ordinary actions."""

from uuid import uuid4

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.types.world import CardinalDirection
from dnd.spatial.spore_fungus import materialize_spore_fungus
from dnd.spells.abjuration import LesserRestoration
from tests.engine.test_triskelion_hazards_and_traps import act, arena, creature, row, walk
from tests.manual.spell_regression_support import create_spell_regression_actor
from dnd.entity import Entity

__all__ = ["arena"]


def turn(entity: Entity, *faces: int) -> None:
    with fixed_dice_faces(*faces):
        entity.on_turn_start()
        entity.on_turn_end()


def test_a_third_turn_end_in_the_spores_asks_one_save_and_leaving_resets_it(arena):
    lingerer = creature("Lingerer", (2, 2), constitution=1)
    materialize_spore_fungus({(3, 2), (4, 2)}, haunt_rounds=20, cue_interval_rounds=3)
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)  # two turn ends: no save yet
    assert "Haunted" not in lingerer.active_conditions
    turn(lingerer, 18)  # the third: Constitution 18 - 5 = 13 meets DC 13
    assert "Haunted" not in lingerer.active_conditions
    turn(lingerer)  # saved: no other save this stay
    walk(lingerer, (2, 2))
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)
    turn(lingerer, 4)  # a fresh stay: 4 - 5 fails
    assert lingerer.active_conditions["Haunted"].duration.duration == 20


def test_a_haunted_creature_hears_a_sound_every_few_rounds_with_its_effect(arena):
    lingerer = creature("Lingerer", (2, 2), constitution=1)
    materialize_spore_fungus({(3, 2)}, cue_interval_rounds=2)
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)
    turn(lingerer, 4)  # haunted now
    walk(lingerer, (2, 2))  # the haunting goes with it
    turn(lingerer)  # one round since: no sound
    assert "Distracted" not in lingerer.active_conditions
    before = lingerer.get_passive_perception()
    with fixed_dice_faces(2, 1):  # d12 2: a frog croaking (distracted); d4: from the north
        lingerer.on_turn_start()
    assert "Distracted" in lingerer.active_conditions and lingerer.get_passive_perception() == before - 5
    lingerer.on_turn_end()
    lingerer.on_turn_start()  # it fades at the next turn start, one round into the next interval
    assert "Distracted" not in lingerer.active_conditions
    lingerer.on_turn_end()
    with fixed_dice_faces(4, 1):  # d12 4: a very loud heartbeat (startled): this turn's reaction is gone
        lingerer.on_turn_start()
    assert lingerer.action_economy.reactions.normalized_score == 0


def test_lesser_restoration_ends_the_haunting(arena):
    lingerer = creature("Lingerer", (2, 2), constitution=1)
    materialize_spore_fungus({(3, 2)})
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)
    turn(lingerer, 4)
    cleric = create_spell_regression_actor("Cleric", (2, 3), "heroes", spell_slots={2: 1})
    cleric.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = LesserRestoration(source_entity_uuid=cleric.uuid, target_entity_uuid=lingerer.uuid).apply()
    assert result is not None and not result.canceled and "Haunted" not in lingerer.active_conditions


def test_a_sound_can_draw_the_haunted_creature_a_step_toward_it(arena):
    lingerer = creature("Lingerer", (2, 2), constitution=1)
    materialize_spore_fungus({(3, 2)}, cue_interval_rounds=1)
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)
    turn(lingerer, 4)
    walk(lingerer, (2, 2))
    with fixed_dice_faces(1, 1):  # d12 1: a baby crying (drawn); d4 1: from the north
        lingerer.on_turn_start()
    assert lingerer.position == (2, 3)


def shoved(entity: Entity, item, *faces: int) -> None:
    act(entity, "Shove Object", target=item, faces=faces)


def test_a_chair_shoved_from_the_side_moves_one_square_straight_away(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    shoved(pusher, chair)  # light: no roll
    assert get_map().get_object_position(chair.uuid) == (4, 2)
    assert get_map().is_walkable_for(3, 2) and not get_map().is_walkable_for(4, 2)


def test_a_wall_or_a_creature_stops_a_shove_and_the_body_stays_put(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    wall = build_directional_wall()
    wall.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)
    other = creature("Other", (3, 3))
    walk(pusher, (2, 1))
    walk(pusher, (3, 1))
    shoved(pusher, chair)  # pushing north into the other creature
    assert get_map().get_object_position(chair.uuid) == (3, 2) and other.position == (3, 3)


def test_a_heavy_couch_moves_whole_only_when_strength_wins(arena):
    pusher = creature("Pusher", (2, 2), strength=18)
    couch = build_authored_item("environment.furniture.couch", uuid4())
    couch.place_on_grid((3, 2))  # covers (3, 2) and (4, 2)
    shoved(pusher, couch, 5)  # Athletics 5 + 4 misses DC 15
    assert set(get_map().get_object_placement(couch.uuid).positions) == {(3, 2), (4, 2)}
    shoved(pusher, couch, 12)
    assert set(get_map().get_object_placement(couch.uuid).positions) == {(4, 2), (5, 2)}


def test_furniture_is_not_shoved_from_a_corner(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 3))
    info = row(pusher, "Shove Object")
    assert info is None or chair.uuid not in {option.target_uuid for option in info.valid_targets}


def test_a_shove_into_another_body_is_refused_and_both_stay_put(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    table = build_authored_item("environment.furniture.table", uuid4())
    table.place_on_grid((4, 2))
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)
    assert get_map().get_object_position(table.uuid) == (4, 2)


def test_a_shove_into_a_barrel_is_refused_even_though_it_fills_no_band(arena):
    pusher = creature("Pusher", (2, 2))
    chair = build_authored_item("environment.furniture.wooden_chair", uuid4())
    chair.place_on_grid((3, 2))
    barrel = build_authored_item("environment.blocker.oil_barrel", uuid4())
    barrel.place_on_grid((4, 2))
    shoved(pusher, chair)
    assert get_map().get_object_position(chair.uuid) == (3, 2)


def test_a_fixture_built_in_place_offers_no_shove(arena):
    pusher = creature("Pusher", (2, 2))
    fireplace = build_authored_item("environment.furniture.fireplace", uuid4())
    fireplace.place_on_grid((3, 2))
    info = row(pusher, "Shove Object")
    assert info is None or fireplace.uuid not in {option.target_uuid for option in info.valid_targets}


def test_only_the_haunted_creatures_own_turns_bring_its_sounds(arena):
    lingerer = creature("Lingerer", (2, 2), constitution=1)
    bystander = creature("Bystander", (6, 6))
    materialize_spore_fungus({(3, 2)}, cue_interval_rounds=2)
    walk(lingerer, (3, 2))
    turn(lingerer)
    turn(lingerer)
    turn(lingerer, 4)
    for _ in range(3):
        turn(bystander)  # no die: another creature's turns never bring the sound
    turn(lingerer)  # the lingerer's first turn since: still one round short
    with fixed_dice_faces(2, 1):
        lingerer.on_turn_start()
    assert "Distracted" in lingerer.active_conditions
