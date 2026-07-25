"""Closed transport contracts for registered external AI policy providers.

The protocol transports only canonical subjective policy input and bounded
authoritative feedback.  It never transports an engine object, player
credential, objective event stream, or gameplay command endpoint.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.policy import PolicyDescriptor


EXTERNAL_AI_PROTOCOL_VERSION: Final[int] = 1
EXTERNAL_AI_PROTOCOL_HASH: Final[str]
EXTERNAL_AI_ROUTES: Final[tuple[str, ...]] = (
    "/handshake",
    "/assignments/open",
    "/assignments/decide",
    "/assignments/close",
)


class ExternalAIProtocolModel(BaseModel):
    """Immutable closed base for every external-policy wire value."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ExternalAIProtocolIdentity(ExternalAIProtocolModel):
    """Exact decoder identity required on every state-changing request."""

    version: int = Field(
        default=EXTERNAL_AI_PROTOCOL_VERSION,
        ge=1,
    )
    contract_hash: str = Field(
        default_factory=lambda: EXTERNAL_AI_PROTOCOL_HASH,
        min_length=64,
        max_length=64,
    )

    @model_validator(mode="after")
    def validate_identity(self) -> "ExternalAIProtocolIdentity":
        if self.version != EXTERNAL_AI_PROTOCOL_VERSION:
            raise ValueError(
                "external AI protocol version does not match this provider"
            )
        if self.contract_hash != EXTERNAL_AI_PROTOCOL_HASH:
            raise ValueError(
                "external AI protocol contract hash does not match this provider"
            )
        return self


class ExternalAIPolicyProviderHandshake(ExternalAIProtocolModel):
    """Cold provider identity, supported policies, and current capacity."""

    protocol: ExternalAIProtocolIdentity = Field(
        default_factory=ExternalAIProtocolIdentity
    )
    provider_id: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )
    policies: tuple[PolicyDescriptor, ...] = Field(min_length=1)
    capacity: int = Field(ge=1)
    active_assignments: int = Field(ge=0)

    @computed_field
    @property
    def available_capacity(self) -> int:
        """Return slots currently available for new assignments."""
        return self.capacity - self.active_assignments

    @model_validator(mode="after")
    def validate_catalog_and_capacity(
        self,
    ) -> "ExternalAIPolicyProviderHandshake":
        policy_ids = tuple(policy.policy_id for policy in self.policies)
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("provider handshake contains duplicate policy ids")
        if self.active_assignments > self.capacity:
            raise ValueError("active assignments exceed provider capacity")
        return self


class ExternalAIAssignmentOpenRequest(ExternalAIProtocolModel):
    """Server-authorized creation of one isolated policy/memory assignment."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(
        min_length=16,
        description=(
            "Opaque server-issued assignment capability; never a player token."
        ),
    )
    game_id: str = Field(min_length=1)
    controlled_entity_uuids: tuple[str, ...] = Field(min_length=1)
    policy_id: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def validate_controlled_entities(
        self,
    ) -> "ExternalAIAssignmentOpenRequest":
        if len(self.controlled_entity_uuids) != len(
            set(self.controlled_entity_uuids)
        ):
            raise ValueError("controlled_entity_uuids contains duplicate values")
        if any(not entity_uuid for entity_uuid in self.controlled_entity_uuids):
            raise ValueError("controlled entity UUIDs must not be empty")
        return self


class ExternalAIAssignmentLease(ExternalAIProtocolModel):
    """Provider acknowledgement for one active assignment generation."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(min_length=16)
    game_id: str = Field(min_length=1)
    controlled_entity_uuids: tuple[str, ...] = Field(min_length=1)
    policy: PolicyDescriptor
    state: Literal["active"] = "active"


class ExternalAIDecisionFeedback(ExternalAIProtocolModel):
    """Ordered authoritative result reduced before the next policy decision."""

    decision_id: int = Field(ge=1)
    actor_uuid: str = Field(min_length=1)
    epoch_id: str | None = None
    row_id: str | None = None
    outcome: NativeAIDecisionOutcome
    event_uuid: str | None = None
    outcome_code: str | None = None
    revalidation_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_native(self) -> NativeAIDecisionFeedback:
        """Convert the wire sequence number into core reducer feedback."""
        return NativeAIDecisionFeedback(
            decision_id=str(self.decision_id),
            actor_uuid=self.actor_uuid,
            epoch_id=self.epoch_id,
            row_id=self.row_id,
            outcome=self.outcome,
            event_uuid=self.event_uuid,
            outcome_code=self.outcome_code,
            revalidation_reason=self.revalidation_reason,
            error_type=self.error_type,
            error_message=self.error_message,
        )


class ExternalAIDecisionRequest(ExternalAIProtocolModel):
    """One monotonic policy invocation for an active assignment fence."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(min_length=16)
    decision_id: int = Field(ge=1)
    state: SubjectiveWorldState
    feedback: tuple[ExternalAIDecisionFeedback, ...] = ()

    @model_validator(mode="after")
    def validate_feedback_order(self) -> "ExternalAIDecisionRequest":
        feedback_ids = tuple(row.decision_id for row in self.feedback)
        if any(
            left >= right
            for left, right in zip(feedback_ids, feedback_ids[1:])
        ):
            raise ValueError("feedback decision ids must be strictly increasing")
        if feedback_ids and feedback_ids[-1] >= self.decision_id:
            raise ValueError(
                "feedback must refer to decisions before the requested decision"
            )
        return self


class ExternalAIDecisionResponse(ExternalAIProtocolModel):
    """Exact cached policy result with every assignment fence echoed."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(min_length=16)
    decision_id: int = Field(ge=1)
    policy: PolicyDescriptor
    intent: PolicyIntent = Field(discriminator="kind")


class ExternalAIAssignmentCloseRequest(ExternalAIProtocolModel):
    """Explicit close of one exact assignment generation."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(min_length=16)


class ExternalAIAssignmentCloseResponse(ExternalAIProtocolModel):
    """Idempotent close acknowledgement retaining the closed fence."""

    protocol: ExternalAIProtocolIdentity
    assignment_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    assignment_token: str = Field(min_length=16)
    closed: Literal[True] = True


_EXTERNAL_AI_SEMANTICS: Final[dict[str, object]] = {
    "transport_input": (
        "canonical SubjectiveWorldState plus ordered dependency-neutral "
        "feedback delta"
    ),
    "transport_output": "typed PolicyIntent only",
    "assignment_fence": (
        "server-issued assignment id, positive generation, and opaque "
        "assignment token"
    ),
    "decision_order": (
        "positive contiguous decision ids; exact retries return the cached "
        "response; conflicting retries and stale ids reject"
    ),
    "memory_ownership": (
        "one serialized policy and memory writer per active assignment"
    ),
    "forbidden": (
        "PlayerSession objects, player credentials, raw objective state, "
        "engine actions, and self-HTTP gameplay calls"
    ),
}


def external_ai_wire_schema() -> dict[str, object]:
    """Return the complete transitive schema authenticated by the hash."""
    return {
        "contract_version": EXTERNAL_AI_PROTOCOL_VERSION,
        "routes": EXTERNAL_AI_ROUTES,
        "semantics": _EXTERNAL_AI_SEMANTICS,
        "protocol_identity": ExternalAIProtocolIdentity.model_json_schema(
            mode="serialization"
        ),
        "handshake": ExternalAIPolicyProviderHandshake.model_json_schema(
            mode="serialization"
        ),
        "assignment_open_request": (
            ExternalAIAssignmentOpenRequest.model_json_schema(
                mode="serialization"
            )
        ),
        "assignment_lease": ExternalAIAssignmentLease.model_json_schema(
            mode="serialization"
        ),
        "decision_request": ExternalAIDecisionRequest.model_json_schema(
            mode="serialization"
        ),
        "decision_response": ExternalAIDecisionResponse.model_json_schema(
            mode="serialization"
        ),
        "assignment_close_request": (
            ExternalAIAssignmentCloseRequest.model_json_schema(
                mode="serialization"
            )
        ),
        "assignment_close_response": (
            ExternalAIAssignmentCloseResponse.model_json_schema(
                mode="serialization"
            )
        ),
    }


EXTERNAL_AI_PROTOCOL_HASH = hashlib.sha256(
    json.dumps(
        external_ai_wire_schema(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


__all__ = [
    "EXTERNAL_AI_PROTOCOL_HASH",
    "EXTERNAL_AI_PROTOCOL_VERSION",
    "EXTERNAL_AI_ROUTES",
    "ExternalAIAssignmentCloseRequest",
    "ExternalAIAssignmentCloseResponse",
    "ExternalAIAssignmentLease",
    "ExternalAIAssignmentOpenRequest",
    "ExternalAIDecisionFeedback",
    "ExternalAIDecisionRequest",
    "ExternalAIDecisionResponse",
    "ExternalAIPolicyProviderHandshake",
    "ExternalAIProtocolIdentity",
    "external_ai_wire_schema",
]
