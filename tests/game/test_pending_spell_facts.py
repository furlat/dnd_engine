"""Actual grants, movement and area results survive the public saved boundary."""

from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.base_tiles import wall_factory
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventPhase, EventQueue, EventType, StepMovementEvent, TemporaryHitPointsChangedEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import AntimagicFieldZone
from dnd.spells.evocation import Shatter
from dnd.spells.necromancy import FalseLife
from dnd.spells.transmutation import EnhanceAbility, ExpeditiousRetreat, Haste
from dnd.types.actor import TemporaryHitPointsGrant
from game.player_facts import SpellFact, StepFact, TemporaryHitPointsFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history
from tests.game.movement_scenarios import movement_history


BATTLEFIELD = "battlefield.open_floor_bright"


@pytest.fixture
def arena():
    reset_engine_runtime()
    build_battlefield(BATTLEFIELD)
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game, name="Caster", position=(3, 3)):
    entity = Entity.create(uuid4(), name, config=EntityConfig(
        position=position, faction="heroes",
        action_economy=ActionEconomyConfig(spell_slots={1: 8, 2: 8, 3: 8}),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=6, mode="maximums")]),
    ))
    setup_standard_actions(entity)
    register_spell(entity, FalseLife)
    entity.register_action(EnhanceAbility(source_entity_uuid=entity.uuid, template=True,
                                         enhance_ability_type="constitution"))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def cast(entity, behavior, *, face=4, position=None, target_entity=None):
    choices = [(action, target) for action in get_available_actions(entity).all_actions
               if action.behavior_id == behavior and action.can_afford
               for target in action.valid_targets
               if (target.position == position if position is not None else target.target_uuid in (None, (target_entity or entity).uuid))]
    assert choices, (behavior, position)
    with fixed_dice_faces(*([face] * 30)):
        result = execute_available_action(entity, *choices[0])
    assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION
    return result


def start_turns(*actors):
    encounter = Encounter(name="Pending spell facts", source_entity_uuid=actors[0].uuid)
    for entity in actors:
        encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    with fixed_dice_faces(*([10] * len(actors))):
        encounter.start_encounter()
    encounter.start_turn()
    while encounter.get_current_entity() is not actors[0]:
        encounter.next_turn()
    return encounter


def next_turn(encounter, entity):
    encounter.next_turn()
    while encounter.get_current_entity() is not entity:
        encounter.next_turn()


def baseline(entity):
    cursor = EventQueue.event_cursor()
    initial = capture_interval(name="pending spell inputs", start_cursor=0, end_cursor=cursor,
                               observer_uuid=entity.uuid, battlefield_id=BATTLEFIELD)
    before, _ = reduce_interval(None, initial)
    return before, cursor


def decode(native):
    restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


def test_temporary_hp_accepted_owner_survives_partial_damage_and_ignored_casts(arena):
    caster = actor(arena)
    watcher = actor(arena, "Watcher", (5, 3))
    turns = start_turns(caster, watcher)
    before, cursor = baseline(caster)
    cast(caster, "spell.false_life")
    first = caster.health.temporary_hit_points_grant
    assert first is not None and first.source_id == "spell.false_life"
    snapshots: list[tuple[int, TemporaryHitPointsGrant | None]] = [(8, first)]
    for face in (1, 4):
        next_turn(turns, caster)
        cast(caster, "spell.false_life", face=face)
        assert caster.health.temporary_hit_points_grant == first
        snapshots.append((8, first))
    caster.receive_damage(3, DamageType.SLASHING, watcher.uuid)
    assert caster.health.temporary_hit_points_grant == first
    snapshots.append((5, first))
    next_turn(turns, caster)
    cast(caster, "spell.false_life")
    second = caster.health.temporary_hit_points_grant
    assert second is not None and second.instance_uuid != first.instance_uuid
    snapshots.append((8, second))
    next_turn(turns, caster)
    cast(caster, "spell.enhance_ability", face=6)
    other = caster.health.temporary_hit_points_grant
    assert other is not None and other.source_id is None and other.instance_uuid != second.instance_uuid
    snapshots.append((12, other))
    caster.receive_damage(12, DamageType.SLASHING, watcher.uuid)
    assert caster.health.temporary_hit_points_grant is None
    snapshots.append((0, None))
    grants = [event for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, TemporaryHitPointsChangedEvent)]
    assert [(event.resulting_temporary_hp, event.grant) for event in grants] == [
        (8, first), (8, second), (12, other)]
    history = capture_history(before, (), observers=(ObserverCapture("self", caster.uuid, cursor),
                                                    ObserverCapture("witness", watcher.uuid, cursor)))
    arena.close()
    reset_engine_runtime()
    for native in history.views.values():
        state, roots = decode(native)
        facts = [node.fact for root in roots for node in root.events if isinstance(node.fact, TemporaryHitPointsFact)]
        assert [(fact.resulting_temporary_hp, fact.grant) for fact in facts] == [
            (8, first), (8, second), (12, other)]
        observed = []
        for root in roots:
            state = reduce_lineage(state, root)
            if any(isinstance(node.fact, (SpellFact, TemporaryHitPointsFact))
                   or node.fact is not None and node.fact.kind == "damage" for node in root.events):
                current = state.actors[caster.uuid]
                observed.append((current.temporary_hp, current.temporary_hp_grant))
        assert observed == snapshots
        assert state.actors[caster.uuid].normal_hp == 60
    assert EventQueue.event_cursor() == 0


def test_temporary_hp_grant_is_in_late_observation_and_explicit_clear(arena):
    caster = actor(arena)
    turns = start_turns(caster)
    cast(caster, "spell.false_life")
    expected = caster.health.temporary_hit_points_grant
    assert expected is not None
    # The second observer did not exist when the grant was made.
    watcher = actor(arena, "Late witness", (5, 3))
    turns.add_combatant(watcher, HumanController(source_entity_uuid=watcher.uuid))
    before, cursor = baseline(watcher)
    assert before.actors[caster.uuid].temporary_hp_grant == expected
    caster.health.clear_temporary_hit_points()
    cleared = caster.health.temporary_hit_points_grant
    assert cleared is None
    history = capture_history(before, (), observers=(ObserverCapture("late", watcher.uuid, cursor),))
    arena.close()
    reset_engine_runtime()
    state, roots = decode(history.views["late"])
    assert state.actors[caster.uuid].temporary_hp_grant == expected
    assert state.actors[caster.uuid].temporary_hp == 8
    for root in roots:
        state = reduce_lineage(state, root)
    assert state.actors[caster.uuid].temporary_hp == 0
    assert state.actors[caster.uuid].temporary_hp_grant is None
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize(("boost", "speed", "behavior"), (
    ("none", 30, "action.move"), ("haste", 60, "action.move"), ("bonus-dash", 30, "action.move"),
    ("none", 30, "action.jump"), ("haste", 60, "action.jump"),
))
def test_committed_leg_speed_survives_native_and_player_wire(boost, speed, behavior):
    history = movement_history(route=((3, 3), (5, 3)), boost=boost, behavior=behavior)
    for native in history.views.values():
        _, roots = decode(native)
        steps = [node.fact for root in roots for node in root.events
                 if isinstance(node.fact, StepFact) and node.fact.committed]
        assert steps and all(step.resolved_speed_feet == speed for step in steps)
    assert EventQueue.event_cursor() == 0


def test_shatter_retains_the_executed_wall_clipped_footprint(arena):
    caster = actor(arena, position=(2, 4))
    register_spell(caster, Shatter)
    recipient = actor(arena, "Recipient", (7, 4))
    blocked = actor(arena, "Behind wall", (9, 4))
    get_map().set_tile(8, 4, tile=wall_factory((8, 4)))
    Entity.update_all_entities_senses()
    start_turns(caster, recipient, blocked)
    before, cursor = baseline(caster)
    result = cast(caster, "spell.shatter", position=recipient.position, face=4)
    assert isinstance(result, SpellEvent)
    footprint = result.resolved_area_positions
    assert footprint is not None and recipient.position in footprint and blocked.position not in footprint
    assert (7, 6) in footprint and (7, 7) not in footprint
    assert recipient.get_hp() == 48 and blocked.get_hp() == 60
    history = capture_history(before, (), observers=(ObserverCapture("caster", caster.uuid, cursor),
                                                    ObserverCapture("recipient", recipient.uuid, cursor)))
    arena.close()
    reset_engine_runtime()
    for native in history.views.values():
        state, roots = decode(native)
        areas = [node.fact for root in roots for node in root.events
                 if isinstance(node.fact, SpellFact) and node.fact.behavior_id == "spell.shatter"
                 and node.fact.target_entity_uuid is None]
        assert areas and all(fact.resolved_area_positions is not None for fact in areas)
        for fact in areas:
            assert fact.resolved_area_positions is not None
            assert set(fact.resolved_area_positions) <= set(footprint)
            assert recipient.position in fact.resolved_area_positions
            assert blocked.position not in fact.resolved_area_positions
        for root in roots:
            state = reduce_lineage(state, root)
        assert state.actors[recipient.uuid].normal_hp == 48
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize(("spell", "speed"), (("spell.haste", 60), ("spell.expeditious_retreat", 30)))
def test_native_dash_adds_allowance_without_multiplying_recorded_speed(arena, spell, speed):
    caster = actor(arena)
    donor = actor(arena, "Haste donor", (2, 3)) if spell == "spell.haste" else caster
    register_spell(donor, Haste if spell == "spell.haste" else ExpeditiousRetreat)
    turns = start_turns(donor, caster) if donor is not caster else start_turns(caster)
    cast(donor, spell, target_entity=caster)
    next_turn(turns, caster)
    cast(caster, "action.dash")
    assert caster.action_economy.current_speed() == speed
    assert caster.action_economy.movement.normalized_score == 2 * speed
    cursor = EventQueue.event_cursor()
    result = cast(caster, "action.move", position=(4, 3))
    assert result is not None and caster.position == (4, 3)
    steps = [event for _, event in EventQueue.iter_events_since(cursor)
             if isinstance(event, StepMovementEvent) and event.phase is EventPhase.COMPLETION]
    assert len(steps) == 1 and steps[0].resolved_speed_feet == speed
    assert caster.action_economy.movement.normalized_score == 2 * speed - 5


def test_committed_speed_is_sampled_before_arrival_suppresses_haste(arena):
    caster = actor(arena, position=(2, 3))
    anchor = actor(arena, "Antimagic source", (3, 4))
    field = AntimagicFieldZone(source_entity_uuid=anchor.uuid, anchor_uuid=anchor.uuid,
                              position=anchor.position, affected_positions={(3, 3)})
    installation = EventQueue.publish_declaration(Event(source_entity_uuid=anchor.uuid,
        name="Antimagic field installation", event_type=EventType.BASE_ACTION, use_register=False))
    result = field.activate(parent_event=installation)
    installation.phase_to(EventPhase.COMPLETION)
    assert result is not None and not result.canceled
    register_spell(anchor, Haste)
    turns = start_turns(anchor, caster)
    cast(anchor, "spell.haste", target_entity=caster)
    next_turn(turns, caster)
    assert caster.action_economy.current_speed() == 60
    cursor = EventQueue.event_cursor()
    cast(caster, "action.move", position=(3, 3))
    assert caster.position == (3, 3) and "Haste" not in caster.active_conditions
    steps = [event for _, event in EventQueue.iter_events_since(cursor)
             if isinstance(event, StepMovementEvent) and event.phase is EventPhase.COMPLETION]
    assert len(steps) == 1 and steps[0].committed and steps[0].resolved_speed_feet == 60
    assert caster.action_economy.current_speed() != 60
