"""Real public engine scenarios shared by tests and the visual review catalog.

Callers install the existing content runtime before producing a case. These
functions return passive retained histories after closing/resetting the engine
and restoring the caller's random state; they do not import pytest or render.
The configurable longsword rider is CON10 Ghoul paralysis, not Hold Person.
"""

import random
from uuid import uuid4

from dnd.actions import AttackEvent, JumpEvent, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.controller import HumanController
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import GhoulClawsParalysisFeature
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)


def attack_history(
    weapon: str, seed: int, *, opportunity: bool = False, whole_movement: bool = False,
    destination: tuple[int, int] = (2, 3), maximum_hp: int = 80,
    movement_behavior: str = "action.move", watcher_positions: tuple[tuple[int, int], ...] = ((4, 3),),
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, goblin_source: bool = False,
) -> tuple[PresentationTarget, CompletedLineage]:
    """Execute the discovered attack/movement and detach its completed history."""
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        hero = Entity.create(uuid4(), "Hero", config=EntityConfig(
            position=(3, 3), faction="heroes", appearance=AppearanceConfig(
                body_category="NakedBody", head_category="Head22", has_beard=False,
            ), health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10 if maximum_hp == 80 else 4,
                hit_dice_count=8 if maximum_hp == 80 else 1, mode="maximums",
            )]),
        ))
        hero.install_initial_items(((build_authored_item(weapon, hero.uuid), weapon_slot),))
        hero_birth = hero.compose_entity()
        setup_standard_actions(hero)
        watchers = tuple(materialize_creature(
            BESTIARY_CREATURE_RECIPES_BY_ID["goblin"], runtime_entity_uuid=uuid4(),
            display_name="Goblin", faction="monsters", position=position,
            deployment_role=CreatureDeploymentRole(role_id="scenario.attack_animation_test"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        ) for position in watcher_positions)
        goblin = watchers[0]
        source, target = (goblin, hero) if goblin_source else (hero, goblin)
        births = (hero_birth, *(watcher.compose_entity() for watcher in watchers))
        for watcher in watchers:
            add_opportunity_attack_handler(watcher)
        for actor in (hero, *watchers):
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Attack history", source_entity_uuid=uuid4())
        for actor in (hero, *watchers):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not source:
            encounter.next_turn()
        # The failed-step case observes the dying mover from a living participant.
        # Observer death/contact acquisition is a separate capture contract.
        observer = goblin if maximum_hp == 4 else hero
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="attack startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(observer.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        before = seed_actors(baseline, births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in (hero, *watchers)
        })
        random.seed(seed)
        available = get_available_actions(source)
        choice = next(row for row in available.all_actions if row.behavior_id == (
            movement_behavior if opportunity else "action.attack") and row.valid_targets
            and (opportunity or row.weapon_slot == weapon_slot.value))
        option = next(row for row in choice.valid_targets
                      if row.position == (destination if opportunity else target.position))
        result = execute_by_index(source, choice.template_name, option.index, available=available)
        assert result is not None and result.phase is EventPhase.COMPLETION
        if opportunity and not whole_movement:
            result = next(event for _, event in EventQueue.iter_events_since(cursor)
                          if isinstance(event, AttackEvent) and event.phase is EventPhase.COMPLETION)
        assert isinstance(result, (AttackEvent, MovementEvent, JumpEvent))
        lineage = capture_lineage(result, observer_uuid=observer.uuid)
        return before, lineage
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)


def movement_with_paralysis(
    seed: int, maximum_hp: int = 80, *, movement_behavior: str = "action.move",
) -> tuple[PresentationTarget, CompletedLineage]:
    """Compose existing ECS values and execute the discovered Move or Jump."""
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        mover = Entity.create(uuid4(), "Mover", config=EntityConfig(
            position=(3, 3), faction="heroes", appearance=AppearanceConfig(
                body_category="NakedBody", head_category="Head22", has_beard=False,
            ), health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10 if maximum_hp == 80 else 4,
                hit_dice_count=8 if maximum_hp == 80 else 1, mode="maximums",
            )]),
        ))
        reactor = Entity.create(uuid4(), "Sword wielder", config=EntityConfig(
            position=(4, 3), faction="enemies", appearance=AppearanceConfig(
                body_category="NakedBody", head_category="Head10", has_beard=False,
            ), health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10, hit_dice_count=8, mode="maximums",
            )]),
        ))
        reactor.install_initial_items(((build_authored_item("weapon.longsword", reactor.uuid), WeaponSlot.MELEE_MAIN),))
        for actor in (mover, reactor):
            setup_standard_actions(actor)
        reactor.add_condition(GhoulClawsParalysisFeature(
            source_entity_uuid=reactor.uuid, target_entity_uuid=reactor.uuid,
            weapon_names=("Longsword",),
        ))
        add_opportunity_attack_handler(reactor)
        births = mover.compose_entity(), reactor.compose_entity()
        for actor in (mover, reactor):
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Disabling opportunity attack", source_entity_uuid=uuid4())
        for actor in (mover, reactor):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not mover:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="movement interruption", start_cursor=0, end_cursor=cursor,
            observer_uuid=reactor.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(reactor.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        before = seed_actors(baseline, births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in (mover, reactor)
        })
        random.seed(seed)
        available = get_available_actions(mover)
        action = next(row for row in available.all_actions if row.behavior_id == movement_behavior and row.valid_targets)
        destination = next(option for option in action.valid_targets if option.position == (2, 3))
        root = execute_by_index(mover, action.template_name, destination.index, available=available)
        assert isinstance(root, (MovementEvent, JumpEvent)) and root.phase is EventPhase.COMPLETION
        lineage = capture_lineage(root, observer_uuid=reactor.uuid)
        after = reduce_lineage(before, lineage)
        actual = after.actors[mover.uuid]
        assert actual.normal_hp == mover.get_hp() and actual.life_state is mover.health.life_state
        assert mover.position == root.end_position
        assert {fact.name for fact in actual.conditions} == {
            condition.name for condition in mover.active_conditions.values()
            if condition.condition_category is not ConditionCategory.INTERNAL
        }
        return before, lineage
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
