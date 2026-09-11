"""Native movement routes and terrain jumps for the shared visual recorder."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import JumpEvent, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.condition_types import ConditionCategory
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue, StepMovementEvent
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import register_cunning_action
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.transmutation import Haste
from dnd.types.senses import SenseMode, SensesType
from game.presentation import (
    CompletedLineage, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage,
)

from game.replay import CapturedHistory, capture_history


def movement_history(
    *, route: tuple[tuple[int, int], ...] = ((3, 3), (5, 3), (5, 5), (3, 5)),
    battlefield_id: str = "battlefield.open_floor_bright",
    behavior: Literal["action.move", "action.jump"] = "action.move",
    boost: Literal["none", "haste", "bonus-dash"] = "none",
) -> CapturedHistory:
    """Execute discovered choices; Haste's actual cast establishes the baseline.

    The Haste casting animation belongs to a later delivery unit. Its original
    complete tree is reduced before these movement clips begin. Bonus Dash is
    retained here as its real action/condition tree before the same-turn route.
    """
    assert len(route) >= 2
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield(battlefield_id)
    game = Game()
    try:
        mover = Entity.create(uuid4(), "Mover", config=EntityConfig(
            position=route[0], faction="heroes", appearance=AppearanceConfig(
                body_category="NakedBody", head_category="Head22", has_beard=False,
            ),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=1, mode="maximums")]),
        ))
        actors = [mover]
        caster = None
        if boost == "haste":
            caster = Entity.create(uuid4(), "Haste caster", config=EntityConfig(
                position=(route[0][0] - 1, route[0][1]), faction="heroes",
                action_economy=ActionEconomyConfig(spell_slots={3: 1}),
                appearance=AppearanceConfig(body_category="NakedBody", head_category="Head10", has_beard=False),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=1, mode="maximums")]),
            ))
            actors.append(caster)
        for actor in actors:
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if built.definition.light_level == "darkness":
                actor.senses.add_sense_mode_source(actor.uuid,
                    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
        if caster is not None:
            register_spell(caster, Haste)
        if boost == "bonus-dash":
            register_cunning_action(mover)
        for actor in actors:
            actor.compose_entity()
        for actor in actors:
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Native movement route", source_entity_uuid=uuid4())
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not (caster or mover):
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(name="movement route startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=mover.uuid, battlefield_id=battlefield_id,)
        baseline, _ = reduce_interval(None, startup)
        latest = baseline
        history: list[CompletedLineage] = []

        def retain(cursor: int) -> None:
            nonlocal latest
            roots = tuple(capture_lineage(event, observer_uuid=mover.uuid)
                          for _, event in EventQueue.iter_events_since(cursor)
                          if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
            for lineage in roots:
                latest = reduce_lineage(latest, lineage)
                for event in lineage.events:
                    original = EventQueue.get_event_by_uuid(event.uuid)
                    assert original is not None
                    assert (event.parent_event, event.parent_lineage, event.children_lineages) == (
                        original.parent_event, original.parent_lineage, original.children_lineages)
                    assert event.identified_entity_observer_uuids == original.identified_entity_observer_uuids
                    assert event.located_entity_observer_uuids == original.located_entity_observer_uuids
                    assert event.located_position_observer_uuids == original.located_position_observer_uuids
                history.append(lineage)
            assert latest.senses is not None and latest.senses.position == mover.position
            for actor in actors:
                retained = latest.actors[actor.uuid]
                assert (retained.normal_hp, retained.life_state) == (actor.get_normal_hp(), actor.health.life_state)
                assert {fact.condition_uuid for fact in retained.conditions} == {
                    condition.uuid for condition in actor.active_conditions.values()
                    if condition.condition_category is not ConditionCategory.INTERNAL}

        base_speed = mover.action_economy.current_speed()
        if caster is not None:
            assert mover.uuid in caster.senses.entities and caster.senses.entities[mover.uuid].visual
            available = get_available_actions(caster)
            action = next((row for row in available.all_actions if row.behavior_id == "spell.haste" and row.valid_targets), None)
            assert action is not None, [(row.behavior_id, row.availability_status, row.can_afford)
                                        for row in available.all_actions]
            option = next(row for row in action.valid_targets if row.target_uuid == mover.uuid)
            cursor = EventQueue.event_cursor()
            result = execute_by_index(caster, action.template_name, option.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION
            retain(cursor)
            assert mover.action_economy.current_speed() == 2 * base_speed
            assert caster.action_economy.spell_slot_3.normalized_score == 0
            assert mover.action_economy.resources["haste_action"].current == 1
            while encounter.get_current_entity() is not mover:
                cursor = EventQueue.event_cursor()
                encounter.next_turn()
                retain(cursor)
        before = latest
        history.clear()
        if boost == "bonus-dash":
            available = get_available_actions(mover)
            action = next(row for row in available.all_actions if row.behavior_id == "action.dash"
                          and row.cost_type == "bonus_actions" and row.valid_targets)
            actions = mover.action_economy.actions.normalized_score
            cursor = EventQueue.event_cursor()
            result = execute_by_index(mover, action.template_name, action.valid_targets[0].index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION
            retain(cursor)
            assert mover.action_economy.movement.normalized_score == 2 * base_speed
            assert mover.action_economy.actions.normalized_score == actions
            assert mover.action_economy.bonus_actions.normalized_score == 0
        for destination in route[1:]:
            available = get_available_actions(mover)
            action = next(row for row in available.all_actions if row.behavior_id == behavior and row.valid_targets)
            option = next(row for row in action.valid_targets if row.position == destination)
            movement_before = mover.action_economy.movement.normalized_score
            cursor = EventQueue.event_cursor()
            result = execute_by_index(mover, action.template_name, option.index, available=available)
            assert isinstance(result, (MovementEvent, JumpEvent)) and result.phase is EventPhase.COMPLETION
            retain(cursor)
            assert mover.position == destination
            spent = sum(event.movement_cost for event in history[-1].events if isinstance(event, StepMovementEvent))
            assert mover.action_economy.movement.normalized_score == movement_before - spent
        return capture_history(before, tuple(history))
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
