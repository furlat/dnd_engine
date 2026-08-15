import type { GameEventFrame, ObjectiveCombatLogFrame, ObjectiveDiagnosticsSync, TimelineProtocolIdentity } from "./generated/contracts.generated.js";
import { type SseMessage } from "./sse.js";
export type ObjectiveDiagnosticsSseEnvelope = {
    readonly event: "sync";
    readonly id: string | null;
    readonly data: ObjectiveDiagnosticsSync;
} | {
    readonly event: "game_event";
    readonly id: string | null;
    readonly data: GameEventFrame;
} | {
    readonly event: "combat_log";
    readonly id: string | null;
    readonly data: ObjectiveCombatLogFrame;
};
export interface ObjectiveDiagnosticsCursor {
    readonly sourceStreamId: string | null;
    readonly generationId: string | null;
    readonly eventCursor: number;
    readonly combatLogCursor: number;
}
export interface ObjectiveDiagnosticsFollowerStart {
    readonly eventCursor?: number;
    readonly combatLogCursor?: number;
    readonly expectedSourceStreamId?: string;
    readonly expectedGenerationId?: string;
}
export declare class ObjectiveDiagnosticsSseDecoder {
    private readonly syntaxDecoder;
    feed(chunk: string): ObjectiveDiagnosticsSseEnvelope[];
    finish(): ObjectiveDiagnosticsSseEnvelope[];
}
export declare class ObjectiveDiagnosticsFollower {
    private sourceStreamId;
    private generationId;
    private eventCursor;
    private combatLogCursor;
    private eventCombatLogCursor;
    private logEventCursor;
    constructor(start?: ObjectiveDiagnosticsFollowerStart);
    cursor(): ObjectiveDiagnosticsCursor;
    ingest(envelope: ObjectiveDiagnosticsSseEnvelope): ObjectiveDiagnosticsCursor;
    private ingestSync;
    private assertIdentity;
    private commitIdentity;
}
export declare function decodeObjectiveDiagnosticsEnvelope(message: SseMessage): ObjectiveDiagnosticsSseEnvelope;
export declare function assertObjectiveGameEventFrame(frame: GameEventFrame, path?: string): void;
export declare function assertObjectiveCombatLogFrame(frame: ObjectiveCombatLogFrame, path?: string): void;
export declare function assertObjectiveProtocolIdentity(protocol: TimelineProtocolIdentity, path?: string): void;
//# sourceMappingURL=objectiveSse.d.ts.map