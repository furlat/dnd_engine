"""Public flat-land gameplay replays from passive facts after engine reset.

Movement, OA, melee, Dodge and turn expiry share the same retained lineage
boundary. The assertions concern positions, HP, condition membership, causal
identity and the actual turn, independent of any animation or asset recipe.
"""

import random
from uuid import UUID, uuid4

from dnd.actions import AttackEvent, MovementEvent
from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.controller import HumanController
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    DamageAppliedEvent, DamageRollResultEvent, Event, EventPhase, EventQueue, EventType,
    SpatialChangeEvent, SpatialChangeType, StepMovementEvent, TurnEvent,
)
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)
from game.session import (
    Operation, advance_controller, close_session, create_session, discover_player_actions,
    end_player_turn, execute_player_action,
)


def _roots_since(cursor: int, observer_uuid: UUID) -> tuple[CompletedLineage, ...]:
    return tuple(capture_lineage(event, observer_uuid=observer_uuid)
                 for _, event in EventQueue.iter_events_since(cursor)
                 if event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
                 and event.parent_event is None and event.parent_lineage is None)


def _action(actor: Entity, behavior: str, position: tuple[int, int] | None = None) -> Event:
    available = get_available_actions(actor)
    choice = next(row for row in available.all_actions if row.behavior_id == behavior and row.valid_targets)
    target = next(row for row in choice.valid_targets if position is None or row.position == position)
    result = execute_by_index(actor, choice.template_name, target.index, available=available)
    assert result is not None and result.phase is EventPhase.COMPLETION
    return result


def test_flat_encounter_retains_movement_oa_melee_conditions_and_turns() -> None:
    random_state = random.getstate()
    try:
        reset_engine_runtime()
        built = build_battlefield("battlefield.open_floor_bright")
        game = Game()
        hero = Entity.create(uuid4(), "Hero", config=EntityConfig(
            position=(3, 3), faction="heroes",
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=10, hit_dice_count=8, mode="maximums",
            )]),
        ))
        hero.install_initial_items(((build_authored_item("weapon.shortsword", hero.uuid), WeaponSlot.MELEE_MAIN),))
        hero_birth = hero.compose_entity()
        setup_standard_actions(hero)
        goblin = materialize_creature(
            BESTIARY_CREATURE_RECIPES_BY_ID["goblin"], runtime_entity_uuid=uuid4(),
            display_name="Goblin", faction="monsters", position=(4, 3),
            deployment_role=CreatureDeploymentRole(role_id="scenario.history_test"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
        goblin_birth = goblin.compose_entity()
        add_opportunity_attack_handler(goblin)
        for actor in (hero, goblin):
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Flat history", source_entity_uuid=uuid4())
        for actor in (hero, goblin):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not hero:
            encounter.next_turn()

        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="flat startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=hero.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(hero.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        seed = seed_actors(baseline, (hero_birth, goblin_birth), active_weapon_sets={
            hero.uuid: hero.equipment.active_weapon_set, goblin.uuid: goblin.equipment.active_weapon_set,
        })
        assert seed.world is not None and seed.tiles and seed.door_uuid is None
        assert seed.current_actor_uuid == hero.uuid and seed.round_number == encounter.round_number
        assert seed.senses is not None and seed.senses.position == (3, 3)

        move = capture_lineage(_action(hero, "action.move", (2, 3)), observer_uuid=hero.uuid)
        assert isinstance(move.root, MovementEvent)
        step = next(event for event in move.events if isinstance(event, StepMovementEvent))
        oa = next(event for event in move.events if isinstance(event, AttackEvent))
        assert oa.parent_lineage == step.lineage_uuid and step.parent_lineage == move.root.lineage_uuid
        assert step.committed and (step.from_position, step.to_position) == ((3, 3), (2, 3))
        assert step.effective_handler_presentations[0].behavior_id == "reaction.opportunity_attack"
        moved = reduce_lineage(seed, move)
        assert moved.senses is not None and moved.senses.position == hero.position == (2, 3)
        assert moved.actors[hero.uuid].last_visual_position == (2, 3)
        assert seed.senses.position == (3, 3)

        dodge = capture_lineage(_action(hero, "action.dodge"), observer_uuid=hero.uuid)
        dodging = reduce_lineage(moved, dodge)
        condition = dodging.actors[hero.uuid].conditions[0]
        assert condition.name == "Dodging" and condition.behavior_id == "condition.dodging"
        assert condition.category is ConditionCategory.STATUS
        header = next(event for event in dodge.events if event.uuid == condition.event_uuid)
        assert type(header) is Event and header.event_type is EventType.CONDITION_APPLICATION
        original = EventQueue.get_event_by_uuid(header.uuid)
        assert isinstance(original, ConditionApplicationEvent)
        assert condition.condition_uuid == original.condition.uuid

        histories = [move, dodge]
        expected = [moved, dodging]
        latest = dodging
        cursor = EventQueue.event_cursor()
        encounter.next_turn()
        turn_roots = _roots_since(cursor, hero.uuid)
        assert any(root.root.event_type is EventType.ROUND_START for root in turn_roots)
        for lineage in turn_roots:
            latest = reduce_lineage(latest, lineage)
            histories.append(lineage)
            expected.append(latest)
        assert latest.current_actor_uuid == goblin.uuid

        for behavior, position in (("action.move", (3, 3)), ("action.attack", None)):
            lineage = capture_lineage(_action(goblin, behavior, position), observer_uuid=hero.uuid)
            latest = reduce_lineage(latest, lineage)
            histories.append(lineage)
            expected.append(latest)
        melee = histories[-1]
        damage = next(event for event in melee.events if isinstance(event, DamageAppliedEvent))
        assert latest.actors[hero.uuid].normal_hp == hero.get_normal_hp() == damage.resulting_normal_hp
        assert latest.actors[hero.uuid].normal_hp < 80
        roll = next(event for event in melee.events if isinstance(event, DamageRollResultEvent))
        assert roll.damage_packets[0].damage.damage_bonus is None
        assert roll.damage_packets[0].final_roll.total == damage.applied_damage
        assert latest.senses is not None and latest.senses.entities[goblin.uuid].position == goblin.position == (3, 3)

        cursor = EventQueue.event_cursor()
        encounter.next_turn()
        expiry_roots = _roots_since(cursor, hero.uuid)
        assert any(root.root.event_type is EventType.CONDITION_REMOVAL for root in expiry_roots)
        for lineage in expiry_roots:
            latest = reduce_lineage(latest, lineage)
            histories.append(lineage)
            expected.append(latest)
        assert latest.current_actor_uuid == hero.uuid
        assert latest.actors[hero.uuid].conditions == () and "Dodging" not in hero.active_conditions
        assert dodging.actors[hero.uuid].conditions == (condition,)
        assert latest.round_number == encounter.round_number

        for lineage in histories:
            assert lineage.dispositions == ()
            for retained in lineage.events:
                original = EventQueue.get_event_by_uuid(retained.uuid)
                assert original is not None
                assert retained.parent_event == original.parent_event
                assert retained.parent_lineage == original.parent_lineage
                assert retained.children_lineages == original.children_lineages
                assert retained.identified_entity_observer_uuids == original.identified_entity_observer_uuids
                assert retained.located_entity_observer_uuids == original.located_entity_observer_uuids
                assert retained.located_position_observer_uuids == original.located_position_observer_uuids
                assert retained.effective_handler_presentations == original.effective_handler_presentations
        reset_engine_runtime()
        replay: PresentationTarget = seed
        for lineage, after in zip(histories, expected, strict=True):
            replay = reduce_lineage(replay, lineage)
            assert replay == after
        assert replay == latest
    finally:
        random.setstate(random_state)


def test_premade_torch_movement_preserves_tile_light_causes_and_subjective_state() -> None:
    """A carried torch's light-change entity_uuid names a tile, not an actor."""
    random_state = random.getstate()
    random.seed(0)
    session = create_session()
    try:
        observer = session.game.entities[session.player_uuids[0]]
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="premade startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=session.battlefield.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(observer.senses),
        )
        seed, _ = reduce_interval(None, startup)
        latest = seed_actors(seed, session.births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in session.game.entities.values()
        })
        while True:
            operation = advance_controller(session)
            for root in operation.roots:
                latest = reduce_lineage(latest, capture_lineage(root, observer_uuid=observer.uuid))
            assert operation.boundary is not None
            if operation.boundary.status == "waiting_for_human":
                break
            assert operation.boundary.status != "encounter_ended"
        actor_uuid = latest.current_actor_uuid
        assert actor_uuid is not None
        available = discover_player_actions(session, actor_uuid)
        action = next(row for row in available.all_actions
                      if row.behavior_id == "action.move" and row.valid_targets)
        destination = min(action.valid_targets, key=lambda option: option.path_cost or 0)
        operation = execute_player_action(session, actor_uuid, action, destination)
        lineages = tuple(capture_lineage(root, observer_uuid=observer.uuid) for root in operation.roots)
        lights = [event for lineage in lineages for event in lineage.events
                  if isinstance(event, SpatialChangeEvent) and event.change_type is SpatialChangeType.LIGHT_CHANGED]
        assert lights and all(Entity.get(event.entity_uuid) is None for event in lights if event.entity_uuid is not None)
        assert all(lineage.dispositions == () for lineage in lineages)
        for event in lights:
            source = EventQueue.get_event_by_uuid(event.uuid)
            assert source is not None
            assert event.identified_entity_observer_uuids == source.identified_entity_observer_uuids
        before = latest
        for lineage in lineages:
            latest = reduce_lineage(latest, lineage)
        actual = capture_senses_snapshot(observer.senses)
        assert latest.senses is not None
        assert latest.senses.position == actual.position
        assert latest.senses.entities == actual.entities
        assert latest.senses.effective_light_levels == actual.effective_light_levels
    finally:
        close_session(session)
        random.setstate(random_state)
    reset_engine_runtime()
    replay = before
    for lineage in lineages:
        replay = reduce_lineage(replay, lineage)
    assert replay == latest


def test_native_turn_after_lethal_oa_preserves_metadata_without_redisclosing_actor() -> None:
    """A dead mover's independent TurnEnd has self-only identity grants."""
    random_state = random.getstate()
    random.seed(0)
    session = create_session(player_positions=((5, 5), (5, 7)), enemy_positions=((9, 5), (9, 7)))
    histories: list[tuple[CompletedLineage, PresentationTarget]] = []
    try:
        observer = session.game.entities[session.player_uuids[0]]
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="native round startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=observer.uuid, battlefield_id=session.battlefield.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(observer.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        seed = seed_actors(baseline, session.births, active_weapon_sets={
            actor.uuid: actor.equipment.active_weapon_set for actor in session.game.entities.values()
        })
        latest = seed

        def receive(operation: Operation) -> None:
            nonlocal latest
            for root in operation.roots:
                lineage = capture_lineage(root, observer_uuid=observer.uuid)
                latest = reduce_lineage(latest, lineage)
                histories.append((lineage, latest))

        acted: set[UUID] = set()
        commands = 0
        for _ in range(30):
            operation = advance_controller(session)
            receive(operation)
            assert operation.boundary is not None
            if operation.boundary.status != "waiting_for_human":
                assert operation.boundary.status != "encounter_ended"
                continue
            if commands == 4:
                break
            actor = latest.current_actor_uuid
            assert actor is not None
            commands += 1
            if actor in acted:
                receive(end_player_turn(session, actor))
                continue
            acted.add(actor)
            available = discover_player_actions(session, actor)
            missile = next((row for row in available.all_actions
                            if row.behavior_id == "spell.magic_missile" and row.valid_targets), None)
            if missile is None:
                action = next(row for row in available.all_actions
                              if row.behavior_id == "action.dodge" and row.valid_targets)
                receive(execute_player_action(session, actor, action, action.valid_targets[0]))
            else:
                targets = tuple(option for option in missile.valid_targets if option.target_uuid is not None
                                and latest.actors[option.target_uuid].creature_content_ref is not None)
                assert len(targets) == 2
                extras = tuple(option.target_uuid for option in (targets[1], targets[0])
                               if option.target_uuid is not None)
                receive(execute_player_action(session, actor, missile, targets[0], extra_target_uuids=extras))
        assert commands == 4 and latest.round_number == 2 and latest.current_actor_uuid in acted
        undisclosed = [(lineage.root, after) for lineage, after in histories
                       if isinstance(lineage.root, TurnEvent)
                       and str(observer.uuid) not in lineage.root.identified_entity_observer_uuids.get(
                           str(lineage.root.entity_uuid), set())
                       and lineage.root.entity_uuid != observer.uuid]
        assert len(undisclosed) == 1
        turn, after_turn = undisclosed[0]
        assert turn.event_type is EventType.TURN_END and after_turn.current_actor_uuid is None
        source = EventQueue.get_event_by_uuid(turn.uuid)
        assert source is not None and turn.identified_entity_observer_uuids == source.identified_entity_observer_uuids
        assert turn.located_entity_observer_uuids == source.located_entity_observer_uuids
        assert after_turn.actors[turn.entity_uuid].life_state is LifeState.DEAD
        assert after_turn.actors[turn.entity_uuid].last_visual_position is not None
        assert after_turn.senses is not None and turn.entity_uuid not in after_turn.senses.entities
        assert all(lineage.dispositions == () for lineage, _ in histories)
    finally:
        close_session(session)
        random.setstate(random_state)
    reset_engine_runtime()
    replay = seed
    for lineage, after in histories:
        replay = reduce_lineage(replay, lineage)
        assert replay == after


def test_witnessed_reaction_survives_moving_observers_death_without_new_location_grants() -> None:
    random_state = random.getstate()
    try:
        reset_engine_runtime()
        built = build_battlefield("battlefield.open_floor_bright")
        game = Game()
        hero = Entity.create(uuid4(), "Hero", config=EntityConfig(
            position=(3, 3), faction="heroes", health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=4, hit_dice_count=1, mode="maximums",
            )]),
        ))
        hero_birth = hero.compose_entity()
        setup_standard_actions(hero)
        goblin = materialize_creature(
            BESTIARY_CREATURE_RECIPES_BY_ID["goblin"], runtime_entity_uuid=uuid4(),
            display_name="Goblin", faction="monsters", position=(4, 3),
            deployment_role=CreatureDeploymentRole(role_id="scenario.history_test"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
        )
        goblin_birth = goblin.compose_entity()
        add_opportunity_attack_handler(goblin)
        for actor in (hero, goblin):
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Observer death", source_entity_uuid=uuid4())
        for actor in (hero, goblin):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not hero:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(
            name="observer startup", start_cursor=0, end_cursor=cursor,
            observer_uuid=hero.uuid, battlefield_id=built.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(hero.senses),
        )
        baseline, _ = reduce_interval(None, startup)
        seed = seed_actors(baseline, (hero_birth, goblin_birth), active_weapon_sets={
            hero.uuid: hero.equipment.active_weapon_set, goblin.uuid: goblin.equipment.active_weapon_set,
        })
        random.seed(5)
        root = _action(hero, "action.move", (2, 3))
        attack_versions = [event for _, event in EventQueue.iter_events_since(cursor)
                           if isinstance(event, AttackEvent)]
        first, terminal = attack_versions[0], attack_versions[-1]
        observer_key, attacker_key = str(hero.uuid), str(goblin.uuid)
        assert observer_key in first.located_entity_observer_uuids[attacker_key]
        assert observer_key in terminal.identified_entity_observer_uuids[attacker_key]
        assert observer_key not in terminal.located_entity_observer_uuids[attacker_key]
        lineage = capture_lineage(root, observer_uuid=hero.uuid)
        after = reduce_lineage(seed, lineage)
        step = next(event for event in lineage.events if isinstance(event, StepMovementEvent))
        assert not step.committed and hero.position == (3, 3)
        assert after.actors[hero.uuid].life_state is LifeState.DEAD
        assert after.actors[hero.uuid].normal_hp == hero.get_normal_hp()
        assert after.senses is not None and goblin.uuid not in after.senses.entities
        assert seed.senses is not None and seed.senses.entities[goblin.uuid].position == (4, 3)
        retained = next(event for event in lineage.events if event.uuid == terminal.uuid)
        assert retained.identified_entity_observer_uuids == terminal.identified_entity_observer_uuids
        assert retained.located_entity_observer_uuids == terminal.located_entity_observer_uuids
        reset_engine_runtime()
        assert reduce_lineage(seed, lineage) == after
    finally:
        random.setstate(random_state)
