import type { GameEventFramesResponse, JsonValue, ObjectiveCombatLogFramesResponse, ObjectiveDiagnosticsBootstrap, SubjectiveRenderParityDiagnosticsResponse } from "./generated/contracts.generated.js";
import { type ObjectiveDiagnosticsSseEnvelope } from "./objectiveSse.js";
export declare const OBJECTIVE_DIAGNOSTICS_ROUTES: Readonly<{
    bootstrap: "/diagnostics/objective/bootstrap";
    events: "/diagnostics/objective/events";
    combatLog: "/diagnostics/objective/combat-log";
    subscribe: "/diagnostics/objective/subscribe";
    subjectiveParity: "/diagnostics/subjective-parity";
}>;
export declare class ObjectiveDiagnosticsHttpError extends Error {
    readonly status: number;
    readonly payload: JsonValue;
    constructor(status: number, payload: JsonValue);
}
export interface ObjectiveDiagnosticsClientOptions {
    readonly fetchImplementation?: typeof fetch;
    readonly headers?: Readonly<Record<string, string>>;
}
export interface ObjectiveDiagnosticsWindowQuery {
    readonly fromCursor?: number;
    readonly throughCursor?: number;
    readonly limit?: number;
    readonly expectedSourceStreamId?: string;
    readonly expectedGenerationId?: string;
}
export interface ObjectiveDiagnosticsStreamPosition {
    readonly eventCursor: number;
    readonly combatLogCursor: number;
    readonly expectedSourceStreamId?: string;
    readonly expectedGenerationId?: string;
}
/** A diagnostics-only transport. It never owns or mutates a player replica. */
export declare class ObjectiveDiagnosticsClient {
    readonly baseUrl: string;
    private readonly fetchImplementation;
    private readonly defaultHeaders;
    constructor(baseUrl: string, options?: ObjectiveDiagnosticsClientOptions);
    bootstrap(signal?: AbortSignal): Promise<ObjectiveDiagnosticsBootstrap>;
    events(query?: ObjectiveDiagnosticsWindowQuery, signal?: AbortSignal): Promise<GameEventFramesResponse>;
    combatLog(query?: ObjectiveDiagnosticsWindowQuery, signal?: AbortSignal): Promise<ObjectiveCombatLogFramesResponse>;
    subjectiveParity(sessionId: string, signal?: AbortSignal): Promise<SubjectiveRenderParityDiagnosticsResponse>;
    subscribe(position: ObjectiveDiagnosticsStreamPosition, signal?: AbortSignal): AsyncGenerator<ObjectiveDiagnosticsSseEnvelope>;
    private getJson;
    private httpError;
    private headers;
}
export declare function assertObjectiveDiagnosticsBootstrap(bootstrap: ObjectiveDiagnosticsBootstrap): void;
export declare function assertSubjectiveRenderParityDiagnostics(response: SubjectiveRenderParityDiagnosticsResponse): void;
export declare function assertObjectiveGameEventWindow(response: GameEventFramesResponse): void;
export declare function assertObjectiveCombatLogWindow(response: ObjectiveCombatLogFramesResponse): void;
//# sourceMappingURL=objectiveDiagnostics.d.ts.map