"""External controller checks against the one shared subjective policy stack."""

from typing import Any, cast

import pytest

from ai.external_agent import ExternalAgent
from ai.observation.models import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from ai.policy import AgentCommand, AgentCommandType, PolicyDecisionTelemetry
from ai.policy.source import policy_source_snapshot
from ai.policy.telemetry import QueuedPolicyTelemetrySink
from ai.protocol.control import (
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    ActionTarget,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
)
from ai.protocol.semantics import ActionSemantics, ActionTag, action_semantics_ref
from ai.subjective.processors import AgentFactsProcessor
from ai.subjective.store import SubjectiveStore


class _FakeRuntime:
    """Minimal event-first runtime boundary consumed by the controller."""

    def __init__(self, store: SubjectiveStore) -> None:
        self.store = store
        self.events: list[dict[str, Any]] = []
        self.resync_count = 0

    def bootstrap(self) -> None:
        return None

    def close(self) -> None:
        return None

    def wait_for_epoch(self) -> DecisionEpoch:
        assert self.store.world is not None
        assert self.store.world.current_epoch is not None
        return self.store.world.current_epoch

    def resync(self) -> None:
        self.resync_count += 1

    def emit_event(self, event_type: str, summary: str, **kwargs: Any) -> None:
        self.events.append({"event_type": event_type, "summary": summary, **kwargs})

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        self.events.append({"event_type": "policy.decision_evaluated", "telemetry": event})


def test_external_controller_has_no_available_actions_polling_surface() -> None:
    """Normal decisions can only consume streamed epochs from the local store."""
    agent = ExternalAgent("http://127.0.0.1:9", "session-ai")

    try:
        assert not hasattr(agent, "fetch_available_actions")
        assert len(agent.runtime.hooks.processors) == 1
        assert isinstance(agent.runtime.hooks.processors[0], AgentFactsProcessor)
    finally:
        agent.close()


def test_external_controller_uses_shared_policy_host_for_door_routine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-contact navigation is selected directly from the streamed subjective epoch."""
    world = _door_world()
    store = SubjectiveStore()
    _install_world(store, world)
    runtime = _FakeRuntime(store)
    agent = _agent_with_runtime(runtime)
    commands: list[AgentCommand] = []

    def accept(command: AgentCommand, *, command_id: str | None = None) -> dict[str, Any]:
        assert command_id is not None
        commands.append(command)
        _clear_epoch(store)
        return _result(
            CommandResultStatus.ACCEPTED,
            command_id,
            row_id=command.row_id,
        ).model_dump(mode="json")

    monkeypatch.setattr(agent, "execute_command", accept)
    try:
        agent.play_current_turn(materialized=world)
    finally:
        agent.close()

    assert len(commands) == 1
    assert commands[0].command_type is AgentCommandType.EXECUTE
    assert commands[0].row_id == "move-to-door"
    assert commands[0].routine_id == "routine.approach_open_reassess"
    assert commands[0].routine_step_id == "approach"
    assert any(event["event_type"] == "policy.decision_evaluated" for event in runtime.events)


def test_external_controller_uses_shared_policy_host_for_visible_combat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Visible legal damage outranks no-contact object navigation."""
    world = _combat_world()
    store = SubjectiveStore()
    _install_world(store, world)
    runtime = _FakeRuntime(store)
    agent = _agent_with_runtime(runtime)
    commands: list[AgentCommand] = []

    def accept(command: AgentCommand, *, command_id: str | None = None) -> dict[str, Any]:
        assert command_id is not None
        commands.append(command)
        _clear_epoch(store)
        return _result(
            CommandResultStatus.ACCEPTED,
            command_id,
            row_id=command.row_id,
        ).model_dump(mode="json")

    monkeypatch.setattr(agent, "execute_command", accept)
    try:
        agent.play_current_turn(materialized=world)
    finally:
        agent.close()

    assert len(commands) == 1
    assert commands[0].row_id == "primary-attack"
    assert commands[0].target_uuid == "hero"
    assert commands[0].reason == "legal semantic damage against a visible hostile"


def test_external_controller_reranks_after_rejected_row_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejection constrains and reruns the same shared host on the same epoch."""
    world = _combat_world(include_backup=True)
    store = SubjectiveStore()
    _install_world(store, world)
    runtime = _FakeRuntime(store)
    agent = _agent_with_runtime(runtime)
    commands: list[AgentCommand] = []

    def reject_then_accept(
        command: AgentCommand,
        *,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        assert command_id is not None
        commands.append(command)
        if len(commands) == 1:
            return _result(
                CommandResultStatus.REJECTED,
                command_id,
                row_id=command.row_id,
            ).model_dump(mode="json")
        _clear_epoch(store)
        return _result(
            CommandResultStatus.ACCEPTED,
            command_id,
            row_id=command.row_id,
        ).model_dump(mode="json")

    monkeypatch.setattr(agent, "execute_command", reject_then_accept)
    try:
        agent.play_current_turn(max_commands=3, materialized=world)
    finally:
        agent.close()

    assert [command.row_id for command in commands] == ["primary-attack", "secondary-attack"]
    decisions = [
        event["telemetry"].decision
        for event in runtime.events
        if event["event_type"] == "policy.decision_evaluated"
    ]
    assert len(decisions) == 2
    assert decisions[1].trace[0].node_path == "PolicyHost/ExecutionConstraints"
    assert decisions[1].trace[0].detail == "applied:row:primary-attack"
    assert runtime.resync_count == 1


def test_policy_source_snapshot_contains_only_the_shared_stack() -> None:
    """Evidence fingerprints the only decision-bearing policy implementation."""
    snapshot = policy_source_snapshot()

    assert snapshot.policy_name == "shared_subjective_hierarchical_policy"
    assert len(snapshot.source_sha256) == 64
    assert snapshot.line_count > 1_000
    assert snapshot.source_path == "ai/policy/host.py"
    assert "ai/protocol/control.py" in snapshot.source_paths
    assert "ai/protocol/semantics.py" in snapshot.source_paths
    assert "ai/semantics/actions.py" in snapshot.source_paths
    assert "ai/subjective/epochs.py" in snapshot.source_paths
    assert "ai/policy/commands.py" in snapshot.source_paths
    assert "ai/policy/candidates.py" in snapshot.source_paths
    assert "ai/policy/routines.py" in snapshot.source_paths
    assert all(not path.startswith("ai/external/") for path in snapshot.source_paths)
    assert "class SelfSetupSemantics" in snapshot.source
    assert "def build_decision_epoch" in snapshot.source
    assert "def evaluate_default_policy" in snapshot.source
    assert "class PolicyHost" in snapshot.source


def _agent_with_runtime(runtime: _FakeRuntime) -> ExternalAgent:
    """Create a controller with its network runtime replaced by a local store."""
    agent = ExternalAgent("http://testserver", "session-ai")
    agent.policy_telemetry.close()
    agent.runtime.close()
    agent.runtime = cast(Any, runtime)
    agent.policy_telemetry = QueuedPolicyTelemetrySink(runtime)
    return agent


def _install_world(store: SubjectiveStore, world: SubjectiveWorldState) -> None:
    """Install one subjective world in the canonical store."""
    store.world = world


def _clear_epoch(store: SubjectiveStore) -> None:
    """Model the follow-up epoch-clear delivered after turn completion."""
    assert store.world is not None
    store.world = store.world.model_copy(update={"current_epoch": None})


def _result(
    status: CommandResultStatus,
    command_id: str,
    *,
    row_id: str | None,
) -> CommandResult:
    """Build one correlated server-shaped result for the active test epoch."""
    return CommandResult(
        status=status,
        command_id=command_id,
        session_id="session-ai",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id=None if status is CommandResultStatus.ACCEPTED else "epoch-1",
        row_id=row_id,
        payload={"encounter_ended": False},
    )


def _door_world() -> SubjectiveWorldState:
    """Build no-contact subjective state with a known closed-door route."""
    move_semantics = ActionSemantics(
        semantic_id="movement.voluntary",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL}),
    )
    move_ref = action_semantics_ref(move_semantics)
    move = ActionAffordance(
        row_id="move-to-door",
        bucket="position_actions",
        template_name="Move",
        semantic_key="action.move",
        display_name="Move",
        action_category="movement",
        target_type="position_path",
        can_afford=True,
        cost=ActionCostProfile(movement_cost=10),
        targets=[ActionTarget(
            index=2,
            position=(2, 0),
            path_cost=10,
            path=[(0, 0), (1, 0), (2, 0)],
        )],
        target_options=[ActionTarget(
            index=2,
            position=(2, 0),
            path_cost=10,
            path=[(0, 0), (1, 0), (2, 0)],
        )],
        semantic_id=move_semantics.semantic_id,
        semantics_ref=move_ref,
        tags=sorted(tag.value for tag in move_semantics.tags),
    )
    return _world([move], {move_ref: move_semantics}, visible_hostile=False)


def _combat_world(*, include_backup: bool = False) -> SubjectiveWorldState:
    """Build adjacent visible combat with one or two equivalent legal attacks."""
    attack_semantics = ActionSemantics(
        semantic_id="attack.weapon.melee",
        tags=frozenset({ActionTag.ATTACK_WEAPON, ActionTag.DAMAGE_SINGLE_TARGET}),
    )
    attack_ref = action_semantics_ref(attack_semantics)
    target = ActionTarget(
        index=0,
        target_uuid="hero",
        target_name="Hero",
        position=(1, 0),
        distance=5,
    )
    primary = ActionAffordance(
        row_id="primary-attack",
        bucket="entity_actions",
        template_name="Attack_MELEE_MAIN",
        semantic_key="attack.melee",
        display_name="Melee Attack",
        action_category="attack",
        target_type="entity",
        can_afford=True,
        cost=ActionCostProfile(action_cost=1),
        targets=[target],
        target_options=[target],
        semantic_id=attack_semantics.semantic_id,
        semantics_ref=attack_ref,
        tags=sorted(tag.value for tag in attack_semantics.tags),
    )
    rows = [primary]
    if include_backup:
        rows.append(primary.model_copy(update={"row_id": "secondary-attack"}))
    return _world(rows, {attack_ref: attack_semantics}, visible_hostile=True)


def _world(
    rows: list[ActionAffordance],
    catalog: dict[str, ActionSemantics],
    *,
    visible_hostile: bool,
) -> SubjectiveWorldState:
    """Build one aligned event-first world and decision epoch."""
    by_bucket: dict[str, list[ActionAffordance]] = {
        "entity_actions": [],
        "position_actions": [],
        "self_actions": [],
        "object_actions": [],
    }
    for row in rows:
        by_bucket[row.bucket].append(row)
    affordances = AffordanceSet(
        actor_uuid="actor",
        computed_at_observation_cursor=1,
        entity_actions=by_bucket["entity_actions"],
        position_actions=by_bucket["position_actions"],
        self_actions=by_bucket["self_actions"],
        object_actions=by_bucket["object_actions"],
        semantic_catalog=catalog,
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=1,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            bonus_actions=1,
            reactions=1,
            movement_remaining=30,
            meaningful_commands_remaining=True,
        ),
        affordances=affordances,
    )
    entities = {
        "actor": ObservationEntityFact(
            uuid="actor",
            name="Skeleton",
            knowledge_state=KnowledgeState.VISIBLE,
            controlled=True,
            position=(0, 0),
            hp=13,
            max_hp=13,
            faction="monsters",
        ),
    }
    if visible_hostile:
        entities["hero"] = ObservationEntityFact(
            uuid="hero",
            name="Hero",
            knowledge_state=KnowledgeState.VISIBLE,
            controlled=False,
            position=(1, 0),
            hp=24,
            max_hp=24,
            faction="heroes",
        )
    return SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id="session-ai",
            player_type="ai",
            name="AI Monsters",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Skeleton",
            is_my_turn=True,
        ),
        known_entities=entities,
        known_objects={
            "door": ObservationObjectFact(
                uuid="door",
                name="Door",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(3, 0),
                state={"is_open": False},
            ),
        },
        known_tiles={
            f"{x},0": ObservationTileFact(
                key=f"{x},0",
                position=(x, 0),
                knowledge_state=KnowledgeState.VISIBLE,
                walkable=True,
                walking_cost=5,
                is_hazardous=False,
            )
            for x in range(5)
        },
        current_epoch=epoch,
        epoch_cursor=1,
    )
