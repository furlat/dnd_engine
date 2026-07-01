"""Executable external melee AI agent.

This process is intentionally simple: it connects with an AI session id, reads
the strict subjective observation stream, asks the engine for legal actions,
and applies the v1 behavior-tree policy.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from typing import Any, Iterator, Optional

import httpx

from ai.external import AgentCommand, AgentCommandType, choose_external_melee_command, reduce_external_agent_state
from ai.observation.materializer import apply_observation_frame, materialize_snapshot
from ai.observation.models import ObservationMaterializedState

logger = logging.getLogger("external_melee_agent")
MAX_COMMANDS_PER_TURN = 20
OFFENSIVE_REASONS = {"attack_visible_enemy", "cast_visible_enemy_spell"}


class ExternalMeleeAgent:
    """HTTP/SSE client that plays one AI session with the v1 melee policy."""

    def __init__(self, base_url: str, session_id: str) -> None:
        """Create an external melee agent.

        Args:
            base_url: Server base URL.
            session_id: AI session UUID.
        """
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
        self.client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def fetch_materialized(self) -> ObservationMaterializedState:
        """Fetch and materialize a fresh subjective snapshot."""
        started = time.perf_counter()
        response = self.client.get(f"/ai/sessions/{self.session_id}/observation/snapshot")
        response.raise_for_status()
        materialized = materialize_snapshot(response.json())
        self.trace(
            "observation_snapshot",
            elapsed_ms=_elapsed_ms(started),
            observation_cursor=materialized.observation_cursor,
            active_entity_uuid=materialized.session.active_entity_uuid,
            is_my_turn=materialized.session.is_my_turn,
            controlled_count=len(materialized.session.controlled_entity_uuids),
            known_entities=len(materialized.known_entities),
            known_objects=len(materialized.known_objects),
        )
        return materialized

    def fetch_available_actions(
        self,
        entity_uuid: str,
        basis_cursor: int,
    ) -> dict[str, Any]:
        """Fetch session-authorized available actions for one controlled actor."""
        started = time.perf_counter()
        response = self.client.get(
            f"/ai/sessions/{self.session_id}/entities/{entity_uuid}/available-actions",
            params={"basis_cursor": basis_cursor},
        )
        response.raise_for_status()
        payload = response.json()
        self.trace(
            "available_actions",
            elapsed_ms=_elapsed_ms(started),
            entity_uuid=entity_uuid,
            basis_cursor=basis_cursor,
            computed_at_observation_cursor=payload.get("computed_at_observation_cursor"),
            entity_actions=len(payload.get("entity_actions", [])),
            position_actions=len(payload.get("position_actions", [])),
            self_actions=len(payload.get("self_actions", [])),
            object_actions=len(payload.get("object_actions", [])),
            total_targets=_count_action_targets(payload),
        )
        return payload

    def execute_command(self, command: AgentCommand) -> Optional[dict[str, Any]]:
        """Execute one behavior-tree command through the server API."""
        if command.entity_uuid is None:
            return None
        started = time.perf_counter()
        if command.command_type == AgentCommandType.END_TURN:
            response = self.client.post(
                "/action/end-turn",
                json={
                    "session_id": self.session_id,
                    "entity_uuid": command.entity_uuid,
                },
            )
            if response.status_code >= 400:
                logger.warning("end-turn failed: %s %s", response.status_code, response.text)
                return None
            payload = response.json()
            self.trace(
                "command_result",
                elapsed_ms=_elapsed_ms(started),
                command_type=command.command_type.value,
                entity_uuid=command.entity_uuid,
                reason=command.reason,
                status_code=response.status_code,
                next_status=payload.get("status"),
                next_entity_uuid=payload.get("entity_uuid"),
            )
            return payload
        if command.command_type == AgentCommandType.EXECUTE and command.template_name:
            response = self.client.post(
                "/action/execute",
                json={
                    "session_id": self.session_id,
                    "entity_uuid": command.entity_uuid,
                    "template_name": command.template_name,
                    "target_index": command.target_index,
                    "prefer_safe": True,
                    "extra_target_uuids": None,
                    "return_available_actions": False,
                },
            )
            if response.status_code >= 400:
                logger.warning(
                    "execute failed: %s %s command=%s",
                    response.status_code,
                    response.text,
                    command.model_dump(mode="json"),
                )
                return None
            payload = response.json()
            self.trace(
                "command_result",
                elapsed_ms=_elapsed_ms(started),
                command_type=command.command_type.value,
                entity_uuid=command.entity_uuid,
                template_name=command.template_name,
                target_index=command.target_index,
                reason=command.reason,
                status_code=response.status_code,
                success=payload.get("success"),
                turn_continues=payload.get("turn_continues"),
                encounter_ended=payload.get("encounter_ended"),
                returned_available_actions=payload.get("available_actions") is not None,
            )
            return payload
        return None

    def play_current_turn(
        self,
        max_commands: int = MAX_COMMANDS_PER_TURN,
        materialized: Optional[ObservationMaterializedState] = None,
    ) -> ObservationMaterializedState:
        """Play commands while the session owns the active turn."""
        if materialized is None:
            materialized = self.fetch_materialized()
        failures = 0
        for command_index in range(max_commands):
            actor_uuid = _active_actor_uuid(materialized)
            if actor_uuid is None:
                return materialized
            try:
                available = self.fetch_available_actions(actor_uuid, materialized.observation_cursor)
            except httpx.HTTPStatusError as exc:
                logger.warning("available-actions failed: %s", exc.response.text)
                return materialized

            reduced = reduce_external_agent_state(materialized, available)
            command = choose_external_melee_command(reduced)
            self.trace(
                "policy_tick",
                command_index=command_index,
                observation_cursor=materialized.observation_cursor,
                actor_uuid=actor_uuid,
                visible_enemies=[
                    {"uuid": enemy.uuid, "name": enemy.name, "distance_feet": enemy.distance_feet}
                    for enemy in reduced.visible_enemies
                ],
                known_closed_doors=len(reduced.known_closed_doors),
                entity_actions=len(reduced.entity_actions),
                position_actions=len(reduced.position_actions),
                self_actions=len(reduced.self_actions),
                object_actions=len(reduced.object_actions),
                selected_command=command.model_dump(mode="json"),
            )
            if command.command_type == AgentCommandType.WAIT:
                return materialized

            result = self.execute_command(command)
            if result is None:
                failures += 1
                materialized = self.fetch_materialized()
                if failures >= 2:
                    end_command = AgentCommand(
                        command_type=AgentCommandType.END_TURN,
                        entity_uuid=_active_actor_uuid(materialized),
                        reason="failed_command_recovery",
                    )
                    self.execute_command(end_command)
                    return self.fetch_materialized()
                continue

            failures = 0
            if command.command_type == AgentCommandType.END_TURN:
                return self.fetch_materialized()
            if command.reason in OFFENSIVE_REASONS or result.get("encounter_ended"):
                if not result.get("encounter_ended"):
                    self.execute_command(AgentCommand(
                        command_type=AgentCommandType.END_TURN,
                        entity_uuid=command.entity_uuid,
                        reason="end_turn_after_offense",
                    ))
                return self.fetch_materialized()

            materialized = self.fetch_materialized()
        return materialized

    def trace(self, event: str, **fields: Any) -> None:
        """Emit one structured AI trace line."""
        payload = {
            "event": event,
            "session_id": self.session_id,
            **fields,
        }
        logger.info("ai_trace %s", json.dumps(payload, sort_keys=True, default=str))

    def run_once(self) -> None:
        """Run one command-selection pass, used by tests and manual debugging."""
        self.play_current_turn(max_commands=1)

    def run_forever(self) -> None:
        """Run the agent until the process is stopped."""
        materialized = self.fetch_materialized()
        while True:
            if _active_actor_uuid(materialized) is not None:
                materialized = self.play_current_turn(materialized=materialized)
                continue

            try:
                for event_name, payload in self.iter_observation_events(materialized.observation_cursor):
                    if event_name == "observation_frame":
                        materialized = apply_observation_frame(materialized, payload)
                    elif event_name == "sync":
                        materialized = self.fetch_materialized()
                    elif event_name in {"evicted", "error"}:
                        logger.warning("observation stream %s: %s", event_name, payload)
                        break
                    else:
                        continue

                    if _active_actor_uuid(materialized) is not None:
                        materialized = self.play_current_turn(materialized=materialized)
                        break
                else:
                    materialized = self.fetch_materialized()
            except httpx.HTTPError as exc:
                logger.error("agent HTTP error, exiting: %s", exc)
                return

    def iter_observation_events(self, since: int) -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield parsed SSE events from the AI observation stream."""
        with self.client.stream(
            "GET",
            f"/ai/sessions/{self.session_id}/observation/subscribe",
            params={"since": since},
        ) as response:
            response.raise_for_status()
            event_name = "message"
            data_lines: list[str] = []
            for line in response.iter_lines():
                if line == "":
                    if data_lines:
                        yield event_name, json.loads("\n".join(data_lines))
                    event_name = "message"
                    data_lines = []
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())


def _active_actor_uuid(materialized: ObservationMaterializedState) -> Optional[str]:
    """Return the active controlled actor UUID for a materialized state."""
    active_uuid = materialized.session.active_entity_uuid
    if materialized.session.is_my_turn and active_uuid in materialized.session.controlled_entity_uuids:
        return active_uuid
    return None


def _elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds from a perf-counter start."""
    return round((time.perf_counter() - started) * 1000, 2)


def _count_action_targets(payload: dict[str, Any]) -> int:
    """Count valid targets across serialized available-action buckets."""
    total = 0
    for bucket_name in ("entity_actions", "position_actions", "self_actions", "object_actions"):
        for action in payload.get(bucket_name, []):
            if isinstance(action, dict):
                targets = action.get("valid_targets", [])
                if isinstance(targets, list):
                    total += len(targets)
    return total


def main() -> int:
    """Run the external melee agent command-line entrypoint."""
    parser = argparse.ArgumentParser(description="Run the external melee AI agent.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--spawned-at", type=float, default=None)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger.info(
        "ai_trace %s",
        json.dumps({
            "event": "process_start",
            "pid": os.getpid(),
            "session_id": args.session_id,
            "base_url": args.base_url,
            "startup_delay_ms": round((time.time() - args.spawned_at) * 1000, 2)
            if args.spawned_at is not None else None,
        }, sort_keys=True),
    )
    agent = ExternalMeleeAgent(args.base_url, args.session_id)
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
