"""Discovered native forced movement, detached with its complete ancestry."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import ShoveEvent
from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import BodyPart
from dnd.core.events import Event, EventPhase, EventQueue, ForcedMovementEvent, StepMovementEvent
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.transmutation import Telekinesis
from dnd.types.senses import SenseMode, SensesType
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)


def _modular_actor(name: str, position: tuple[int, int], *, source: bool = False, hp: int = 40) -> Entity:
    actor = Entity.create(uuid4(), name, config=EntityConfig(
        position=position, faction="heroes" if source else "monsters",
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18 if source else 10)),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=4 if hp == 4 else 10, hit_dice_count=1 if hp == 4 else 4, mode="maximums",
        )]),
        action_economy=ActionEconomyConfig(spell_slots={5: 1} if source else {}),
        appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22" if source else "Head10",
                                    has_beard=False),
    ))
    actor.install_initial_items((
        (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
        (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
    ))
    setup_standard_actions(actor)
    return actor


def forced_movement_history(
    *, source_position: tuple[int, int] = (3, 3), target_position: tuple[int, int] = (4, 3),
    battlefield_id: str = "battlefield.open_floor_bright", seed: int = 0,
    blocker_position: tuple[int, int] | None = None, watcher_position: tuple[int, int] | None = None,
    target_identity: str | None = None, target_hp: Literal[4, 40] = 40,
    mechanism: Literal["shove", "telekinesis"] = "shove", destination: tuple[int, int] | None = None,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Execute a Shove or an earned Telekinesis Move through action discovery.

    For Telekinesis, the actual cast/grab establishes the returned baseline;
    the complete granted Move lineage is the reviewed forced-movement action.
    Map content owns hazards, support transitions and blocking objects. An
    optional native creature carries an opportunity handler beside the route.
    """
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield(battlefield_id)
    game = Game()
    try:
        source = _modular_actor("Shover" if mechanism == "shove" else "Telekinesis caster", source_position, source=True)
        if target_identity is None:
            target = _modular_actor("Recipient", target_position, hp=target_hp)
        else:
            assert target_hp == 40, "canonical creature health comes from its content recipe"
            declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[target_identity]
            target = materialize_creature(
                ContentRecipe.create(ref=declaration.ref, parameters={}), runtime_entity_uuid=uuid4(),
                display_name=declaration.descriptor.display_name, faction="monsters", position=target_position,
                deployment_role=CreatureDeploymentRole(role_id="scenario.forced_movement"),
                possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
            )
        actors = [source, target]
        if blocker_position is not None:
            actors.append(_modular_actor("Blocking creature", blocker_position))
        watcher = None
        if watcher_position is not None:
            watcher = materialize_creature(
                BESTIARY_CREATURE_RECIPES_BY_ID["goblin"], runtime_entity_uuid=uuid4(),
                display_name="Armed watcher", faction="heroes", position=watcher_position,
                deployment_role=CreatureDeploymentRole(role_id="scenario.forced_movement"),
                possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
            )
            add_opportunity_attack_handler(watcher)
            actors.append(watcher)
        if mechanism == "telekinesis":
            assert destination is not None
            register_spell(source, Telekinesis)
        births = tuple(actor.compose_entity() for actor in actors)
        for actor in actors:
            if built.definition.light_level == "darkness":
                actor.senses.add_sense_mode_source(actor.uuid,
                    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Native forced movement", source_entity_uuid=uuid4())
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not source:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(name="forced movement startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=source.uuid, battlefield_id=battlefield_id, seed_cursor=cursor,
            seed_snapshot=capture_senses_snapshot(source.senses))
        baseline, _ = reduce_interval(None, startup)
        latest = seed_actors(baseline, births,
            active_weapon_sets={actor.uuid: actor.equipment.active_weapon_set for actor in actors})
        history: list[CompletedLineage] = []

        def retain(start: int) -> None:
            nonlocal latest
            for _, root in EventQueue.iter_events_since(start):
                if root.parent_lineage is not None or root.phase not in (EventPhase.COMPLETION, EventPhase.CANCEL):
                    continue
                lineage = capture_lineage(root, observer_uuid=source.uuid)
                for event in lineage.events:
                    native = EventQueue.get_event_by_uuid(event.uuid)
                    assert native is not None
                    assert (event.parent_event, event.parent_lineage, event.children_lineages) == (
                        native.parent_event, native.parent_lineage, native.children_lineages)
                    assert event.identified_entity_observer_uuids == native.identified_entity_observer_uuids
                    assert event.located_entity_observer_uuids == native.located_entity_observer_uuids
                    assert event.located_position_observer_uuids == native.located_position_observer_uuids
                latest = reduce_lineage(latest, lineage)
                history.append(lineage)
            for actor in actors:
                retained = latest.actors[actor.uuid]
                assert (retained.normal_hp, retained.life_state) == (actor.get_normal_hp(), actor.health.life_state)
                assert {fact.condition_uuid for fact in retained.conditions} == {
                    condition.uuid for condition in actor.active_conditions.values()
                    if condition.condition_category is not ConditionCategory.INTERNAL}

        def execute(behavior: str, *, position: tuple[int, int] | None = None) -> Event:
            available = get_available_actions(source)
            action = next(row for row in available.all_actions if row.behavior_id == behavior and row.valid_targets)
            option = next(row for row in action.valid_targets if row.position == position) if position is not None else next(
                row for row in action.valid_targets if row.target_uuid == target.uuid)
            start = EventQueue.event_cursor()
            result = execute_by_index(source, action.template_name, option.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION
            retain(start)
            return result

        random.seed(seed)
        if mechanism == "telekinesis":
            execute("spell.telekinesis")
            assert source.action_economy.spell_slot_5.normalized_score == 0
            assert "Concentrating" in source.active_conditions
        before = latest
        history.clear()
        movement_before = target.action_economy.movement.normalized_score
        actions_before = source.action_economy.actions.normalized_score
        bonus_before = source.action_economy.bonus_actions.normalized_score
        watcher_reactions = watcher.action_economy.reactions.normalized_score if watcher is not None else None
        result = execute("action.shove" if mechanism == "shove" else "action.spell.telekinesis.move", position=destination)
        assert source.action_economy.actions.normalized_score == actions_before
        assert source.action_economy.bonus_actions.normalized_score == bonus_before - (mechanism == "shove")
        if target.can_take_actions():
            assert target.action_economy.movement.normalized_score == movement_before
        if watcher is not None:
            assert watcher.action_economy.reactions.normalized_score == watcher_reactions == 1
        events = tuple(event for lineage in history for event in lineage.events)
        assert not any(isinstance(event, StepMovementEvent) for event in events)
        forced = tuple(event for event in events if isinstance(event, ForcedMovementEvent))
        if forced:
            assert forced[-1].end_position == target.position
        if isinstance(result, ShoveEvent):
            assert result.end_position == target.position or (result.contest_success is False and target.position == target_position)
        return before, tuple(history)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
