"""Finite player API envelopes over the engine's existing detached values."""

from functools import cache
from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from dnd.core.base_actions import AvailableActionsResult, AvailableSelectionPreview
from dnd.core.content.descriptors import ContentDescriptor
from dnd.player.audience import PlayerAudience
from dnd.player.commands import ActionSelection, EquipItem, UnequipItem, ToggleHandler
from dnd.player.facts import PlayerInitialization, PlayerUpdate

MAX_SAFE_INTEGER = 9007199254740991
Counter = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
PositiveCounter = Annotated[int, Field(strict=True, ge=1, le=MAX_SAFE_INTEGER)]
Token = Annotated[str, Field(min_length=1, max_length=128)]
Lifecycle = Literal['starting', 'waiting_for_human', 'advancing', 'delivery_blocked', 'terminal', 'failed', 'closing', 'closed']
FailureReason = Literal['recording_capacity', 'catch_up', 'reader_backpressure', 'worker_failure',
    'capture_failure', 'contract_failure', 'recording_failure', 'host_close']
RejectionReason = Literal['stale_state', 'stale_discovery', 'not_your_turn', 'actor_unavailable',
    'invalid_selection', 'unavailable_action', 'invalid_item', 'invalid_slot', 'invalid_handler']


class Wire(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)


class Identity(Wire):
    game_id: Token
    game_epoch: UUID
    audience_id: UUID


class PlayerCursor(Identity):
    sequence: Counter


class ProtocolIdentity(Wire):
    protocol_version: Literal[1] = 1
    player_schema_version: Literal[5] = 5
    schema_digest: Annotated[str, Field(pattern='^[0-9a-f]{64}$')]


class BoundaryState(Wire):
    lifecycle: Lifecycle
    input_actor_uuid: UUID | None
    state_revision: Token | None
    reason: FailureReason | None = None
    incident_id: UUID | None = None


class StatusSnapshot(Identity):
    boundary: BoundaryState
    published_cursor: PlayerCursor | None
    final_cursor: PlayerCursor | None
    attachment_epoch: UUID | None
    catch_up_cursor: PlayerCursor | None
    acknowledged_cursor: PlayerCursor | None
    next_command_number: PositiveCounter
    pending_command_numbers: tuple[PositiveCounter, ...]


class HealthResponse(Wire):
    kind: Literal['health'] = 'health'
    status: Literal['ok'] = 'ok'


class BootstrapResponse(Wire):
    kind: Literal['bootstrap'] = 'bootstrap'
    protocol: ProtocolIdentity
    status: StatusSnapshot
    audience: PlayerAudience | None
    encounter_name: str
    content_revision: Token | None


class StatusResponse(Wire):
    kind: Literal['status'] = 'status'
    status: StatusSnapshot


class AttachmentRequest(Wire):
    acquisition_id: UUID
    expected_attachment_epoch: UUID | None


class AttachmentResponse(Wire):
    kind: Literal['attachment'] = 'attachment'
    acquisition_id: UUID
    attachment_epoch: UUID
    status: StatusSnapshot


class InitializationResponse(Wire):
    kind: Literal['initialization'] = 'initialization'
    protocol: ProtocolIdentity
    cursor: PlayerCursor
    content_revision: Token
    content_additions: tuple[ContentDescriptor, ...]
    initialization: PlayerInitialization

    @model_validator(mode='after')
    def initial_sequence(self) -> 'InitializationResponse':
        if self.cursor.sequence != 0:
            raise ValueError('Initialization sequence must be zero')
        return self


class AckRequest(Wire):
    cursor: PlayerCursor


class AckResponse(Wire):
    kind: Literal['ack'] = 'ack'
    cursor: PlayerCursor
    catch_up_cursor: PlayerCursor


class ChoicesRequest(Wire):
    actor_uuid: UUID
    state_revision: Token
    force_attack: Annotated[bool, Field(strict=True)]
    correlation_id: UUID


class ChoicesResponse(Identity):
    kind: Literal['choices'] = 'choices'
    state_revision: Token
    correlation_id: UUID
    force_attack: Annotated[bool, Field(strict=True)]
    choices: AvailableActionsResult


class PreviewRequest(Wire):
    actor_uuid: UUID
    state_revision: Token
    discovery_generation: PositiveCounter
    correlation_id: UUID
    selection: ActionSelection


class PreviewResponse(Identity):
    kind: Literal['preview'] = 'preview'
    state_revision: Token
    request: PreviewRequest
    preview: AvailableSelectionPreview


class ExecuteSelectionIntent(Wire):
    kind: Literal['execute_selection'] = 'execute_selection'
    discovery_generation: PositiveCounter
    selection: ActionSelection


class EndTurnIntent(Wire):
    kind: Literal['end_turn'] = 'end_turn'


class EquipIntent(Wire):
    kind: Literal['equip'] = 'equip'
    item: EquipItem


class UnequipIntent(Wire):
    kind: Literal['unequip'] = 'unequip'
    item: UnequipItem


class ToggleHandlerIntent(Wire):
    kind: Literal['toggle_handler'] = 'toggle_handler'
    discovery_generation: PositiveCounter
    handler: ToggleHandler


PlayerIntent = Annotated[ExecuteSelectionIntent | EndTurnIntent | EquipIntent | UnequipIntent | ToggleHandlerIntent,
    Field(discriminator='kind')]


class CommandRequest(Wire):
    command_number: PositiveCounter
    actor_uuid: UUID
    state_revision: Token
    intent: PlayerIntent


class Receipt(Identity):
    command_number: PositiveCounter


class PendingReceipt(Receipt):
    kind: Literal['pending'] = 'pending'


class CommittedReceipt(Receipt):
    kind: Literal['committed'] = 'committed'
    cursor: PlayerCursor


class RejectedReceipt(Receipt):
    kind: Literal['rejected'] = 'rejected'
    reason: RejectionReason


class IndeterminateReceipt(Receipt):
    kind: Literal['indeterminate'] = 'indeterminate'
    incident_id: UUID


class ExpiredReceipt(Receipt):
    kind: Literal['expired'] = 'expired'


class UnknownReceipt(Receipt):
    kind: Literal['unknown'] = 'unknown'


CommandReceipt = Annotated[PendingReceipt | CommittedReceipt | RejectedReceipt | IndeterminateReceipt | ExpiredReceipt | UnknownReceipt,
    Field(discriminator='kind')]


class ReceiptResponse(Wire):
    kind: Literal['receipt'] = 'receipt'
    receipt: CommandReceipt


class ContentResponse(Wire):
    kind: Literal['content'] = 'content'
    revision: Token
    descriptors: tuple[ContentDescriptor, ...]


class StreamReady(Wire):
    kind: Literal['ready'] = 'ready'
    protocol: ProtocolIdentity
    after: PlayerCursor
    head: PlayerCursor
    status: StatusSnapshot


class StreamStatus(Wire):
    kind: Literal['stream_status'] = 'stream_status'
    status: StatusSnapshot


class PlayerOperation(PlayerUpdate):
    kind: Literal['operation'] = 'operation'
    protocol: ProtocolIdentity
    cursor: PlayerCursor
    state_revision: Token
    command_number: PositiveCounter | None
    boundary: BoundaryState

    @model_validator(mode='after')
    def operation_sequence(self) -> 'PlayerOperation':
        if self.cursor.sequence < 1:
            raise ValueError('Operation sequence must be positive')
        return self


class ErrorBase(Wire):
    kind: Literal['error'] = 'error'
    incident_id: UUID | None = None


class ErrorInvalidRequest(ErrorBase):
    code: Literal['invalid_request'] = 'invalid_request'
    http_status: Literal[400] = 400
    retryable: Literal[False] = False


class ErrorUnauthenticated(ErrorBase):
    code: Literal['unauthenticated'] = 'unauthenticated'
    http_status: Literal[401] = 401
    retryable: Literal[False] = False


class ErrorForbidden(ErrorBase):
    code: Literal['forbidden'] = 'forbidden'
    http_status: Literal[403] = 403
    retryable: Literal[False] = False


class ErrorGameNotFound(ErrorBase):
    code: Literal['game_not_found'] = 'game_not_found'
    http_status: Literal[404] = 404
    retryable: Literal[False] = False


class ErrorEpochMismatch(ErrorBase):
    code: Literal['epoch_mismatch'] = 'epoch_mismatch'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorAudienceMismatch(ErrorBase):
    code: Literal['audience_mismatch'] = 'audience_mismatch'
    http_status: Literal[403] = 403
    retryable: Literal[False] = False


class ErrorAttachmentReplaced(ErrorBase):
    code: Literal['attachment_replaced'] = 'attachment_replaced'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorAttachmentConflict(ErrorBase):
    code: Literal['attachment_conflict'] = 'attachment_conflict'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorCommandConflict(ErrorBase):
    code: Literal['command_conflict'] = 'command_conflict'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorCommandNumber(ErrorBase):
    code: Literal['command_number'] = 'command_number'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorStaleState(ErrorBase):
    code: Literal['stale_state'] = 'stale_state'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorStaleDiscovery(ErrorBase):
    code: Literal['stale_discovery'] = 'stale_discovery'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorNotYourTurn(ErrorBase):
    code: Literal['not_your_turn'] = 'not_your_turn'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorCatchUpRequired(ErrorBase):
    code: Literal['catch_up_required'] = 'catch_up_required'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False
    required_cursor: PlayerCursor


class ErrorQuerySuperseded(ErrorBase):
    code: Literal['query_superseded'] = 'query_superseded'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorInvalidCursor(ErrorBase):
    code: Literal['invalid_cursor'] = 'invalid_cursor'
    http_status: Literal[400] = 400
    retryable: Literal[False] = False


class ErrorResumeUnavailable(ErrorBase):
    code: Literal['resume_unavailable'] = 'resume_unavailable'
    http_status: Literal[410] = 410
    retryable: Literal[False] = False
    earliest_cursor: PlayerCursor | None


class ErrorProtocolMismatch(ErrorBase):
    code: Literal['protocol_mismatch'] = 'protocol_mismatch'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorRequestTooLarge(ErrorBase):
    code: Literal['request_too_large'] = 'request_too_large'
    http_status: Literal[413] = 413
    retryable: Literal[False] = False


class ErrorResponseTooLarge(ErrorBase):
    code: Literal['response_too_large'] = 'response_too_large'
    http_status: Literal[500] = 500
    retryable: Literal[False] = False


class ErrorBusy(ErrorBase):
    code: Literal['busy'] = 'busy'
    http_status: Literal[429] = 429
    retryable: Literal[True] = True
    retry_after_ms: Counter = 100


class ErrorStarting(ErrorBase):
    code: Literal['starting'] = 'starting'
    http_status: Literal[503] = 503
    retryable: Literal[True] = True
    retry_after_ms: Counter = 100


class ErrorRecordingCapacity(ErrorBase):
    code: Literal['recording_capacity'] = 'recording_capacity'
    http_status: Literal[503] = 503
    retryable: Literal[True] = True
    retry_after_ms: Counter = 100


class ErrorGameTerminal(ErrorBase):
    code: Literal['game_terminal'] = 'game_terminal'
    http_status: Literal[409] = 409
    retryable: Literal[False] = False


class ErrorGameFailed(ErrorBase):
    code: Literal['game_failed'] = 'game_failed'
    http_status: Literal[503] = 503
    retryable: Literal[False] = False


class ErrorGameClosed(ErrorBase):
    code: Literal['game_closed'] = 'game_closed'
    http_status: Literal[410] = 410
    retryable: Literal[False] = False


class ErrorInternalFailure(ErrorBase):
    code: Literal['internal_failure'] = 'internal_failure'
    http_status: Literal[500] = 500
    retryable: Literal[False] = False


ApiError = Annotated[
    ErrorInvalidRequest |
    ErrorUnauthenticated |
    ErrorForbidden |
    ErrorGameNotFound |
    ErrorEpochMismatch |
    ErrorAudienceMismatch |
    ErrorAttachmentReplaced |
    ErrorAttachmentConflict |
    ErrorCommandConflict |
    ErrorCommandNumber |
    ErrorStaleState |
    ErrorStaleDiscovery |
    ErrorNotYourTurn |
    ErrorCatchUpRequired |
    ErrorQuerySuperseded |
    ErrorInvalidCursor |
    ErrorResumeUnavailable |
    ErrorProtocolMismatch |
    ErrorRequestTooLarge |
    ErrorResponseTooLarge |
    ErrorBusy |
    ErrorStarting |
    ErrorRecordingCapacity |
    ErrorGameTerminal |
    ErrorGameFailed |
    ErrorGameClosed |
    ErrorInternalFailure,
    Field(discriminator='code'),
]

PUBLIC_ROOTS = (HealthResponse, BootstrapResponse, StatusResponse, AttachmentRequest, AttachmentResponse,
    InitializationResponse, AckRequest, AckResponse, ChoicesRequest, ChoicesResponse, PreviewRequest, PreviewResponse,
    CommandRequest, ReceiptResponse, ContentResponse, StreamReady, StreamStatus, PlayerOperation)
ERROR_CODEC: TypeAdapter[ApiError] = TypeAdapter(ApiError)


@cache
def public_schema() -> dict:
    owners = (*((owner.__name__, owner) for owner in PUBLIC_ROOTS), ('ApiError', ApiError))
    schemas, combined = TypeAdapter.json_schemas(
        (name, 'serialization', TypeAdapter(owner)) for name, owner in owners)
    definitions = combined['$defs']
    roots = []
    for name, _ in owners:
        schema = schemas[name, 'serialization']
        if schema != {'$ref': '#/$defs/' + name}:
            if name in definitions and definitions[name] != schema:
                raise ValueError(f'Conflicting protocol definition: {name}')
            definitions[name] = schema
        roots.append({'$ref': '#/$defs/' + name})
    def close_fields(value):
        if isinstance(value, dict):
            if value.get('type') == 'object' and 'properties' in value:
                value['additionalProperties'] = False
            if value.get('type') == 'integer':
                value['minimum'] = max(value.get('minimum', -MAX_SAFE_INTEGER), -MAX_SAFE_INTEGER)
                value['maximum'] = min(value.get('maximum', MAX_SAFE_INTEGER), MAX_SAFE_INTEGER)
            for member in value.values():
                close_fields(member)
        elif isinstance(value, list):
            for member in value:
                close_fields(member)
    close_fields(definitions)
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema',
        '$id': 'https://neurodragon.invalid/contracts/player-api-v1.schema.json',
        '$defs': definitions, 'oneOf': roots}


@cache
def protocol_identity() -> ProtocolIdentity:
    encoded = json.dumps(public_schema(), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return ProtocolIdentity(schema_digest=sha256(encoded).hexdigest())
