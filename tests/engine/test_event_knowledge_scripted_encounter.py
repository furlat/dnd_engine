"""Freeze the public event stream of the direct E3 proving encounter."""

from collections import Counter
from typing import Callable, Optional
from uuid import UUID, uuid4

import pytest

from dnd.actions.operations import execute_available_action, get_available_actions
from dnd.actions.reactions import add_opportunity_attack_handler
from dnd.actions.standard import AttackEvent, MovementEvent, SpellEvent
from dnd.blocks.sensory import PartyKnowledge
from dnd.content.monsters.monster_builders import create_monster
from dnd.content.scenarios.battlefield_builders import build_battlefield
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.encounter_events import (
    EncounterEndEvent,
    EncounterStartEvent,
    RoundStartEvent,
    TurnStartEvent,
)
from dnd.core.events.entity_events import EntityCreatedEvent
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.knowledge import (
    EventArchive,
    EventBatch,
    EventKnowledge,
    Known,
    KnowledgeMask,
    KnowledgeDiagnostic,
)
from dnd.core.events.world_events import SensoryUpdateEvent
from dnd.encounters.controllers import (
    Controller,
    ControllerStepResult,
    HumanController,
    TurnContext,
)
from dnd.encounters.encounter import AdvanceResult, Encounter
from dnd.entities.entity import Entity
from dnd.game import Game
import dnd.core.gridmap as gridmap_module
from dnd.event_reduction import (
    EventReducer,
    format_objective_event,
    format_subjective_delivery,
    format_subjective_delivery_tree,
    party_event_delivery,
    party_event_router,
)
from dnd.runtime_reset import reset_engine_runtime


class DiscoveredIntentController(Controller):
    """Execute one stored action intention through public discovery results."""

    action_template: str
    target_position: Optional[tuple[int, int]] = None
    target_uuid: Optional[UUID] = None
    used: bool = False

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Stop after the one intended action has been applied."""
        return not self.used

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        """Discover and execute the stored action intent."""
        if self.used:
            return ControllerStepResult(end_turn=True)

        available = get_available_actions(entity)
        action_info = next(
            info
            for info in available.all_actions
            if info.template_name == self.action_template
        )
        target = next(
            target
            for target in action_info.valid_targets
            if (
                self.target_position is not None
                and target.position == self.target_position
            )
            or (
                self.target_uuid is not None
                and target.target_uuid == self.target_uuid
            )
        )
        self.used = True
        return ControllerStepResult(
            event=execute_available_action(entity, action_info, target),
        )


def _record_range(
    ranges: list[tuple[str, int, int]],
    label: str,
    operation: Callable[[], object],
) -> object:
    """Record one public operation's exact source-cursor interval."""
    start = EventQueue.event_cursor()
    result = operation()
    stop = EventQueue.event_cursor()
    ranges.append((label, start, stop))
    assert stop >= start
    return result


def _find_discovered_target(
    entity: Entity,
    template_name: str,
    *,
    position: Optional[tuple[int, int]] = None,
    target_uuid: Optional[UUID] = None,
):
    """Select one target from the entity's current public action discovery."""
    available = get_available_actions(entity)
    action_info = next(
        info
        for info in available.all_actions
        if info.template_name == template_name
    )
    target = next(
        target
        for target in action_info.valid_targets
        if (
            position is not None
            and target.position == position
        )
        or (
            target_uuid is not None
            and target.target_uuid == target_uuid
        )
    )
    return action_info, target


def _event_inventory(events: list[Event]) -> list[str]:
    """Return the complete ordered concrete event inventory for the ledger."""
    return [
        (
            f"{index:03d} "
            f"{event.__class__.__module__}.{event.__class__.__qualname__} "
            f"{event.phase.value} {event.event_type.value}"
        )
        for index, event in enumerate(events)
    ]


def test_direct_public_proving_encounter_freezes_the_real_event_inventory() -> None:
    """Run all Slice 3.1 beats through real public encounter boundaries."""
    reset_engine_runtime()
    ranges: list[tuple[str, int, int]] = []
    try:
        _record_range(
            ranges,
            "world_initialization",
            lambda: build_battlefield("battlefield.open_floor_bright"),
        )
        game = Game()
        roles: dict[str, Entity] = {}
        authored_roles = (
            ("hero_frontline", "monster.goblin", (3, 3), "heroes"),
            ("hero_caster", "monster.generic_caster", (2, 6), "heroes"),
            ("enemy_guard", "monster.skeleton", (4, 3), "monsters"),
            ("enemy_raider", "monster.skeleton", (2, 5), "monsters"),
        )
        for role_name, monster_id, position, faction in authored_roles:
            start = EventQueue.event_cursor()
            role = create_monster(
                monster_id,
                uuid4(),
                name=role_name,
                faction=faction,
            )
            game.deploy_entity(role, position)
            stop = EventQueue.event_cursor()
            ranges.append((f"create_and_deploy:{role_name}", start, stop))
            assert isinstance(role, Entity)
            roles[role_name] = role

        add_opportunity_attack_handler(roles["enemy_guard"])

        controllers = {
            "hero_frontline": HumanController(
                source_entity_uuid=roles["hero_frontline"].uuid,
            ),
            "hero_caster": HumanController(
                source_entity_uuid=roles["hero_caster"].uuid,
            ),
            "enemy_guard": DiscoveredIntentController(
                source_entity_uuid=roles["enemy_guard"].uuid,
                action_template="Move",
                target_position=(3, 3),
            ),
            "enemy_raider": DiscoveredIntentController(
                source_entity_uuid=roles["enemy_raider"].uuid,
                action_template="Attack_MELEE_MAIN",
                target_uuid=roles["hero_caster"].uuid,
            ),
        }
        encounter = Encounter(
            name="Event knowledge proving encounter",
            source_entity_uuid=uuid4(),
        )
        for role_name in (
            "hero_frontline",
            "enemy_guard",
            "enemy_raider",
            "hero_caster",
        ):
            encounter.add_combatant(roles[role_name], controllers[role_name])

        expected_initiative_order = [
            roles[role_name].uuid
            for role_name in (
                "hero_frontline",
                "enemy_guard",
                "enemy_raider",
                "hero_caster",
            )
        ]
        with fixed_dice_faces(20, 16, 12, 8):
            _record_range(ranges, "initiative_roll", encounter.roll_initiative)
        assert encounter.initiative_order == expected_initiative_order
        _record_range(ranges, "encounter_start", encounter.start_encounter)

        frontline_start = _record_range(
            ranges,
            "hero_frontline_turn_start",
            encounter.advance_one_controller_action_boundary,
        )
        assert isinstance(frontline_start, AdvanceResult)
        assert frontline_start.status.value == "waiting_for_human"
        move_info, move_target = _find_discovered_target(
            roles["hero_frontline"],
            "Move",
            position=(2, 3),
        )
        assert move_info.can_afford
        assert move_target.path == [(3, 3), (2, 3)]
        move_start = EventQueue.event_cursor()
        with fixed_dice_faces(19, 1):
            move_event = _record_range(
                ranges,
                "hero_frontline_move",
                lambda: encounter.execute_action(
                    roles["hero_frontline"].uuid,
                    move_info.template_name,
                    move_target.index,
                ),
            )
        assert isinstance(move_event, MovementEvent)
        assert move_event.end_position == (2, 3)
        assert roles["hero_frontline"].position == (2, 3)

        attack_info, attack_target = _find_discovered_target(
            roles["hero_frontline"],
            "Attack_RANGED_MAIN",
            target_uuid=roles["enemy_guard"].uuid,
        )
        assert attack_info.can_afford
        with fixed_dice_faces(19, 1):
            attack_event = _record_range(
                ranges,
                "hero_frontline_weapon_attack",
                lambda: encounter.execute_action(
                    roles["hero_frontline"].uuid,
                    attack_info.template_name,
                    attack_target.index,
                ),
            )
        assert isinstance(attack_event, AttackEvent)
        assert attack_event.source_entity_uuid == roles["hero_frontline"].uuid
        assert attack_event.target_entity_uuid == roles["enemy_guard"].uuid
        _record_range(
            ranges,
            "hero_frontline_turn_end",
            encounter.complete_current_turn,
        )

        enemy_guard_start = EventQueue.event_cursor()
        guard_result = _record_range(
            ranges,
            "enemy_guard_action_boundary",
            encounter.advance_one_controller_action_boundary,
        )
        assert isinstance(guard_result, AdvanceResult)
        assert guard_result.status.value == "advanced_autonomous"
        assert roles["enemy_guard"].position == (3, 3)

        enemy_raider_start = EventQueue.event_cursor()
        with fixed_dice_faces(19, 1):
            raider_result = _record_range(
                ranges,
                "enemy_raider_action_boundary",
                encounter.advance_one_controller_action_boundary,
            )
        assert isinstance(raider_result, AdvanceResult)
        assert raider_result.status.value == "advanced_autonomous"
        assert enemy_guard_start != enemy_raider_start
        guard_range = next(
            row for row in ranges if row[0] == "enemy_guard_action_boundary"
        )
        raider_range = next(
            row for row in ranges if row[0] == "enemy_raider_action_boundary"
        )
        assert guard_range[2] == raider_range[1]
        assert roles["hero_caster"].health.life_state.value == "alive"

        caster_start = _record_range(
            ranges,
            "hero_caster_turn_start",
            encounter.advance_one_controller_action_boundary,
        )
        assert isinstance(caster_start, AdvanceResult)
        assert caster_start.status.value == "waiting_for_human"
        spell_info, spell_target = _find_discovered_target(
            roles["hero_caster"],
            "Magic Missile__slot_1",
            target_uuid=roles["enemy_raider"].uuid,
        )
        assert spell_info.can_afford
        with fixed_dice_faces(1, 1, 1):
            spell_event = _record_range(
                ranges,
                "hero_caster_discovered_spell",
                lambda: encounter.execute_action(
                    roles["hero_caster"].uuid,
                    spell_info.template_name,
                    spell_target.index,
                ),
            )
        assert isinstance(spell_event, SpellEvent)
        assert spell_event.source_entity_uuid == roles["hero_caster"].uuid
        assert spell_event.target_entity_uuid == roles["enemy_raider"].uuid
        _record_range(
            ranges,
            "hero_caster_turn_end",
            encounter.complete_current_turn,
        )
        end_event = _record_range(
            ranges,
            "encounter_end",
            lambda: encounter.end_encounter("proving inventory complete"),
        )
        assert isinstance(end_event, EncounterEndEvent)
        assert encounter.state.value == "ended"

        events = [event for _, event in EventQueue.iter_events_since(0)]
        assert len(events) == EventQueue.event_cursor()
        assert isinstance(events[0], Event)
        world_versions = [
            event
            for event in events
            if event.event_type is EventType.WORLD_INITIALIZED
        ]
        assert [event.phase for event in world_versions] == [
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        ]
        assert sum(
            isinstance(event, EntityCreatedEvent) for event in events
        ) == 4
        assert any(
            isinstance(event, EncounterStartEvent) for event in events
        )
        assert any(isinstance(event, RoundStartEvent) for event in events)
        assert any(
            isinstance(event, AttackEvent)
            and event.name == "Opportunity Attack"
            and event.source_entity_uuid == roles["enemy_guard"].uuid
            and event.target_entity_uuid == roles["hero_frontline"].uuid
            for event in events[move_start:]
        )
        assert any(
            event.event_type is EventType.MOVEMENT
            and event.source_entity_uuid == roles["enemy_guard"].uuid
            for event in events[guard_range[1]:guard_range[2]]
        )
        assert any(
            event.event_type is EventType.ATTACK
            and event.source_entity_uuid == roles["enemy_raider"].uuid
            and event.target_entity_uuid == roles["hero_caster"].uuid
            for event in events[raider_range[1]:raider_range[2]]
        )
        assert any(
            isinstance(event, TurnStartEvent)
            and event.entity_uuid in {
                roles["hero_frontline"].uuid,
                roles["hero_caster"].uuid,
            }
            for event in events
        )
        for role_name in ("hero_frontline", "hero_caster"):
            assert any(
                isinstance(event, TurnStartEvent)
                and event.entity_uuid == roles[role_name].uuid
                for event in events
            )

        parent_edges: list[tuple[int, int]] = []
        resolved_parent_lineage_edges = 0
        for index, event in enumerate(events):
            if event.parent_event is None:
                continue
            parent = EventQueue.get_event_by_uuid(event.parent_event)
            assert parent is not None
            parent_index = EventQueue.get_event_index(parent.uuid)
            assert parent_index is not None
            assert parent_index < index, (
                index,
                type(event).__name__,
                event.phase,
                event.uuid,
                event.parent_event,
            )
            parent_edges.append((index, parent_index))
            if event.phase is EventPhase.COMPLETION:
                assert event.parent_lineage == parent.lineage_uuid
                resolved_parent_lineage_edges += 1
        assert resolved_parent_lineage_edges > 0

        def root_lineage(event: Event) -> UUID:
            """Resolve one stored event to its parentless source lineage."""
            current = event
            visited: set[UUID] = set()
            while current.parent_event is not None:
                assert current.uuid not in visited
                visited.add(current.uuid)
                parent = EventQueue.get_event_by_uuid(current.parent_event)
                assert parent is not None
                current = parent
            return current.lineage_uuid

        root_rows: dict[UUID, tuple[int, Event]] = {}
        event_root_lineages: list[UUID] = []
        for index, event in enumerate(events):
            lineage = root_lineage(event)
            event_root_lineages.append(lineage)
            if event.parent_event is None:
                root_rows.setdefault(lineage, (index, event))

        for lineage, (root_index, _) in root_rows.items():
            terminal_rows = [
                (index, event)
                for index, event in enumerate(events)
                if event_root_lineages[index] == lineage
                and event.lineage_uuid == lineage
                and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
            ]
            assert terminal_rows
            terminal_index, terminal = terminal_rows[-1]
            assert terminal.is_last
            tree_indices = [
                index
                for index, event_lineage in enumerate(event_root_lineages)
                if event_lineage == lineage
            ]
            assert tree_indices == list(range(root_index, terminal_index + 1))
            assert tree_indices[-1] == terminal_index

        sensory_before_causative_completion = 0
        sensory_causality: list[tuple[int, int, int]] = []
        for index, event in enumerate(events):
            if not isinstance(event, SensoryUpdateEvent):
                continue
            cause = EventQueue.get_event_by_uuid(event.cause_event_uuid)
            if cause is None:
                continue
            history = EventQueue.get_event_history(cause.uuid)
            completions = [
                candidate
                for candidate in history
                if candidate.phase is EventPhase.COMPLETION
            ]
            if not completions:
                continue
            completion_index = EventQueue.get_event_index(completions[-1].uuid)
            assert completion_index is not None
            cause_index = EventQueue.get_event_index(cause.uuid)
            assert cause_index is not None
            sensory_causality.append(
                (index, cause_index, completion_index)
            )
            if index < completion_index:
                sensory_before_causative_completion += 1
        assert sensory_before_causative_completion > 0

        log_events = {
            id(event.combat_log): event
            for event in events
            if event.combat_log is not None and event.parent_event is None
        }
        assert encounter.combat_log
        assert all(id(log) in log_events for log in encounter.combat_log)
        assert all(log.sub_entries is not None for log in encounter.combat_log)

        def combat_log_shape(entry) -> tuple:
            """Describe one public combat-log tree without reading internals."""
            return (
                entry.entry_type.value,
                tuple(
                    combat_log_shape(child)
                    for child in (entry.sub_entries or ())
                ),
            )

        encounter_start_index = next(
            start for label, start, _ in ranges if label == "encounter_start"
        )
        encounter_ranges = [
            row for row in ranges if row[1] >= encounter_start_index
        ]
        combat_log_ranges: list[tuple[str, int, int]] = []
        log_count = 0
        for label, start, stop in encounter_ranges:
            boundary_log_count = sum(
                event.parent_event is None and event.combat_log is not None
                for event in events[start:stop]
            )
            combat_log_ranges.append(
                (label, log_count, log_count + boundary_log_count)
            )
            log_count += boundary_log_count
        assert log_count == len(encounter.combat_log)

        combat_log_links = []
        terminal_links = []
        for log_index, log in enumerate(encounter.combat_log):
            source_event = log_events[id(log)]
            source_index = EventQueue.get_event_index(source_event.uuid)
            assert source_index is not None
            assert source_event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
            assert source_event.combat_log is log
            combat_log_links.append(
                (
                    log_index,
                    source_index,
                    str(source_event.uuid),
                    str(source_event.lineage_uuid),
                    f"{source_event.__class__.__module__}.{source_event.__class__.__qualname__}",
                    log.entry_type.value,
                    combat_log_shape(log),
                )
            )
            terminal_links.append(
                (
                    log_index,
                    str(source_event.uuid),
                    str(source_event.lineage_uuid),
                    f"{source_event.__class__.__module__}.{source_event.__class__.__qualname__}",
                    source_index,
                    log.entry_type.value,
                    combat_log_shape(log),
                )
            )
        assert len(terminal_links) == len(encounter.combat_log)

        archive = EventArchive.capture_queue_range(0)
        party = PartyKnowledge.cold(
            roles["hero_frontline"].uuid,
            roles["hero_caster"].uuid,
        )
        router = party_event_router(party)
        formatted_rows = 0
        for captured in archive.entries:
            if captured.event_class is Event:
                continue
            objective_text = format_objective_event(captured)
            assert isinstance(objective_text, str) and objective_text
            assert "CombatLogEntry" not in objective_text
            delivery = party_event_delivery(captured, router)
            if delivery is None or isinstance(delivery, KnowledgeDiagnostic):
                continue
            objective_knowledge = EventKnowledge(
                captured,
                KnowledgeMask.top(),
            )
            assert delivery.knowledge.captured is captured
            assert delivery.knowledge.event_class is captured.event_class
            assert delivery.knowledge.read(("uuid",)) == objective_knowledge.read(
                ("uuid",),
            )
            assert delivery.knowledge.read(("lineage_uuid",)) == objective_knowledge.read(
                ("lineage_uuid",),
            )
            assert delivery.knowledge.read(("phase",)) == objective_knowledge.read(
                ("phase",),
            )
            subjective_text = format_subjective_delivery(delivery)
            assert isinstance(objective_text, str) and objective_text
            assert isinstance(subjective_text, str) and subjective_text
            assert "CombatLogEntry" not in objective_text
            assert "CombatLogEntry" not in subjective_text
            formatted_rows += 1
        assert formatted_rows > 0

        inventory = _event_inventory(events)
        counts = Counter(
            f"{event.__class__.__module__}.{event.__class__.__qualname__} "
            f"{event.phase.value} {event.event_type.value}"
            for event in events
        )
        print("SLICE_3_1_BOUNDARY_RANGES")
        for label, start, stop in ranges:
            print(f"{label} [{start},{stop})")
        print("SLICE_3_1_EVENT_COUNTS")
        for key in sorted(counts):
            print(f"{key} = {counts[key]}")
        print("SLICE_3_1_PARENT_EDGE_COUNT", len(parent_edges))
        print(
            "SLICE_3_1_RESOLVED_PARENT_LINEAGE_EDGE_COUNT",
            resolved_parent_lineage_edges,
        )
        print("SLICE_3_1_PARENT_EDGES", parent_edges)
        print(
            "SLICE_3_1_SENSORY_CAUSALITY_COUNT",
            len(sensory_causality),
        )
        print(
            "SLICE_3_1_SENSORY_BEFORE_CAUSATIVE_COMPLETION",
            sensory_before_causative_completion,
        )
        print("SLICE_3_1_ENCOUNTER_UUID", encounter.uuid)
        print("SLICE_3_1_COMBAT_LOG_RANGES", combat_log_ranges)
        print("SLICE_3_1_TERMINAL_LINKS", terminal_links)
        print("SLICE_3_1_COMBAT_LOG_LINKS", combat_log_links)
        print("SLICE_3_1_EVENT_INVENTORY")
        print("\n".join(inventory))
        print("SLICE_3_1_COMBAT_LOGS", len(encounter.combat_log))
    finally:
        reset_engine_runtime()


def _run_full_detached_replay() -> tuple[
    int,
    int,
    list[tuple[int, int, tuple[str, ...]]],
    tuple[tuple[object, ...], ...],
    int,
    int,
    int,
]:
    """Reduce and consume the complete public proving encounter from cursor zero."""
    reset_engine_runtime()
    role_ids = {
        "hero_frontline": UUID("00000000-0000-0000-0000-000000000101"),
        "hero_caster": UUID("00000000-0000-0000-0000-000000000102"),
        "enemy_guard": UUID("00000000-0000-0000-0000-000000000103"),
        "enemy_raider": UUID("00000000-0000-0000-0000-000000000104"),
    }
    reducer = EventReducer(
        role_ids["hero_frontline"],
        role_ids["hero_caster"],
        source_cursor=0,
    )
    tree_ranges: list[tuple[int, int, tuple[str, ...]]] = []
    batches: list[EventBatch] = []
    batch_shapes: list[tuple[object, ...]] = []
    formatted_count = 0
    tree_count = 0
    try:
        build_battlefield("battlefield.open_floor_bright")
        game = Game()
        roles: dict[str, Entity] = {}
        authored_roles = (
            ("hero_frontline", "monster.goblin", (3, 3), "heroes"),
            ("hero_caster", "monster.generic_caster", (2, 6), "heroes"),
            ("enemy_guard", "monster.skeleton", (4, 3), "monsters"),
            ("enemy_raider", "monster.skeleton", (2, 5), "monsters"),
        )
        for role_name, monster_id, position, faction in authored_roles:
            role = create_monster(
                monster_id,
                role_ids[role_name],
                name=role_name,
                faction=faction,
            )
            game.deploy_entity(role, position)
            assert isinstance(role, Entity)
            roles[role_name] = role

        add_opportunity_attack_handler(roles["enemy_guard"])
        controllers = {
            "hero_frontline": HumanController(
                source_entity_uuid=roles["hero_frontline"].uuid,
            ),
            "hero_caster": HumanController(
                source_entity_uuid=roles["hero_caster"].uuid,
            ),
            "enemy_guard": DiscoveredIntentController(
                source_entity_uuid=roles["enemy_guard"].uuid,
                action_template="Move",
                target_position=(3, 3),
            ),
            "enemy_raider": DiscoveredIntentController(
                source_entity_uuid=roles["enemy_raider"].uuid,
                action_template="Attack_MELEE_MAIN",
                target_uuid=roles["hero_caster"].uuid,
            ),
        }
        encounter = Encounter(
            name="Detached full event knowledge proving encounter",
            source_entity_uuid=UUID("00000000-0000-0000-0000-000000000105"),
        )
        for role_name in (
            "hero_frontline",
            "enemy_guard",
            "enemy_raider",
            "hero_caster",
        ):
            encounter.add_combatant(roles[role_name], controllers[role_name])
        with fixed_dice_faces(20, 16, 12, 8):
            encounter.roll_initiative()
        assert encounter.initiative_order == [
            roles[role_name].uuid
            for role_name in (
                "hero_frontline",
                "enemy_guard",
                "enemy_raider",
                "hero_caster",
            )
        ]
        encounter.start_encounter()

        result = encounter.advance_one_controller_action_boundary()
        assert result.status.value == "waiting_for_human"
        move_info, move_target = _find_discovered_target(
            roles["hero_frontline"],
            "Move",
            position=(2, 3),
        )
        assert move_info.can_afford
        assert move_target.path == [(3, 3), (2, 3)]
        with fixed_dice_faces(19, 1):
            move_event = encounter.execute_action(
                roles["hero_frontline"].uuid,
                move_info.template_name,
                move_target.index,
            )
        assert isinstance(move_event, MovementEvent)

        attack_info, attack_target = _find_discovered_target(
            roles["hero_frontline"],
            "Attack_RANGED_MAIN",
            target_uuid=roles["enemy_guard"].uuid,
        )
        assert attack_info.can_afford
        with fixed_dice_faces(19, 1):
            attack_event = encounter.execute_action(
                roles["hero_frontline"].uuid,
                attack_info.template_name,
                attack_target.index,
            )
        assert isinstance(attack_event, AttackEvent)
        encounter.complete_current_turn()

        with fixed_dice_faces(19, 1):
            guard_result = encounter.advance_one_controller_action_boundary()
        assert guard_result.status.value == "advanced_autonomous"
        with fixed_dice_faces(19, 1):
            raider_result = encounter.advance_one_controller_action_boundary()
        assert raider_result.status.value == "advanced_autonomous"
        assert roles["enemy_guard"].position == (3, 3)
        assert roles["hero_caster"].health.life_state.value == "alive"

        result = encounter.advance_one_controller_action_boundary()
        assert result.status.value == "waiting_for_human"
        spell_info, spell_target = _find_discovered_target(
            roles["hero_caster"],
            "Magic Missile__slot_1",
            target_uuid=roles["enemy_raider"].uuid,
        )
        assert spell_info.can_afford
        with fixed_dice_faces(1, 1, 1):
            spell_event = encounter.execute_action(
                roles["hero_caster"].uuid,
                spell_info.template_name,
                spell_target.index,
            )
        assert isinstance(spell_event, SpellEvent)
        encounter.complete_current_turn()
        end_event = encounter.end_encounter("detached full replay complete")
        assert isinstance(end_event, EncounterEndEvent)

        source_stop = EventQueue.event_cursor()
        with pytest.MonkeyPatch.context() as fatal_accessors:
            fatal_accessors.setattr(
                Entity,
                "get",
                classmethod(
                    lambda _cls, _uuid: (_ for _ in ()).throw(
                        AssertionError("detached consumer accessed live Entity")
                    )
                ),
            )
            fatal_accessors.setattr(
                EventQueue,
                "get_event_by_uuid",
                classmethod(
                    lambda _cls, _uuid: (_ for _ in ()).throw(
                        AssertionError("detached consumer accessed live EventQueue")
                    )
                ),
            )
            fatal_accessors.setattr(
                gridmap_module,
                "get_map",
                lambda: (_ for _ in ()).throw(
                    AssertionError("detached consumer accessed live GridMap")
                ),
            )
            while (batch := reducer.reduce_next_committed_tree()) is not None:
                batches.append(batch)
                detached_events = reducer.archives[-1].entries
                tree_ranges.append((
                    batch.start,
                    batch.stop,
                    tuple(
                        f"{captured.event_class.__module__}.{captured.event_class.__qualname__}"
                        for captured in detached_events
                    ),
                ))
                assert not batch.diagnostics
                assert tuple(
                    coverage.source_index
                    for coverage in batch.coverage
                ) == tuple(range(batch.start, batch.stop))
                assert len(batch.coverage) == len(detached_events)
                batch_shapes.append((
                    batch.start,
                    batch.stop,
                    tuple(
                        (
                            coverage.source_index,
                            coverage.disposition.value,
                            len(coverage.delivery_ids),
                        )
                        for coverage in batch.coverage
                    ),
                    tuple(
                        (
                            delivery.knowledge.event_class.__module__,
                            delivery.knowledge.event_class.__qualname__,
                            delivery.knowledge.captured.source_index,
                            delivery.disclosure_cause_source_index is not None,
                        )
                        for delivery in batch.deliveries
                    ),
                ))
                for delivery in batch.deliveries:
                    rendered = format_subjective_delivery(delivery)
                    assert isinstance(rendered, str) and rendered
                    formatted_count += 1
                tree_deliveries = tuple(
                    delivery
                    for delivery in batch.deliveries
                    if all(
                        isinstance(delivery.knowledge.read((path,)), Known)
                        for path in ("uuid", "parent_event", "parent_lineage")
                    )
                )
                if tree_deliveries:
                    tree = format_subjective_delivery_tree(tree_deliveries)
                    assert tree
                    tree_count += 1
        assert len(batches) == len(tree_ranges)
        assert len(tree_ranges) == 27
        assert tree_ranges[0][0] == 0
        assert all(
            current[0] == previous[1]
            for previous, current in zip(tree_ranges, tree_ranges[1:])
        )
        assert tree_ranges[-1][1] == source_stop
        assert tuple(
            coverage.source_index
            for batch in batches
            for coverage in batch.coverage
        ) == tuple(range(source_stop))
        assert len(reducer.archives) == len(tree_ranges)
        return (
            source_stop,
            len(tree_ranges),
            tree_ranges,
            tuple(batch_shapes),
            formatted_count,
            tree_count,
            len(reducer.archives),
        )
    finally:
        reset_engine_runtime()


def test_full_public_encounter_replays_and_consumes_detached_batches_deterministically() -> None:
    """The full real encounter reduces and formats identically across cold runs."""
    first = _run_full_detached_replay()
    second = _run_full_detached_replay()
    assert first == second
    (
        source_stop,
        tree_count,
        _tree_ranges,
        _shapes,
        formatted_count,
        subjective_tree_count,
        archive_count,
    ) = first
    assert source_stop == 250
    assert tree_count == 27
    assert formatted_count > 0
    assert subjective_tree_count > 0
    assert archive_count == tree_count
