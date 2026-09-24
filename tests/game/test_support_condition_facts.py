"""Support outcomes remain sufficient after native owners are gone."""

from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Invisible, Poisoned
from dnd.controller import HumanController
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType, HealEvent
from dnd.core.life_types import LifeState
from dnd.core.modifiers import AdvantageStatus
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.abjuration import DeathWard
from dnd.spells.necromancy import NoHealing
from dnd.spells.transmutation import EnhanceAbility, Regenerate
from game.event_record import decode_event, encode_event
from game.player_facts import ConditionChangeFact, HealFact, SpellFact, TurnFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.presentation import capture_interval, reduce_interval
from game.replay import ObserverCapture, RecordedSequence, capture_history


BATTLEFIELD = "battlefield.open_floor_bright"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def actor(game, name, position, *, faction="heroes"):
    entity = Entity.create(uuid4(), name, config=EntityConfig(
        position=position, faction=faction,
        action_economy=ActionEconomyConfig(spell_slots={2: 8, 4: 8, 7: 8}),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=12, mode="maximums")]),
    ))
    setup_standard_actions(entity)
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


@pytest.fixture
def arena():
    reset_engine_runtime()
    build_battlefield(BATTLEFIELD)
    game = Game()
    caster = actor(game, "Caster", (3, 6))
    recipient = actor(game, "Recipient", (4, 6))
    opponent = actor(game, "Opponent", (9, 7), faction="monsters")
    turns = Encounter(name="Support conditions", source_entity_uuid=caster.uuid)
    for entity in (caster, recipient, opponent):
        turns.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid))
    with fixed_dice_faces(20, 10, 1):
        turns.start_encounter()
    turns.start_turn()
    while turns.get_current_entity() is not caster:
        assert turns.next_turn() is not None
    try:
        yield game, caster, recipient, turns
    finally:
        game.close()
        reset_engine_runtime()


def cast(caster, target, behavior):
    choices = [(action, option) for action in get_available_actions(caster).all_actions
               if action.behavior_id == behavior and action.can_afford
               for option in action.valid_targets if option.target_uuid == target.uuid]
    assert choices, (behavior, target.name)
    with fixed_dice_faces(*([2] * 20)):
        result = execute_available_action(caster, *choices[0])
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    return result


def baseline(observer):
    cursor = EventQueue.event_cursor()
    initial = capture_interval(name="Support facts", start_cursor=0, end_cursor=cursor,
                               observer_uuid=observer.uuid, battlefield_id=BATTLEFIELD)
    before, _ = reduce_interval(None, initial)
    return before, cursor


def saved_views(game, before, cursor, *observers):
    captured = capture_history(before, (), observers=tuple(
        ObserverCapture(observer.name, observer.uuid, cursor) for observer in observers))
    encoded = {role: value.model_dump_json() for role, value in captured.views.items()}
    game.close()
    reset_engine_runtime()
    result = {}
    for role, value in encoded.items():
        native = RecordedSequence.model_validate_json(value, context=PASSIVE_EVENT_REPLAY)
        for lineage in native.lineages:
            if lineage.root.canceled:
                assert set(lineage.root.children_lineages) == {
                    node.lineage_uuid for node in lineage.events
                    if node.parent_lineage == lineage.root.lineage_uuid}
        public = project_sequence(native)
        result[role] = decode_player_sequence(encode_player_sequence(public))
    assert EventQueue.event_cursor() == 0
    return result


@pytest.mark.parametrize("ability", ABILITIES)
@pytest.mark.parametrize("self_target", (False, True), ids=("touch", "self"))
def test_enhance_choice_and_one_paid_cast_survive_both_recorded_boundaries(arena, ability, self_target):
    game, caster, recipient, _ = arena
    target = caster if self_target else recipient
    caster.register_action(EnhanceAbility(source_entity_uuid=caster.uuid, template=True,
                                         enhance_ability_type=ability))
    before, cursor = baseline(caster)
    slots = caster.action_economy.spell_slot_2.normalized_score
    result = cast(caster, target, "spell.enhance_ability")
    assert result.effect_id == f"support.enhance_ability.{ability}"
    assert caster.action_economy.spell_slot_2.normalized_score == slots - 1
    member = target.active_conditions["Enhance Ability"]
    identity = member.uuid
    assert member.snapshot_state().enhanced_ability == ability
    assert target.ability_scores.get_ability(ability).ability_score.advantage is AdvantageStatus.ADVANTAGE
    assert target.health.temporary_hit_points.normalized_score == (4 if ability == "constitution" else 0)
    caster.remove_condition("Concentrating")
    assert "Enhance Ability" not in target.active_conditions
    for _, roots in saved_views(game, before, cursor, caster, recipient).values():
        spells = [node.fact for root in roots for node in root.events if isinstance(node.fact, SpellFact)]
        assert len(spells) == 1
        assert spells[0].effect_id == f"support.enhance_ability.{ability}"
        changes = [node.fact for root in roots for node in root.events
                   if isinstance(node.fact, ConditionChangeFact) and node.fact.condition.condition_uuid == identity]
        assert [change.event_type for change in changes] == [EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL]
        assert all(change.condition.state.enhanced_ability == ability and not change.consumed for change in changes)


@pytest.mark.parametrize("ability", ABILITIES)
def test_enhance_choice_is_in_late_observation_without_inventing_a_default(arena, ability):
    game, caster, recipient, _ = arena
    caster.register_action(EnhanceAbility(source_entity_uuid=caster.uuid, template=True,
                                         enhance_ability_type=ability))
    cast(caster, recipient, "spell.enhance_ability")
    observer = actor(game, "Late observer", (5, 6))
    before, cursor = baseline(observer)
    member = next(row for row in before.actors[recipient.uuid].conditions if row.name == "Enhance Ability")
    assert member.state.enhanced_ability == ability
    legacy = member.state.model_dump(mode="json")
    legacy.pop("enhanced_ability")
    assert type(member.state).model_validate(legacy).enhanced_ability is None
    views = saved_views(game, before, cursor, observer)
    state, _ = views[observer.name]
    retained = next(row for row in state.actors[recipient.uuid].conditions if row.name == "Enhance Ability")
    assert retained.state.enhanced_ability == ability


@pytest.mark.parametrize("ending", ("lethal", "instant_death", "remove", "expire", "replace"))
def test_ward_consumption_distinguishes_actual_protection_from_cleanup(arena, ending):
    game, caster, recipient, turns = arena
    register_spell(caster, DeathWard)
    before, cursor = baseline(caster)
    cast(caster, recipient, "spell.death_ward")
    ward = recipient.active_conditions["Death Ward"]
    recipient.receive_damage(1, DamageType.SLASHING, caster.uuid)
    assert recipient.active_conditions["Death Ward"].uuid == ward.uuid
    if ending == "lethal":
        recipient.receive_damage(200, DamageType.SLASHING, caster.uuid)
        assert recipient.get_normal_hp() == 1
        recipient.receive_damage(200, DamageType.SLASHING, caster.uuid)
        assert recipient.health.life_state is LifeState.DEAD
    elif ending == "instant_death":
        event = recipient.receive_instant_death(caster.uuid)
        assert event.canceled and recipient.health.life_state is LifeState.ALIVE
    elif ending == "replace":
        turns.next_turn()
        while turns.get_current_entity() is not caster:
            assert turns.next_turn() is not None
        cast(caster, recipient, "spell.death_ward")
        assert recipient.active_conditions["Death Ward"].uuid != ward.uuid
    else:
        recipient.remove_condition("Death Ward", expire=ending == "expire")
    native = [event for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, ConditionRemovalEvent) and event.phase is EventPhase.COMPLETION
              and event.condition_state.condition_uuid == ward.uuid]
    assert len(native) == 1
    assert native[0].consumed is (ending in ("lethal", "instant_death"))
    for _, roots in saved_views(game, before, cursor, caster, recipient).values():
        removals = [node.fact for root in roots for node in root.events
                    if isinstance(node.fact, ConditionChangeFact) and node.fact.event_type is EventType.CONDITION_REMOVAL
                    and node.fact.condition.condition_uuid == ward.uuid]
        assert len(removals) == 1
        assert removals[0].consumed is (ending in ("lethal", "instant_death"))
        if ending == "instant_death":
            root, removal = next((root, node) for root in roots for node in root.events
                                 if node.fact is removals[0])
            assert root.root.canceled
            assert removal.parent_lineage == root.root.lineage_uuid
            assert removal.lineage_uuid in root.root.children_lineages


def test_consumed_owner_does_not_label_linked_cleanup_as_consumption(arena):
    game, caster, recipient, _ = arena
    register_spell(caster, DeathWard)
    cast(caster, recipient, "spell.death_ward")
    ward = recipient.active_conditions["Death Ward"]
    child = Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid)
    recipient.add_condition(child)
    ward.add_linked_condition(recipient.uuid, child.uuid)
    before, cursor = baseline(caster)
    recipient.receive_instant_death(caster.uuid)
    for _, roots in saved_views(game, before, cursor, caster, recipient).values():
        removals = {node.fact.condition.condition_uuid: node.fact.consumed
                    for root in roots for node in root.events if isinstance(node.fact, ConditionChangeFact)
                    and node.fact.event_type is EventType.CONDITION_REMOVAL}
        assert removals == {ward.uuid: True, child.uuid: False}


def test_regenerate_records_only_its_actual_heals_through_final_tick_and_expiry(arena):
    game, caster, recipient, turns = arena
    register_spell(caster, Regenerate)
    recipient.receive_damage(90, DamageType.FORCE, caster.uuid)
    before, cursor = baseline(caster)
    cast(caster, recipient, "spell.regenerate")
    identity = recipient.active_conditions["Regenerating"].uuid
    recipient.receive_healing(2, caster.uuid)
    for _ in range(10):
        turns.next_turn()
        while turns.get_current_entity() is not recipient:
            assert turns.next_turn() is not None
    assert "Regenerating" not in recipient.active_conditions
    assert recipient.get_normal_hp() == 30 + 23 + 2 + 10
    for state, roots in saved_views(game, before, cursor, caster, recipient).values():
        heals = [node.fact for root in roots for node in root.events if isinstance(node.fact, HealFact)]
        assert [(heal.actual_healing, heal.source_condition_uuid) for heal in heals] == [(23, None), (2, None), *[(1, identity)] * 10]
        last = next(root for root in roots if any(isinstance(node.fact, ConditionChangeFact)
                    and node.fact.condition.condition_uuid == identity
                    and node.fact.event_type is EventType.CONDITION_REMOVAL for node in root.events))
        assert any(isinstance(node.fact, HealFact) and node.fact.source_condition_uuid == identity for node in last.events)
        assert isinstance(last.root.fact, TurnFact) and last.root.fact.entity_uuid == recipient.uuid
        for root in roots:
            state = reduce_lineage(state, root)
        assert all(member.condition_uuid != identity for member in state.actors[recipient.uuid].conditions)


@pytest.mark.parametrize("blocked", (False, True), ids=("full_hp", "blocked"))
def test_regenerate_zero_healing_keeps_provenance_without_claiming_a_positive_result(arena, blocked):
    game, caster, recipient, turns = arena
    register_spell(caster, Regenerate)
    if blocked:
        recipient.receive_damage(60, DamageType.FORCE, caster.uuid)
        recipient.add_condition(NoHealing(source_entity_uuid=recipient.uuid, target_entity_uuid=recipient.uuid))
    cast(caster, recipient, "spell.regenerate")
    identity = recipient.active_conditions["Regenerating"].uuid
    before, cursor = baseline(caster)
    turns.next_turn()
    while turns.get_current_entity() is not recipient:
        assert turns.next_turn() is not None
    for _, roots in saved_views(game, before, cursor, caster, recipient).values():
        heal, = (node.fact for root in roots for node in root.events if isinstance(node.fact, HealFact))
        assert heal.actual_healing == 0 and heal.was_blocked is blocked
        assert heal.source_condition_uuid == identity


def test_healing_owner_survives_late_observation_without_disclosing_an_unseen_caster(arena):
    game, caster, recipient, turns = arena
    register_spell(caster, Regenerate)
    recipient.receive_damage(80, DamageType.FORCE, caster.uuid)
    cast(caster, recipient, "spell.regenerate")
    identity = recipient.active_conditions["Regenerating"].uuid
    caster.add_condition(Invisible(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    observer = actor(game, "Late enemy observer", (5, 6), faction="monsters")
    before, cursor = baseline(observer)
    assert caster.uuid not in before.actors
    assert any(member.condition_uuid == identity for member in before.actors[recipient.uuid].conditions)
    turns.next_turn()
    while turns.get_current_entity() is not recipient:
        assert turns.next_turn() is not None
    state, roots = saved_views(game, before, cursor, observer)[observer.name]
    heal, = (node.fact for root in roots for node in root.events if isinstance(node.fact, HealFact))
    assert heal.source_condition_uuid == identity and heal.source_entity_uuid is None
    assert caster.uuid not in state.actors


def test_old_healing_record_does_not_acquire_a_condition_source():
    event = HealEvent.model_validate({"source_entity_uuid": uuid4()}, context=PASSIVE_EVENT_REPLAY)
    record = encode_event(event)
    record.pop("source_condition_uuid")
    assert decode_event(record).source_condition_uuid is None
