import { EVENT_CONTRACT_HASH, EVENT_CONTRACT_VERSION, TIMELINE_CONTRACT_HASH, TIMELINE_CONTRACT_VERSION, } from "./generated/contracts.generated.js";
import { SseDecoder } from "./sse.js";
import { ContractValidationError, decodeModel } from "./validation.js";
export class ObjectiveDiagnosticsSseDecoder {
    syntaxDecoder = new SseDecoder();
    feed(chunk) {
        return this.syntaxDecoder.feed(chunk).map(decodeObjectiveDiagnosticsEnvelope);
    }
    finish() {
        return this.syntaxDecoder.finish().map(decodeObjectiveDiagnosticsEnvelope);
    }
}
export class ObjectiveDiagnosticsFollower {
    sourceStreamId;
    generationId;
    eventCursor;
    combatLogCursor;
    eventCombatLogCursor = -1;
    logEventCursor = -1;
    constructor(start = {}) {
        this.eventCursor = requireCursor(start.eventCursor ?? 0, "$objective.event_cursor");
        this.combatLogCursor = requireCursor(start.combatLogCursor ?? 0, "$objective.combat_log_cursor");
        this.sourceStreamId = start.expectedSourceStreamId === undefined
            ? null
            : requireNonEmpty(start.expectedSourceStreamId, "$objective.source_stream_id");
        this.generationId = start.expectedGenerationId === undefined
            ? null
            : requireNonEmpty(start.expectedGenerationId, "$objective.generation_id");
    }
    cursor() {
        return {
            sourceStreamId: this.sourceStreamId,
            generationId: this.generationId,
            eventCursor: this.eventCursor,
            combatLogCursor: this.combatLogCursor,
        };
    }
    ingest(envelope) {
        switch (envelope.event) {
            case "sync":
                this.ingestSync(envelope.data);
                break;
            case "game_event":
                assertObjectiveGameEventFrame(envelope.data);
                this.assertIdentity(envelope.data.source_stream_id, envelope.data.generation_id, "$objective.game_event");
                if (envelope.data.event_cursor !== this.eventCursor + 1) {
                    throw new ContractValidationError("$objective.game_event.event_cursor", `expected contiguous cursor ${this.eventCursor + 1}`);
                }
                if (envelope.data.event_index + 1 !== envelope.data.event_cursor) {
                    throw new ContractValidationError("$objective.game_event.event_index", "event_index must be exactly event_cursor - 1");
                }
                if (envelope.data.combat_log_cursor < this.eventCombatLogCursor) {
                    throw new ContractValidationError("$objective.game_event.combat_log_cursor", "event combat-log barriers must be nondecreasing");
                }
                this.commitIdentity(envelope.data.source_stream_id, envelope.data.generation_id);
                this.eventCursor = envelope.data.event_cursor;
                this.eventCombatLogCursor = envelope.data.combat_log_cursor;
                break;
            case "combat_log":
                assertObjectiveCombatLogFrame(envelope.data);
                this.assertIdentity(envelope.data.source_stream_id, envelope.data.generation_id, "$objective.combat_log");
                if (envelope.data.combat_log_cursor !== this.combatLogCursor + 1) {
                    throw new ContractValidationError("$objective.combat_log.combat_log_cursor", `expected contiguous cursor ${this.combatLogCursor + 1}`);
                }
                if (envelope.data.event_cursor < this.logEventCursor) {
                    throw new ContractValidationError("$objective.combat_log.event_cursor", "combat-log event barriers must be nondecreasing");
                }
                this.commitIdentity(envelope.data.source_stream_id, envelope.data.generation_id);
                this.combatLogCursor = envelope.data.combat_log_cursor;
                this.logEventCursor = envelope.data.event_cursor;
                break;
        }
        return this.cursor();
    }
    ingestSync(sync) {
        assertObjectiveProtocolIdentity(sync.protocol, "$objective.sync.protocol");
        this.assertIdentity(sync.source_stream_id, sync.generation_id, "$objective.sync");
        requireCursor(sync.event_cursor, "$objective.sync.event_cursor");
        requireCursor(sync.combat_log_cursor, "$objective.sync.combat_log_cursor");
        if (sync.event_cursor < this.eventCursor) {
            throw new ContractValidationError("$objective.sync.event_cursor", "source event cursor is behind the requested cursor");
        }
        if (sync.combat_log_cursor < this.combatLogCursor) {
            throw new ContractValidationError("$objective.sync.combat_log_cursor", "source combat-log cursor is behind the requested cursor");
        }
        this.commitIdentity(sync.source_stream_id, sync.generation_id);
    }
    assertIdentity(source, generation, path) {
        requireNonEmpty(source, `${path}.source_stream_id`);
        requireNonEmpty(generation, `${path}.generation_id`);
        if (this.sourceStreamId !== null && source !== this.sourceStreamId) {
            throw new ContractValidationError(`${path}.source_stream_id`, "objective source stream changed");
        }
        if (this.generationId !== null && generation !== this.generationId) {
            throw new ContractValidationError(`${path}.generation_id`, "objective event generation changed");
        }
    }
    commitIdentity(source, generation) {
        this.sourceStreamId = source;
        this.generationId = generation;
    }
}
export function decodeObjectiveDiagnosticsEnvelope(message) {
    switch (message.event) {
        case "sync": {
            const sync = decodeModel("ObjectiveDiagnosticsSync", message.data);
            assertObjectiveProtocolIdentity(sync.protocol, "$objective.sync.protocol");
            requireNonEmpty(sync.source_stream_id, "$objective.sync.source_stream_id");
            requireNonEmpty(sync.generation_id, "$objective.sync.generation_id");
            requireCursor(sync.event_cursor, "$objective.sync.event_cursor");
            requireCursor(sync.combat_log_cursor, "$objective.sync.combat_log_cursor");
            return { event: "sync", id: message.id, data: sync };
        }
        case "game_event": {
            const frame = decodeModel("GameEventFrame", message.data);
            assertObjectiveGameEventFrame(frame);
            return {
                event: "game_event",
                id: message.id,
                data: frame,
            };
        }
        case "combat_log": {
            const frame = decodeModel("ObjectiveCombatLogFrame", message.data);
            assertObjectiveCombatLogFrame(frame);
            return { event: "combat_log", id: message.id, data: frame };
        }
        default:
            throw new ContractValidationError("$objective_sse.event", `unsupported objective diagnostics event ${message.event}`);
    }
}
export function assertObjectiveGameEventFrame(frame, path = "$objective.game_event") {
    requireNonEmpty(frame.source_stream_id, `${path}.source_stream_id`);
    requireNonEmpty(frame.generation_id, `${path}.generation_id`);
    requirePositiveCursor(frame.event_cursor, `${path}.event_cursor`);
    requireCursor(frame.event_index, `${path}.event_index`);
    requireCursor(frame.combat_log_cursor, `${path}.combat_log_cursor`);
    if (frame.event_index + 1 !== frame.event_cursor) {
        throw new ContractValidationError(`${path}.event_index`, "event_index must be exactly event_cursor - 1");
    }
}
export function assertObjectiveCombatLogFrame(frame, path = "$objective.combat_log") {
    requireNonEmpty(frame.source_stream_id, `${path}.source_stream_id`);
    requireNonEmpty(frame.generation_id, `${path}.generation_id`);
    if (frame.projection !== "objective") {
        throw new ContractValidationError(`${path}.projection`, "expected objective projection");
    }
    if (frame.perspective_epoch_id !== "objective") {
        throw new ContractValidationError(`${path}.perspective_epoch_id`, "expected the canonical objective epoch");
    }
    if (frame.entry === null) {
        throw new ContractValidationError(`${path}.entry`, "objective log entry cannot be null");
    }
    requirePositiveCursor(frame.combat_log_cursor, `${path}.combat_log_cursor`);
    requireCursor(frame.event_cursor, `${path}.event_cursor`);
}
export function assertObjectiveProtocolIdentity(protocol, path = "$objective.protocol") {
    if (protocol.timeline_contract_version !== TIMELINE_CONTRACT_VERSION) {
        throw new ContractValidationError(`${path}.timeline_contract_version`, "unsupported timeline contract version");
    }
    if (protocol.timeline_contract_hash !== TIMELINE_CONTRACT_HASH) {
        throw new ContractValidationError(`${path}.timeline_contract_hash`, "timeline contract hash mismatch");
    }
    if (protocol.event_contract_version !== EVENT_CONTRACT_VERSION) {
        throw new ContractValidationError(`${path}.event_contract_version`, "unsupported event contract version");
    }
    if (protocol.event_contract_hash !== EVENT_CONTRACT_HASH) {
        throw new ContractValidationError(`${path}.event_contract_hash`, "event contract hash mismatch");
    }
}
function requireCursor(value, path) {
    if (!Number.isSafeInteger(value) || value < 0) {
        throw new ContractValidationError(path, "expected a non-negative safe integer cursor");
    }
    return value;
}
function requirePositiveCursor(value, path) {
    if (!Number.isSafeInteger(value) || value < 1) {
        throw new ContractValidationError(path, "expected a positive safe integer cursor");
    }
    return value;
}
function requireNonEmpty(value, path) {
    if (value.trim().length === 0) {
        throw new ContractValidationError(path, "expected a non-empty string");
    }
    return value;
}
//# sourceMappingURL=objectiveSse.js.map