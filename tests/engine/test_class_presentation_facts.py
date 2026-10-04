"""Existing class commands publish outcomes without changing their costs or owners."""

from uuid import uuid4

import pytest

from dnd.actions_functional import setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig
from dnd.classes.barbarian import RelentlessRage
from dnd.classes.fighter import Indomitable, Survivor
from dnd.classes.rage import Raging
from dnd.classes.sorcerer import (SorceryPointsFeature, ConvertSlotToSP, ConvertSPToSlot,
    QuickenedSpell, TwinnedSpell, DistantSpell, ElementalAffinityResistanceAction, DraconicPresence)
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, EventType, HealEvent, SavingThrowEvent, TakeDamageEvent
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import set_hp
from dnd.content.characters.fighter_grants import apply_fighter_level
from dnd.content.characters.barbarian_grants import apply_barbarian_level
from tests.progression.test_direct_fighter_progression import _fighter_level
from tests.progression.test_direct_barbarian_progression import _barbarian_level


@pytest.fixture
def scene():
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    actors = []
    for name, position in (("Owner", (3, 3)), ("Observer", (5, 3))):
        actor = Entity.create(uuid4(), name, config=EntityConfig(
            action_economy=ActionEconomyConfig(spell_slots={1: 3, 2: 2}),
            health=HealthConfig(max_hit_points_bonus=200)))
        actor.compose_entity(); setup_standard_actions(actor); game.deploy_entity(actor, position)
        actors.append(actor)
    Entity.update_all_entities_senses()
    yield tuple(actors)
    game.close(); reset_engine_runtime()


def add_feature(actor, feature, **kwargs):
    condition = feature(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, **kwargs)
    actor.add_condition(condition)
    assert condition.applied
    return condition


@pytest.mark.parametrize("face,succeeded", [(20, True), (1, False)])
def test_relentless_intervention_has_exact_owner_and_real_save_result(scene, face, succeeded):
    actor, source = scene
    add_feature(actor, Raging)
    feature = add_feature(actor, RelentlessRage)
    set_hp(actor, 10)
    with fixed_dice_faces(face):
        actor.receive_damage(20, DamageType.FORCE, source.uuid)
    damage = [event for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION][-1]
    assert damage.relentless_rage is not None
    assert damage.relentless_rage.condition_uuid == feature.uuid
    assert damage.relentless_rage.succeeded is succeeded
    hit_points = actor.get_normal_hp()
    assert hit_points == (1 if succeeded else -10), hit_points
    assert actor.action_economy.resources["relentless_rage"].current == (4 if succeeded else 5)
    if succeeded:
        assert actor.action_economy.reactions.normalized_score == 1


@pytest.mark.parametrize("face,succeeded", [(20, True), (1, False)])
def test_indomitable_records_actual_reroll_and_one_resource_debit(scene, face, succeeded):
    actor, source = scene
    feature = add_feature(actor, Indomitable)
    with fixed_dice_faces(1, face):
        actor.saving_throw(source.create_saving_throw_request(actor.uuid, "wisdom", 15))
    save = [event for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if isinstance(event, SavingThrowEvent) and event.phase is EventPhase.COMPLETION][-1]
    assert save.indomitable_reroll is not None
    assert save.indomitable_reroll.condition_uuid == feature.uuid
    assert save.indomitable_reroll.succeeded is succeeded and save.result is succeeded
    assert actor.action_economy.resources["indomitable"].current == 0
    assert actor.action_economy.reactions.normalized_score == 1


def test_survivor_healing_keeps_actual_condition_owner(scene):
    actor, _ = scene
    feature = add_feature(actor, Survivor)
    set_hp(actor, 25)
    actor.on_turn_start(round_number=1)
    heal = [event for event in EventQueue.get_events_by_type(EventType.HEAL)
        if isinstance(event, HealEvent) and event.phase is EventPhase.COMPLETION][-1]
    assert heal.source_condition_uuid == feature.uuid
    assert heal.actual_healing == 5 + actor.ability_scores.constitution.modifier
    assert actor.get_normal_hp() == 25 + heal.actual_healing


@pytest.mark.parametrize("remaining,expected_gain", [(3, 2), (5, 0)])
def test_font_gather_records_capped_gain_and_actual_slot_debit(scene, remaining, expected_gain):
    actor, _ = scene
    add_feature(actor, SorceryPointsFeature, sorcery_points=5)
    actor.action_economy.resources["sorcery_points"].current = remaining
    before_slots = actor.action_economy.spell_slot_value(2).normalized_score
    action = next(action for action in actor.registered_actions
        if isinstance(action, ConvertSlotToSP) and action.slot_level == 2)
    result = action.instantiate().apply()
    assert result is not None and not result.canceled and result.font_conversion is not None
    assert result.font_conversion.model_dump() == dict(direction="slot_to_points", slot_level=2,
        sorcery_points_delta=expected_gain, spell_slots_delta=-1)
    assert actor.action_economy.spell_slot_value(2).normalized_score == before_slots - 1
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert actor.action_economy.actions.normalized_score == 1


def test_font_shape_records_created_slot_and_actual_points_debit(scene):
    actor, _ = scene
    add_feature(actor, SorceryPointsFeature, sorcery_points=5)
    actor.action_economy.consume("spell_slot_2", 1)
    before_slots = actor.action_economy.spell_slot_value(2).normalized_score
    action = next(action for action in actor.registered_actions
        if isinstance(action, ConvertSPToSlot) and action.slot_level == 2)
    result = action.instantiate().apply()
    assert result is not None and not result.canceled and result.font_conversion is not None
    assert result.font_conversion.model_dump() == dict(direction="points_to_slot", slot_level=2,
        sorcery_points_delta=-3, spell_slots_delta=1)
    assert actor.action_economy.spell_slot_value(2).normalized_score == before_slots + 1
    assert actor.action_economy.resources["sorcery_points"].current == 2
    assert actor.action_economy.bonus_actions.normalized_score == 0


@pytest.mark.parametrize("action_type,mode", [(QuickenedSpell, "quickened"),
    (TwinnedSpell, "twinned"), (DistantSpell, "distant")])
def test_metamagic_snapshot_exposes_selected_mode_on_exact_pending_owner(scene, action_type, mode):
    actor, _ = scene
    add_feature(actor, SorceryPointsFeature, sorcery_points=5, metamagic_choices=[mode])
    action = next(action for action in actor.registered_actions if isinstance(action, action_type))
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    condition = actor.active_conditions["MetamagicActive"]
    assert condition.snapshot_state().metamagic_mode == mode
    assert condition.snapshot_state().condition_uuid == condition.uuid


def test_affinity_snapshot_exposes_native_energy_without_name_parsing(scene):
    actor, _ = scene
    add_feature(actor, SorceryPointsFeature, sorcery_points=5)
    action = ElementalAffinityResistanceAction(source_entity_uuid=actor.uuid, damage_type=DamageType.COLD, template=True)
    actor.register_action(action)
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    condition = actor.active_conditions["Elemental Affinity Resistance (Cold)"]
    assert condition.snapshot_state().energy_type is DamageType.COLD


@pytest.mark.parametrize("mode", ["awe", "fear"])
def test_presence_observation_carries_native_mode_and_only_observed_cells(scene, mode):
    actor, observer = scene
    add_feature(actor, SorceryPointsFeature, sorcery_points=10)
    action = DraconicPresence(source_entity_uuid=actor.uuid, mode=mode, template=True)
    actor.register_action(action)
    result = action.instantiate().apply()
    assert result is not None and not result.canceled
    Entity.update_all_entities_senses()
    effects = [effect for effect in observer.senses.spatial_effects.values()
        if effect.presence_mode is not None]
    assert len(effects) == 1 and effects[0].presence_mode == mode
    assert set(effects[0].positions) <= set(observer.senses.visible)
    assert effects[0].anchor_entity_uuid == actor.uuid


@pytest.mark.parametrize('feature,succeeded', [('indomitable',True),('indomitable',False),
    ('relentless',True),('relentless',False)])
def test_direct_progression_intervention_retains_outcome_without_a_synthetic_condition(scene, feature, succeeded):
    actor, source = scene
    if feature == 'indomitable':
        for level in range(1,10):
            apply_fighter_level(actor,_fighter_level(level))
        with fixed_dice_faces(1,20 if succeeded else 1):
            actor.saving_throw(source.create_saving_throw_request(actor.uuid,'wisdom',15))
        events = [row for row in EventQueue.get_events_by_type(EventType.SAVING_THROW)
            if isinstance(row,SavingThrowEvent) and row.phase is EventPhase.COMPLETION]
        outcome = events[-1].indomitable_reroll
        assert actor.action_economy.resources['indomitable'].current == 0
    else:
        for level in range(1,12):
            apply_barbarian_level(actor,_barbarian_level(level))
        rage = actor.get_action_template('Frenzy'); assert rage is not None
        result = rage.instantiate().apply(); assert result is not None and not result.canceled
        set_hp(actor,10)
        with fixed_dice_faces(20 if succeeded else 1):
            actor.receive_damage(20,DamageType.FORCE,source.uuid)
        events = [row for row in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
            if isinstance(row,TakeDamageEvent) and row.phase is EventPhase.COMPLETION]
        outcome = events[-1].relentless_rage
        assert actor.get_normal_hp() == (1 if succeeded else -10)
    assert outcome is not None and outcome.condition_uuid is None
    assert outcome.succeeded is succeeded
    assert any(row.behavior_id.endswith('.'+('indomitable' if feature == 'indomitable' else 'relentless_rage'))
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW if feature == 'indomitable'
            else EventType.TAKE_DAMAGE) for row in event.effective_handler_presentations)
