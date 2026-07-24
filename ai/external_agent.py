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
from typing import Optional

import httpx

from server.runtime_performance import latency_sensitive_gc
from ai.subjective.processors import AgentFactsProcessor
from ai.subjective.policy_agent import SubjectivePolicyAgent
from ai.subjective.runtime import (
    SubjectiveEncounterEndedError,
    SubjectiveRuntime,
    SubjectiveRuntimeClosedError,
)
from ai.subjective.runtime_gc import (
    RuntimeGcPolicy,
    SUSPEND_AUTOMATIC_GC,
)

logger = logging.getLogger("external_agent")
TAKEOVER_HEARTBEAT_SECONDS = 30.0


class ExternalAgent(SubjectivePolicyAgent):
    """HTTP/SSE controller that executes the shared subjective policy."""

    runtime: SubjectiveRuntime

    def __init__(
        self,
        base_url: str,
        session_id: str,
        *,
        unix_socket_path: Optional[str] = None,
        runtime_token: Optional[str] = None,
        takeover_claim_id: Optional[str] = None,
        readiness_token: Optional[str] = None,
        gc_policy: RuntimeGcPolicy = SUSPEND_AUTOMATIC_GC,
        control_request_timeout: float = 10.0,
    ) -> None:
        """Create an external agent.

        Args:
            base_url: Server base URL.
            session_id: AI session UUID.
        """
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id
        runtime = SubjectiveRuntime(
            base_url=self.base_url,
            session_id=self.session_id,
            processors=[AgentFactsProcessor()],
            unix_socket_path=unix_socket_path,
            runtime_token=runtime_token,
            gc_policy=gc_policy,
            control_request_timeout=control_request_timeout,
        )
        super().__init__(
            runtime,
            policy_id="external.default",
            controller_mode="external_ai",
            trace_event_prefix="external_ai",
        )
        self.takeover_claim_id = takeover_claim_id
        self.readiness_token = readiness_token
        self._managed_service_ready = False
        self._takeover_heartbeat_stop = ThreadEvent()
        self._takeover_heartbeat_thread: Optional[Thread] = None
        if takeover_claim_id is not None:
            runtime.heartbeat_takeover_claim(takeover_claim_id)
            self._takeover_heartbeat_thread = Thread(
                target=self._takeover_heartbeat_loop,
                name=f"takeover-heartbeat-{session_id}",
                daemon=True,
            )
            self._takeover_heartbeat_thread.start()

    def close(self, timeout_seconds: float = 4.0) -> None:
        """Close policy and transport resources within one deadline."""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        deadline = time.monotonic() + timeout_seconds
        self.request_stop()
        failures: list[BaseException] = []
        if self._takeover_heartbeat_thread is not None:
            self._takeover_heartbeat_thread.join(
                timeout=max(0.0, deadline - time.monotonic())
            )
            if self._takeover_heartbeat_thread.is_alive():
                failures.append(TimeoutError(
                    "takeover heartbeat worker did not stop for session "
                    f"{self.session_id}"
                ))
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("policy telemetry cleanup exhausted its deadline")
            super().close(remaining)
        except BaseException as exc:
            failures.append(exc)
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("runtime cleanup exhausted its deadline")
            self.runtime.close(remaining)
        except BaseException as exc:
            failures.append(exc)
        if failures:
            details = "; ".join(
                f"{type(exc).__name__}: {exc}"
                for exc in failures
            )
            raise RuntimeError(
                f"External agent cleanup failed: {details}"
            ) from failures[0]

    def request_stop(self) -> None:
        """Signal cooperative termination without joining runtime threads."""
        self._takeover_heartbeat_stop.set()
        self.runtime.request_close()

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

    def run_once(self) -> None:
        """Run one command-selection pass, used by tests and manual debugging."""
        self._ensure_runtime_ready()
        super().run_once()

    def run_forever(self) -> None:
        """Run the agent until the process is stopped."""
        try:
            self._ensure_runtime_ready()
            super().run_forever()
        except SubjectiveEncounterEndedError as exc:
            logger.info("subjective encounter ended, exiting: %s", exc)
        except SubjectiveRuntimeClosedError:
            logger.info("subjective runtime closed, exiting")
        except httpx.HTTPError as exc:
            logger.error("agent HTTP error, exiting: %s", exc)
            raise

    def _ensure_runtime_ready(self) -> None:
        """Bootstrap once and complete the managed-service handshake."""
        if self.runtime.store.world is None:
            self.runtime.bootstrap()
        if self.readiness_token is None or self._managed_service_ready:
            return
        self.runtime.wait_until_stream_synced()
        self.runtime.acknowledge_managed_service_ready(self.readiness_token)
        self._managed_service_ready = True


def main() -> int:
    """Run the external agent command-line entrypoint."""
    parser = argparse.ArgumentParser(description="Run the external AI agent.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--spawned-at", type=float, default=None)
    parser.add_argument("--unix-socket", default=None)
    parser.add_argument("--runtime-token", default=os.environ.get("DND_RUNTIME_TOKEN"))
    parser.add_argument("--takeover-claim-id", default=os.environ.get("DND_TAKEOVER_CLAIM_ID"))
    parser.add_argument("--readiness-token")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    base_url = args.base_url
    session_id = args.session_id
    runtime_token = args.runtime_token
    takeover_claim_id = args.takeover_claim_id

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
            readiness_token=args.readiness_token,
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
