"""Dread-pool entry causes a real save and affordable, interrupting retreat.

Commands are native Move/Jump and ordinary turn/condition operations. Observable
positions, budgets and completed causal events establish the fear contract.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import AttackEvent, Jump, JumpEvent, Move, MovementEvent, Shove, ShoveEvent, SpellEvent
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import DREAD_BODY_RESPONSE, install_body_response
from dnd.conditions import Blinded
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, ForcedMovementEvent, SavingThrowEvent, SpatialChangeEvent, SpatialChangeType, StepMovementEvent
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import GhoulClawsParalysisFeature
from dnd.reactions import add_opportunity_attack_handler
from dnd.residues import DREAD_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import MistyStep
from dnd.spells.transmutation import Telekinesis
from dnd.types.world import OccupancyLayer


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(6, 3))
    instance = Game()
    try:
        yield instance
    finally:
        instance.close()
        reset_engine_runtime()


def actor(game: Game, position: tuple[int, int], *, movement: int = 30, caster: bool = False,
          faction: str = "heroes") -> Entity:
    creature = Entity.create(uuid4(), "Dread-pool traveler", config=EntityConfig(
        position=position, faction=faction,
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(movement=movement, spell_slots={2: 1} if caster else {}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
    ))
    setup_standard_actions(creature)
    if caster:
        register_spell(creature, MistyStep, caster_level=3)
    creature.compose_entity()
    game.deploy_entity(creature, position)
    return creature


def armed_reactor(game: Game, position: tuple[int, int], *, paralyzing: bool = False) -> Entity:
    reactor = Entity.create(uuid4(), "Armed fear witness", config=EntityConfig(
        position=position, faction="enemies",
    ))
    reactor.install_initial_items(((
        build_authored_item("weapon.longsword", reactor.uuid), WeaponSlot.MELEE_MAIN,
    ),))
    setup_standard_actions(reactor)
    if paralyzing:
        reactor.add_condition(GhoulClawsParalysisFeature(
            source_entity_uuid=reactor.uuid, target_entity_uuid=reactor.uuid,
            weapon_names=("Longsword",),
        ))
    add_opportunity_attack_handler(reactor)
    reactor.compose_entity()
    game.deploy_entity(reactor, position)
    Entity.update_all_entities_senses()
    return reactor


def pool(position: tuple[int, int] = (1, 1)):
    tile = get_map().get_tile(*position)
    assert tile is not None
    state = deposit_residue(tile, DREAD_RESIDUE)
    assert state is not None
    Entity.update_all_entities_senses()
    return tile, state


def walk(creature: Entity, path: list[tuple[int, int]]) -> MovementEvent:
    result = Move(source_entity_uuid=creature.uuid, end_position=path[-1],
        path=path, prefer_safe=False).apply()
    assert isinstance(result, MovementEvent)
    return result


def completed(cursor: int) -> list[Event]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("save_face,immune,retreat", ((1, False, True), (20, False, False), (1, True, False)))
def test_save_and_immunity_control_paid_retreat(
    game: Game, save_face: int, immune: bool, retreat: bool,
) -> None:
    traveler = actor(game, (0, 1))
    pool()
    if immune:
        traveler.add_condition_immunity("Frightened", immunity_name="Native fear immunity")
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(save_face):
        result = walk(traveler, [(0, 1), (1, 1), (2, 1)])

    assert not result.canceled
    assert result.end_position == traveler.position == ((0, 1) if retreat else (2, 1))
    assert result.requested_end_position == (2, 1)
    assert traveler.action_economy.movement.normalized_score == 20
    assert "Frightened" not in traveler.active_conditions
    events = completed(cursor)
    saves = [event for event in events if isinstance(event, SavingThrowEvent)]
    assert len(saves) == 1 and saves[0].result is (save_face == 20)
    applied = [event for event in events if isinstance(event, ConditionApplicationEvent)
               and event.condition_state is not None and event.condition_state.name == "Frightened"]
    removed = [event for event in events if isinstance(event, ConditionRemovalEvent)
               and event.condition_state is not None and event.condition_state.name == "Frightened"]
    assert len(applied) == len(removed) == int(retreat)
    steps = [event for event in events if isinstance(event, StepMovementEvent) and event.committed]
    assert [(step.from_position, step.to_position) for step in steps] == (
        [((0, 1), (1, 1)), ((1, 1), (0, 1))] if retreat
        else [((0, 1), (1, 1)), ((1, 1), (2, 1))])
    for event in (*saves, *applied, *removed, *steps):
        ancestor = event
        while (parent := ancestor.get_parent_event()) is not None:
            ancestor = parent
        assert ancestor.lineage_uuid == result.lineage_uuid


def test_exhausted_entrant_stays_frightened_then_pays_for_later_reverse_move(game: Game) -> None:
    traveler = actor(game, (0, 1), movement=5)
    pool()
    with fixed_dice_faces(1):
        result = walk(traveler, [(0, 1), (1, 1)])
    assert not result.canceled and traveler.position == (1, 1)
    assert "Frightened" in traveler.active_conditions
    assert traveler.action_economy.movement.normalized_score == 0
    assert traveler.skill_set.athletics.skill_bonus.advantage is AdvantageStatus.DISADVANTAGE
    traveler.on_turn_end()
    traveler.on_turn_start(round_number=2)
    assert traveler.position == (1, 1) and "Frightened" in traveler.active_conditions
    refreshed = traveler.action_economy.movement.normalized_score
    forward = walk(traveler, [(1, 1), (2, 1)])
    assert forward.canceled and traveler.position == (1, 1)
    assert traveler.action_economy.movement.normalized_score == refreshed
    result = walk(traveler, [(1, 1), (0, 1)])
    assert not result.canceled and traveler.position == (0, 1)
    assert traveler.action_economy.movement.normalized_score == refreshed - 5
    assert "Frightened" not in traveler.active_conditions


def test_jump_landing_uses_last_airborne_step_as_retreat_origin(game: Game) -> None:
    traveler = actor(game, (0, 1))
    pool((2, 1))
    with fixed_dice_faces(1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(2, 1)).apply()
    assert isinstance(result, JumpEvent) and not result.canceled
    assert result.end_position == result.objective_end_position == traveler.position == (1, 1)
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    assert traveler.action_economy.movement.normalized_score == 15
    assert "Frightened" not in traveler.active_conditions


def test_occupied_retreat_cell_blocks_jump_response_until_real_exit_is_clear(game: Game) -> None:
    traveler = actor(game, (0, 1))
    blocker = actor(game, (1, 1))
    pool((2, 1))
    with fixed_dice_faces(1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(2, 1)).apply()
    assert result is not None and not result.canceled
    assert traveler.position == (2, 1) and "Frightened" in traveler.active_conditions
    assert traveler.action_economy.movement.normalized_score == 20
    assert not walk(blocker, [(1, 1), (1, 0)]).canceled
    assert not walk(traveler, [(2, 1), (1, 1)]).canceled
    assert traveler.position == (1, 1) and "Frightened" not in traveler.active_conditions
    assert traveler.action_economy.movement.normalized_score == 15


def test_donor_departure_visibility_and_actual_source_removal(game: Game) -> None:
    traveler = actor(game, (0, 1), movement=5)
    donor = actor(game, (1, 1))
    install_body_response(donor, DREAD_BODY_RESPONSE)
    donor.receive_damage(1, DamageType.SLASHING, traveler.uuid)
    game.remove_entity(donor.uuid)
    Entity.update_all_entities_senses()
    with fixed_dice_faces(1):
        result = walk(traveler, [(0, 1), (1, 1)])
    assert not result.canceled and "Frightened" in traveler.active_conditions
    assert traveler.equipment.attack_bonus.advantage is AdvantageStatus.DISADVANTAGE
    blindness = Blinded(source_entity_uuid=traveler.uuid, target_entity_uuid=traveler.uuid)
    traveler.add_condition(blindness)
    assert traveler.skill_set.athletics.skill_bonus.advantage is AdvantageStatus.NONE
    traveler.remove_condition_by_uuid(blindness.uuid)
    assert traveler.skill_set.athletics.skill_bonus.advantage is AdvantageStatus.DISADVANTAGE
    tile = get_map().get_tile(1, 1)
    assert tile is not None and tile.remove_condition(DREAD_RESIDUE.name)
    assert "Frightened" not in traveler.active_conditions
    assert traveler.equipment.attack_bonus.advantage is AdvantageStatus.NONE


def test_teleport_entry_pays_one_adjacent_step_toward_actual_departure(game: Game) -> None:
    traveler = actor(game, (0, 1), caster=True)
    pool((4, 1))
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = MistyStep(source_entity_uuid=traveler.uuid, end_position=(4, 1)).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert traveler.position == (3, 1)
    assert traveler.action_economy.movement.normalized_score == 25
    assert traveler.action_economy.bonus_actions.normalized_score == 0
    assert traveler.action_economy.spell_slot_2.normalized_score == 0
    assert "Frightened" not in traveler.active_conditions
    steps = [event for event in completed(cursor)
             if isinstance(event, StepMovementEvent) and event.committed]
    assert [(step.from_position, step.to_position) for step in steps] == [((4, 1), (3, 1))]
    entries = [event for event in completed(cursor) if isinstance(event, SpatialChangeEvent)
               and event.change_type is SpatialChangeType.ENTITY_ENTERED]
    assert [(entry.old_position, entry.position) for entry in entries] == [
        ((0, 1), (4, 1)), ((4, 1), (3, 1)),
    ]
    retreat = steps[0].get_parent_event()
    assert isinstance(retreat, MovementEvent)
    assert retreat.parent_lineage == result.lineage_uuid


def test_paid_retreat_uses_ordinary_opportunity_attack_rules(game: Game) -> None:
    traveler = actor(game, (0, 1))
    reactor = armed_reactor(game, (2, 1))
    pool()
    cursor, health = EventQueue.event_cursor(), traveler.get_hp()
    with fixed_dice_faces(1, 18, 2):
        result = walk(traveler, [(0, 1), (1, 1)])
    assert not result.canceled and traveler.position == (0, 1)
    assert traveler.action_economy.movement.normalized_score == 20
    assert traveler.get_hp() < health
    attacks = [event for event in completed(cursor) if isinstance(event, AttackEvent)]
    assert len(attacks) == 1 and attacks[0].source_entity_uuid == reactor.uuid
    assert reactor.action_economy.reactions.normalized_score == 0


def test_interrupted_jump_records_retreat_from_its_last_committed_step(game: Game) -> None:
    traveler = actor(game, (0, 1))
    armed_reactor(game, (1, 0), paralyzing=True)
    pool((2, 1))
    with fixed_dice_faces(18, 2, 1, 1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    assert result is not None and not result.canceled
    assert traveler.position == (2, 1) and traveler.occupancy_layer is OccupancyLayer.GROUND
    assert {"Paralyzed", "Frightened"} <= traveler.active_conditions.keys()
    assert traveler.action_economy.movement.normalized_score == 0
    assert traveler.remove_condition("Paralyzed")
    assert traveler.action_economy.movement.normalized_score == 20
    assert not walk(traveler, [(2, 1), (1, 1)]).canceled
    assert traveler.position == (1, 1) and "Frightened" not in traveler.active_conditions
    assert traveler.action_economy.movement.normalized_score == 15


def test_shove_entry_stops_for_a_paid_reverse_step(game: Game) -> None:
    shover = actor(game, (0, 1))
    traveler = actor(game, (1, 1))
    pool((2, 1))
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=traveler.uuid).apply()
    assert isinstance(result, ShoveEvent) and not result.canceled
    assert result.end_position == traveler.position == (1, 1)
    assert result.push_distance == 5
    assert traveler.action_economy.movement.normalized_score == 25
    assert shover.action_economy.movement.normalized_score == 30
    assert "Frightened" not in traveler.active_conditions
    forced = [event for event in completed(cursor) if isinstance(event, ForcedMovementEvent)]
    assert len(forced) == 1 and forced[0].actual_distance == 5
    assert forced[0].end_position == (2, 1)
    events = completed(cursor)
    retreat = next(event for event in events if isinstance(event, MovementEvent))
    assert events.index(forced[0]) < events.index(retreat)


def test_telekinesis_granted_move_retains_incoming_contact_before_paid_retreat(game: Game) -> None:
    caster = Entity.create(uuid4(), "Telekinetic caster", config=EntityConfig(
        position=(0, 1), faction="heroes",
        action_economy=ActionEconomyConfig(spell_slots={5: 1}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
    ))
    setup_standard_actions(caster)
    register_spell(caster, Telekinesis)
    caster.compose_entity()
    game.deploy_entity(caster, caster.position)
    traveler = actor(game, (1, 1), faction="enemies")
    pool((4, 1))
    with fixed_dice_faces(1):
        cast = Telekinesis(source_entity_uuid=caster.uuid, target_entity_uuid=traveler.uuid).apply()
    assert cast is not None and not cast.canceled
    template = caster.get_action_template("Telekinesis: Move")
    assert template is not None
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = template.instantiate(end_position=(4, 1)).apply()
    assert result is not None and not result.canceled
    assert traveler.position == (3, 1)
    assert traveler.action_economy.movement.normalized_score == 25
    assert "Frightened" not in traveler.active_conditions
    assert caster.get_action_template("Telekinesis: Move") is None
    events = completed(cursor)
    incoming, = (event for event in events if isinstance(event, ForcedMovementEvent))
    retreat, = (event for event in events if isinstance(event, MovementEvent))
    assert (incoming.start_position, incoming.end_position, incoming.actual_distance) == (
        (1, 1), (4, 1), 15,
    )
    assert events.index(incoming) < events.index(retreat)
    assert (retreat.start_position, retreat.end_position) == ((4, 1), (3, 1))
