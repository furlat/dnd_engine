"""Native summon casts, targeting, allegiance and terminal ownership."""

from uuid import uuid4

import pytest

from dnd.actions import DropConcentration
from dnd.core.base_actions import ActionEvent
from dnd.summoning.forms import SUMMON_FORMS
from dnd.types.summoning import SummonFamily, SummonRules, SummonSelection, SummonSustain
from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.creature_types import DamageType
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.summoning.actions import DismissSummon
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.summoning import ConjureAnimals, ConjureFey, ConjureFiend
from dnd.summoning.system import bind_summoning


@pytest.fixture
def battle():
    reset_engine_runtime(grid_size=(20,20))
    if not SERVER_CONTENT_SYSTEM_RUNTIME.is_installed:
        SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    game = Game()
    actors = []
    encounter = Encounter(source_entity_uuid=uuid4(), name="Summoning")
    for index, faction in enumerate(("heroes", "enemy")):
        actor = Entity.create(source_entity_uuid=uuid4(), name=f"Actor {index}", config=EntityConfig(
            faction=faction, position=(2+index*10,2), health=HealthConfig(max_hit_points_bonus=100),
            action_economy=ActionEconomyConfig(spell_slots={level:3 for level in range(3,10)}),
            spellcasting=SpellcastingConfig(spellcasting_ability="wisdom")))
        setup_standard_actions(actor)
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        actors.append(actor)
    encounter.initiative_order = [actor.uuid for actor in actors]
    encounter.start_encounter()
    encounter.start_turn()
    Entity.update_all_entities_senses()
    system = bind_summoning(game, encounter)
    yield game, encounter, system, *actors
    system.close()
    reset_engine_runtime(grid_size=(20,20))


@pytest.mark.parametrize("spell,form,level", [(ConjureAnimals,"wolf",3),
    (ConjureAnimals,"raptor",9),(ConjureFey,"jaguar",6),(ConjureFiend,"dretch",3)])
def test_one_chosen_creature_appears_at_one_chosen_position(battle, spell, form, level):
    game, encounter, system, caster, enemy = battle
    before = EventQueue.event_cursor()
    action = spell(source_entity_uuid=caster.uuid, form_id=form, cast_at_level=level, end_position=(4,2))
    result = action.apply()
    assert result is not None and not result.canceled, result
    assert len(system.memberships) == 1
    member = next(iter(system.memberships.values()))
    assert member.entity.position == (4,2)
    assert get_map().get_entity_position(member.entity.uuid) == (4,2)
    assert game.get_entity(member.entity.uuid) is member.entity
    assert encounter.initiative_order == [caster.uuid, member.entity.uuid, enemy.uuid]
    assert member.entity.faction == caster.faction
    assert member.existence.applied
    assert caster.action_economy.actions.normalized_score == 0
    births = [event for _,event in EventQueue.iter_events_since(before)
              if event.event_type is EventType.ENTITY_CREATED and event.phase is EventPhase.COMPLETION]
    assert len(births) == 1 and births[0].summon_origin == member.existence.origin
    assert births[0].initial_condition_states


@pytest.mark.parametrize("position,form,level", [((2,2),"wolf",3),((12,2),"wolf",3),
    ((19,19),"wolf",3),((4,2),"raptor",3),((4,2),"not-a-creature",3)])
def test_invalid_form_or_destination_spends_no_action(battle, position, form, level):
    _, _, system, caster, _ = battle
    result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id=form,
        cast_at_level=level, end_position=position).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert not system.memberships


def test_discovery_has_per_form_destination_choices_without_creating_creatures(battle):
    game, _, system, caster, _ = battle
    register_spell(caster, ConjureAnimals, caster_level=17)
    before = (set(game.entities), EventQueue.event_cursor())
    available = get_available_actions(caster, legal_only=True)
    rows = [row for row in available.all_actions if "__summon_" in row.template_name]
    assert rows and any("__summon_raptor" in row.template_name for row in rows)
    assert all(row.valid_targets for row in rows)
    assert before == (set(game.entities), EventQueue.event_cursor())
    assert not system.memberships


def cast_one(battle, spell=ConjureAnimals, form="wolf", level=3):
    _, _, system, caster, _ = battle
    result = spell(source_entity_uuid=caster.uuid, form_id=form, cast_at_level=level, end_position=(4,2)).apply()
    assert result is not None and not result.canceled
    return next(iter(system.memberships.values()))


def test_replacement_retires_previous_and_retains_only_new_birth(battle):
    game, encounter, system, caster, _ = battle
    first = cast_one(battle)
    caster.action_economy.reset_all_costs()
    result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id="boar", end_position=(5,2)).apply()
    assert result is not None and not result.canceled
    assert len(system.memberships) == 1
    assert first.entity.uuid not in game.entities
    assert first.entity.uuid not in encounter.combatants
    assert Entity.get(first.entity.uuid) is None
    assert next(iter(system.memberships.values())).entity.name == "Boar"


def test_fey_control_loss_preserves_body_duration_and_controller(battle):
    game, encounter, system, caster, _ = battle
    member = cast_one(battle, ConjureFey,"jaguar",6)
    identity, controller, duration = member.entity.uuid, member.controller, member.existence.duration.duration
    assert caster.remove_condition("Concentrating")
    assert system.memberships[identity] is member
    assert game.get_entity(identity) is member.entity
    assert member.entity.faction != caster.faction
    assert member.existence.duration.duration == duration
    assert member.controller is controller
    assert not DismissSummon(source_entity_uuid=caster.uuid, target_entity_uuid=identity).pre_validate()
    assert identity in encounter.combatants


def test_duration_skips_birth_interval_then_deduplicates_and_expires(battle):
    game, encounter, system, caster, _ = battle
    member = cast_one(battle)
    member.existence.duration.duration = 2
    member.entity.turn_duration_interval = (encounter.uuid, encounter.round_number)
    assert not member.entity.advance_duration_condition("Summoned")
    assert member.existence.duration.duration == 2
    member.entity.turn_duration_interval = (encounter.uuid, encounter.round_number+1)
    assert not member.entity.advance_duration_condition("Summoned")
    assert not member.entity.advance_duration_condition("Summoned")
    assert member.existence.duration.duration == 1
    member.entity.turn_duration_interval = (encounter.uuid, encounter.round_number+2)
    assert member.entity.advance_duration_condition("Summoned")
    assert not system.memberships and member.entity.uuid not in game.entities
    assert member.entity.uuid not in encounter.combatants


def test_duplicate_binding_rejected(battle):
    game, encounter, _, _, _ = battle
    with pytest.raises(ValueError, match="already bound"):
        bind_summoning(game, encounter)


def test_native_dismissal_discovery_execution_and_fey_lost_authority(battle):
    _, _, system, caster, _ = battle
    member = cast_one(battle, ConjureFey, "jaguar", 6)
    caster.action_economy.reset_all_costs()
    available = get_available_actions(caster, legal_only=True)
    action = next(row for row in available.all_actions if row.template_name == "Dismiss Summon")
    selected = next(target for target in action.valid_targets if target.target_uuid == member.entity.uuid)
    result = execute_by_index(caster, action.template_name, selected.index, available=available)
    assert result is not None and not result.canceled
    assert not system.memberships
    assert caster.action_economy.actions.normalized_score == 0
    caster.action_economy.reset_all_costs()
    member = cast_one(battle, ConjureFey, "jaguar", 6)
    assert caster.remove_condition("Concentrating")
    caster.action_economy.reset_all_costs()
    result = DismissSummon(source_entity_uuid=caster.uuid, target_entity_uuid=member.entity.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert member.existence.applied


def test_dismissal_veto_keeps_creature_but_expiry_is_mandatory(battle):
    game, _, system, caster, _ = battle
    member = cast_one(battle)
    def veto(event, source_uuid):
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == member.existence.uuid:
            return event.cancel(status_message="Reject voluntary removal")
    handler = EventHandler(source_entity_uuid=caster.uuid, event_processor=veto,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EXECUTION)])
    EventQueue.add_event_handler(handler)
    result = DropConcentration(source_entity_uuid=caster.uuid).apply()
    assert result is not None and result.canceled
    assert member.existence.applied and member.entity.uuid in game.entities
    member.existence.duration.duration = 1
    member.entity.turn_duration_interval = (uuid4(), 1)
    assert member.entity.advance_duration_condition("Summoned")
    assert not system.memberships and member.entity.uuid not in game.entities


def test_acquired_real_item_falls_intact_but_intrinsics_retire(battle):
    _, _, system, caster, _ = battle
    member = cast_one(battle)
    dagger = build_authored_item("weapon.dagger", member.entity.uuid)
    assert member.entity.loot_item(dagger)
    anatomy = tuple(item.uuid for item in member.entity.equipment.get_all_equipped_items())
    caster.action_economy.reset_all_costs()
    result = DismissSummon(source_entity_uuid=caster.uuid, target_entity_uuid=member.entity.uuid).apply()
    assert result is not None and not result.canceled
    assert not system.memberships
    assert dagger.owner_uuid is None
    assert get_map().get_object_position(dagger.uuid) == (4,2)
    assert all(BaseItem.get(identity) is None for identity in anatomy)


def test_zero_hp_is_terminal_without_corpse_or_death_saves(battle):
    game, encounter, system, caster, enemy = battle
    member = cast_one(battle)
    member.entity.uses_death_saves = True
    before = EventQueue.event_cursor()
    member.entity.receive_damage(member.entity.get_hp(), DamageType.FORCE, enemy.uuid)
    assert not system.memberships
    assert member.entity.uuid not in game.entities
    assert member.entity.uuid not in encounter.combatants
    assert Entity.get(member.entity.uuid) is None
    assert not member.entity.active_conditions_by_uuid
    assert not [event for _,event in EventQueue.iter_events_since(before)
        if event.source_entity_uuid == member.entity.uuid and event.event_type is EventType.DEATH_SAVE]


def test_extra_positions_cannot_silently_spawn_or_ignore_another_creature(battle):
    _,_, system, caster,_ = battle
    result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id="wolf", end_position=(4,2),
        extra_target_positions=[(5,2)]).apply()
    assert result is not None and result.canceled
    assert not system.memberships and caster.action_economy.actions.normalized_score == 1


def test_rebind_survivor_preserves_identity_duration_and_changes_assignment(battle):
    game, previous, system, caster, enemy = battle
    member = cast_one(battle, ConjureFey, "jaguar", 6)
    duration = member.existence.duration.duration
    old_controller = member.controller
    previous.end_encounter()
    next_encounter = Encounter(source_entity_uuid=uuid4(), name="Later fight")
    for actor in (caster, enemy):
        next_encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
    next_encounter.initiative_order = [caster.uuid, enemy.uuid]
    next_encounter.start_encounter()
    before = EventQueue.event_cursor()
    system.rebind_encounter(next_encounter)
    assert member.existence.duration.duration == duration
    assert member.controller is not old_controller
    assert previous.get_controller_for(member.entity.uuid) is None
    assert next_encounter.initiative_order == [caster.uuid, member.entity.uuid, enemy.uuid]
    assert not [event for _,event in EventQueue.iter_events_since(before) if event.event_type is EventType.ENTITY_CREATED]
    member.entity.turn_duration_interval = (next_encounter.uuid, next_encounter.round_number)
    member.entity.advance_duration_condition("Summoned")
    assert member.existence.duration.duration == duration - 1


def test_uncontrolled_fey_rejoins_without_its_former_summoner(battle):
    _, previous, system, caster, enemy = battle
    member = cast_one(battle, ConjureFey, "jaguar", 6)
    caster.remove_condition("Concentrating")
    previous.end_encounter()
    later = Encounter(source_entity_uuid=uuid4(), name="Hostile spirit")
    later.add_combatant(enemy, HumanController(source_entity_uuid=enemy.uuid))
    later.initiative_order = [enemy.uuid]
    later.start_encounter()
    system.rebind_encounter(later)
    assert member.entity.uuid in later.initiative_order
    assert caster.uuid not in later.combatants
    assert member.existence.applied


@pytest.mark.parametrize("form", SUMMON_FORMS, ids=lambda form:f"{form.family.value}-{form.form_id}")
def test_all_authored_forms_cast_at_their_unlock_level(battle,form):
    _,_,system,caster,_ = battle
    spells = {SummonFamily.ANIMALS: ConjureAnimals, SummonFamily.FEY: ConjureFey, SummonFamily.FIEND: ConjureFiend}
    result = spells[form.family](source_entity_uuid=caster.uuid, form_id=form.form_id,
        cast_at_level=form.minimum_slot, end_position=(4,2)).apply()
    assert result is not None and not result.canceled
    member = next(iter(system.memberships.values()))
    assert member.entity.content_ref == form.recipe.ref
    assert member.existence.origin.manifestation is form.manifestation


def test_authored_independent_summon_expires_without_a_concentration_owner(battle):
    game,encounter,system,caster,_ = battle
    event = ActionEvent(source_entity_uuid=caster.uuid, phase=EventPhase.EFFECT)
    selection = SummonSelection(family=SummonFamily.ANIMALS, form_id="wolf",cast_at_level=3,target_position=(4,2))
    assert system.create_summon(selection, parent_event=event,
        rules=SummonRules(duration_rounds=2,sustain=SummonSustain.NONE))
    member = next(iter(system.memberships.values()))
    assert "Concentrating" not in caster.active_conditions
    assert member.existence.parent_link is None
    member.entity.turn_duration_interval = (encounter.uuid,encounter.round_number+2)
    member.entity.advance_duration_condition("Summoned")
    member.entity.turn_duration_interval = (encounter.uuid,encounter.round_number+3)
    assert member.entity.advance_duration_condition("Summoned")
    assert member.entity.uuid not in game.entities


def test_missing_binding_rejects_cast_before_costs(battle):
    _, _, system, caster, _ = battle
    system.close()
    result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id="wolf", end_position=(4,2)).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1


@pytest.mark.parametrize("interruption", ("execution", "effect", "effect_exception", "incoming_condition"))
def test_paid_interruption_preserves_previous_summon_and_has_no_new_birth(battle, interruption):
    game, _, system, caster, _ = battle
    first = cast_one(battle)
    old_concentration = caster.active_conditions["Concentrating"].uuid
    caster.action_economy.reset_all_costs()
    start = EventQueue.event_cursor()
    event_type = EventType.CONDITION_APPLICATION if interruption == "incoming_condition" else EventType.CAST_SPELL
    phase = EventPhase.EFFECT if interruption in ("effect", "effect_exception") else EventPhase.EXECUTION
    def reject(event, source_uuid):
        if interruption == "effect_exception":
            raise RuntimeError("Injected cast effect failure")
        if interruption != "incoming_condition" or event.condition.name == "Concentrating":
            return event.cancel(status_message="Incoming cast interrupted")
    handler = EventHandler(source_entity_uuid=caster.uuid, event_processor=reject,
        trigger_conditions=[Trigger(event_type=event_type, event_phase=phase)])
    EventQueue.add_event_handler(handler)
    try:
        action = ConjureAnimals(source_entity_uuid=caster.uuid, form_id="boar", end_position=(5,2))
        if interruption == "effect_exception":
            with pytest.raises(RuntimeError, match="Injected cast effect failure"):
                action.apply()
        else:
            result = action.apply()
            assert result is not None and result.canceled
        assert caster.action_economy.actions.normalized_score == 0
        assert caster.active_conditions["Concentrating"].uuid == old_concentration
        assert list(system.memberships) == [first.entity.uuid]
        assert first.existence.applied and game.get_entity(first.entity.uuid) is first.entity
        assert not any(event.event_type is EventType.ENTITY_CREATED and event.phase is EventPhase.COMPLETION
            for _,event in EventQueue.iter_events_since(start))
    finally:
        handler.remove()
        handler.remove_from_register()


@pytest.mark.parametrize("spell,form,level,survives", (
    (ConjureAnimals,"wolf",3,False),(ConjureFiend,"dretch",3,False),(ConjureFey,"jaguar",6,True)))
def test_source_death_ends_required_sustain_even_when_removal_is_vetoed(battle, spell, form, level, survives):
    game, _, system, caster, enemy = battle
    member = cast_one(battle, spell, form, level)
    identity, clock, controller = member.entity.uuid, member.existence.duration.duration, member.controller
    def reject(event, source_uuid):
        return event.cancel(status_message="Voluntary removal forbidden")
    handler = EventHandler(source_entity_uuid=enemy.uuid, event_processor=reject,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EXECUTION)])
    EventQueue.add_event_handler(handler)
    try:
        caster.receive_damage(caster.get_hp() + caster.get_max_hp(), DamageType.FORCE, enemy.uuid)
        assert (identity in game.entities) is survives
        if survives:
            assert system.memberships[identity].entity is member.entity
            assert member.entity.faction != caster.faction
            assert member.existence.duration.duration == clock
            assert member.controller is controller
        else:
            assert identity not in system.memberships and Entity.get(identity) is None
    finally:
        handler.remove()
        handler.remove_from_register()


def test_close_twice_removes_authority_and_allows_a_fresh_explicit_binding(battle):
    game, encounter, system, _, _ = battle
    member = cast_one(battle)
    system.close()
    system.close()
    assert member.entity.uuid not in game.entities and Entity.get(member.entity.uuid) is None
    assert not member.entity.has_runtime_agency()
    replacement = bind_summoning(game, encounter)
    replacement.close()


def test_replaced_creature_has_no_agency_during_incoming_birth_publication(battle):
    _, _, _, caster, _ = battle
    first = cast_one(battle)
    caster.action_economy.reset_all_costs()
    observations = []
    def observe(event):
        if event.event_type is EventType.ENTITY_CREATED:
            observations.append((first.existence.applied, first.entity.has_runtime_agency(),
                first.entity.can_take_actions()))
    EventQueue.add_pre_completion_callback(observe)
    result = ConjureAnimals(source_entity_uuid=caster.uuid, form_id="boar", end_position=(5,2)).apply()
    assert result is not None and not result.canceled
    assert observations == [(False,False,False)]


def test_duplicate_admitted_effect_delivery_does_not_create_another_creature(battle):
    game, _, system, caster, _ = battle
    cursor = EventQueue.event_cursor()
    member = cast_one(battle)
    effect = next(event for _, event in EventQueue.iter_events_since(cursor)
                  if event.event_type is EventType.CAST_SPELL and event.phase is EventPhase.EFFECT)
    entities = set(game.entities)
    before = EventQueue.event_cursor()
    result = EventQueue.invoke_admitted_system_effect(system.uuid, effect)
    assert result is effect
    assert set(game.entities) == entities
    assert list(system.memberships) == [member.entity.uuid]
    assert caster.action_economy.actions.normalized_score == 0
    assert not any(event.event_type is EventType.ENTITY_CREATED
                   for _, event in EventQueue.iter_events_since(before))
