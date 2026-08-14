import type { JsonValue, SubjectiveBootstrapDeferred, SubjectiveCombatLogFramesResponse, SubjectiveFramesResponse, SubjectiveReplicationBootstrap } from "./generated/contracts.generated.js";
import { SubjectiveReplicationJournal, type SubjectiveJournalIngestResult, type SubjectiveReplicationJournalState, type SubjectiveResyncReason } from "./subjectiveJournal.js";
import { type SubjectiveSseEnvelope } from "./subjectiveSse.js";
export declare const SUBJECTIVE_REPLICATION_ROUTES: Readonly<{
    bootstrap: "/replication/bootstrap";
    frames: "/replication/frames";
    combatLog: "/replication/combat-log";
    subscribe: "/replication/subscribe";
}>;
export declare class SubjectiveReplicationHttpError extends Error {
    readonly status: number;
    readonly payload: JsonValue;
    constructor(status: number, payload: JsonValue);
}
export interface SubjectiveReplicationClientOptions {
    readonly fetchImplementation?: typeof fetch;
    readonly headers?: Readonly<Record<string, string>>;
    readonly monotonicNow?: () => number;
}
export type SubjectiveBootstrapAttempt = {
    readonly status: "ready";
    readonly bootstrap: SubjectiveReplicationBootstrap;
} | {
    readonly status: "deferred";
    readonly deferral: SubjectiveBootstrapDeferred;
};
export declare class SubjectiveBootstrapUnavailableError extends Error {
    readonly lastDeferral: SubjectiveBootstrapDeferred | null;
    constructor(lastDeferral: SubjectiveBootstrapDeferred | null);
}
export interface SubjectiveReplicationIdentity {
    readonly sourceStreamId: string;
    readonly generationId: string;
    readonly perspectiveEpochId: string;
}
export interface SubjectiveFramesQuery extends SubjectiveReplicationIdentity {
    readonly fromObservationCursor?: number;
    readonly limit?: number;
}
export interface SubjectivePresentationCatchupTarget {
    readonly sourceEventCursor: number;
    readonly observationCursor: number;
    readonly presentationCursor: number;
}
export interface IngestSubjectiveFramesThroughOptions {
    readonly sessionId: string;
    readonly fixedTarget: SubjectivePresentationCatchupTarget;
    readonly signal?: AbortSignal;
    readonly onUpdate?: (update: SubjectiveReplicationUpdate) => void | Promise<void>;
}
export declare class SubjectiveFrameCatchupResyncError extends Error {
    readonly reason: SubjectiveResyncReason;
    readonly state: SubjectiveReplicationJournalState;
    constructor(state: SubjectiveReplicationJournalState);
}
export interface SubjectiveCombatLogQuery extends SubjectiveReplicationIdentity {
    readonly fromCombatLogCursor?: number;
    readonly limit?: number;
}
export interface SubjectiveSubscribeOptions extends SubjectiveReplicationIdentity {
    readonly sessionId: string;
    readonly sourceEventCursor: number;
    readonly fromObservationCursor: number;
    readonly presentationCursor: number;
    readonly fromCombatLogCursor: number;
    readonly signal?: AbortSignal;
}
export interface SubjectiveReplicationUpdate {
    readonly envelope: SubjectiveSseEnvelope;
    readonly result: SubjectiveJournalIngestResult;
}
export interface SubjectiveReplicaReset {
    readonly reason: "initial_bootstrap" | SubjectiveResyncReason;
    readonly bootstrap: SubjectiveReplicationBootstrap;
    readonly state: SubjectiveReplicationJournalState;
}
export interface FollowSubjectiveReplicationOptions {
    readonly sessionId: string;
    readonly initialBootstrap?: SubjectiveReplicationBootstrap;
    readonly signal?: AbortSignal;
    readonly onUpdate?: (update: SubjectiveReplicationUpdate) => void | Promise<void>;
    readonly onReplicaReset?: (reset: SubjectiveReplicaReset) => void | Promise<void>;
    readonly initialReconnectDelayMs?: number;
    readonly maximumReconnectDelayMs?: number;
}
/** HTTP/SSE client for the one canonical player replication surface. */
export declare class SubjectiveReplicationClient {
    readonly baseUrl: string;
    private readonly fetchImplementation;
    private readonly defaultHeaders;
    private readonly monotonicNow;
    constructor(baseUrl: string, options?: SubjectiveReplicationClientOptions);
    bootstrap(sessionId: string, signal?: AbortSignal): Promise<SubjectiveReplicationBootstrap>;
    bootstrapAttempt(sessionId: string, signal?: AbortSignal): Promise<SubjectiveBootstrapAttempt>;
    frames(sessionId: string, query: SubjectiveFramesQuery, signal?: AbortSignal): Promise<SubjectiveFramesResponse>;
    /**
     * Feed one validated REST observation page and only the continuations needed
     * for its original captured fence through the existing canonical journal.
     * The operation does not reduce world state itself and never extends the
     * caller's fixed target when a continuation reports a newer capture.
     */
    ingestFramesThrough(journal: SubjectiveReplicationJournal, firstPage: SubjectiveFramesResponse, options: IngestSubjectiveFramesThroughOptions): Promise<SubjectiveReplicationJournalState>;
    combatLog(sessionId: string, query: SubjectiveCombatLogQuery, signal?: AbortSignal): Promise<SubjectiveCombatLogFramesResponse>;
    subscribe(options: SubjectiveSubscribeOptions): AsyncGenerator<SubjectiveSseEnvelope>;
    follow(journal: SubjectiveReplicationJournal, options: FollowSubjectiveReplicationOptions): Promise<void>;
    private getJson;
    private httpError;
    private headers;
    private readMonotonicNow;
    private bootstrapWindowExpired;
}
//# sourceMappingURL=subjectiveClient.d.ts.map