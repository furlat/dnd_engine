"""T6, the look split's premise: no writer changes an object's look (`ObjectLook`) in place.

A seat is sent an object's look once per uuid, so a look changed in place would leave every client that holds it
with a stale look and no error. Native in, fold out: each scenario's completed versions are folded with
`world_facts`, and each object's look, floor objects and contained items alike, stays the one it first had.
"""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest

from dnd.actions import Attack
from dnd.actions_functional import execute_available_action, execute_use_action, setup_standard_actions
from dnd.actor_projection import condition_fact
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, WorldInitializedEvent
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment_interactables import StorageChest
from dnd.player.facts import ObjectLook
from dnd.player.world_columns import split_floor_item
from dnd.player.world_publication import floor_item
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.transmutation import Disintegrate
from dnd.spells.wall_constructions import WallOfStone, WallOfStoneZone, WallSection
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection
from dnd.world_authoring import project_world_connector, project_world_object, project_world_tile
from dnd.world_facts import WorldFacts, apply_world_fact
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


def live_world() -> WorldFacts:
    """The world as it stands, as the fold holds it: what a scenario's facts are folded onto."""
    grid = get_map()
    world = WorldFacts()
    objects = []
    for placement in grid.iter_object_placements():
        item = BaseBlock.get(placement.object_uuid)
        assert isinstance(item, BaseItem)
        objects.append(project_world_object(item, placement))
    apply_world_fact(world, WorldInitializedEvent(source_entity_uuid=uuid4(), source_entity_name="World",
        phase=EventPhase.COMPLETION, use_register=False, battlefield_id="look constancy",
        battlefield_name="look constancy", bounds=grid.bounds, width=grid.width, height=grid.height,
        tiles=tuple(project_world_tile(tile) for _, tile in sorted(grid.get_all_tiles().items())),
        objects=tuple(objects), connectors=tuple(project_world_connector(row) for row in grid.get_all_connectors())))
    return world


@contextmanager
def looks_stay_constant() -> Iterator[Counter[UUID]]:
    """Run a scenario, then fold what it committed: every object's look stays the one it first had. Yields the
    folded writes per uuid (counted on exit), so a scenario can show its subjects were written."""
    written: Counter[UUID] = Counter()
    world = live_world()
    start = EventQueue.event_cursor()
    looks: dict[UUID, ObjectLook] = {}
    for obj in world.objects.values():
        for item in (obj.item, *(obj.contained_items or ())):
            looks[item.item_uuid] = split_floor_item(floor_item(item, ()))[0]
    yield written
    for _, event in EventQueue.iter_events_since(start):
        if event.phase is not EventPhase.COMPLETION:
            continue
        applied = apply_world_fact(world, event, condition_fact(event))
        for identity in applied.objects if applied is not None else ():
            obj = world.objects.get(identity)
            for item in (obj.item, *(obj.contained_items or ())) if obj is not None else ():
                look = split_floor_item(floor_item(item, ()))[0]
                assert looks.setdefault(item.item_uuid, look) == look, item.name
                written[item.item_uuid] += 1


@pytest.fixture
def arena():
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def armed_actor(game, position):
    result = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=position, faction="heroes",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(result)
    result.install_initial_items(((build_authored_item("weapon.longsword", result.uuid), WeaponSlot.MELEE_MAIN),))
    result.compose_entity()
    game.deploy_entity(result, position)
    return result


def attack(attacker, item, amount):
    attacker.action_economy.reset_all_costs()
    with fixed_dice_faces(19, amount):
        attacker.update_entity_senses()
        result = Attack(weapon_slot=WeaponSlot.MELEE_MAIN, source_entity_uuid=attacker.uuid,
            target_entity_uuid=item.uuid).apply()
    assert result is not None and not result.canceled and result.total_damage == amount


def use(actor, item, name):
    actor.action_economy.reset_all_costs()
    result = execute_use_action(actor, item.uuid, name)
    assert result is not None and not result.canceled, result


@pytest.mark.parametrize("outcome", ("clear", "jammed"))
def test_a_door_keeps_its_look_through_open_close_damage_and_destruction(arena, outcome):
    attacker = armed_actor(arena, (4, 3))
    door = build_authored_door("environment.door.fantasy_a1", destruction_outcome=outcome, hit_points=12)
    door.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST, orientation=CardinalDirection.SOUTH)
    with looks_stay_constant() as written:
        use(attacker, door, "Open Door")
        use(attacker, door, "Close Door")
        attack(attacker, door, 4)
        attack(attacker, door, 8)
    assert door.integrity is ItemIntegrity.DESTROYED
    assert written[door.uuid] >= 4


def test_a_chest_and_its_contents_keep_their_looks_through_loot():
    reset_engine_runtime()
    built = build_battlefield("battlefield.field_cache_bright")
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Collector", config=EntityConfig(position=(4, 7)))
        actor.compose_entity()
        game.deploy_entity(actor, (4, 7))
        actor.update_entity_senses(max_distance=12)
        chest = BaseBlock.get(built.object_uuids["field_cache"])
        assert isinstance(chest, StorageChest)
        contents = set(chest.chest_inventory.items)
        with looks_stay_constant() as written:
            use(actor, chest, "Open Chest")
            row = next(row for row in actor.get_available_actions().all_actions
                       if row.source_item_uuid == chest.uuid and row.loot_item_uuid is not None)
            looted = execute_available_action(actor, row, row.valid_targets[0])
            assert looted is not None and not looted.canceled
            use(actor, chest, "Close Chest")
            use(actor, chest, "Open Chest")
            use(actor, chest, "Loot All")
        assert not chest.chest_inventory.items
        assert written[chest.uuid] >= 4 and all(written[identity] for identity in contents)
    finally:
        game.close()
        reset_engine_runtime()


def test_a_wall_of_stone_section_keeps_its_look_through_a_disintegrate_cut():
    reset_spell_regression_arena(18, 9)
    try:
        caster = create_spell_regression_actor("Caster", (2, 4), "heroes", spell_slots={5: 2, 6: 2})
        for tile in get_map().get_all_tiles().values():
            tile.surface = tile.surface.model_copy(update={"base_material": Material.STONE})
        Entity.update_all_entities_senses(max_distance=100)
        with looks_stay_constant() as written:
            raised = WallOfStone(source_entity_uuid=caster.uuid, end_position=(5, 6),
                extra_target_positions=[(9, 6)], stone_panel_width_feet=20).apply()
            assert raised is not None and not raised.canceled
            zone, = (row for row in get_map().get_spatial_conditions() if isinstance(row, WallOfStoneZone))
            identity, = zone.sections
            section = BaseBlock.get(identity)
            assert isinstance(section, WallSection)
            caster.action_economy.reset_all_costs()
            Entity.update_all_entities_senses(max_distance=100)
            with fixed_dice_faces(*([4] * 100)):
                cut = Disintegrate(source_entity_uuid=caster.uuid, target_entity_uuid=identity, cast_at_level=6).apply()
            assert cut is not None and not cut.canceled
        assert len(section.geometry.removed_sections) == 1
        assert written[identity] >= 2
    finally:
        reset_engine_runtime()
