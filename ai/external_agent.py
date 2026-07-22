"""Executable external AI agent.

The process connects with an AI session id, reads the strict subjective runtime
stream, consumes decision epochs, and executes the shared policy host.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from threading import Event as ThreadEvent, Thread
import time
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx

from ai.knowledge import AgentFacts, derive_agent_facts
from ai.observation.models import SubjectiveWorldState
from ai.policy import (
    AgentCommand,
    AgentCommandType,
    command_from_policy_decision,
    ExecuteIntent,
    policy_memory_trace,
    PolicyExecutionConstraints,
    PolicyContext,
    PolicyMemoryStore,
    reconcile_policy_memory,
)
from ai.policy.generations.current_commitments import create_generation_policy_host
from ai.policy.generations.registry import (
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from ai.protocol.control import CommandResult, CommandResultStatus, DecisionEpoch
from ai.policy.telemetry import QueuedPolicyTelemetrySink
from ai.remote_connection import redeem_remote_agent_grant
from ai.runtime_performance import latency_sensitive_gc
from ai.subjective.processors import AgentFactsProcessor
from ai.subjective.runtime import SubjectiveEncounterEndedError, SubjectiveRuntime
from dnd.spells.effect_ids import COUNTERSPELL_INTERRUPTION_OUTCOME_CODE

logger = logging.getLogger("external_agent")
MAX_COMMANDS_PER_TURN = 20
TAKEOVER_HEARTBEAT_SECONDS = 30.0


class ExternalAgent:
    """HTTP/SSE controller that executes the shared subjective policy."""

    def __init__(
        self,
        base_url: str,
        session_id: str,
        *,
        unix_socket_path: Optional[str] = None,
        runtime_token: Optional[str] = None,
        takeover_claim_id: Optional[str] = None,
    ) -> None:
        """Create an external agent.

        Args:
            base_url: Server base URL.
            session_id: AI session UUID.
        """
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        self.runtime = SubjectiveRuntime(
            base_url=self.base_url,
            session_id=self.session_id,
            processors=[AgentFactsProcessor()],
            unix_socket_path=unix_socket_path,
            runtime_token=runtime_token,
        )
        self.takeover_claim_id = takeover_claim_id
        self._takeover_heartbeat_stop = ThreadEvent()
        self._takeover_heartbeat_thread: Optional[Thread] = None
        if takeover_claim_id is not None:
            self.runtime.heartbeat_takeover_claim(takeover_claim_id)
            self._takeover_heartbeat_thread = Thread(
                target=self._takeover_heartbeat_loop,
                name=f"takeover-heartbeat-{session_id}",
                daemon=True,
            )
            self._takeover_heartbeat_thread.start()
        self.policy_memories = PolicyMemoryStore()
        self.policy_host = create_generation_policy_host(
            get_policy_implementation(CANDIDATE_GENERATION_ID),
            policy_id="external.default",
            controller_mode="external_ai",
            memory_store=self.policy_memories,
        )
        self.policy_telemetry = QueuedPolicyTelemetrySink(self.runtime)

    def close(self) -> None:
        """Close the subjective runtime transport."""
        self._takeover_heartbeat_stop.set()
        if self._takeover_heartbeat_thread is not None:
            self._takeover_heartbeat_thread.join(timeout=2.0)
        self.policy_telemetry.close()
        self.runtime.close()

    def _takeover_heartbeat_loop(self) -> None:
        """Refresh a remote-controller lease without delaying policy ticks."""
        assert self.takeover_claim_id is not None
        while not self._takeover_heartbeat_stop.wait(TAKEOVER_HEARTBEAT_SECONDS):
            try:
                self.runtime.heartbeat_takeover_claim(self.takeover_claim_id)
            except httpx.HTTPError:
                logger.exception(
                    "remote takeover heartbeat failed for claim %s",
                    self.takeover_claim_id,
                )
                return

    def execute_command(
        self,
        command: AgentCommand,
        *,
        command_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Execute one behavior-tree command through the subjective command API."""
        if command.entity_uuid is None:
            return None
        started = time.perf_counter()
        if command.command_type == AgentCommandType.END_TURN:
            result = self.runtime.end_turn(command_id=command_id)
            payload = result.model_dump(mode="json")
            logical_tags = _logical_tags_payload(command)
            outcome_tags = _outcome_logical_tags(payload, logical_tags)
            self.trace(
                "command_result",
                elapsed_ms=_elapsed_ms(started),
                command_type=command.command_type.value,
                entity_uuid=command.entity_uuid,
                reason=command.reason,
                logical_tags=logical_tags,
                outcome_logical_tags=outcome_tags,
                status=payload.get("status"),
                command_message=payload.get("message"),
                current_epoch_id=payload.get("current_epoch_id"),
                result_payload=payload.get("payload", {}),
                runtime_timing=getattr(self.runtime, "last_command_timing", None),
            )
            if result.status != CommandResultStatus.ACCEPTED:
                logger.warning("end-turn failed: %s", payload)
            return payload
        if command.command_type == AgentCommandType.EXECUTE and command.row_id:
            result = self.runtime.execute(
                command.row_id,
                command_id=command_id,
                prefer_safe=command.prefer_safe,
                extra_target_uuids=command.extra_target_uuids,
            )
            payload = result.model_dump(mode="json")
            logical_tags = _logical_tags_payload(command)
            outcome_tags = _outcome_logical_tags(payload, logical_tags)
            self.trace(
                "command_result",
                elapsed_ms=_elapsed_ms(started),
                command_type=command.command_type.value,
                entity_uuid=command.entity_uuid,
                row_id=command.row_id,
                template_name=command.template_name,
                target_index=command.target_index,
                extra_target_uuids=command.extra_target_uuids,
                reason=command.reason,
                logical_tags=logical_tags,
                outcome_logical_tags=outcome_tags,
                status=payload.get("status"),
                command_message=payload.get("message"),
                result_payload=payload.get("payload", {}),
                runtime_timing=getattr(self.runtime, "last_command_timing", None),
            )
            if result.status != CommandResultStatus.ACCEPTED:
                logger.warning("execute failed: %s command=%s", payload, command.model_dump(mode="json"))
            return payload
        if command.command_type == AgentCommandType.EXECUTE:
            logger.warning("execute command has no row_id: %s", command.model_dump(mode="json"))
        return None

    def play_current_turn(
        self,
        max_commands: int = MAX_COMMANDS_PER_TURN,
        materialized: Optional[SubjectiveWorldState] = None,
    ) -> SubjectiveWorldState:
        """Play commands while the session owns the active turn."""
        if self.runtime.store.world is None:
            self.runtime.bootstrap()
        if materialized is None:
            materialized = self.runtime.store.world
        if materialized is None:
            raise RuntimeError("Subjective runtime bootstrap produced no world state")
        failures = 0
        blocked_row_ids: set[str] = set()
        blocked_semantic_keys: set[str] = set()
        blocked_action_categories: set[str] = set()
        for command_index in range(max_commands):
            tick_started = time.perf_counter()
            epoch_wait_started = time.perf_counter()
            epoch = self.runtime.wait_for_epoch()
            epoch_wait_ms = _elapsed_ms(epoch_wait_started)
            materialized = self.runtime.store.world
            if materialized is None:
                raise RuntimeError("Subjective runtime lost its world state")
            actor_uuid = epoch.actor_uuid
            if actor_uuid is None:
                return materialized
            facts = self.runtime.store.agent_state.facts
            if (
                facts is None
                or facts.observation_cursor != materialized.observation_cursor
                or facts.epoch_id != epoch.epoch_id
            ):
                facts = derive_agent_facts(materialized).facts
                self.runtime.store.agent_state.facts = facts
            execution_constraints = PolicyExecutionConstraints(
                blocked_row_ids=frozenset(blocked_row_ids),
                blocked_semantic_keys=frozenset(blocked_semantic_keys),
                blocked_action_categories=frozenset(blocked_action_categories),
            )
            policy_context = PolicyContext.model_construct(
                world=materialized,
                facts=facts,
                execution_constraints=execution_constraints,
                deadline_monotonic=None,
            )
            policy_memory = self.policy_host.memory_for(self.session_id, actor_uuid)
            reconcile_policy_memory(policy_context, policy_memory)
            policy_started = time.perf_counter()
            host_decision = self.policy_host.decide(
                materialized,
                facts=facts,
                execution_constraints=execution_constraints,
                telemetry_sink=self.policy_telemetry,
            )
            host_binding = self.policy_host.binding_for(
                self.session_id,
                actor_uuid,
                epoch.epoch_id,
            )
            selected_intent = host_decision.selected.intent
            selected_row = (
                facts.affordances.by_id.get(selected_intent.row_id)
                if isinstance(selected_intent, ExecuteIntent)
                else None
            )
            command = command_from_policy_decision(
                policy_context,
                host_decision,
                host_binding.routine_plan,
            )
            if command is None:
                raise RuntimeError("PolicyHost selected a row absent from its canonical fact index")
            policy_ms = _elapsed_ms(policy_started)
            trace_context = _shared_trace_context(materialized, facts, actor_uuid, epoch)
            spacing_evidence = host_decision.selected.evidence.spacing
            capability_target_projection = (
                spacing_evidence.capability_target_projection.model_dump(mode="json")
                if spacing_evidence is not None
                and spacing_evidence.capability_target_projection is not None
                else None
            )
            self.trace(
                "policy_tick",
                elapsed_ms=_elapsed_ms(tick_started),
                epoch_wait_ms=epoch_wait_ms,
                affordance_projection_ms=0.0,
                state_reduction_ms=0.0,
                policy_selection_ms=policy_ms,
                command_index=command_index,
                observation_cursor=materialized.observation_cursor,
                epoch_id=epoch.epoch_id,
                actor_uuid=actor_uuid,
                **trace_context,
                affordance_timing={},
                reduction_timing={},
                policy_memory=policy_memory_trace(policy_memory),
                routine_revalidation=host_binding.revalidation.model_dump(mode="json"),
                policy_decision_id=host_binding.decision_id,
                capability_target_projection=capability_target_projection,
                logical_tags=_logical_tags_payload(command),
                selected_command=command.model_dump(mode="json"),
            )
            if command.command_type == AgentCommandType.WAIT:
                return materialized

            host_command_id = str(uuid4())
            self.policy_host.prepare_submission(
                session_id=self.session_id,
                actor_uuid=actor_uuid,
                epoch_id=epoch.epoch_id,
                command_id=host_command_id,
            )
            result = self.execute_command(command, command_id=host_command_id)
            materialized = self.runtime.store.world or materialized
            if result is not None:
                host_result = self.policy_host.record_result(CommandResult.model_validate(result))
                self.trace(
                    "policy_host_result",
                    actor_uuid=actor_uuid,
                    epoch_id=epoch.epoch_id,
                    observation_cursor=materialized.observation_cursor,
                    result=host_result.model_dump(mode="json"),
                )
            if result is None:
                failures += 1
                if command.row_id is not None:
                    blocked_row_ids.add(command.row_id)
                self.runtime.resync()
                materialized = self.runtime.store.world or materialized
                continue

            status = result.get("status")
            if status != CommandResultStatus.ACCEPTED.value:
                failures += 1
                if command.row_id is not None:
                    blocked_row_ids.add(command.row_id)
                if selected_row is not None and failures >= 2:
                    blocked_semantic_keys.add(selected_row.semantic_key)
                self.runtime.resync()
                materialized = self.runtime.store.world or materialized
                continue

            failures = 0
            if _control_command_was_resisted(command, result) and selected_row is not None:
                blocked_semantic_keys.add(selected_row.semantic_key)
            if command.command_type == AgentCommandType.END_TURN:
                return self.runtime.store.world or materialized
            if _command_result_encounter_ended(result):
                return self.runtime.store.world or materialized

            materialized = self.runtime.store.world or materialized
            current_epoch = self.runtime.store.world.current_epoch if self.runtime.store.world is not None else None
            if current_epoch is None:
                return materialized
        return materialized

    def trace(self, event: str, **fields: Any) -> None:
        """Emit one structured AI trace line."""
        payload = {
            "event": event,
            "session_id": self.session_id,
            **fields,
        }
        logger.info("ai_trace %s", json.dumps(payload, sort_keys=True, default=str))
        self.runtime.emit_event(
            f"external_ai.{event}",
            event.replace("_", " "),
            actor_uuid=fields.get("actor_uuid") or fields.get("entity_uuid"),
            epoch_id=fields.get("epoch_id"),
            observation_cursor=fields.get("observation_cursor"),
            payload=payload,
        )

    def run_once(self) -> None:
        """Run one command-selection pass, used by tests and manual debugging."""
        self.play_current_turn(max_commands=1)

    def run_forever(self) -> None:
        """Run the agent until the process is stopped."""
        self.runtime.bootstrap()
        while True:
            try:
                self.runtime.wait_for_epoch()
                self.play_current_turn()
            except SubjectiveEncounterEndedError as exc:
                logger.info("subjective encounter ended, exiting: %s", exc)
                return
            except httpx.HTTPError as exc:
                logger.error("agent HTTP error, exiting: %s", exc)
                return

def _active_actor_uuid(materialized: SubjectiveWorldState) -> Optional[str]:
    """Return the active controlled actor UUID for a materialized state."""
    active_uuid = materialized.session.active_entity_uuid
    if materialized.session.is_my_turn and active_uuid in materialized.session.controlled_entity_uuids:
        return active_uuid
    return None


def _shared_trace_context(
    materialized: SubjectiveWorldState,
    facts: AgentFacts,
    actor_uuid: str,
    epoch: DecisionEpoch,
) -> dict[str, Any]:
    """Build policy telemetry directly from the canonical subjective revision."""
    actor = materialized.known_entities.get(actor_uuid)
    actor_position = actor.position if actor is not None else None

    def entity_payload(entity_uuid: str, *, include_distance: bool) -> dict[str, Any]:
        entity = materialized.known_entities[entity_uuid]
        payload: dict[str, Any] = {
            "uuid": entity.uuid,
            "name": entity.name,
            "position": entity.position,
        }
        if include_distance:
            payload["distance_feet"] = _subjective_distance_feet(actor_position, entity.position)
        return payload

    return {
        "actor_name": actor.name if actor is not None else None,
        "actor_position": actor_position,
        "actor_conditions": list(actor.conditions) if actor is not None else [],
        "visible_enemies": [
            entity_payload(entity_uuid, include_distance=True)
            for entity_uuid in facts.contacts.visible_hostile_uuids
        ],
        "remembered_enemies": [
            entity_payload(entity_uuid, include_distance=False)
            for entity_uuid in facts.contacts.remembered_hostile_uuids
        ],
        "known_closed_doors": len(facts.objects.closed_door_uuids),
        "entity_actions": len(epoch.affordances.entity_actions),
        "position_actions": len(epoch.affordances.position_actions),
        "self_actions": len(epoch.affordances.self_actions),
        "object_actions": len(epoch.affordances.object_actions),
    }


def _subjective_distance_feet(
    origin: Optional[tuple[int, int]],
    target: Optional[tuple[int, int]],
) -> Optional[int]:
    """Return Manhattan distance only when both subjective positions are known."""
    if origin is None or target is None:
        return None
    return (abs(origin[0] - target[0]) + abs(origin[1] - target[1])) * 5


def _elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds from a perf-counter start."""
    return round((time.perf_counter() - started) * 1000, 2)


def _command_result_encounter_ended(result: dict[str, Any]) -> bool:
    """Return whether a typed command-result payload ended the encounter."""
    payload = result.get("payload", {})
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("encounter_ended"))


def _outcome_logical_tags(
    result: dict[str, Any],
    command_logical_tags: list[str],
) -> list[str]:
    """Return outcome tags inferred from a command-result payload."""
    if _is_counterspell_interruption(result):
        return ["spell_interruption"]
    if "control_effect" in command_logical_tags:
        if _control_effect_was_resisted(result):
            return ["control_resisted"]
        if result.get("status") == CommandResultStatus.ACCEPTED.value:
            return ["control_landed"]
    return []


def _control_command_was_resisted(command: AgentCommand, result: dict[str, Any]) -> bool:
    """Return whether a selected control row was accepted but resisted."""
    if result.get("status") != CommandResultStatus.ACCEPTED.value:
        return False
    return "control_effect" in _logical_tags_payload(command) and _control_effect_was_resisted(result)


def _is_counterspell_interruption(result: dict[str, Any]) -> bool:
    """Return whether a command result carries the Counterspell outcome identity."""
    return result.get("outcome_code") == COUNTERSPELL_INTERRUPTION_OUTCOME_CODE


def _control_effect_was_resisted(result: dict[str, Any]) -> bool:
    """Return whether a control command result reports a successful save or resist."""
    text = _result_message_text(result)
    return "target saved" in text or "resisted" in text or "resists" in text


def _result_message_text(result: dict[str, Any]) -> str:
    """Return lower-case message text from a command-result payload."""
    message_parts = [str(result.get("message") or "")]
    payload = result.get("payload")
    if isinstance(payload, dict):
        for key in ("engine_message", "message"):
            value = payload.get(key)
            if value:
                message_parts.append(str(value))
        action_result = payload.get("action_result")
        if isinstance(action_result, dict):
            value = action_result.get("message")
            if value:
                message_parts.append(str(value))
    return " ".join(message_parts).lower()


def _logical_tags_payload(command: AgentCommand) -> list[str]:
    """Return command logical tags as JSON-friendly strings."""
    return [
        tag.value if hasattr(tag, "value") else str(tag)
        for tag in command.logical_tags
    ]


def main() -> int:
    """Run the external agent command-line entrypoint."""
    parser = argparse.ArgumentParser(description="Run the external AI agent.")
    parser.add_argument("--base-url")
    parser.add_argument("--session-id")
    parser.add_argument("--gateway-url")
    parser.add_argument("--game-id", default=os.environ.get("DND_GAME_ID"))
    parser.add_argument("--grant-id", default=os.environ.get("DND_AGENT_GRANT_ID"))
    parser.add_argument(
        "--grant-capability",
        default=os.environ.get("DND_AGENT_GRANT_CAPABILITY"),
    )
    parser.add_argument(
        "--client-instance-id",
        default=f"external-agent-{os.getpid()}",
    )
    parser.add_argument("--spawned-at", type=float, default=None)
    parser.add_argument("--unix-socket", default=None)
    parser.add_argument("--runtime-token", default=os.environ.get("DND_RUNTIME_TOKEN"))
    parser.add_argument("--takeover-claim-id", default=os.environ.get("DND_TAKEOVER_CLAIM_ID"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    base_url = args.base_url
    session_id = args.session_id
    runtime_token = args.runtime_token
    takeover_claim_id = args.takeover_claim_id
    remote_values = (args.gateway_url, args.game_id, args.grant_id, args.grant_capability)
    if any(value is not None for value in remote_values):
        if not all(value is not None for value in remote_values):
            parser.error(
                "remote attachment requires --gateway-url, --game-id, --grant-id, "
                "and --grant-capability"
            )
        connection = redeem_remote_agent_grant(
            gateway_url=args.gateway_url,
            game_id=UUID(args.game_id),
            grant_id=UUID(args.grant_id),
            grant_capability=args.grant_capability,
            client_instance_id=args.client_instance_id,
        )
        base_url = connection.engine_base_url
        session_id = str(connection.runtime_session_id)
        runtime_token = connection.runtime_token
        takeover_claim_id = (
            str(connection.takeover_claim_uuids[0])
            if connection.takeover_claim_uuids
            else None
        )
    if base_url is None or session_id is None:
        parser.error(
            "provide direct --base-url/--session-id or a complete remote attachment grant"
        )

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger.info(
        "ai_trace %s",
        json.dumps({
            "event": "process_start",
            "pid": os.getpid(),
            "session_id": session_id,
            "base_url": base_url,
            "startup_delay_ms": round((time.time() - args.spawned_at) * 1000, 2)
            if args.spawned_at is not None else None,
        }, sort_keys=True),
    )
    with latency_sensitive_gc():
        agent = ExternalAgent(
            base_url,
            session_id,
            unix_socket_path=args.unix_socket,
            runtime_token=runtime_token,
            takeover_claim_id=takeover_claim_id,
        )
        try:
            if args.once:
                agent.run_once()
            else:
                agent.run_forever()
        finally:
            agent.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
