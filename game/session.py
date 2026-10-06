"""Live application composition and commands through existing engine owners.

This module owns no presentation state or clock. Callers capture each returned
operation before executing another command; the renderer never receives this
live session or its discovery templates.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, get_extra_position_options, preview_available_selection
from dnd.ai.runtime.controller import NativeAIController
from dnd.content.characters.premades import (
    FIGHTER_PREMADE_ID, SORCERER_PREMADE_ID, create_premade_character,
)
from dnd.content.characters.builds import CharacterBuild, create_character, resolve_character_build
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.base_actions import AvailableActionInfo, AvailableActionsResult, AvailableTarget, AvailableSelectionPreview
from dnd.core.equipment_types import EquipmentSlot
from dnd.blocks.equipment import EquippableItem
from game.player_facts import PlayerCharacterSheet, PlayerHUDSnapshot, PlayerResource, CombatLogAppend
from dnd.subjective_combat_log import project_combat_log
from dnd.core.combat_log import CombatLogEntry
from typing import Callable
from dnd.core.base_actions import CostType, spell_slot_cost_type
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.events import EntityCreatedEvent, Event, EventPhase, EventQueue
from dnd.encounter import AdvanceResult, Encounter, EncounterState, TurnState
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.summoning.system import SummoningSystem, bind_summoning
from dnd.scenarios.battlefield_catalog import BuiltBattlefield, build_battlefield
from dnd.scenarios.encounter_assembler import assemble_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe


@dataclass(slots=True)
class DiscoveryCache:
    """One application-owned discovery epoch, never exposed to a view."""

    generation: int = 0
    cursor: int = -1
    original: AvailableActionsResult | None = None
    detached: AvailableActionsResult | None = None
    previews: dict[tuple[int, tuple[int, ...], tuple[tuple[int, int], ...]], AvailableSelectionPreview] = field(default_factory=dict)
    log_appends: list[tuple[int, CombatLogEntry]] = field(default_factory=list)
    log_listener: Callable[[Encounter, int, CombatLogEntry, Event], None] | None = None


@dataclass(frozen=True, slots=True)
class Session:
    """Existing live owners for human characters and one native enemy side."""

    game: Game
    encounter: Encounter
    battlefield: BuiltBattlefield
    player_uuids: tuple[UUID, ...]
    enemy_controller: NativeAIController
    births: tuple[EntityCreatedEvent, ...]
    summoning: SummoningSystem | None = None
    discovery: DiscoveryCache = field(default_factory=DiscoveryCache)


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
    hud_snapshot: PlayerHUDSnapshot | None = None
    combat_log_appends: tuple[CombatLogAppend, ...] = ()


def snapshot_player_hud(session: Session) -> PlayerHUDSnapshot:
    """Evaluate permitted party facts once at a native committed boundary."""
    observer = session.game.entities[session.player_uuids[0]]
    seen = set(observer.senses.entities) | {observer.uuid}
    sheets = []
    for identity in session.player_uuids:
        actor = session.game.entities[identity]
        economy = actor.action_economy
        channels: tuple[CostType, ...] = ("actions", "bonus_actions", "reactions")
        resources = [PlayerResource(key=key, label=label, current=value.normalized_score,
                                    maximum=economy.channel_capacity(key))
                     for key, label, value in zip(channels, ("Actions", "Bonus", "Reaction"),
                         (economy.actions, economy.bonus_actions, economy.reactions))]
        resources.append(PlayerResource(key="movement", label="Movement (ft)",
                         current=economy.movement_remaining(), maximum=economy.channel_capacity("movement")))
        resources.extend(PlayerResource(key=f"spell_slot_{rank}", label=f"Spell rank {rank}",
            current=economy.spell_slot_value(rank).normalized_score, maximum=economy.channel_capacity(spell_slot_cost_type(rank)))
            for rank, capacity in economy.get_normal_spell_slot_capacities().items() if capacity)
        resources.extend(PlayerResource(key=f"resource:{name}", label=name.replace('_', ' ').title(),
            current=resource.current, maximum=resource.maximum) for name, resource in economy.resources.items())
        sheets.append(PlayerCharacterSheet(actor_uuid=identity, species=actor.character_species,
            species_variant=actor.character_species_variant, background=actor.character_background,
            origin=actor.applied_origin_state, class_levels=actor.applied_class_levels,
            abilities=tuple((ability.name, ability.ability_score.score) for ability in actor.ability_scores.abilities_list),
            skills=tuple(skill.name for skill in actor.skill_set.proficiencies),
            expertise=tuple(skill.name for skill in actor.skill_set.expertise),
            saves=tuple(save.name for save in actor.saving_throws.proficiencies),
            proficiency_bonus=actor.proficiency_bonus.normalized_score, resources=tuple(resources),
            compatible_item_slots=tuple((item.uuid, tuple(slot.value for slot in actor.equipment.compatible_slots_for_actor(item)))
                for item in actor.inventory.items.values() if isinstance(item, EquippableItem))))
    return PlayerHUDSnapshot(generation=EventQueue.generation_id(), observer_uuid=observer.uuid,
        revision=EventQueue.event_cursor(), initiative=tuple(identity for identity in session.encounter.initiative_order if identity in seen),
        sheets=tuple(sheets))


def _bind_log_capture(session: Session) -> Session:
    def capture(encounter: Encounter, index: int, entry: CombatLogEntry, event: Event) -> None:
        if encounter is not session.encounter or (event.context or {}).get("combat_log_origin") != "standalone":
            return
        observer = str(session.player_uuids[0])
        projected = project_combat_log(entry, controlled_entity_uuids=frozenset({observer}),
                                     observer_entity_uuids=frozenset({observer}))
        if projected is not None:
            session.discovery.log_appends.append((index, CombatLogEntry.model_validate_json(projected.model_dump_json())))
    session.discovery.log_listener = capture
    Encounter.add_combat_log_listener(capture)
    return session


def create_session(
    *,
    encounter_id: str | None = None,
    battlefield_id: str = "battlefield.open_floor_bright",
    player_positions: tuple[tuple[int, int], tuple[int, int]] = ((10, 10), (10, 12)),
    enemy_positions: tuple[tuple[int, int], tuple[int, int]] = ((14, 10), (14, 12)),
    player_builds: tuple[CharacterBuild, ...] | None = None,
) -> Session:
    """Compose a new encounter, stopping before its first turn or AI decision.

    Content bootstrap belongs to the composition entry. Dice use the live RNG;
    a test or authored replay may supply a seed outside this function.
    """
    SERVER_CONTENT_SYSTEM_RUNTIME.require()
    if player_builds is not None:
        if not 1 <= len(player_builds) <= len(player_positions):
            raise ValueError("Choose one or two player characters")
        for build in player_builds:
            resolve_character_build(build)
        if encounter_id is not None:
            raise ValueError("Custom party deployment requires the skirmish encounter")
    reset_engine_runtime()
    if encounter_id is not None:
        return _create_authored_session(encounter_id)
    battlefield = build_battlefield(battlefield_id)
    game = Game()
    players = (tuple(create_character(build, faction="heroes", position=position)
                     for build, position in zip(player_builds, player_positions))
               if player_builds is not None else
               tuple(create_premade_character(identity, faction="heroes", position=position)
                     for identity, position in zip((FIGHTER_PREMADE_ID, SORCERER_PREMADE_ID), player_positions)))
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
    return _bind_log_capture(Session(game, encounter, battlefield, tuple(player.uuid for player in players), enemy_controller, births,
                   bind_summoning(game, encounter)))


def _create_authored_session(encounter_id: str) -> Session:
    """Connect the selected two-side workshop recipe to existing controllers."""
    recipe = encounter_recipe(encounter_id)
    human_slot, = (slot for slot in recipe.roster_slots if slot.controller_defaults.controller == "human")
    ai_slot, = (slot for slot in recipe.roster_slots if slot.controller_defaults.controller == "ai")
    game = Game()
    assembled = assemble_encounter_recipe(recipe, game=game, start_encounter=False)
    encounter = assembled.encounter
    players = assembled.entities_by_roster_slot[human_slot.roster_slot_id]
    enemies = assembled.entities_by_roster_slot[ai_slot.roster_slot_id]
    policy = ai_slot.controller_defaults.policy_id
    assert policy is not None
    controller = NativeAIController.create(
        source_entity_uuid=enemies[0].uuid, game_id=str(encounter.uuid),
        assignment_id=f"{encounter.uuid}:{ai_slot.roster_slot_id}",
        controlled_entity_uuids=tuple(enemy.uuid for enemy in enemies),
        policy_id=policy,
    )
    for player in players:
        encounter.set_controller_for(player.uuid, HumanController(source_entity_uuid=player.uuid))
    for enemy in enemies:
        encounter.set_controller_for(enemy.uuid, controller)
    encounter.start_encounter()
    births = tuple(event for _, event in EventQueue.iter_events_since(0)
                   if isinstance(event, EntityCreatedEvent) and event.entity_uuid in game.entities)
    return _bind_log_capture(Session(game, encounter, assembled.battlefield, tuple(player.uuid for player in players), controller, births,
                   bind_summoning(game, encounter)))


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


def discover_player_actions(session: Session, actor_uuid: UUID, *, force_attack: bool = False) -> AvailableActionsResult:
    """Return current engine choices, including their typed unavailable reasons."""
    actor = _current_player(session, actor_uuid)
    cache = session.discovery
    cache.generation += 1
    original = get_available_actions(actor, target_filter="all" if force_attack else "enemies")
    original.discovery_generation = cache.generation
    for index, row in enumerate(original.all_actions):
        row.discovery_generation = cache.generation
        row.discovery_index = index
        row.discovery_runtime = EventQueue.generation_id()
        row.discovery_actor_uuid = actor.uuid
    cache.original = original
    cache.detached = AvailableActionsResult.model_validate(original.model_dump())
    cache.cursor = EventQueue.event_cursor()
    cache.previews.clear()
    return cache.detached


def _retained_row(session: Session, action: AvailableActionInfo) -> AvailableActionInfo:
    cache = session.discovery
    if (cache.original is None or cache.detached is None
            or action.discovery_actor_uuid != cache.original.entity_uuid
            or action.discovery_runtime != EventQueue.generation_id()
            or action.discovery_generation != cache.generation
            or cache.cursor != EventQueue.event_cursor()):
        raise ValueError("This selection is stale; choose again")
    if not 0 <= action.discovery_index < len(cache.original.all_actions):
        raise ValueError("Selection does not belong to the current discovery")
    return cache.original.all_actions[action.discovery_index]


def preview_player_selection(session: Session, actor_uuid: UUID, action: AvailableActionInfo,
                             selected: tuple[AvailableTarget, ...] = (),
                             positions: tuple[tuple[int, int], ...] = ()) -> AvailableSelectionPreview:
    actor = _current_player(session, actor_uuid)
    original = _retained_row(session, action)
    key = (original.discovery_index,
           tuple(target.index for target in selected), positions)
    cache = session.discovery.previews
    if key not in cache:
        primary = next((target for target in original.valid_targets if selected and target.index == selected[0].index), None)
        pool = (primary.secondary_targets if primary is not None and primary.secondary_targets is not None
                else original.valid_targets)
        by_index = {target.index: target for target in pool}
        if any(chosen.index not in by_index for chosen in selected[1:]):
            raise ValueError("This allocation is not admitted")
        retained = (() if primary is None else (primary, *tuple(
            by_index[chosen.index] for chosen in selected[1:])))
        if selected and primary is None:
            raise ValueError("This target is not admitted")
        value = preview_available_selection(actor, original, retained, positions)
        cache[key] = AvailableSelectionPreview.model_validate(value.model_dump())
    return AvailableSelectionPreview.model_validate(cache[key].model_dump())


def _operation(session: Session, start_cursor: int, boundary: AdvanceResult | None = None) -> Operation:
    end_cursor = EventQueue.event_cursor()
    roots = tuple(event for index, event in EventQueue.iter_events_since(start_cursor)
                  if index <= end_cursor and event.parent_lineage is None
                  and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    appends = tuple(CombatLogAppend(generation=EventQueue.generation_id(), observer_uuid=session.player_uuids[0],
        encounter_log_index=index, operation_end_cursor=end_cursor, entry=entry)
        for index, entry in session.discovery.log_appends)
    session.discovery.log_appends.clear()
    return Operation(start_cursor, end_cursor, roots, boundary, snapshot_player_hud(session), appends)


def execute_player_action(
    session: Session,
    actor_uuid: UUID,
    action: AvailableActionInfo,
    target: AvailableTarget,
    *,
    extra_target_uuids: tuple[UUID, ...] = (),
    extra_target_positions: tuple[tuple[int, int], ...] = (),
    prefer_safe: bool = True,
) -> Operation:
    """Submit the current human's exact discovered choice to the rules engine."""
    actor = _current_player(session, actor_uuid)
    original = _retained_row(session, action)
    retained = next((candidate for candidate in original.valid_targets if candidate.index == target.index), None)
    if retained is None:
        raise ValueError("selected target does not belong to the discovered action")
    start = EventQueue.event_cursor()
    execute_available_action(
        actor, original, retained, extra_target_uuids=[str(identity) for identity in extra_target_uuids],
        extra_target_positions=list(extra_target_positions),
        prefer_safe=prefer_safe,
    )
    session.encounter.check_deaths()
    return _operation(session, start)


def player_position_options(
    session: Session, actor_uuid: UUID, action: AvailableActionInfo,
    target: AvailableTarget, selected: tuple[tuple[int, int], ...] = (),
) -> tuple[tuple[int, int], ...]:
    """Disclose the engine-admitted next vertices for one current human choice."""
    actor = _current_player(session, actor_uuid)
    original = _retained_row(session, action)
    retained = next((candidate for candidate in original.valid_targets if candidate.index == target.index), None)
    if retained is None:
        raise ValueError("selected target does not belong to the discovered action")
    if original.position_selection is None or original.position_selection.kind not in ("path", "entity_destination"):
        return ()
    return tuple(get_extra_position_options(actor, original, retained, list(selected)))


def equip_player_item(session: Session, actor_uuid: UUID, item_uuid: UUID,
                      slot: EquipmentSlot | None = None) -> Operation:
    actor = _current_player(session, actor_uuid)
    start = EventQueue.event_cursor()
    if not actor.equip_item(item_uuid, slot):
        raise ValueError("This equipment change is not admitted")
    return _operation(session, start)


def unequip_player_item(session: Session, actor_uuid: UUID, slot: EquipmentSlot,
                        *, allow_ground_fallback: bool = False) -> Operation:
    actor = _current_player(session, actor_uuid)
    start = EventQueue.event_cursor()
    if actor.unequip_item(slot, allow_ground_fallback=allow_ground_fallback) is None:
        raise ValueError("Cannot move this equipment into inventory")
    return _operation(session, start)


def toggle_player_handler(session: Session, actor_uuid: UUID, handler_uuid: UUID, enabled: bool) -> Operation:
    actor = _current_player(session, actor_uuid)
    choices = session.discovery.original
    if (choices is None or choices.entity_uuid != actor_uuid
            or session.discovery.cursor != EventQueue.event_cursor()
            or not any(row.uuid == handler_uuid for row in choices.handler_details)):
        raise ValueError("This reaction preference is not admitted")
    start = EventQueue.event_cursor()
    if not actor.set_handler_enabled_by_uuid(handler_uuid, enabled):
        raise ValueError("This reaction preference is not available")
    session.discovery.cursor = -1
    session.discovery.previews.clear()
    return _operation(session, start)


def end_player_turn(session: Session, actor_uuid: UUID) -> Operation:
    """End this human turn without starting the next actor's decision."""
    _current_player(session, actor_uuid)
    start = EventQueue.event_cursor()
    session.encounter.complete_current_turn()
    return _operation(session, start)


def advance_controller(session: Session) -> Operation:
    """Run one engine decision or expose its existing human/end boundary."""
    start = EventQueue.event_cursor()
    return _operation(session, start, session.encounter.advance_one_controller_action_boundary())


def close_session(session: Session) -> None:
    """Release native controller ownership before removing world deployment."""
    if session.discovery.log_listener is not None:
        Encounter.remove_combat_log_listener(session.discovery.log_listener)
    session.enemy_controller.close()
    session.game.close()
