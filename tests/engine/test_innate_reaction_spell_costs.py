"""Existing fiend bodies exercise exact finite reaction-source ownership.

The test grants use existing source/resource APIs; they do not author a new NPC
or change the existing Devil's selected kit.
"""

from uuid import uuid4

import pytest

from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType
from dnd.blocks.health import HealthConfig
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.action_types import ActionSelection
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.progression import CasterProgression
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import (
    ShieldBuff,
    create_counterspell_reaction_handler,
    create_shield_reaction_handler,
)
from dnd.spells.evocation import MagicMissile
from dnd.types.character_progression import RitualPreparationPolicy


@pytest.fixture
def world():
    reset_engine_runtime(grid_size=(10, 6))
    game = Game()
    fiend = materialize_creature(FIEND_RECIPES_BY_ID["fellwing_devil"],
        runtime_entity_uuid=uuid4(), display_name="Fellwing Devil", position=(4, 2),
        faction="fiends", deployment_role=CreatureDeploymentRole(role_id="tests.innate_reactions"),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
    fiend.compose_entity()
    game.deploy_entity(fiend, fiend.position)
    caster = Entity.create(uuid4(), "Enemy caster", config=EntityConfig(faction="enemies",
        action_economy=ActionEconomyConfig(spell_slots={1: 6}),
        health=HealthConfig(max_hit_points_bonus=100)))
    caster.compose_entity()
    game.deploy_entity(caster, (2, 2))
    setup_standard_actions(caster)
    register_spell(caster, MagicMissile)
    yield fiend, caster
    game.close()
    reset_engine_runtime()


def innate_reaction(fiend, spell_id):
    source = uuid4()
    rank = 1 if spell_id == "spell.shield" else 3
    fiend.spellcasting.add_innate_source(source, "charisma",
        provider_id="species.fellwing_devil", provider_level=1, maximum_spell_rank=rank)
    resource = "daily_" + spell_id.removeprefix("spell.")
    fiend.action_economy.add_resource(resource, 1, RechargeType.LONG_REST)
    factory = create_shield_reaction_handler if spell_id == "spell.shield" else create_counterspell_reaction_handler
    handler = factory(fiend.uuid)
    fiend.add_event_handler(handler)
    fiend.spellcasting.add_learned_reaction_spell_source(spell_id=spell_id,
        source_id=source, handler_uuid=handler.uuid, fixed_cast_rank=rank, resource_name=resource)
    return source, resource, handler


def missiles(caster, target):
    caster.on_turn_start()
    Entity.update_all_entities_senses(max_distance=60)
    template = next(action for action in caster.registered_actions if isinstance(action, MagicMissile))
    with fixed_dice_faces(*([1] * 20)):
        result = caster.perform(template, ActionSelection(template_uuid=template.uuid,
            target_uuids=(target.uuid,)))
    assert result is not None
    return result


def reaction_payments(fiend):
    return [event for event in EventQueue.get_events_by_type(EventType.ACTION_COSTS_COMMITTED)
        if event.phase is EventPhase.COMPLETION and event.source_entity_uuid == fiend.uuid
        and event.effect_origin is not None]


@pytest.mark.parametrize("spell_id", ["spell.shield", "spell.counterspell"])
def test_innate_reaction_uses_one_daily_resource_and_only_long_rest_recovers_it(world, spell_id):
    fiend, caster = world
    source, resource, _ = innate_reaction(fiend, spell_id)
    hp = fiend.get_normal_hp()

    missiles(caster, fiend)

    assert fiend.get_normal_hp() == hp
    assert fiend.action_economy.get_resource_current(resource) == 0
    assert fiend.action_economy.reactions.normalized_score == 0
    payments = reaction_payments(fiend)
    assert len(payments) == 1
    assert payments[0].effect_origin.spellcasting_source_id == source
    assert payments[0].named_resource_costs == ((resource, 1),)
    fiend.on_turn_start()
    missiles(caster, fiend)
    assert fiend.get_normal_hp() == hp - 6
    assert fiend.action_economy.reactions.normalized_score == 1
    fiend.on_short_rest()
    assert fiend.action_economy.get_resource_current(resource) == 0
    assert fiend.on_long_rest()
    assert fiend.action_economy.get_resource_current(resource) == 1
    hp = fiend.get_normal_hp()
    missiles(caster, fiend)
    assert fiend.get_normal_hp() == hp


@pytest.mark.parametrize("spell_id", ["spell.shield", "spell.counterspell"])
def test_exhausted_innate_source_uses_only_a_learned_class_source_for_slot_fallback(world, spell_id):
    fiend, caster = world
    _, resource, handler = innate_reaction(fiend, spell_id)
    class_source = uuid4()
    fiend.spellcasting.add_source(class_source, "intelligence", provider_id="class.wizard",
        caster_progression=CasterProgression.FULL_CASTER, provider_level=5,
        maximum_spell_rank=3, ritual_policy=RitualPreparationPolicy.NONE)
    fiend.spellcasting.add_learned_reaction_spell_source(spell_id=spell_id,
        source_id=class_source, handler_uuid=handler.uuid)
    fiend.action_economy.set_normal_spell_slot_capacity(class_source, {3: 1})
    fiend.action_economy.set_resource_current(resource, 0)
    hp = fiend.get_normal_hp()

    missiles(caster, fiend)

    assert fiend.get_normal_hp() == hp
    assert fiend.action_economy.spell_slot_value(3).normalized_score == 0
    assert fiend.action_economy.get_resource_current(resource) == 0
    payment = reaction_payments(fiend)[0]
    assert payment.effect_origin.spellcasting_source_id == class_source
    assert payment.named_resource_costs == ()


@pytest.mark.parametrize("spell_id", ["spell.shield", "spell.counterspell"])
def test_refused_innate_reaction_keeps_its_daily_resource(world, spell_id):
    fiend, caster = world
    _, resource, _ = innate_reaction(fiend, spell_id)

    def refuse(event, _source):
        if spell_id == "spell.shield" and (
                not isinstance(event, ConditionApplicationEvent) or not isinstance(event.condition, ShieldBuff)):
            return None
        return event.cancel(status_message="Refused reaction")

    fiend.add_event_handler(EventHandler(source_entity_uuid=fiend.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION if spell_id == "spell.shield" else EventType.TRIGGER_EVENT,
            event_phase=EventPhase.DECLARATION)], event_processor=refuse))
    hp = fiend.get_normal_hp()

    missiles(caster, fiend)

    assert fiend.get_normal_hp() == hp - 6
    assert fiend.action_economy.get_resource_current(resource) == 1
    assert fiend.action_economy.reactions.normalized_score == 1
    assert not reaction_payments(fiend)


@pytest.mark.parametrize("spell_id", ["spell.shield", "spell.counterspell"])
def test_exhausted_innate_reaction_cannot_spend_unrelated_slots(world, spell_id):
    fiend, caster = world
    _, resource, _ = innate_reaction(fiend, spell_id)
    fiend.action_economy.set_resource_current(resource, 0)
    fiend.action_economy.set_normal_spell_slot_capacity(uuid4(), {3: 1})
    hp = fiend.get_normal_hp()

    missiles(caster, fiend)

    assert fiend.get_normal_hp() == hp - 6
    assert fiend.action_economy.spell_slot_value(3).normalized_score == 1
    assert fiend.action_economy.reactions.normalized_score == 1


@pytest.mark.parametrize("spell_id", ["spell.shield", "spell.counterspell"])
def test_source_removed_during_reaction_admission_cannot_pay(world, spell_id):
    fiend, caster = world
    source, resource, handler = innate_reaction(fiend, spell_id)

    def remove_source(event, _source):
        if spell_id == "spell.shield" and (
                not isinstance(event, ConditionApplicationEvent) or not isinstance(event.condition, ShieldBuff)):
            return None
        fiend.spellcasting.remove_learned_reaction_spell_source(
            spell_id=spell_id, source_id=source, handler_uuid=handler.uuid)
        return None

    fiend.add_event_handler(EventHandler(source_entity_uuid=fiend.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION if spell_id == "spell.shield" else EventType.TRIGGER_EVENT,
            event_phase=EventPhase.DECLARATION)], event_processor=remove_source))
    hp = fiend.get_normal_hp()

    missiles(caster, fiend)

    assert fiend.get_normal_hp() == hp - 6
    assert fiend.action_economy.get_resource_current(resource) == 1
    assert fiend.action_economy.reactions.normalized_score == 1
    assert "Shield" not in fiend.active_conditions
    assert not reaction_payments(fiend)
