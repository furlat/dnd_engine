"""Misty Step discovery and one committed teleport retain the spell's lineage."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, SpatialChangeEvent, SpatialChangeType, StepMovementEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import MistyStep
from dnd.core.world_edges import ElevationSurfaceKind


@pytest.fixture
def casters() -> Iterator[tuple[UUID, UUID]]:
    reset_engine_runtime(grid_size=(12, 8))
    game = Game()
    caster = Entity.create(uuid4(), "Caster", config=EntityConfig(
        position=(1, 2), faction="heroes",
        action_economy=ActionEconomyConfig(spell_slots={2: 2}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
    ))
    setup_standard_actions(caster)
    register_spell(caster, MistyStep, caster_level=3)
    caster.compose_entity()
    witness = Entity.create(uuid4(), "Armed Witness", config=EntityConfig(
        position=(2, 2), faction="enemies",
    ))
    witness.install_initial_items(((build_authored_item("weapon.shortsword", witness.uuid), WeaponSlot.MELEE_MAIN),))
    setup_standard_actions(witness)
    witness.compose_entity()
    add_opportunity_attack_handler(witness)
    game.deploy_entity(caster, caster.position)
    game.deploy_entity(witness, witness.position)
    Entity.update_all_entities_senses()
    try:
        yield caster.uuid, witness.uuid
    finally:
        game.close()
        reset_engine_runtime()


def discovered_cast(caster: Entity, destination: tuple[int, int]) -> SpellEvent:
    available = get_available_actions(caster)
    row = next(row for row in available.all_actions if row.behavior_id == "spell.misty_step")
    target = next(target for target in row.valid_targets if target.position == destination)
    result = execute_by_index(caster, row.template_name, target.index, available=available)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    return result


def test_misty_step_records_one_parented_relocation_without_opportunity_attack(
    casters: tuple[UUID, UUID],
) -> None:
    caster, witness = (Entity.get(identity) for identity in casters)
    assert isinstance(caster, Entity) and isinstance(witness, Entity)
    origin, destination = caster.position, (5, 2)
    threatened = witness.senses.get_threathened_positions()
    assert origin in threatened, threatened
    before = (caster.action_economy.bonus_actions.normalized_score,
              caster.action_economy.spell_slot_2.normalized_score,
              caster.action_economy.movement.normalized_score,
              witness.action_economy.reactions.normalized_score)
    cursor = EventQueue.event_cursor()
    root = discovered_cast(caster, destination)
    completed = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    relocation = [event for event in completed if isinstance(event, SpatialChangeEvent)
                  and event.entity_uuid == caster.uuid
                  and event.change_type in (SpatialChangeType.ENTITY_LEFT, SpatialChangeType.ENTITY_ENTERED)]
    assert [(event.change_type, event.position) for event in relocation] == [
        (SpatialChangeType.ENTITY_LEFT, origin), (SpatialChangeType.ENTITY_ENTERED, destination),
    ]
    assert all(event.parent_lineage == root.lineage_uuid for event in relocation)
    assert not any(isinstance(event, (StepMovementEvent, AttackEvent)) for event in completed)
    assert caster.position == caster.senses.position == destination
    assert get_map().get_entities_at(destination) == {caster.uuid}
    assert caster.uuid not in get_map().get_entities_at(origin)
    assert (caster.action_economy.bonus_actions.normalized_score,
            caster.action_economy.spell_slot_2.normalized_score,
            caster.action_economy.movement.normalized_score,
            witness.action_economy.reactions.normalized_score) == (before[0] - 1, before[1] - 1, before[2], before[3])


def test_misty_step_discovers_a_visible_landing_across_unwalkable_water(
    casters: tuple[UUID, UUID],
) -> None:
    caster = Entity.get(casters[0])
    assert isinstance(caster, Entity)
    grid = get_map()
    for y in range(8):
        grid.set_tile(3, y, name="Water", walking_cost=0, swimming_cost=1)
    destination = (5, 2)
    caster.materialize_navigation()
    assert caster.senses.visible[destination]
    assert destination not in caster.senses.paths
    assert MistyStep(source_entity_uuid=caster.uuid, end_position=destination).pre_validate()
    available = get_available_actions(caster)
    row = next(row for row in available.all_actions if row.behavior_id == "spell.misty_step")
    landings = {target.position: target for target in row.valid_targets}
    assert destination in landings
    assert landings[destination].path is None
    assert landings[destination].opportunity_attack_exposures == []
    discovered_cast(caster, destination)
    assert caster.position == destination


@pytest.mark.parametrize("case", ("occupied", "out-of-range", "unseen"))
def test_misty_step_refuses_invalid_landings_without_position_or_resource_changes(
    casters: tuple[UUID, UUID], case: str,
) -> None:
    caster = Entity.get(casters[0])
    assert isinstance(caster, Entity)
    destination = (2, 2) if case == "occupied" else (9, 2) if case == "out-of-range" else (5, 2)
    if case == "unseen":
        for y in range(8):
            get_map().set_tile(3, y, name="Wall", walking_cost=0, blocks_optics=True)
    caster.update_entity_senses()
    available = get_available_actions(caster)
    row = next(row for row in available.all_actions if row.behavior_id == "spell.misty_step")
    assert destination not in {target.position for target in row.valid_targets}
    before = (caster.position, caster.action_economy.bonus_actions.normalized_score,
              caster.action_economy.spell_slot_2.normalized_score)
    cursor = EventQueue.event_cursor()
    result = MistyStep(source_entity_uuid=caster.uuid, end_position=destination).apply()
    canceled = result is not None and result.canceled
    assert canceled
    assert (caster.position, caster.action_economy.bonus_actions.normalized_score,
            caster.action_economy.spell_slot_2.normalized_score) == before
    assert not any(isinstance(event, SpatialChangeEvent)
                   and event.entity_uuid == caster.uuid
                   for _, event in EventQueue.iter_events_since(cursor))


@pytest.mark.parametrize("source_height, landing_height", ((0, 2), (2, 0)))
def test_misty_step_lands_on_the_actual_visible_support_elevation(
    casters: tuple[UUID, UUID], source_height: int, landing_height: int,
) -> None:
    caster = Entity.get(casters[0])
    assert isinstance(caster, Entity)
    grid, destination = get_map(), (5, 2)
    for position, height in ((caster.position, source_height), (destination, landing_height)):
        grid.set_tile_elevation(position, height=height,
            surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    caster.update_entity_senses()
    discovered_cast(caster, destination)
    assert caster.position == destination
    assert grid.get_support_elevation_feet(caster.position) == landing_height * 5
