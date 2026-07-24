"""Contracts for the dependency-neutral agent protocol layer."""

from __future__ import annotations

import ast
from pathlib import Path

from server.agent_protocol.observation import ObservationFrame, ObservationFrameType
from server.agent_protocol.control import (
    ActionAffordance,
    ActionEconomyState,
    ActionSourceDefinition,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_control_protocol_embeds_in_subjective_event_envelopes() -> None:
    """Observation envelopes carry neutral epochs and command results."""
    affordance = ActionAffordance(
        row_id="entity|Attack|uuid=target",
        source=ActionSourceDefinition(
            source_action_id="entity|Attack",
            bucket="entity_actions",
            template_name="Attack",
            display_name="Attack",
            action_category="attack",
            target_type="entity",
            can_afford=True,
        ),
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=3,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(actor_uuid="actor", actions=1),
        affordances=AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=3,
            entity_actions=[affordance],
        ),
    )
    result = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-1",
        session_id="session-1",
        actor_uuid="actor",
        requested_epoch_id="epoch-1",
        current_epoch_id="epoch-1",
        row_id=affordance.row_id,
    )

    epoch_frame = ObservationFrame(
        observation_cursor=3,
        frame_type=ObservationFrameType.DECISION_EPOCH,
        decision_epoch=epoch,
    )
    result_frame = ObservationFrame(
        observation_cursor=4,
        frame_type=ObservationFrameType.COMMAND_RESULT,
        command_result=result,
    )

    assert epoch_frame.decision_epoch is not None
    assert epoch_frame.decision_epoch.affordances.all_rows == (affordance,)
    assert result_frame.command_result == result


def test_protocol_modules_do_not_import_engine_runtime_or_policy_layers() -> None:
    """Neutral protocol contracts remain below engine and controller adapters."""
    protocol_root = REPOSITORY_ROOT / "server" / "agent_protocol"
    forbidden_prefixes = (
        "ai",
        "server.agent_runtime",
        "server.event_server",
        "server.session",
    )

    for path in protocol_root.glob("*.py"):
        imported_modules = _imported_modules(path)
        forbidden = sorted(
            module
            for module in imported_modules
            if module in forbidden_prefixes or module.startswith(forbidden_prefixes)
        )
        assert forbidden == [], f"{path.relative_to(REPOSITORY_ROOT)} imports {forbidden}"


def test_observation_models_do_not_import_subjective_runtime_models() -> None:
    """Observation wire models depend downward on protocol contracts only."""
    path = REPOSITORY_ROOT / "server" / "agent_protocol" / "observation.py"

    assert not any(
        module == "ai" or module.startswith("ai.")
        for module in _imported_modules(path)
    )


def _imported_modules(path: Path) -> set[str]:
    """Return absolute modules imported by one Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules
