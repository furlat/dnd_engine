import { type PlayerReplicationProtocolIdentity, type PlayerReplicationWatermarks, type SubjectiveCombatLogDelivery, type SubjectivePerspective, type SubjectiveReplicationFrame, type SubjectiveStreamDelivery } from "./generated/contracts.generated.js";
import { type SseMessage } from "./sse.js";
export type SubjectiveSseEnvelope = {
    readonly event: "sync";
    readonly id: string;
    readonly data: Extract<SubjectiveStreamDelivery, {
        readonly kind: "sync";
    }>;
} | {
    readonly event: "frame";
    readonly id: string;
    readonly data: Extract<SubjectiveStreamDelivery, {
        readonly kind: "frame";
    }>;
} | {
    readonly event: "combat_log";
    readonly id: string;
    readonly data: Extract<SubjectiveStreamDelivery, {
        readonly kind: "combat_log";
    }>;
};
export interface SubjectiveStreamPosition {
    readonly sourceStreamId: string;
    readonly generationId: string;
    readonly perspectiveEpochId: string;
    readonly sourceEventCursor: number;
    readonly observationCursor: number;
    readonly presentationCursor: number;
    readonly combatLogCursor: number;
}
export declare class SubjectiveSseDecoder {
    private readonly syntax;
    feed(chunk: string): SubjectiveSseEnvelope[];
    finish(): SubjectiveSseEnvelope[];
}
/** Stateful ordering check used by reconnecting stream consumers. */
export declare class SubjectiveStreamFollower {
    private positionValue;
    private synchronized;
    constructor(position: SubjectiveStreamPosition);
    position(): SubjectiveStreamPosition;
    ingest(envelope: SubjectiveSseEnvelope): SubjectiveStreamPosition;
    private assertIdentity;
}
export declare function decodeSubjectiveEnvelope(message: SseMessage): SubjectiveSseEnvelope;
export declare function assertProtocol(protocol: PlayerReplicationProtocolIdentity): void;
export declare function assertPerspective(perspective: SubjectivePerspective): void;
export declare function assertSubjectiveFrame(frame: SubjectiveReplicationFrame): void;
export declare function assertSubjectiveCombatLogDelivery(delivery: SubjectiveCombatLogDelivery): void;
export declare function assertWatermarks(watermarks: PlayerReplicationWatermarks, path: string): void;
export declare function assertDominates(later: PlayerReplicationWatermarks, earlier: PlayerReplicationWatermarks, path: string): void;
export declare function deliveryWatermarks(delivery: SubjectiveStreamDelivery): PlayerReplicationWatermarks;
//# sourceMappingURL=subjectiveSse.d.ts.map