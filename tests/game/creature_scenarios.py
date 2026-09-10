"""Canonical creatures exercising the same native movement/attack history.

The caller selects a registered identity and weapon slot. Species differences
remain in content compositions and rig JSON, never in this producer's rules.
"""

import random
from uuid import uuid4

from dnd.actions import AttackEvent, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.characters.premades import FIGHTER_PREMADE_ID, create_premade_character
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EntityCreatedEvent, EventPhase, EventQueue
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)


def creature_history(
    creature_identity: str, *, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, seed: int = 17,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Move, make the selected attack, then duel a native Fighter until death.

Every action is discovered afresh and every independent root is captured before
the next operation. Native rules own rolls, defenses, resources and life state.
"""
    previous = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        fighter = create_premade_character(FIGHTER_PREMADE_ID, faction="heroes", position=(3, 3))
        declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.declarations[creature_identity]
        creature = materialize_creature(
            ContentRecipe.create(ref=declaration.ref, parameters={}), runtime_entity_uuid=uuid4(),
            display_name=declaration.descriptor.display_name, faction="monsters", position=(6, 3),
            deployment_role=CreatureDeploymentRole(role_id="scenario.creature_review"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
        creature.compose_entity()
        actors = (fighter, creature)
        for actor in actors:
            add_opportunity_attack_handler(actor)
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Creature review", source_entity_uuid=uuid4())
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not creature:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="creature startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=fighter.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(fighter.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        births = tuple(event for _, event in EventQueue.iter_events_since(0)
                       if isinstance(event, EntityCreatedEvent) and event.entity_uuid in game.entities)
        before = seed_actors(baseline, births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in actors
        })
        latest = before
        history: list[CompletedLineage] = []

        def retain(start: int) -> None:
            nonlocal latest
            for _, event in EventQueue.iter_events_since(start):
                if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
                    lineage = capture_lineage(event, observer_uuid=fighter.uuid)
                    latest = reduce_lineage(latest, lineage)
                    history.append(lineage)
            for actor in actors:
                retained = latest.actors[actor.uuid]
                assert (retained.normal_hp, retained.life_state) == (actor.get_normal_hp(), actor.health.life_state)

        random.seed(seed)
        available = get_available_actions(creature)
        move = next(row for row in available.all_actions if row.behavior_id == "action.move"
                    and any(target.position == (4, 3) for target in row.valid_targets))
        target = next(row for row in move.valid_targets if row.position == (4, 3))
        start = EventQueue.event_cursor()
        movement = execute_by_index(creature, move.template_name, target.index, available=available)
        assert isinstance(movement, MovementEvent) and creature.position == (4, 3)
        retain(start)
        # The creature's normal attack is the covered body vocabulary. Native
        # Multiattack remains available but is not substituted for this case.
        for _ in range(10):
            actor = encounter.get_current_entity()
            assert actor is not None
            target_actor = fighter if actor is creature else creature
            selected_slot = weapon_slot if actor is creature else WeaponSlot.MELEE_MAIN
            for _attack in range(2 if actor is fighter else 1):
                available = get_available_actions(actor)
                attack = next((row for row in available.all_actions
                               if row.behavior_id in ("action.attack", "action.feature.extra_attack")
                               and row.weapon_slot == selected_slot.value
                               and any(target.position == target_actor.position for target in row.valid_targets)), None)
                if attack is None:
                    break
                option = next(row for row in attack.valid_targets if row.position == target_actor.position)
                start = EventQueue.event_cursor()
                event = execute_by_index(actor, attack.template_name, option.index, available=available)
                assert isinstance(event, AttackEvent) and event.phase is EventPhase.COMPLETION
                retain(start)
                if target_actor.health.life_state is LifeState.DEAD:
                    return before, tuple(history)
            start = EventQueue.event_cursor()
            encounter.next_turn()
            retain(start)
        raise AssertionError("native creature duel did not settle within ten turns")
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
