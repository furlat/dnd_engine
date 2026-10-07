"""Scalar reads preserve native math without retaining temporary value graphs."""

import random
from uuid import UUID, uuid4

import pytest

from dnd.blocks.abilities import Ability, AbilityConfig, ability_score_normalizer
from dnd.blocks.equipment import ArmorClassFormulaCandidate
from dnd.controller import Controller, HumanController, PassController, TurnContext
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.modifiers import ContextualNumericalModifier, NumericalModifier
from dnd.core.values import BaseValue, ModifiableValue
from dnd.encounter import AdvanceResult, Encounter, TurnState
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.player.session import close_session, create_session, snapshot_player_hud
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def isolated_native_runtime():
    random_state = random.getstate()
    reset_engine_runtime()
    try:
        yield
    finally:
        reset_engine_runtime()
        random.setstate(random_state)


def registry_identities():
    # Registry retention is the measured regression, alongside observable math.
    return frozenset(BaseObject._registry), frozenset(BaseValue._registry)


@pytest.mark.parametrize("target_on_base", [True, False])
@pytest.mark.parametrize("focused_context, expected", [(False, 5), (True, 6)])
def test_temporary_values_preserve_context_bounds_and_owned_uuid_lookup(
        target_on_base, focused_context, expected):
    owner, target = uuid4(), uuid4()
    base = ModifiableValue.create(source_entity_uuid=owner, target_entity_uuid=target, base_value=16,
        score_normalizer=ability_score_normalizer)
    bonus = ModifiableValue.create(source_entity_uuid=owner, target_entity_uuid=target, base_value=1)
    ceiling = NumericalModifier(source_entity_uuid=owner, value=6)
    bonus.self_static.add_max_constraint(ceiling)
    incoming = ModifiableValue.create(source_entity_uuid=target, target_entity_uuid=owner)
    incoming.to_target_static.add_value_modifier(
        NumericalModifier(source_entity_uuid=target, value=1))
    focused = NumericalModifier(source_entity_uuid=target, value=2)

    def focus_bonus(source_entity_uuid: UUID, target_entity_uuid: UUID | None,
                    context: dict | None) -> NumericalModifier | None:
        return focused if context and context.get("focused") else None

    incoming.to_target_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=target, callable=focus_bonus))
    incoming.set_context({"focused": focused_context})
    (base if target_on_base else bonus).set_from_target(incoming)
    registered = base.combine_values([bonus])
    assert ModifiableValue.get(registered.uuid) is registered
    before = registry_identities()
    for _ in range(20):
        temporary = base.combine_values([bonus], use_register=False)
        standalone = ModifiableValue.create(source_entity_uuid=owner,
            base_value=16, score_normalizer=ability_score_normalizer, use_register=False)
        assert standalone.normalized_score == 3
        assert ModifiableValue.get(standalone.uuid) is None
        assert ModifiableValue.get(temporary.uuid) is None
        assert temporary.normalized_score == registered.normalized_score == expected
        assert temporary.get_breakdown() == registered.get_breakdown()
    assert registry_identities() == before
    assert ModifiableValue.get(base.uuid) is base
    assert ModifiableValue.get(bonus.uuid) is bonus
    assert NumericalModifier.get(ceiling.uuid) is ceiling
    assert NumericalModifier.get(focused.uuid) is focused
    base_modifier = base.get_base_modifier()
    assert base_modifier is not None
    assert NumericalModifier.get(base_modifier.uuid) is base_modifier


def test_temporary_ability_read_keeps_combined_constraints():
    ability = Ability.create(source_entity_uuid=uuid4(), name="constitution",
        config=AbilityConfig(ability_score=16, modifier_bonus=2))
    ability.modifier_bonus.self_static.add_max_constraint(
        NumericalModifier(source_entity_uuid=ability.source_entity_uuid, value=4))
    registered = ability.get_combined_values()
    assert ModifiableValue.get(registered.uuid) is registered
    assert registered.normalized_score == 4
    # Adding separately normalized channel scores would incorrectly return 5.
    before = registry_identities()
    for _ in range(30):
        assert ability.get_combined_values(use_register=False).normalized_score == 4
    assert registry_identities() == before
    assert ModifiableValue.get(ability.ability_score.uuid) is ability.ability_score
    assert ModifiableValue.get(ability.modifier_bonus.uuid) is ability.modifier_bonus


def test_repeated_hud_and_stat_reads_leave_registries_and_native_events_unchanged():
    session = create_session()
    try:
        actors = tuple(session.game.entities[identity] for identity in session.player_uuids)
        # Exercise the temporary AC base-delta modifier, as well as ordinary AC.
        actors[0].equipment.add_armor_class_formula_candidate(ArmorClassFormulaCandidate(
            source_id=uuid4(), base_ac=22, ability_names=("dexterity",),
            requires_unarmored=False))
        expected_ac = tuple(actor.ac_bonus().normalized_score for actor in actors)
        hud = snapshot_player_hud(session)
        stats = tuple(actor.snapshot_entity_stats() for actor in actors)
        passive = tuple(actor.get_passive_perception() for actor in actors)
        owned = tuple(actor.ability_scores.constitution.ability_score for actor in actors)
        before = registry_identities()
        cursor = EventQueue.event_cursor()
        for _ in range(30):
            assert snapshot_player_hud(session) == hud
            assert tuple(actor.snapshot_entity_stats() for actor in actors) == stats
            assert tuple(actor.get_passive_perception() for actor in actors) == passive
            assert tuple(actor.ac_bonus(use_register=False).normalized_score
                for actor in actors) == expected_ac
        assert registry_identities() == before
        assert EventQueue.event_cursor() == cursor
        assert all(ModifiableValue.get(value.uuid) is value for value in owned)
    finally:
        close_session(session)


def test_turn_inputs_and_results_are_disposable_without_changing_native_boundaries():
    reset_engine_runtime(grid_size=(4, 4))
    game = Game()
    try:
        actors = tuple(Entity.create(uuid4(), name, config=EntityConfig(
            position=position, faction=faction)) for name, position, faction in (
                ("Human", (1, 1), "heroes"), ("Pass", (2, 1), "monsters")))
        for actor in actors:
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        human, automated = actors
        human_controller = HumanController(source_entity_uuid=human.uuid)
        pass_controller = PassController(source_entity_uuid=automated.uuid)
        encounter = Encounter(name="Passive return values", source_entity_uuid=uuid4())
        encounter.add_combatant(human, human_controller)
        encounter.add_combatant(automated, pass_controller)
        encounter.roll_initiative()
        encounter.initiative_order = [automated.uuid, human.uuid]
        encounter.start_encounter()

        result = encounter.advance_until_player()
        context = encounter.build_current_turn_context()
        assert result.status == "waiting_for_human"
        assert result.entity_uuid == human.uuid and result.entity_name == human.name
        assert result.round_number == 1 and result.turn_index == 1
        assert encounter.turn_state is TurnState.IN_PROGRESS
        assert encounter.combatants[automated.uuid].turn_count == 1
        assert context.entity_uuid == human.uuid and context.encounter_uuid == encounter.uuid
        assert context.turn_execution_id == encounter.current_turn_execution_id
        assert context.actions_remaining == human.action_economy.actions.normalized_score
        assert context.initiative_order == encounter.initiative_order
        expected_context = context.model_dump(exclude={"uuid"})
        before = registry_identities()
        history = tuple(EventQueue.iter_events_since(0))
        assert history
        for _ in range(30):
            latest = encounter.advance_until_player()
            current = encounter.build_current_turn_context()
            assert latest.status == result.status and latest.entity_uuid == result.entity_uuid
            assert latest.round_number == result.round_number and latest.turn_index == result.turn_index
            assert current.model_dump(exclude={"uuid"}) == expected_context
            assert TurnContext.get(current.uuid) is None
            assert AdvanceResult.get(latest.uuid) is None
        assert registry_identities() == before
        assert tuple(EventQueue.iter_events_since(0)) == history
        assert all(EventQueue.get_event_by_uuid(event.uuid) is event for _, event in history)
        assert Controller.get(human_controller.uuid) is human_controller
        assert Controller.get(pass_controller.uuid) is pass_controller
        assert Encounter.get(encounter.uuid) is encounter
        assert BaseObject.get(encounter.combatants[human.uuid].uuid) is encounter.combatants[human.uuid]
        assert not any(isinstance(value, (TurnContext, AdvanceResult))
            for value in BaseObject._registry.values())
    finally:
        game.close()


def test_passive_turn_values_keep_explicit_registration_available():
    owner = uuid4()
    context = TurnContext(source_entity_uuid=owner, entity_uuid=owner, use_register=True)
    result = AdvanceResult(source_entity_uuid=owner, status="waiting_for_human", use_register=True)
    assert TurnContext.get(context.uuid) is context
    assert AdvanceResult.get(result.uuid) is result
