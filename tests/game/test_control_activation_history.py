"""Recorded native Command turns own activation; its crest does not block movement."""

from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.enchantment import Command
from devtools.animation_review.control_cases import control_spell_history
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography, sample_motion
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.player_facts import SpellFact, TurnFact
from game.player_reduction import reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def appearances(state, data):
    return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
                                                        data.condition_media)
            for actor in state.actors.values()}


@pytest.mark.parametrize("program", ("grovel", "halt", "flee"))
@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_command_activates_once_at_actual_recipient_turn_without_delaying_flee(data, program, role):
    state, roots = player_history(control_spell_history(program=program), role=role)
    recipient = next(actor.uuid for actor in state.actors.values() if actor.name == "Recipient")
    behavior = f"condition.spell.command.{program}"
    records, clock, owner, activated, observed_turns = {}, 500., None, None, 0
    for root in roots:
        # Same retained presentation input used by live/review head admission.
        executed = frozenset(owner for owner, lifetime in records.items()
            if lifetime.activated_ms is not None and lifetime.activated_ms <= clock)
        group = bind_choreography(state, root, data, activated_conditions=executed)
        assert not group.gaps
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                               lineage=root, choreography=group)
        assert records == register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                                       lineage=root, choreography=group)
        after = reduce_lineage(state, root)
        owned = [row for row in records.values() if row.actor_uuid == recipient and row.behavior_id == behavior]
        if owned:
            record, = owned
            owner = record.owner_uuid
            if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.command":
                assert record.applied_ms is not None and record.activated_ms is None
            turn = root.root.fact
            if isinstance(turn, TurnFact) and turn.event_type is EventType.TURN_START and turn.entity_uuid == recipient:
                observed_turns += 1
                assert record.activated_ms == clock
                activated = record.activated_ms
                if program == "flee":
                    movement, = group.movements
                    assert movement.start_ms == 0
                    first = movement.timeline.legs[0]
                    assert first.start_ms == 0
                    midpoint = (first.start_ms + first.end_ms) / 2
                    sample = sample_motion(movement.timeline, data, midpoint)
                    assert sample.contact is not None
                    assert movement.timeline.settled_contact is not None
                    assert sample.contact.grid != movement.timeline.actor.grid
                    assert sample.contact.grid != movement.timeline.settled_contact.grid
                    # Flee has already moved while its Command execution crest is playing.
                    shown = sample_condition_lifetimes(appearances(sample.displayed, data), records, data,
                                                      clock + midpoint)[str(recipient)]
                    assert any("command.execute" in data.condition_media[layer.layer.assetId].asset_id
                               for layer in shown.layers)
                if program == "grovel":
                    assert any(condition.behavior_id == "condition.prone"
                               for condition in after.actors[recipient].conditions)
                    settled = sample_choreography(group, group.complete_ms).displayed
                    assert appearances(settled, data)[str(recipient)].body_pose == "Die"
            elif activated is not None:
                assert record.activated_ms == activated
            if isinstance(turn, TurnFact) and turn.event_type is EventType.TURN_END and turn.entity_uuid == recipient:
                assert group.complete_ms == 0, "Completed execution must not reserve a hidden cancellation window"
                assert not any(condition.behavior_id == behavior for condition in after.actors[recipient].conditions)
                if program == "grovel":
                    assert any(condition.behavior_id == "condition.prone"
                               for condition in after.actors[recipient].conditions)
        state = after
        clock += group.complete_ms + 25
    assert owner is not None and activated is not None and observed_turns == 1
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def canceled_command_history():
    """A real pending Halt is removed before the recipient's next native turn."""
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        caster = Entity.create(uuid4(), "Caster", config=EntityConfig(position=(3, 6), faction="heroes",
            action_economy=ActionEconomyConfig(spell_slots={1: 1}),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=3, mode="maximums")])))
        target = Entity.create(uuid4(), "Recipient", config=EntityConfig(position=(4, 6), faction="enemies",
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=3, mode="maximums")])))
        for actor in (caster, target):
            setup_standard_actions(actor)
            if actor is caster:
                register_spell(actor, Command)
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        encounter = Encounter(name="Cancel pending Command", source_entity_uuid=caster.uuid)
        for actor in (caster, target):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Pending Command initialization", start_cursor=0, end_cursor=baseline,
                                   observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        template = next(action for action in caster.registered_actions if isinstance(action, Command))
        command = template.instantiate(target_entity_uuid=target.uuid, command_word="halt")
        with fixed_dice_faces(1):
            result = command.apply()
        assert isinstance(result, SpellEvent) and not result.canceled
        assert "Command: Halt" in target.active_conditions
        assert target.remove_condition("Command: Halt")
        encounter.next_turn()
        assert encounter.get_current_entity() is target
        assert target.action_economy.actions.normalized_score == 1
        captured = capture_history(before, (), observers=(ObserverCapture("caster", caster.uuid, baseline),
                                                          ObserverCapture("recipient", target.uuid, baseline)))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_pending_command_removed_before_turn_never_plays_execution(data, role):
    state, roots = player_history(canceled_command_history(), role=role)
    records, clock, application_seen, clear_seen, turn_seen = {}, 0., False, False, False
    for root in roots:
        executed = frozenset(owner for owner, lifetime in records.items()
            if lifetime.activated_ms is not None and lifetime.activated_ms <= clock)
        group = bind_choreography(state, root, data, activated_conditions=executed)
        assert not group.gaps
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
                                               lineage=root, choreography=group)
        after = reduce_lineage(state, root)
        for record in records.values():
            if record.behavior_id != "condition.spell.command.halt":
                continue
            application_seen |= record.applied_ms is not None
            clear_seen |= record.removed_ms is not None
            assert record.activated_ms is None
            if record.removed_ms is not None and clock <= record.removed_ms:
                recipe = data.condition_recipes[record.behavior_id]
                clear_duration = max(effect.startOffsetMs + effect.durationMs for effect in recipe.removal.effects)
                assert group.complete_ms == pytest.approx(clear_duration)
                clearing = sample_condition_lifetimes(appearances(after, data), records, data,
                    record.removed_ms + clear_duration / 2)[str(record.actor_uuid)]
                assert len(clearing.layers) == 2
                assert all("command.removal" in layer.layer.assetId for layer in clearing.layers)
            for at in (clock, clock + group.complete_ms / 2, clock + group.complete_ms):
                shown = sample_condition_lifetimes(appearances(after, data), records, data, at)
                assert not any("command.execute" in (data.condition_media[layer.layer.assetId].asset_id or "")
                               for appearance in shown.values() for layer in appearance.layers)
        if isinstance(root.root.fact, TurnFact) and root.root.fact.event_type is EventType.TURN_START:
            turn_seen = True
        state = after
        clock += group.complete_ms + 25
    assert application_seen and clear_seen and turn_seen
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
