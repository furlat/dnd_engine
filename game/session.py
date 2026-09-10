"""Live application composition and commands through existing engine owners.

This module owns no presentation state or clock. Callers capture each returned
operation before executing another command; the renderer never receives this
live session or its discovery templates.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.ai.runtime.controller import NativeAIController
from dnd.content.characters.premades import (
    FIGHTER_PREMADE_ID, SORCERER_PREMADE_ID, create_premade_character,
)
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult, AvailableTarget
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.events import EntityCreatedEvent, Event, EventPhase, EventQueue
from dnd.encounter import AdvanceResult, Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import BuiltBattlefield, build_battlefield


@dataclass(frozen=True, slots=True)
class Session:
    """Existing live owners for two human characters and one native enemy side."""

    game: Game
    encounter: Encounter
    battlefield: BuiltBattlefield
    player_uuids: tuple[UUID, UUID]
    enemy_controller: NativeAIController
    births: tuple[EntityCreatedEvent, ...]


@dataclass(frozen=True, slots=True)
class Operation:
    """Actual terminal roots, in completion order, ready for immediate capture.

    An operation may complete several independent roots. It does not merge them
    into a synthetic lineage, and retains cancellations for explicit coverage.
    """

    start_cursor: int
    end_cursor: int
    roots: tuple[Event, ...]
    boundary: AdvanceResult | None = None


def create_session(
    *,
    battlefield_id: str = "battlefield.open_floor_bright",
    player_positions: tuple[tuple[int, int], tuple[int, int]] = ((10, 10), (10, 12)),
    enemy_positions: tuple[tuple[int, int], tuple[int, int]] = ((14, 10), (14, 12)),
) -> Session:
    """Compose a new encounter, stopping before its first turn or AI decision.

    Content bootstrap belongs to the composition entry. Dice use the live RNG;
    a test or authored replay may supply a seed outside this function.
    """
    SERVER_CONTENT_SYSTEM_RUNTIME.require()
    reset_engine_runtime()
    battlefield = build_battlefield(battlefield_id)
    game = Game()
    fighter = create_premade_character(FIGHTER_PREMADE_ID, faction="heroes", position=player_positions[0])
    sorcerer = create_premade_character(SORCERER_PREMADE_ID, faction="heroes", position=player_positions[1])
    players = (fighter, sorcerer)
    enemies = tuple(materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=uuid4(), display_name=f"Goblin {index + 1}",
        faction="enemies", position=position,
        deployment_role=CreatureDeploymentRole(role_id=f"encounter.enemy_{index + 1}"),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    ) for index, position in enumerate(enemy_positions))
    # Direct characters already publish their complete birth. Creature factories
    # leave that commit to composition, after their canonical loadout is ready.
    for enemy in enemies:
        enemy.compose_entity()
    actors = (*players, *enemies)
    for actor in actors:
        add_opportunity_attack_handler(actor)
        game.deploy_entity(actor, actor.position)
    Entity.update_all_entities_senses()
    encounter = Encounter(name="Goblin skirmish", source_entity_uuid=uuid4())
    enemy_controller = NativeAIController.create(
        source_entity_uuid=enemies[0].uuid,
        game_id=str(encounter.uuid), assignment_id=f"{encounter.uuid}:enemies",
        controlled_entity_uuids=tuple(enemy.uuid for enemy in enemies),
    )
    for player in players:
        encounter.add_combatant(player, HumanController(source_entity_uuid=player.uuid))
    for enemy in enemies:
        encounter.add_combatant(enemy, enemy_controller)
    encounter.start_encounter()
    births = tuple(event for _, event in EventQueue.iter_events_since(0)
                   if isinstance(event, EntityCreatedEvent) and event.entity_uuid in game.entities)
    return Session(game, encounter, battlefield, (fighter.uuid, sorcerer.uuid), enemy_controller, births)


def _current_player(session: Session, actor_uuid: UUID) -> Entity:
    encounter = session.encounter
    actor = encounter.get_current_entity()
    if (encounter.state is not EncounterState.ACTIVE
            or encounter.turn_state is not TurnState.IN_PROGRESS
            or actor_uuid not in session.player_uuids
            or actor is None or actor.uuid != actor_uuid
            or not isinstance(encounter.get_current_controller(), HumanController)):
        raise ValueError("the selected actor does not own the current human turn")
    return actor


def discover_player_actions(session: Session, actor_uuid: UUID) -> AvailableActionsResult:
    """Return current engine choices, including their typed unavailable reasons."""
    return get_available_actions(_current_player(session, actor_uuid))


def _operation(start_cursor: int, boundary: AdvanceResult | None = None) -> Operation:
    end_cursor = EventQueue.event_cursor()
    roots = tuple(event for index, event in EventQueue.iter_events_since(start_cursor)
                  if index <= end_cursor and event.parent_lineage is None
                  and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    return Operation(start_cursor, end_cursor, roots, boundary)


def execute_player_action(
    session: Session,
    actor_uuid: UUID,
    action: AvailableActionInfo,
    target: AvailableTarget,
    *,
    extra_target_uuids: tuple[UUID, ...] = (),
    prefer_safe: bool = True,
) -> Operation:
    """Submit the current human's exact discovered choice to the rules engine."""
    actor = _current_player(session, actor_uuid)
    if target not in action.valid_targets:
        raise ValueError("selected target does not belong to the discovered action")
    start = EventQueue.event_cursor()
    execute_available_action(
        actor, action, target, extra_target_uuids=[str(identity) for identity in extra_target_uuids],
        prefer_safe=prefer_safe,
    )
    session.encounter.check_deaths()
    return _operation(start)


def end_player_turn(session: Session, actor_uuid: UUID) -> Operation:
    """End this human turn without starting the next actor's decision."""
    _current_player(session, actor_uuid)
    start = EventQueue.event_cursor()
    session.encounter.complete_current_turn()
    return _operation(start)


def advance_controller(session: Session) -> Operation:
    """Run one engine decision or expose its existing human/end boundary."""
    start = EventQueue.event_cursor()
    return _operation(start, session.encounter.advance_one_controller_action_boundary())


def close_session(session: Session) -> None:
    """Release native controller ownership before removing world deployment."""
    session.enemy_controller.close()
    session.game.close()
