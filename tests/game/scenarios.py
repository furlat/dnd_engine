"""Real public engine scenarios shared by tests and the visual review catalog.

Callers install the existing content runtime before producing a case. These
functions return passive retained histories after closing/resetting the engine
and restoring the caller's random state; they do not import pytest or render.
The configurable longsword rider is CON10 Ghoul paralysis, not Hold Person.
"""

import random
from contextlib import contextmanager
from typing import Iterator
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
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, HealEvent
from dnd.core.life_types import LifeState
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
    uses_death_saves: bool = False,
) -> tuple[PresentationTarget, CompletedLineage]:
    """Execute the discovered attack/movement and detach its completed history."""
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        hero = Entity.create(uuid4(), "Hero", config=EntityConfig(
            position=(3, 3), faction="heroes", uses_death_saves=uses_death_saves, appearance=AppearanceConfig(
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


@contextmanager
def _condition_encounter(
    *, maximum_hp: int = 80, paralysis_rider: bool = True,
) -> Iterator[tuple[PresentationTarget, Entity, Entity, Encounter]]:
    """The same two native participants, kept alive for a bounded sequence."""
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
        if paralysis_rider:
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
        yield before, mover, reactor, encounter
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)


def _condition_action(actor: Entity, behavior: str, position: tuple[int, int] | None = None) -> Event:
    """Submit an actual currently discovered choice while this actor owns its turn."""
    assert actor.is_my_turn
    available = get_available_actions(actor)
    action = next(row for row in available.all_actions if row.behavior_id == behavior and row.valid_targets)
    target = next(option for option in action.valid_targets if position is None or option.position == position)
    root = execute_by_index(actor, action.template_name, target.index, available=available)
    assert root is not None and root.phase is EventPhase.COMPLETION
    return root


def _capture_operation(
    before: PresentationTarget, cursor: int, mover: Entity, observer: Entity, encounter: Encounter,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Keep every real operation root, then compare its retained result to the engine."""
    roots = tuple(capture_lineage(event, observer_uuid=observer.uuid)
                  for _, event in EventQueue.iter_events_since(cursor)
                  if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    result = before
    for lineage in roots:
        result = reduce_lineage(result, lineage)
        for retained in lineage.events:
            original = EventQueue.get_event_by_uuid(retained.uuid)
            assert original is not None
            assert (retained.parent_event, retained.parent_lineage, retained.children_lineages) == (
                original.parent_event, original.parent_lineage, original.children_lineages)
            assert retained.identified_entity_observer_uuids == original.identified_entity_observer_uuids
            assert retained.located_entity_observer_uuids == original.located_entity_observer_uuids
            assert retained.located_position_observer_uuids == original.located_position_observer_uuids
    assert result.senses is not None and result.senses.position == observer.position
    for actor in (mover, observer):
        retained_actor = result.actors[actor.uuid]
        assert retained_actor.normal_hp == actor.get_normal_hp()
        assert retained_actor.life_state is actor.health.life_state
        if actor is not observer:
            contact = result.senses.entities.get(actor.uuid)
            if contact is not None and contact.visual:
                assert contact.position == actor.position
    # The subject starts without conditions. Compare its full non-internal
    # membership, including the UUIDs of owned children; the reactor's static
    # pre-baseline trait is not a newly observed condition application.
    assert {fact.condition_uuid for fact in result.actors[mover.uuid].conditions} == {
        condition.uuid for condition in mover.active_conditions.values()
        if condition.condition_category is not ConditionCategory.INTERNAL
    }
    assert result.round_number == encounter.round_number
    current = encounter.get_current_entity()
    assert current is not None and result.current_actor_uuid == current.uuid
    return result, roots


def movement_with_paralysis(
    seed: int, maximum_hp: int = 80, *, movement_behavior: str = "action.move",
) -> tuple[PresentationTarget, CompletedLineage]:
    """Compatibility case: detach just the original complete Move or Jump."""
    with _condition_encounter(maximum_hp=maximum_hp) as (before, mover, reactor, encounter):
        random.seed(seed)
        cursor = EventQueue.event_cursor()
        root = _condition_action(mover, movement_behavior, (2, 3))
        assert isinstance(root, (MovementEvent, JumpEvent))
        _, roots = _capture_operation(before, cursor, mover, reactor, encounter)
        lineage, = (lineage for lineage in roots if lineage.root.uuid == root.uuid)
        assert mover.position == root.end_position
        return before, lineage


def paralysis_lifecycle(
    *, repeat_save_seeds: tuple[int, ...] = (0,), movement_behavior: str = "action.move",
    resume: bool = True,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Native repeat saves/removal across turns, optionally followed by actual movement."""
    with _condition_encounter() as (before, mover, reactor, encounter):
        latest = before
        history: list[CompletedLineage] = []

        def retain(cursor: int) -> None:
            nonlocal latest
            latest, roots = _capture_operation(latest, cursor, mover, reactor, encounter)
            history.extend(roots)

        random.seed(0)
        cursor = EventQueue.event_cursor()
        _condition_action(mover, movement_behavior, (2, 3))
        retain(cursor)
        assert "Paralyzed" in mover.active_conditions
        for save_seed in repeat_save_seeds:
            # Discovery is checked while the restricted mover owns its turn;
            # no renderer decides whether paralysis permits another action.
            assert encounter.get_current_entity() is mover
            if "Paralyzed" in mover.active_conditions:
                assert not any(row.valid_targets for row in get_available_actions(mover).all_actions)
            random.seed(save_seed)
            cursor = EventQueue.event_cursor()
            encounter.next_turn()
            retain(cursor)
            assert encounter.get_current_entity() is reactor
            cursor = EventQueue.event_cursor()
            encounter.next_turn()
            retain(cursor)
            assert encounter.get_current_entity() is mover
        if resume:
            assert "Paralyzed" not in mover.active_conditions
            choices = get_available_actions(mover).all_actions
            assert any(row.behavior_id == movement_behavior and row.valid_targets for row in choices)
            cursor = EventQueue.event_cursor()
            _condition_action(mover, "action.disengage")
            retain(cursor)
            cursor = EventQueue.event_cursor()
            resumed = _condition_action(mover, movement_behavior, (2, 3))
            retain(cursor)
            assert isinstance(resumed, (MovementEvent, JumpEvent)) and resumed.end_position == (2, 3)
        elif "Paralyzed" in mover.active_conditions:
            assert not any(row.valid_targets for row in get_available_actions(mover).all_actions)
        return before, tuple(history)


def dodge_expiry_history() -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Dodge, a real opposing sword attack, and natural next-turn expiration."""
    with _condition_encounter(paralysis_rider=False) as (before, mover, reactor, encounter):
        latest = before
        history: list[CompletedLineage] = []

        def retain(cursor: int) -> None:
            nonlocal latest
            latest, roots = _capture_operation(latest, cursor, mover, reactor, encounter)
            history.extend(roots)

        cursor = EventQueue.event_cursor()
        _condition_action(mover, "action.dodge")
        retain(cursor)
        assert "Dodging" in mover.active_conditions
        cursor = EventQueue.event_cursor()
        encounter.next_turn()
        retain(cursor)
        assert encounter.get_current_entity() is reactor
        random.seed(17)
        cursor = EventQueue.event_cursor()
        _condition_action(reactor, "action.attack", mover.position)
        retain(cursor)
        assert "Dodging" in mover.active_conditions
        cursor = EventQueue.event_cursor()
        encounter.next_turn()
        retain(cursor)
        assert encounter.get_current_entity() is mover and "Dodging" not in mover.active_conditions
        assert any(row.behavior_id == "action.dodge" and row.valid_targets
                   for row in get_available_actions(mover).all_actions)
        return before, tuple(history)


@contextmanager
def _healing_encounter() -> Iterator[tuple[PresentationTarget, Entity, Entity, Encounter]]:
    """Keep the native healing participants available for one bounded history."""
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        observer = Entity.create(uuid4(), "Healer", config=EntityConfig(
            position=(3, 3), faction="heroes", appearance=AppearanceConfig(
                body_category="NakedBody", head_category="Head10", has_beard=False,
            ), health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10, hit_dice_count=2, mode="maximums",
            )]),
        ))
        target = Entity.create(uuid4(), "Recipient", config=EntityConfig(
            position=(4, 3), faction="heroes", uses_death_saves=True,
            appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22", has_beard=False),
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10, hit_dice_count=2, mode="maximums",
            )]),
        ))
        births = observer.compose_entity(), target.compose_entity()
        for actor in (observer, target):
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        # Ordinary encounter startup installs the engine's event observer
        # computers. Direct HP operations need no turn progression here.
        encounter = Encounter(name="Healing review", source_entity_uuid=uuid4())
        for actor in (observer, target):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="healing startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(observer.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        before = seed_actors(baseline, births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in (observer, target)
        })
        yield before, observer, target, encounter
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)


def healing_history(*, dying: bool = False) -> tuple[PresentationTarget, CompletedLineage]:
    """Heal a natively injured actor; only the engine changes HP and life state."""
    with _healing_encounter() as (before, observer, target, _encounter):
        # Establish the injured baseline from the real completed damage tree,
        # including the player's authoritative DYING transition when applicable.
        cursor = EventQueue.event_cursor()
        target.receive_damage(20 if dying else 7, DamageType.SLASHING, observer.uuid)
        for _, event in EventQueue.iter_events_since(cursor):
            if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
                before = reduce_lineage(before, capture_lineage(event, observer_uuid=observer.uuid))
        injured = before.actors[target.uuid]
        assert injured.normal_hp == target.get_normal_hp() == (0 if dying else 13)
        assert injured.life_state is target.health.life_state is (LifeState.DYING if dying else LifeState.ALIVE)

        cursor = EventQueue.event_cursor()
        actual = target.receive_healing(5 if dying else 20, observer.uuid, source_description="Native healing review")
        root, = (event for _, event in EventQueue.iter_events_since(cursor)
                 if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        assert isinstance(root, HealEvent) and root.actual_healing == actual
        lineage = capture_lineage(root, observer_uuid=observer.uuid)
        after = reduce_lineage(before, lineage)
        healed = after.actors[target.uuid]
        assert healed.normal_hp == target.get_normal_hp() == (5 if dying else 20)
        assert healed.life_state is target.health.life_state is LifeState.ALIVE
        assert after.senses is not None and after.senses.entities[target.uuid].position == target.position == (4, 3)
        for retained in lineage.events:
            original = EventQueue.get_event_by_uuid(retained.uuid)
            assert original is not None
            assert (retained.parent_event, retained.parent_lineage, retained.children_lineages) == (
                original.parent_event, original.parent_lineage, original.children_lineages)
            assert retained.identified_entity_observer_uuids == original.identified_entity_observer_uuids
            assert retained.located_entity_observer_uuids == original.located_entity_observer_uuids
            assert retained.located_position_observer_uuids == original.located_position_observer_uuids
        return before, lineage


def lifecycle_history(
    *, save_seeds: tuple[int, ...] = (0,), heal_after: bool = False, revive_after: bool = False,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Retain actual turn-start death saves and native recovery of the same actor."""
    assert save_seeds and not (heal_after and revive_after)
    with _healing_encounter() as (latest, observer, target, encounter):
        history: list[CompletedLineage] = []

        def retain(cursor: int) -> None:
            nonlocal latest
            latest, roots = _capture_operation(latest, cursor, target, observer, encounter)
            history.extend(roots)

        cursor = EventQueue.event_cursor()
        encounter.start_turn()
        retain(cursor)
        while encounter.get_current_entity() is not observer:
            cursor = EventQueue.event_cursor()
            encounter.next_turn()
            retain(cursor)
        cursor = EventQueue.event_cursor()
        target.receive_damage(target.get_normal_hp(), DamageType.SLASHING, observer.uuid)
        retain(cursor)
        assert target.health.life_state is LifeState.DYING and target.get_normal_hp() == 0
        # Direct damage establishes the native baseline. The selected clips
        # begin with the ensuing real turns, not an unbound damage animation.
        before = latest
        history.clear()
        for seed in save_seeds:
            while encounter.get_current_entity() is not observer:
                cursor = EventQueue.event_cursor()
                encounter.next_turn()
                retain(cursor)
            assert target.is_dying
            random.seed(seed)
            cursor = EventQueue.event_cursor()
            encounter.next_turn()
            retain(cursor)
            assert encounter.get_current_entity() is target
        if heal_after or revive_after:
            cursor = EventQueue.event_cursor()
            encounter.next_turn()
            retain(cursor)
            assert encounter.get_current_entity() is observer
        if heal_after:
            assert target.health.life_state is LifeState.STABLE
            cursor = EventQueue.event_cursor()
            healed = target.receive_healing(5, observer.uuid, source_description="Native stable recovery")
            assert healed == 5
            retain(cursor)
        if revive_after:
            assert target.health.life_state is LifeState.DEAD
            cursor = EventQueue.event_cursor()
            revived = target.revive(hit_points=3)
            assert revived
            retain(cursor)
        return before, tuple(history)
