import { ObjectiveDiagnosticsSseDecoder, ObjectiveDiagnosticsFollower, assertObjectiveCombatLogFrame, assertObjectiveGameEventFrame, assertObjectiveProtocolIdentity, } from "./objectiveSse.js";
import { ContractValidationError, decodeModel, parseJson } from "./validation.js";
export const OBJECTIVE_DIAGNOSTICS_ROUTES = Object.freeze({
    bootstrap: "/diagnostics/objective/bootstrap",
    events: "/diagnostics/objective/events",
    combatLog: "/diagnostics/objective/combat-log",
    subscribe: "/diagnostics/objective/subscribe",
    subjectiveParity: "/diagnostics/subjective-parity",
});
export class ObjectiveDiagnosticsHttpError extends Error {
    status;
    payload;
    constructor(status, payload) {
        super(`Objective diagnostics request failed with HTTP ${status}`);
        this.name = "ObjectiveDiagnosticsHttpError";
        this.status = status;
        this.payload = payload;
    }
}
/** A diagnostics-only transport. It never owns or mutates a player replica. */
export class ObjectiveDiagnosticsClient {
    baseUrl;
    fetchImplementation;
    defaultHeaders;
    constructor(baseUrl, options = {}) {
        this.baseUrl = baseUrl.replace(/\/$/, "");
        this.fetchImplementation = (options.fetchImplementation ?? globalThis.fetch).bind(globalThis);
        this.defaultHeaders = Object.freeze({ ...(options.headers ?? {}) });
    }
    async bootstrap(signal) {
        const bootstrap = decodeModel("ObjectiveDiagnosticsBootstrap", await this.getJson(OBJECTIVE_DIAGNOSTICS_ROUTES.bootstrap, signal));
        assertObjectiveDiagnosticsBootstrap(bootstrap);
        return bootstrap;
    }
    async events(query = {}, signal) {
        const response = decodeModel("GameEventFramesResponse", await this.getJson(withWindowQuery(OBJECTIVE_DIAGNOSTICS_ROUTES.events, query), signal));
        assertObjectiveGameEventWindow(response);
        assertExpectedIdentity(response, query, "$objective.events");
        return response;
    }
    async combatLog(query = {}, signal) {
        const response = decodeModel("ObjectiveCombatLogFramesResponse", await this.getJson(withWindowQuery(OBJECTIVE_DIAGNOSTICS_ROUTES.combatLog, query), signal));
        assertObjectiveCombatLogWindow(response);
        assertExpectedIdentity(response, query, "$objective.combat_log");
        return response;
    }
    async subjectiveParity(sessionId, signal) {
        const parameters = new URLSearchParams({
            session_id: requireNonEmpty(sessionId, "$subjectiveParity.sessionId"),
        });
        const response = decodeModel("SubjectiveRenderParityDiagnosticsResponse", await this.getJson(`${OBJECTIVE_DIAGNOSTICS_ROUTES.subjectiveParity}?${parameters.toString()}`, signal));
        assertSubjectiveRenderParityDiagnostics(response);
        return response;
    }
    async *subscribe(position, signal) {
        const parameters = new URLSearchParams({
            since_event: String(requireCursor(position.eventCursor, "$subscribe.eventCursor")),
            since_log: String(requireCursor(position.combatLogCursor, "$subscribe.combatLogCursor")),
        });
        appendExpectedIdentity(parameters, position);
        const request = {
            headers: this.headers({ Accept: "text/event-stream" }),
            ...(signal === undefined ? {} : { signal }),
        };
        const response = await this.fetchImplementation(`${this.baseUrl}${OBJECTIVE_DIAGNOSTICS_ROUTES.subscribe}?${parameters.toString()}`, request);
        if (!response.ok) {
            throw await this.httpError(response);
        }
        if (response.body === null) {
            throw new Error("Objective diagnostics stream response has no body");
        }
        const reader = response.body.getReader();
        const textDecoder = new TextDecoder();
        const sseDecoder = new ObjectiveDiagnosticsSseDecoder();
        const follower = new ObjectiveDiagnosticsFollower({
            eventCursor: position.eventCursor,
            combatLogCursor: position.combatLogCursor,
            ...(position.expectedSourceStreamId === undefined
                ? {}
                : { expectedSourceStreamId: position.expectedSourceStreamId }),
            ...(position.expectedGenerationId === undefined
                ? {}
                : { expectedGenerationId: position.expectedGenerationId }),
        });
        let streamCompleted = false;
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    streamCompleted = true;
                    break;
                }
                for (const envelope of sseDecoder.feed(textDecoder.decode(value, { stream: true }))) {
                    follower.ingest(envelope);
                    yield envelope;
                }
            }
            const tail = textDecoder.decode();
            for (const envelope of sseDecoder.feed(tail)) {
                follower.ingest(envelope);
                yield envelope;
            }
            for (const envelope of sseDecoder.finish()) {
                follower.ingest(envelope);
                yield envelope;
            }
        }
        finally {
            if (!streamCompleted) {
                await reader.cancel().catch(() => undefined);
            }
            reader.releaseLock();
        }
    }
    async getJson(path, signal) {
        const request = signal === undefined
            ? { headers: this.headers() }
            : { headers: this.headers(), signal };
        const response = await this.fetchImplementation(`${this.baseUrl}${path}`, request);
        const payload = parseJson(await response.text());
        if (!response.ok) {
            throw new ObjectiveDiagnosticsHttpError(response.status, payload);
        }
        return payload;
    }
    async httpError(response) {
        const text = await response.text();
        const payload = text.length === 0 ? null : parseJson(text);
        return new ObjectiveDiagnosticsHttpError(response.status, payload);
    }
    headers(additional = {}) {
        return { ...this.defaultHeaders, ...additional };
    }
}
export function assertObjectiveDiagnosticsBootstrap(bootstrap) {
    assertObjectiveProtocolIdentity(bootstrap.protocol);
    requireNonEmpty(bootstrap.source_stream_id, "$objective.bootstrap.source_stream_id");
    requireNonEmpty(bootstrap.generation_id, "$objective.bootstrap.generation_id");
    requireCursor(bootstrap.event_cursor, "$objective.bootstrap.event_cursor");
    requireCursor(bootstrap.combat_log_cursor, "$objective.bootstrap.combat_log_cursor");
    const encounter = bootstrap.world.state.encounter;
    if (encounter === null) {
        throw new ContractValidationError("$objective.bootstrap.world.state.encounter", "objective diagnostics require an encounter");
    }
    if (encounter.uuid !== bootstrap.source_stream_id) {
        throw new ContractValidationError("$objective.bootstrap.world.state.encounter.uuid", "encounter UUID must equal the objective source stream");
    }
}
export function assertSubjectiveRenderParityDiagnostics(response) {
    if (response.projection !== "subjective_parity") {
        throw new ContractValidationError("$subjectiveParity.projection", "expected subjective_parity");
    }
    requireNonEmpty(response.source_stream_id, "$subjectiveParity.source_stream_id");
    requireNonEmpty(response.generation_id, "$subjectiveParity.generation_id");
    requireNonEmpty(response.perspective_epoch_id, "$subjectiveParity.perspective_epoch_id");
    requireCursor(response.source_event_cursor, "$subjectiveParity.source_event_cursor");
    requireCursor(response.observation_cursor, "$subjectiveParity.observation_cursor");
    requireCursor(response.presentation_cursor, "$subjectiveParity.presentation_cursor");
    requireCursor(response.combat_log_cursor, "$subjectiveParity.combat_log_cursor");
    requireDigest(response.expected_digest, "$subjectiveParity.expected_digest");
    requireDigest(response.actual_digest, "$subjectiveParity.actual_digest");
    const comparedPaths = requireCursor(response.compared_path_count, "$subjectiveParity.compared_path_count");
    if (comparedPaths < 1) {
        throw new ContractValidationError("$subjectiveParity.compared_path_count", "comparison must exercise at least one manifest path");
    }
    const structuralEdges = requireCursor(response.structural_edge_count, "$subjectiveParity.structural_edge_count");
    const doorEdges = requireCursor(response.door_edge_count, "$subjectiveParity.door_edge_count");
    requireCursor(response.visible_tile_count, "$subjectiveParity.visible_tile_count");
    if (doorEdges > structuralEdges) {
        throw new ContractValidationError("$subjectiveParity.door_edge_count", "door edge count cannot exceed structural edge count");
    }
    if (response.non_empty_structural_edges !== (structuralEdges > 0)) {
        throw new ContractValidationError("$subjectiveParity.non_empty_structural_edges", "flag must match structural edge count");
    }
    const expectedMatches = response.expected_digest === response.actual_digest
        && response.mismatches.length === 0;
    if (response.matches !== expectedMatches) {
        throw new ContractValidationError("$subjectiveParity.matches", "status must match digests and mismatch list");
    }
}
export function assertObjectiveGameEventWindow(response) {
    requireNonEmpty(response.source_stream_id, "$objective.events.source_stream_id");
    requireNonEmpty(response.generation_id, "$objective.events.generation_id");
    assertWindowBounds(response, "$objective.events");
    let combatLogBarrier = -1;
    response.frames.forEach((frame, offset) => {
        assertObjectiveGameEventFrame(frame, `$objective.events.frames[${offset}]`);
        assertWindowIdentity(response, frame, `$objective.events.frames[${offset}]`);
        const expectedCursor = response.from_cursor + offset + 1;
        if (frame.event_cursor !== expectedCursor) {
            throw new ContractValidationError(`$objective.events.frames[${offset}].event_cursor`, `expected contiguous cursor ${expectedCursor}`);
        }
        if (frame.combat_log_cursor < combatLogBarrier) {
            throw new ContractValidationError(`$objective.events.frames[${offset}].combat_log_cursor`, "combat-log barriers must be nondecreasing");
        }
        combatLogBarrier = frame.combat_log_cursor;
    });
}
export function assertObjectiveCombatLogWindow(response) {
    requireNonEmpty(response.source_stream_id, "$objective.combat_log.source_stream_id");
    requireNonEmpty(response.generation_id, "$objective.combat_log.generation_id");
    if (response.projection !== "objective") {
        throw new ContractValidationError("$objective.combat_log.projection", "expected objective");
    }
    if (response.perspective_epoch_id !== "objective") {
        throw new ContractValidationError("$objective.combat_log.perspective_epoch_id", "expected the canonical objective epoch");
    }
    assertWindowBounds(response, "$objective.combat_log");
    let eventBarrier = -1;
    response.frames.forEach((frame, offset) => {
        assertObjectiveCombatLogFrame(frame, `$objective.combat_log.frames[${offset}]`);
        assertWindowIdentity(response, frame, `$objective.combat_log.frames[${offset}]`);
        const expectedCursor = response.from_cursor + offset + 1;
        if (frame.combat_log_cursor !== expectedCursor) {
            throw new ContractValidationError(`$objective.combat_log.frames[${offset}].combat_log_cursor`, `expected contiguous cursor ${expectedCursor}`);
        }
        if (frame.event_cursor < eventBarrier) {
            throw new ContractValidationError(`$objective.combat_log.frames[${offset}].event_cursor`, "event barriers must be nondecreasing");
        }
        eventBarrier = frame.event_cursor;
    });
}
function assertWindowBounds(response, path) {
    const retained = requireCursor(response.retained_from_cursor, `${path}.retained_from_cursor`);
    const from = requireCursor(response.from_cursor, `${path}.from_cursor`);
    const through = requireCursor(response.through_cursor, `${path}.through_cursor`);
    const total = requireCursor(response.total, `${path}.total`);
    if (!(retained <= from && from <= through && through <= total)) {
        throw new ContractValidationError(path, "expected retained_from_cursor <= from_cursor <= through_cursor <= total");
    }
    if (response.frames.length !== through - from) {
        throw new ContractValidationError(`${path}.frames`, `expected exactly ${through - from} contiguous frames`);
    }
}
function assertWindowIdentity(response, frame, path) {
    if (frame.source_stream_id !== response.source_stream_id) {
        throw new ContractValidationError(`${path}.source_stream_id`, "source stream changed");
    }
    if (frame.generation_id !== response.generation_id) {
        throw new ContractValidationError(`${path}.generation_id`, "generation changed");
    }
}
function assertExpectedIdentity(response, expected, path) {
    if (expected.expectedSourceStreamId !== undefined
        && response.source_stream_id !== expected.expectedSourceStreamId) {
        throw new ContractValidationError(`${path}.source_stream_id`, "response does not match expected source stream");
    }
    if (expected.expectedGenerationId !== undefined
        && response.generation_id !== expected.expectedGenerationId) {
        throw new ContractValidationError(`${path}.generation_id`, "response does not match expected generation");
    }
}
function withWindowQuery(path, query) {
    const parameters = new URLSearchParams();
    appendCursor(parameters, "from_cursor", query.fromCursor, "$query.fromCursor");
    appendCursor(parameters, "through_cursor", query.throughCursor, "$query.throughCursor");
    appendCursor(parameters, "limit", query.limit, "$query.limit");
    appendExpectedIdentity(parameters, query);
    const encoded = parameters.toString();
    return encoded.length === 0 ? path : `${path}?${encoded}`;
}
function appendExpectedIdentity(parameters, identity) {
    if (identity.expectedSourceStreamId !== undefined) {
        parameters.set("expected_source_stream_id", requireNonEmpty(identity.expectedSourceStreamId, "$query.expectedSourceStreamId"));
    }
    if (identity.expectedGenerationId !== undefined) {
        parameters.set("expected_generation_id", requireNonEmpty(identity.expectedGenerationId, "$query.expectedGenerationId"));
    }
}
function appendCursor(parameters, name, value, path) {
    if (value !== undefined)
        parameters.set(name, String(requireCursor(value, path)));
}
function requireCursor(value, path) {
    if (!Number.isSafeInteger(value) || value < 0) {
        throw new ContractValidationError(path, "expected a non-negative safe integer cursor");
    }
    return value;
}
function requireNonEmpty(value, path) {
    if (value.trim().length === 0) {
        throw new ContractValidationError(path, "expected a non-empty string");
    }
    return value;
}
function requireDigest(value, path) {
    if (!/^[0-9a-f]{64}$/.test(value)) {
        throw new ContractValidationError(path, "expected a lowercase SHA-256 digest");
    }
    return value;
}
//# sourceMappingURL=objectiveDiagnostics.js.map